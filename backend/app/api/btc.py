from fastapi import APIRouter, HTTPException
from app.services import btc_service
from app.database import get_db

router = APIRouter(tags=["btc"])


@router.get("/btc/price")
async def btc_price():
    try:
        price = await btc_service.get_btc_price()
        return {
            "usd": price.usd,
            "usd_24h_change": price.usd_24h_change,
            "usd_market_cap": price.usd_market_cap,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch BTC price: {e}")


@router.get("/btc/address/{address}")
async def btc_address(address: str):
    if not address or len(address) < 26:
        raise HTTPException(status_code=400, detail="Invalid BTC address")
    try:
        info = await btc_service.get_address_info(address)
        return {
            "address": info.address,
            "balance_btc": info.balance_btc,
            "balance_sats": info.balance_sats,
            "tx_count": info.tx_count,
            "utxo_count": len(info.utxos),
            "utxos": [
                {
                    "txid": u.txid,
                    "vout": u.vout,
                    "value_sats": u.value,
                    "confirmed": u.status_confirmed,
                }
                for u in info.utxos
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch address info: {e}")


@router.get("/btc/fees")
async def btc_fees():
    try:
        fees = await btc_service.get_fee_estimates()
        return {
            "fastest": fees.fastest,
            "half_hour": fees.half_hour,
            "hour": fees.hour,
            "economy": fees.economy,
            "minimum": fees.minimum,
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch fee estimates: {e}")


@router.post("/btc/track-address")
async def track_btc_address(address: str, account_name: str = "On-chain BTC"):
    """Add a BTC address as a crypto account and fetch its balance."""
    try:
        info = await btc_service.get_address_info(address)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch address: {e}")

    try:
        price_data = await btc_service.get_btc_price()
        btc_usd = price_data.usd
    except Exception:
        btc_usd = 0

    value_usd = info.balance_btc * btc_usd

    with get_db() as conn:
        # Create or update the account
        existing = conn.execute(
            "SELECT id FROM accounts WHERE institution = 'onchain' AND name = ?",
            (account_name,),
        ).fetchone()

        if existing:
            account_id = existing["id"]
        else:
            cursor = conn.execute(
                "INSERT INTO accounts (name, type, institution) VALUES (?, 'crypto', 'onchain')",
                (account_name,),
            )
            account_id = cursor.lastrowid

        # Upsert the BTC holding
        conn.execute(
            "DELETE FROM holdings WHERE account_id = ? AND asset = 'BTC'",
            (account_id,),
        )
        conn.execute(
            """INSERT INTO holdings (account_id, asset, quantity, current_value)
               VALUES (?, 'BTC', ?, ?)""",
            (account_id, info.balance_btc, value_usd),
        )

        conn.execute(
            "UPDATE accounts SET last_import_date = datetime('now') WHERE id = ?",
            (account_id,),
        )

    return {
        "account_id": account_id,
        "address": address,
        "balance_btc": info.balance_btc,
        "balance_usd": value_usd,
        "btc_price": btc_usd,
        "utxo_count": len(info.utxos),
    }
