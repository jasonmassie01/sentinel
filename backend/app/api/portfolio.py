from fastapi import APIRouter
from app.services.net_worth_service import compute_net_worth
from app.services import btc_service
from app.database import get_db

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio/net-worth")
async def net_worth():
    # Try to get live BTC price for accurate valuation
    btc_price = None
    try:
        price_data = await btc_service.get_btc_price()
        btc_price = price_data.usd
    except Exception:
        pass

    snapshot = compute_net_worth(btc_price=btc_price)

    return {
        "total": snapshot.total,
        "total_cost_basis": snapshot.total_cost_basis,
        "total_unrealized_gain_loss": snapshot.total_unrealized,
        "btc_price": btc_price,
        "accounts": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "institution": a.institution,
                "current_value": a.current_value,
                "cost_basis": a.cost_basis,
                "unrealized_gain_loss": a.unrealized_gain_loss,
                "allocation_pct": round(a.allocation_pct, 2),
                "last_import_date": a.last_import_date,
            }
            for a in snapshot.accounts
        ],
        "by_asset_class": [
            {
                "asset_class": ac.asset_class,
                "value": ac.value,
                "pct": round(ac.pct, 2),
            }
            for ac in snapshot.by_asset_class
        ],
    }


@router.get("/portfolio/holdings")
def all_holdings():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT h.id, h.account_id, a.name as account_name, a.institution,
                      h.asset, h.quantity, h.current_value, h.cost_basis_total,
                      h.unrealized_gain_loss
               FROM holdings h
               JOIN accounts a ON h.account_id = a.id
               ORDER BY h.current_value DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/portfolio/transactions")
def all_transactions(limit: int = 100, offset: int = 0, account_id: int | None = None):
    with get_db() as conn:
        query = """SELECT t.id, t.account_id, a.name as account_name,
                          t.date, t.type, t.asset, t.quantity, t.price_per_unit,
                          t.total_amount, t.category, t.description, t.source
                   FROM transactions t
                   JOIN accounts a ON t.account_id = a.id"""
        params: list = []

        if account_id is not None:
            query += " WHERE t.account_id = ?"
            params.append(account_id)

        query += " ORDER BY t.date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
