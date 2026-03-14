"""
CSV import parsers for various financial institutions.

Each parser normalizes institution-specific CSV formats into a common
transaction/holding format that the import service can ingest.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ParsedTransaction:
    date: str  # ISO format YYYY-MM-DD
    type: str  # buy, sell, dividend, fee, expense, income, transfer
    asset: Optional[str] = None
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: float = 0.0
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    tax_relevant: bool = False


@dataclass
class ParsedHolding:
    asset: str
    quantity: float
    current_value: float
    cost_basis_total: Optional[float] = None
    unrealized_gain_loss: Optional[float] = None


@dataclass
class ParseResult:
    transactions: list[ParsedTransaction] = field(default_factory=list)
    holdings: list[ParsedHolding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    row_count: int = 0
    parsed_count: int = 0


def _clean_currency(value: str) -> Optional[float]:
    """Strip $, commas, and whitespace from currency strings."""
    if not value or value.strip() in ("", "--", "N/A", "n/a"):
        return None
    cleaned = value.strip().replace("$", "").replace(",", "").replace("+", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(value: str) -> Optional[str]:
    """Try common date formats and return ISO format."""
    formats = [
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%m-%d-%Y",
        "%m/%d/%y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]
    value = value.strip()
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_fidelity_brokerage(content: str) -> ParseResult:
    """
    Parse Fidelity brokerage CSV export.

    Expected columns (typical Fidelity positions export):
    Account Number, Account Name, Symbol, Description, Quantity,
    Last Price, Current Value, Cost Basis Total, Gain/Loss Dollar,
    Gain/Loss Percent, ...

    Also handles Fidelity transaction history exports:
    Run Date, Account, Action, Symbol, Description, Type,
    Quantity, Price ($), Commission ($), Fees ($), Amount ($), ...
    """
    result = ParseResult()
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        result.errors.append("Empty CSV or no headers found")
        return result

    headers_lower = [h.lower().strip() for h in reader.fieldnames]

    # Detect format: positions vs. transaction history
    is_positions = any("current value" in h for h in headers_lower)
    is_transactions = any("run date" in h for h in headers_lower)

    for row in reader:
        result.row_count += 1
        # Normalize keys: strip whitespace
        row = {k.strip(): v.strip() if v else "" for k, v in row.items()}

        try:
            if is_positions:
                _parse_fidelity_position_row(row, result)
            elif is_transactions:
                _parse_fidelity_transaction_row(row, result)
            else:
                result.errors.append(f"Row {result.row_count}: Unrecognized Fidelity CSV format")
        except Exception as e:
            result.errors.append(f"Row {result.row_count}: {e}")

    return result


def _parse_fidelity_position_row(row: dict, result: ParseResult):
    symbol = row.get("Symbol", "").strip()
    if not symbol or symbol.upper() in ("PENDING ACTIVITY", ""):
        return

    quantity = _clean_currency(row.get("Quantity", ""))
    current_value = _clean_currency(row.get("Current Value", ""))
    cost_basis = _clean_currency(row.get("Cost Basis Total", ""))
    gain_loss = _clean_currency(row.get("Gain/Loss Dollar", ""))

    if quantity is not None and current_value is not None:
        result.holdings.append(ParsedHolding(
            asset=symbol,
            quantity=quantity,
            current_value=current_value,
            cost_basis_total=cost_basis,
            unrealized_gain_loss=gain_loss,
        ))
        result.parsed_count += 1


def _parse_fidelity_transaction_row(row: dict, result: ParseResult):
    date_str = row.get("Run Date", "") or row.get("Date", "")
    date = _parse_date(date_str)
    if not date:
        result.errors.append(f"Row {result.row_count}: Could not parse date '{date_str}'")
        return

    action = row.get("Action", "").upper()
    symbol = row.get("Symbol", "").strip()
    amount = _clean_currency(row.get("Amount ($)", "") or row.get("Amount", ""))
    quantity = _clean_currency(row.get("Quantity", ""))
    price = _clean_currency(row.get("Price ($)", "") or row.get("Price", ""))

    tx_type = _map_fidelity_action(action)
    if not tx_type:
        return  # Skip unrecognized actions silently

    result.transactions.append(ParsedTransaction(
        date=date,
        type=tx_type,
        asset=symbol or None,
        quantity=abs(quantity) if quantity else None,
        price_per_unit=abs(price) if price else None,
        total_amount=amount or 0.0,
        description=row.get("Description", ""),
        tax_relevant=tx_type in ("sell", "dividend"),
    ))
    result.parsed_count += 1


def _map_fidelity_action(action: str) -> Optional[str]:
    action = action.strip().upper()
    buy_keywords = ["BOUGHT", "YOU BOUGHT", "PURCHASE", "REINVESTMENT"]
    sell_keywords = ["SOLD", "YOU SOLD", "REDEMPTION"]
    div_keywords = ["DIVIDEND", "DISTRIBUTION", "INTEREST"]
    fee_keywords = ["FEE", "COMMISSION"]
    transfer_keywords = ["TRANSFER", "JOURNAL"]

    for kw in buy_keywords:
        if kw in action:
            return "buy"
    for kw in sell_keywords:
        if kw in action:
            return "sell"
    for kw in div_keywords:
        if kw in action:
            return "dividend"
    for kw in fee_keywords:
        if kw in action:
            return "fee"
    for kw in transfer_keywords:
        if kw in action:
            return "transfer"
    return None


def parse_schwab_brokerage(content: str) -> ParseResult:
    """
    Parse Schwab brokerage CSV export.

    Schwab positions typically:
    Symbol, Description, Quantity, Price, Price Change %, Market Value,
    Day Change %, Day Change $, Cost Basis, Gain/Loss $, Gain/Loss %,
    Reinvest Dividends?, Capital Gains?, % of Account

    Schwab transactions:
    Date, Action, Symbol, Description, Quantity, Price, Fees & Comm, Amount
    """
    result = ParseResult()

    # Schwab CSVs often have header lines before the actual CSV data
    lines = content.strip().split("\n")
    # Find the actual header row (skip "Positions for..." or "Transactions for..." lines)
    start_idx = 0
    for i, line in enumerate(lines):
        if "symbol" in line.lower() or "date" in line.lower():
            start_idx = i
            break

    cleaned_content = "\n".join(lines[start_idx:])
    reader = csv.DictReader(io.StringIO(cleaned_content))

    if not reader.fieldnames:
        result.errors.append("Empty CSV or no headers found")
        return result

    headers_lower = [h.lower().strip() for h in reader.fieldnames]
    is_positions = any("market value" in h for h in headers_lower)

    for row in reader:
        result.row_count += 1
        row = {k.strip(): v.strip() if v else "" for k, v in row.items()}

        try:
            if is_positions:
                _parse_schwab_position_row(row, result)
            else:
                _parse_schwab_transaction_row(row, result)
        except Exception as e:
            result.errors.append(f"Row {result.row_count}: {e}")

    return result


def _parse_schwab_position_row(row: dict, result: ParseResult):
    symbol = row.get("Symbol", "").strip()
    if not symbol or symbol in ("Account Total", "Cash & Cash Investments"):
        return

    quantity = _clean_currency(row.get("Quantity", ""))
    market_value = _clean_currency(row.get("Market Value", ""))
    cost_basis = _clean_currency(row.get("Cost Basis", ""))
    gain_loss = _clean_currency(row.get("Gain/Loss $", ""))

    if quantity is not None and market_value is not None:
        result.holdings.append(ParsedHolding(
            asset=symbol,
            quantity=quantity,
            current_value=market_value,
            cost_basis_total=cost_basis,
            unrealized_gain_loss=gain_loss,
        ))
        result.parsed_count += 1


def _parse_schwab_transaction_row(row: dict, result: ParseResult):
    date_str = row.get("Date", "")
    date = _parse_date(date_str)
    if not date:
        # Schwab sometimes has summary rows at end
        return

    action = row.get("Action", "").upper()
    symbol = row.get("Symbol", "").strip()
    amount = _clean_currency(row.get("Amount", ""))
    quantity = _clean_currency(row.get("Quantity", ""))
    price = _clean_currency(row.get("Price", ""))

    tx_type = _map_schwab_action(action)
    if not tx_type:
        return

    result.transactions.append(ParsedTransaction(
        date=date,
        type=tx_type,
        asset=symbol or None,
        quantity=abs(quantity) if quantity else None,
        price_per_unit=abs(price) if price else None,
        total_amount=amount or 0.0,
        description=row.get("Description", ""),
        tax_relevant=tx_type in ("sell", "dividend"),
    ))
    result.parsed_count += 1


def _map_schwab_action(action: str) -> Optional[str]:
    action = action.strip().upper()
    if "BUY" in action or "PURCHASE" in action:
        return "buy"
    if "SELL" in action:
        return "sell"
    if "DIVIDEND" in action or "INTEREST" in action or "DISTRIBUTION" in action:
        return "dividend"
    if "FEE" in action or "ADR" in action:
        return "fee"
    if "TRANSFER" in action or "JOURNAL" in action:
        return "transfer"
    return None


def parse_fidelity_credit_card(content: str) -> ParseResult:
    """
    Parse Fidelity credit card CSV export.

    Expected columns:
    Date, Transaction, Name, Memo, Amount
    """
    result = ParseResult()
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        result.errors.append("Empty CSV or no headers found")
        return result

    for row in reader:
        result.row_count += 1
        row = {k.strip(): v.strip() if v else "" for k, v in row.items()}

        try:
            date_str = row.get("Date", "")
            date = _parse_date(date_str)
            if not date:
                result.errors.append(f"Row {result.row_count}: Could not parse date '{date_str}'")
                continue

            amount = _clean_currency(row.get("Amount", ""))
            if amount is None:
                continue

            merchant = row.get("Name", "") or row.get("Memo", "")
            tx_type_val = row.get("Transaction", "").upper()

            # Negative amounts = charges, positive = payments/credits
            is_payment = amount > 0 or "PAYMENT" in tx_type_val or "CREDIT" in tx_type_val
            tx_type = "income" if is_payment else "expense"

            result.transactions.append(ParsedTransaction(
                date=date,
                type=tx_type,
                total_amount=abs(amount),
                description=merchant,
                category=_auto_categorize_merchant(merchant),
            ))
            result.parsed_count += 1

        except Exception as e:
            result.errors.append(f"Row {result.row_count}: {e}")

    return result


def parse_bank_csv(content: str) -> ParseResult:
    """
    Parse generic bank CSV (checking/savings).

    Tries to handle common bank export formats:
    Date, Description, Amount
    or
    Date, Description, Debit, Credit
    """
    result = ParseResult()
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        result.errors.append("Empty CSV or no headers found")
        return result

    headers_lower = [h.lower().strip() for h in reader.fieldnames]
    has_debit_credit = any("debit" in h for h in headers_lower)

    for row in reader:
        result.row_count += 1
        row = {k.strip(): v.strip() if v else "" for k, v in row.items()}

        try:
            date_str = row.get("Date", "") or row.get("date", "")
            date = _parse_date(date_str)
            if not date:
                result.errors.append(f"Row {result.row_count}: Could not parse date '{date_str}'")
                continue

            description = (
                row.get("Description", "")
                or row.get("description", "")
                or row.get("Memo", "")
            )

            if has_debit_credit:
                debit = _clean_currency(row.get("Debit", "") or row.get("debit", ""))
                credit = _clean_currency(row.get("Credit", "") or row.get("credit", ""))
                if debit:
                    amount = abs(debit)
                    tx_type = "expense"
                elif credit:
                    amount = abs(credit)
                    tx_type = "income"
                else:
                    continue
            else:
                amount_val = _clean_currency(row.get("Amount", "") or row.get("amount", ""))
                if amount_val is None:
                    continue
                tx_type = "income" if amount_val > 0 else "expense"
                amount = abs(amount_val)

            result.transactions.append(ParsedTransaction(
                date=date,
                type=tx_type,
                total_amount=amount,
                description=description,
                category=_auto_categorize_merchant(description),
            ))
            result.parsed_count += 1

        except Exception as e:
            result.errors.append(f"Row {result.row_count}: {e}")

    return result


# Merchant → category mapping (expandable rules engine)
MERCHANT_CATEGORIES: dict[str, tuple[str, str]] = {
    # (category, subcategory)
    "AMAZON": ("shopping", "online"),
    "AMZN": ("shopping", "online"),
    "WALMART": ("shopping", "retail"),
    "TARGET": ("shopping", "retail"),
    "COSTCO": ("food", "grocery"),
    "KROGER": ("food", "grocery"),
    "HEB": ("food", "grocery"),
    "TRADER JOE": ("food", "grocery"),
    "WHOLE FOODS": ("food", "grocery"),
    "ALDI": ("food", "grocery"),
    "CHICK-FIL-A": ("food", "dining"),
    "MCDONALD": ("food", "dining"),
    "STARBUCKS": ("food", "dining"),
    "CHIPOTLE": ("food", "dining"),
    "DOORDASH": ("food", "delivery"),
    "UBER EATS": ("food", "delivery"),
    "GRUBHUB": ("food", "delivery"),
    "UBER": ("transport", "rideshare"),
    "LYFT": ("transport", "rideshare"),
    "SHELL": ("transport", "fuel"),
    "EXXON": ("transport", "fuel"),
    "CHEVRON": ("transport", "fuel"),
    "NETFLIX": ("entertainment", "streaming"),
    "SPOTIFY": ("entertainment", "streaming"),
    "HULU": ("entertainment", "streaming"),
    "DISNEY+": ("entertainment", "streaming"),
    "APPLE.COM": ("entertainment", "subscription"),
    "GOOGLE": ("utilities", "tech"),
    "AT&T": ("utilities", "telecom"),
    "VERIZON": ("utilities", "telecom"),
    "T-MOBILE": ("utilities", "telecom"),
    "XFINITY": ("utilities", "internet"),
    "COMCAST": ("utilities", "internet"),
    "STATE FARM": ("insurance", "auto"),
    "GEICO": ("insurance", "auto"),
    "CVS": ("health", "pharmacy"),
    "WALGREENS": ("health", "pharmacy"),
}


def _auto_categorize_merchant(merchant: str) -> Optional[str]:
    """Simple keyword-based auto-categorization."""
    merchant_upper = merchant.upper()
    for keyword, (category, _) in MERCHANT_CATEGORIES.items():
        if keyword in merchant_upper:
            return category
    return None
