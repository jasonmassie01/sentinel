"""
Scenario Lab — "What if?" modeling engine.

Simulates financial moves before you make them:
- What if I sell this asset?
- What if I cut this expense?
- Tax year planner with bracket visualization
- DCA analyzer
"""

from dataclasses import dataclass
from typing import Optional
from datetime import date

from app.services.tax_engine import model_sale, get_bracket_position, FEDERAL_BRACKETS, LTCG_BRACKETS
from app.database import get_db


@dataclass
class ExpenseCutProjection:
    monthly_amount: float
    annual_savings: float
    pre_tax_cost: float  # at marginal rate
    hours_of_work: float  # at hourly rate
    invested_1yr: float
    invested_5yr: float
    invested_10yr: float
    btc_equivalent: Optional[float]  # at current price


@dataclass
class TaxYearModel:
    gross_income: float
    standard_deduction: float
    taxable_income: float
    ordinary_tax: float
    ltcg_tax: float
    niit: float
    total_tax: float
    effective_rate: float
    marginal_rate: float
    ltcg_rate: float
    remaining_in_bracket: float


def simulate_sale(
    asset: str,
    quantity: float,
    sale_price: float,
    w2_income: float = 0,
    account_id: Optional[int] = None,
) -> dict:
    """
    Simulate selling an asset and show full tax impact.
    Compares FIFO vs HIFO vs LIFO side by side.
    """
    methods = ["FIFO", "HIFO", "LIFO"]
    results = {}

    for method in methods:
        result = model_sale(
            asset=asset,
            quantity=quantity,
            sale_price=sale_price,
            method=method,
            account_id=account_id,
        )
        results[method] = {
            "total_proceeds": result.total_proceeds,
            "total_cost_basis": result.total_cost_basis,
            "total_gain_loss": result.total_gain_loss,
            "short_term_gain": result.short_term_gain,
            "long_term_gain": result.long_term_gain,
            "estimated_tax": result.estimated_tax,
            "after_tax_proceeds": result.total_proceeds - result.estimated_tax,
            "lots_used": result.lots_used,
        }

    # If W-2 income provided, show bracket impact
    bracket_impact = None
    if w2_income > 0:
        # Before sale
        before = get_bracket_position(w2_income)
        # After sale (use FIFO as reference)
        fifo = results["FIFO"]
        after = get_bracket_position(
            w2_income,
            ytd_st_gains=fifo["short_term_gain"],
            ytd_lt_gains=fifo["long_term_gain"],
        )
        bracket_impact = {
            "before": {
                "marginal_rate": before.current_bracket_rate,
                "remaining_in_bracket": before.remaining_in_bracket,
                "ltcg_rate": before.ltcg_rate,
            },
            "after": {
                "marginal_rate": after.current_bracket_rate,
                "remaining_in_bracket": after.remaining_in_bracket,
                "ltcg_rate": after.ltcg_rate,
            },
            "bracket_change": after.current_bracket_rate != before.current_bracket_rate,
        }

    return {
        "comparisons": results,
        "best_method": min(results, key=lambda m: results[m]["estimated_tax"]),
        "bracket_impact": bracket_impact,
    }


def project_expense_cut(
    monthly_amount: float,
    marginal_tax_rate: float = 0.24,
    hourly_rate: Optional[float] = None,
    annual_salary: Optional[float] = None,
    portfolio_return_rate: float = 0.08,
    btc_price: Optional[float] = None,
) -> ExpenseCutProjection:
    """
    Model the impact of cutting a recurring expense.
    Shows opportunity cost across multiple lenses.
    """
    annual = monthly_amount * 12

    # Pre-tax cost: how much you had to earn to pay for this
    pre_tax_cost = annual / (1 - marginal_tax_rate)

    # Hours of work
    if hourly_rate:
        hours = annual / hourly_rate
    elif annual_salary:
        hours = annual / (annual_salary / 2080)
    else:
        hours = 0

    # Investment opportunity cost (compound growth)
    rate = portfolio_return_rate
    invested_1yr = annual * (1 + rate)
    invested_5yr = sum(annual * (1 + rate) ** i for i in range(5))
    invested_10yr = sum(annual * (1 + rate) ** i for i in range(10))

    # BTC equivalent
    btc_equiv = None
    if btc_price and btc_price > 0:
        btc_equiv = annual / btc_price

    return ExpenseCutProjection(
        monthly_amount=monthly_amount,
        annual_savings=annual,
        pre_tax_cost=pre_tax_cost,
        hours_of_work=hours,
        invested_1yr=invested_1yr,
        invested_5yr=invested_5yr,
        invested_10yr=invested_10yr,
        btc_equivalent=btc_equiv,
    )


def model_tax_year(
    w2_income: float,
    other_income: float = 0,
    short_term_gains: float = 0,
    long_term_gains: float = 0,
    realized_losses: float = 0,
    deductions: float = 0,
    filing_status: str = "single",
) -> TaxYearModel:
    """
    Full-year tax model with bracket visualization.
    """
    # Standard deduction (2026 estimate)
    standard_deduction = max(15_700, deductions) if deductions else 15_700

    # Net capital gains
    net_st = max(0, short_term_gains - min(realized_losses, short_term_gains))
    remaining_losses = max(0, realized_losses - short_term_gains)
    net_lt = max(0, long_term_gains - remaining_losses)

    # Capital loss deduction (up to $3,000 against ordinary income)
    excess_losses = max(0, realized_losses - short_term_gains - long_term_gains)
    loss_deduction = min(excess_losses, 3_000)

    # Taxable ordinary income
    gross = w2_income + other_income + net_st - loss_deduction
    taxable_ordinary = max(0, gross - standard_deduction)

    # Compute ordinary tax
    ordinary_tax = 0.0
    prev_ceiling = 0.0
    current_marginal = 0.10
    remaining_in_bracket = 0.0

    for ceiling, rate in FEDERAL_BRACKETS:
        bracket_income = min(taxable_ordinary, ceiling) - prev_ceiling
        if bracket_income <= 0:
            remaining_in_bracket = ceiling - taxable_ordinary
            break
        ordinary_tax += bracket_income * rate
        current_marginal = rate
        remaining_in_bracket = ceiling - taxable_ordinary
        prev_ceiling = ceiling

    # LTCG tax
    ltcg_tax = 0.0
    ltcg_rate = 0.0
    total_for_ltcg = taxable_ordinary + net_lt
    prev_ceiling = 0.0

    for ceiling, rate in LTCG_BRACKETS:
        bracket_income = min(total_for_ltcg, ceiling) - max(prev_ceiling, taxable_ordinary)
        if bracket_income > 0:
            ltcg_tax += bracket_income * rate
            ltcg_rate = rate
        prev_ceiling = ceiling

    # NIIT (3.8% on investment income above threshold)
    agi = w2_income + other_income + net_st + net_lt
    niit = 0.0
    if agi > 200_000:
        investment_income = net_st + net_lt
        niit = min(investment_income, agi - 200_000) * 0.038

    total_tax = ordinary_tax + ltcg_tax + niit
    effective_rate = total_tax / gross if gross > 0 else 0

    return TaxYearModel(
        gross_income=gross,
        standard_deduction=standard_deduction,
        taxable_income=taxable_ordinary,
        ordinary_tax=ordinary_tax,
        ltcg_tax=ltcg_tax,
        niit=niit,
        total_tax=total_tax,
        effective_rate=effective_rate,
        marginal_rate=current_marginal,
        ltcg_rate=ltcg_rate,
        remaining_in_bracket=max(0, remaining_in_bracket),
    )


def analyze_dca(account_id: Optional[int] = None, asset: Optional[str] = None) -> dict:
    """
    Analyze DCA performance for a given asset.
    Compares actual purchase history against lump sum.
    """
    with get_db() as conn:
        query = """SELECT date, quantity, price_per_unit, total_amount
                   FROM transactions
                   WHERE type = 'buy'"""
        params: list = []

        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        if asset:
            query += " AND asset = ?"
            params.append(asset)

        query += " ORDER BY date ASC"
        rows = conn.execute(query, params).fetchall()

    if not rows:
        return {"error": "No buy transactions found"}

    total_invested = sum(r["total_amount"] for r in rows)
    total_quantity = sum(r["quantity"] for r in rows if r["quantity"])
    avg_cost = total_invested / total_quantity if total_quantity else 0

    purchases = [
        {
            "date": r["date"],
            "quantity": r["quantity"],
            "price": r["price_per_unit"],
            "amount": r["total_amount"],
        }
        for r in rows
    ]

    # If lump sum at first purchase date
    first_price = rows[0]["price_per_unit"] if rows[0]["price_per_unit"] else 0
    lump_sum_qty = total_invested / first_price if first_price else 0

    return {
        "total_invested": total_invested,
        "total_quantity": total_quantity,
        "average_cost_basis": avg_cost,
        "num_purchases": len(rows),
        "first_purchase": purchases[0]["date"] if purchases else None,
        "last_purchase": purchases[-1]["date"] if purchases else None,
        "lump_sum_comparison": {
            "quantity_if_lump_sum": lump_sum_qty,
            "price_at_first_purchase": first_price,
            "dca_advantage": total_quantity - lump_sum_qty,
        },
        "purchases": purchases,
    }
