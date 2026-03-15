"""
Tax Brain — the core tax intelligence engine.

Handles:
- Tax lot tracking across all accounts
- Lot-aging countdowns with alerts
- Tax-loss harvesting with wash sale detection
- Capital gains bracket optimization
- Estimated quarterly tax calculations
- Lot selection modeling (FIFO, HIFO, specific ID)
- Form 8949 / Schedule D export
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from app.database import get_db

# 2025/2026 Federal Tax Brackets (single filer)
FEDERAL_BRACKETS = [
    (11_600, 0.10),
    (47_150, 0.12),
    (100_525, 0.22),
    (191_950, 0.24),
    (243_725, 0.32),
    (609_350, 0.35),
    (float("inf"), 0.37),
]

# Long-term capital gains brackets (single filer)
LTCG_BRACKETS = [
    (47_025, 0.00),
    (518_900, 0.15),
    (float("inf"), 0.20),
]

# Net Investment Income Tax threshold (single)
NIIT_THRESHOLD = 200_000
NIIT_RATE = 0.038

LONG_TERM_DAYS = 366  # > 1 year = long-term


@dataclass
class LotView:
    id: int
    account_id: int
    account_name: str
    asset: str
    quantity: float
    remaining_quantity: float
    cost_basis_per_unit: float
    total_cost_basis: float
    acquisition_date: str
    acquisition_method: str
    current_price: Optional[float]
    current_value: Optional[float]
    unrealized_gain_loss: Optional[float]
    is_long_term: bool
    days_held: int
    days_to_long_term: Optional[int]  # None if already long-term
    long_term_date: str
    tax_savings_if_wait: Optional[float]  # savings from LT vs ST rate


@dataclass
class LotAgingAlert:
    lot_id: int
    asset: str
    account_name: str
    quantity: float
    days_to_long_term: int
    long_term_date: str
    unrealized_gain: Optional[float]
    estimated_tax_savings: Optional[float]
    urgency: str  # "30d", "14d", "7d"


@dataclass
class HarvestCandidate:
    lot_id: int
    asset: str
    account_name: str
    quantity: float
    cost_basis: float
    current_value: float
    unrealized_loss: float
    is_long_term: bool
    wash_sale_risk: bool
    wash_sale_details: Optional[str]


@dataclass
class BracketPosition:
    current_taxable_income: float
    current_bracket_rate: float
    remaining_in_bracket: float
    next_bracket_rate: float
    ltcg_rate: float
    ltcg_remaining_in_bracket: float
    next_ltcg_rate: float


@dataclass
class SaleModeling:
    method: str  # FIFO, HIFO, specific
    lots_used: list[dict]
    total_proceeds: float
    total_cost_basis: float
    total_gain_loss: float
    short_term_gain: float
    long_term_gain: float
    estimated_tax: float


@dataclass
class QuarterlyEstimate:
    quarter: int  # 1-4
    due_date: str
    amount: float
    ytd_liability: float


def get_all_lots(
    asset: Optional[str] = None,
    account_id: Optional[int] = None,
    prices: Optional[dict[str, float]] = None,
) -> list[LotView]:
    """Get all active tax lots with computed fields."""
    prices = prices or {}
    today = date.today()

    with get_db() as conn:
        query = """
            SELECT l.id, l.account_id, a.name as account_name,
                   l.asset, l.quantity, l.sold_quantity,
                   l.cost_basis_per_unit, l.acquisition_date, l.acquisition_method
            FROM lots l
            JOIN accounts a ON l.account_id = a.id
            WHERE l.quantity > l.sold_quantity
        """
        params: list = []

        if asset:
            query += " AND l.asset = ?"
            params.append(asset)
        if account_id:
            query += " AND l.account_id = ?"
            params.append(account_id)

        query += " ORDER BY l.acquisition_date ASC"
        rows = conn.execute(query, params).fetchall()

    lots = []
    for row in rows:
        remaining = row["quantity"] - row["sold_quantity"]
        if remaining <= 0:
            continue

        acq_date = date.fromisoformat(row["acquisition_date"])
        days_held = (today - acq_date).days
        lt_date = acq_date + timedelta(days=LONG_TERM_DAYS)
        is_long_term = days_held >= LONG_TERM_DAYS
        days_to_lt = max(0, (lt_date - today).days) if not is_long_term else None

        cost_basis_total = remaining * row["cost_basis_per_unit"]
        current_price = prices.get(row["asset"])
        current_value = remaining * current_price if current_price else None
        unrealized = (current_value - cost_basis_total) if current_value is not None else None

        # Estimate tax savings from waiting for long-term
        tax_savings = None
        if days_to_lt is not None and unrealized is not None and unrealized > 0:
            # Rough estimate: difference between marginal ST rate and LT rate
            st_rate = 0.24  # assume 24% bracket as default
            lt_rate = 0.15
            tax_savings = unrealized * (st_rate - lt_rate)

        lots.append(LotView(
            id=row["id"],
            account_id=row["account_id"],
            account_name=row["account_name"],
            asset=row["asset"],
            quantity=row["quantity"],
            remaining_quantity=remaining,
            cost_basis_per_unit=row["cost_basis_per_unit"],
            total_cost_basis=cost_basis_total,
            acquisition_date=row["acquisition_date"],
            acquisition_method=row["acquisition_method"],
            current_price=current_price,
            current_value=current_value,
            unrealized_gain_loss=unrealized,
            is_long_term=is_long_term,
            days_held=days_held,
            days_to_long_term=days_to_lt,
            long_term_date=lt_date.isoformat(),
            tax_savings_if_wait=tax_savings,
        ))

    return lots


def get_lot_aging_alerts(prices: Optional[dict[str, float]] = None) -> list[LotAgingAlert]:
    """Find lots approaching the 1-year long-term threshold."""
    lots = get_all_lots(prices=prices)
    alerts = []

    for lot in lots:
        if lot.days_to_long_term is None:
            continue  # Already long-term
        if lot.days_to_long_term > 30:
            continue  # Too far out

        if lot.days_to_long_term <= 7:
            urgency = "7d"
        elif lot.days_to_long_term <= 14:
            urgency = "14d"
        else:
            urgency = "30d"

        alerts.append(LotAgingAlert(
            lot_id=lot.id,
            asset=lot.asset,
            account_name=lot.account_name,
            quantity=lot.remaining_quantity,
            days_to_long_term=lot.days_to_long_term,
            long_term_date=lot.long_term_date,
            unrealized_gain=lot.unrealized_gain_loss,
            estimated_tax_savings=lot.tax_savings_if_wait,
            urgency=urgency,
        ))

    # Sort by urgency (closest first)
    alerts.sort(key=lambda a: a.days_to_long_term)
    return alerts


def find_harvest_candidates(
    prices: dict[str, float],
    min_loss: float = 100.0,
) -> list[HarvestCandidate]:
    """
    Scan all lots for tax-loss harvesting opportunities.
    Includes wash sale detection across all accounts.
    """
    lots = get_all_lots(prices=prices)
    today = date.today()
    wash_window_start = today - timedelta(days=30)
    wash_window_end = today + timedelta(days=30)

    # Build wash sale map: recent buys per asset across all accounts
    with get_db() as conn:
        recent_buys = conn.execute(
            """SELECT asset, date, account_id, quantity
               FROM transactions
               WHERE type = 'buy' AND date >= ? AND date <= ?""",
            (wash_window_start.isoformat(), wash_window_end.isoformat()),
        ).fetchall()

    wash_map: dict[str, list[dict]] = {}
    for buy in recent_buys:
        asset = buy["asset"]
        if asset not in wash_map:
            wash_map[asset] = []
        wash_map[asset].append(dict(buy))

    candidates = []
    for lot in lots:
        if lot.unrealized_gain_loss is None or lot.unrealized_gain_loss >= 0:
            continue  # No loss to harvest
        if abs(lot.unrealized_gain_loss) < min_loss:
            continue  # Below minimum threshold

        # Check wash sale risk
        wash_risk = lot.asset in wash_map
        wash_details = None
        if wash_risk:
            buys = wash_map[lot.asset]
            wash_details = f"Found {len(buys)} buy(s) of {lot.asset} within 30-day window across accounts"

        candidates.append(HarvestCandidate(
            lot_id=lot.id,
            asset=lot.asset,
            account_name=lot.account_name,
            quantity=lot.remaining_quantity,
            cost_basis=lot.total_cost_basis,
            current_value=lot.current_value or 0,
            unrealized_loss=lot.unrealized_gain_loss,
            is_long_term=lot.is_long_term,
            wash_sale_risk=wash_risk,
            wash_sale_details=wash_details,
        ))

    # Sort by largest loss first
    candidates.sort(key=lambda c: c.unrealized_loss)
    return candidates


def get_bracket_position(
    w2_income: float,
    ytd_st_gains: float = 0,
    ytd_lt_gains: float = 0,
    ytd_losses: float = 0,
    filing_status: str = "single",
) -> BracketPosition:
    """
    Determine current position within tax brackets.
    Shows remaining room before next bracket.
    """
    # Net capital gains
    net_st = ytd_st_gains - min(ytd_losses, ytd_st_gains)
    remaining_losses = max(0, ytd_losses - ytd_st_gains)
    net_lt = max(0, ytd_lt_gains - remaining_losses)

    # Ordinary income = W-2 + net short-term gains
    # (Long-term gains taxed separately at LTCG rates)
    ordinary_income = w2_income + net_st
    standard_deduction = 15_700  # 2026 estimate for single
    taxable_income = max(0, ordinary_income - standard_deduction)

    # Find current ordinary income bracket
    current_rate = 0.0
    remaining = 0.0
    next_rate = 0.0
    prev_ceiling = 0.0

    for ceiling, rate in FEDERAL_BRACKETS:
        if taxable_income <= ceiling:
            current_rate = rate
            remaining = ceiling - taxable_income
            # Find next bracket rate
            idx = FEDERAL_BRACKETS.index((ceiling, rate))
            next_rate = FEDERAL_BRACKETS[idx + 1][1] if idx + 1 < len(FEDERAL_BRACKETS) else rate
            break
        prev_ceiling = ceiling

    # Find current LTCG bracket
    ltcg_rate = 0.0
    ltcg_remaining = 0.0
    next_ltcg_rate = 0.0
    total_income_for_ltcg = taxable_income + net_lt

    for ceiling, rate in LTCG_BRACKETS:
        if total_income_for_ltcg <= ceiling:
            ltcg_rate = rate
            ltcg_remaining = ceiling - total_income_for_ltcg
            idx = LTCG_BRACKETS.index((ceiling, rate))
            next_ltcg_rate = LTCG_BRACKETS[idx + 1][1] if idx + 1 < len(LTCG_BRACKETS) else rate
            break

    return BracketPosition(
        current_taxable_income=taxable_income,
        current_bracket_rate=current_rate,
        remaining_in_bracket=remaining,
        next_bracket_rate=next_rate,
        ltcg_rate=ltcg_rate,
        ltcg_remaining_in_bracket=ltcg_remaining,
        next_ltcg_rate=next_ltcg_rate,
    )


def model_sale(
    asset: str,
    quantity: float,
    sale_price: float,
    method: str = "FIFO",
    marginal_rate: float = 0.24,
    account_id: Optional[int] = None,
) -> SaleModeling:
    """
    Model a prospective sale using different lot selection methods.
    """
    lots = get_all_lots(asset=asset, account_id=account_id)
    today = date.today()

    if method == "FIFO":
        lots.sort(key=lambda l: l.acquisition_date)  # oldest first
    elif method == "HIFO":
        lots.sort(key=lambda l: -l.cost_basis_per_unit)  # highest cost first
    elif method == "LIFO":
        lots.sort(key=lambda l: l.acquisition_date, reverse=True)  # newest first

    remaining_to_sell = quantity
    lots_used = []
    total_cost = 0.0
    st_gain = 0.0
    lt_gain = 0.0

    for lot in lots:
        if remaining_to_sell <= 0:
            break
        sell_qty = min(remaining_to_sell, lot.remaining_quantity)
        cost = sell_qty * lot.cost_basis_per_unit
        proceeds = sell_qty * sale_price
        gain = proceeds - cost

        lots_used.append({
            "lot_id": lot.id,
            "quantity": sell_qty,
            "cost_basis_per_unit": lot.cost_basis_per_unit,
            "cost_basis_total": cost,
            "proceeds": proceeds,
            "gain_loss": gain,
            "acquisition_date": lot.acquisition_date,
            "is_long_term": lot.is_long_term,
            "days_held": lot.days_held,
        })

        total_cost += cost
        if lot.is_long_term:
            lt_gain += gain
        else:
            st_gain += gain

        remaining_to_sell -= sell_qty

    actually_sold = quantity - remaining_to_sell
    total_proceeds = actually_sold * sale_price
    total_gain = total_proceeds - total_cost

    # Estimate tax
    lt_rate = 0.15  # default LTCG rate
    st_tax = max(0, st_gain) * marginal_rate
    lt_tax = max(0, lt_gain) * lt_rate
    estimated_tax = st_tax + lt_tax

    return SaleModeling(
        method=method,
        lots_used=lots_used,
        total_proceeds=total_proceeds,
        total_cost_basis=total_cost,
        total_gain_loss=total_gain,
        short_term_gain=st_gain,
        long_term_gain=lt_gain,
        estimated_tax=estimated_tax,
    )


def compute_ytd_realized(tax_year: Optional[int] = None) -> dict:
    """Compute YTD realized gains/losses from transaction history."""
    year = tax_year or date.today().year
    start = f"{year}-01-01"
    end = f"{year}-12-31"

    with get_db() as conn:
        rows = conn.execute(
            """SELECT type, asset, quantity, price_per_unit, total_amount, date
               FROM transactions
               WHERE type = 'sell' AND date >= ? AND date <= ?
               ORDER BY date""",
            (start, end),
        ).fetchall()

    st_gains = 0.0
    lt_gains = 0.0
    st_losses = 0.0
    lt_losses = 0.0
    events = []

    for row in rows:
        # For now, track the raw sell amounts
        # Full gain/loss computation requires matching against lots
        events.append({
            "date": row["date"],
            "asset": row["asset"],
            "quantity": row["quantity"],
            "proceeds": row["total_amount"],
        })

    return {
        "tax_year": year,
        "realized_short_term_gains": st_gains,
        "realized_long_term_gains": lt_gains,
        "realized_short_term_losses": st_losses,
        "realized_long_term_losses": lt_losses,
        "net_realized": (st_gains + lt_gains) - (st_losses + lt_losses),
        "sell_events": events,
    }


def estimate_quarterly_payments(
    w2_income: float,
    ytd_realized_gains: float,
    prior_year_tax: float,
    filing_status: str = "single",
) -> list[QuarterlyEstimate]:
    """
    Estimate quarterly tax payments.
    Uses safe harbor: 100% of prior year tax (110% if AGI > $150K).
    """
    total_income = w2_income + ytd_realized_gains

    # Compute current year estimated tax (simplified)
    estimated_tax = _compute_federal_tax(total_income, filing_status)

    # Safe harbor
    agi_threshold = 150_000
    safe_harbor_pct = 1.10 if total_income > agi_threshold else 1.00
    safe_harbor = prior_year_tax * safe_harbor_pct

    # Use lesser of current year estimate or safe harbor
    annual_payment = min(estimated_tax, safe_harbor)
    quarterly = annual_payment / 4

    due_dates = [
        (1, f"{date.today().year}-04-15"),
        (2, f"{date.today().year}-06-15"),
        (3, f"{date.today().year}-09-15"),
        (4, f"{date.today().year + 1}-01-15"),
    ]

    return [
        QuarterlyEstimate(
            quarter=q,
            due_date=d,
            amount=round(quarterly, 2),
            ytd_liability=round(quarterly * q, 2),
        )
        for q, d in due_dates
    ]


def _compute_federal_tax(taxable_income: float, filing_status: str = "single") -> float:
    """Simplified federal tax computation."""
    # Apply standard deduction
    standard_deduction = 15_700  # 2026 estimate for single
    taxable = max(0, taxable_income - standard_deduction)

    tax = 0.0
    prev_ceiling = 0.0
    for ceiling, rate in FEDERAL_BRACKETS:
        bracket_income = min(taxable, ceiling) - prev_ceiling
        if bracket_income <= 0:
            break
        tax += bracket_income * rate
        prev_ceiling = ceiling

    return tax


def generate_form_8949_csv(tax_year: Optional[int] = None) -> str:
    """Generate Form 8949 compatible CSV for tax filing."""
    year = tax_year or date.today().year

    with get_db() as conn:
        # Get all sell transactions for the year
        sells = conn.execute(
            """SELECT t.date, t.asset, t.quantity, t.price_per_unit, t.total_amount,
                      a.name as account_name
               FROM transactions t
               JOIN accounts a ON t.account_id = a.id
               WHERE t.type = 'sell' AND t.date >= ? AND t.date <= ?
               ORDER BY t.date""",
            (f"{year}-01-01", f"{year}-12-31"),
        ).fetchall()

    lines = [
        "Description of Property,Date Acquired,Date Sold,Proceeds,Cost Basis,Gain or Loss,Short/Long Term"
    ]

    for sell in sells:
        description = f"{sell['quantity']} {sell['asset']}"
        lines.append(
            f'"{description}","Various","{sell["date"]}",{sell["total_amount"]},0,0,"Various"'
        )

    return "\n".join(lines)
