"""
Net worth calculation across all accounts.
"""

from dataclasses import dataclass
from typing import Optional

from app.database import get_db


@dataclass
class AccountSummary:
    id: int
    name: str
    type: str
    institution: str
    current_value: float
    cost_basis: Optional[float]
    unrealized_gain_loss: Optional[float]
    allocation_pct: float  # filled in after totals computed
    last_import_date: Optional[str]


@dataclass
class AssetClassBreakdown:
    asset_class: str  # equities, btc, cash, other
    value: float
    pct: float


@dataclass
class NetWorthSnapshot:
    total: float
    accounts: list[AccountSummary]
    by_asset_class: list[AssetClassBreakdown]
    total_cost_basis: Optional[float]
    total_unrealized: Optional[float]


def compute_net_worth(btc_price: Optional[float] = None) -> NetWorthSnapshot:
    """
    Compute current net worth from all accounts and holdings.
    If btc_price is provided, BTC holdings are valued at that price.
    """
    with get_db() as conn:
        accounts = conn.execute(
            "SELECT id, name, type, institution, last_import_date FROM accounts"
        ).fetchall()

        account_summaries = []
        asset_class_totals: dict[str, float] = {}

        for acct in accounts:
            holdings = conn.execute(
                "SELECT asset, quantity, current_value, cost_basis_total, unrealized_gain_loss FROM holdings WHERE account_id = ?",
                (acct["id"],),
            ).fetchall()

            acct_value = 0.0
            acct_cost = 0.0
            acct_gain = 0.0

            for h in holdings:
                value = h["current_value"] or 0.0
                cost = h["cost_basis_total"] or 0.0

                # If this is a BTC holding and we have a live price, revalue
                if h["asset"] and h["asset"].upper() in ("BTC", "BITCOIN") and btc_price:
                    value = (h["quantity"] or 0) * btc_price

                acct_value += value
                if cost:
                    acct_cost += cost
                    acct_gain += value - cost
                elif h["unrealized_gain_loss"]:
                    acct_gain += h["unrealized_gain_loss"]

                # Classify asset
                asset_class = _classify_asset(h["asset"], acct["type"])
                asset_class_totals[asset_class] = asset_class_totals.get(asset_class, 0) + value

            # If no holdings but it's a checking account, check for balance from transactions
            if not holdings and acct["type"] == "checking":
                balance = _compute_checking_balance(conn, acct["id"])
                acct_value = balance
                asset_class_totals["cash"] = asset_class_totals.get("cash", 0) + balance

            account_summaries.append(AccountSummary(
                id=acct["id"],
                name=acct["name"],
                type=acct["type"],
                institution=acct["institution"],
                current_value=acct_value,
                cost_basis=acct_cost if acct_cost else None,
                unrealized_gain_loss=acct_gain if acct_gain else None,
                allocation_pct=0.0,
                last_import_date=acct["last_import_date"],
            ))

    total = sum(a.current_value for a in account_summaries)

    # Compute allocation percentages
    for a in account_summaries:
        a.allocation_pct = (a.current_value / total * 100) if total > 0 else 0

    # Build asset class breakdown
    by_asset_class = [
        AssetClassBreakdown(
            asset_class=ac,
            value=val,
            pct=(val / total * 100) if total > 0 else 0,
        )
        for ac, val in sorted(asset_class_totals.items(), key=lambda x: -x[1])
    ]

    total_cost = sum(a.cost_basis or 0 for a in account_summaries)
    total_unrealized = sum(a.unrealized_gain_loss or 0 for a in account_summaries)

    return NetWorthSnapshot(
        total=total,
        accounts=account_summaries,
        by_asset_class=by_asset_class,
        total_cost_basis=total_cost if total_cost else None,
        total_unrealized=total_unrealized if total_unrealized else None,
    )


def _classify_asset(asset: Optional[str], account_type: str) -> str:
    if not asset:
        if account_type in ("checking", "credit_card"):
            return "cash"
        return "other"
    asset_upper = asset.upper()
    if asset_upper in ("BTC", "BITCOIN"):
        return "btc"
    if asset_upper in ("SPAXX", "FDRXX", "SWVXX", "VMFXX"):
        # Money market / cash equivalents
        return "cash"
    return "equities"


def _compute_checking_balance(conn, account_id: int) -> float:
    """Approximate checking balance from transaction history."""
    row = conn.execute(
        """SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN total_amount ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN type = 'expense' THEN total_amount ELSE 0 END), 0) as balance
           FROM transactions WHERE account_id = ?""",
        (account_id,),
    ).fetchone()
    return row["balance"] if row else 0.0
