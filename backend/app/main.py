import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import init_db
from app.api.health import router as health_router
from app.api.accounts import router as accounts_router
from app.api.imports import router as imports_router
from app.api.btc import router as btc_router
from app.api.portfolio import router as portfolio_router
from app.api.tax import router as tax_router
from app.api.email import router as email_router
from app.api.scenarios import router as scenarios_router
from app.api.alerts import router as alerts_router
from app.api.plaid import router as plaid_router
from app.api.coinbase import router as coinbase_router

log = logging.getLogger("sentinel")

scheduler = BackgroundScheduler()


def _plaid_sync_job():
    """Background job to sync Plaid data every 4 hours."""
    from app.services import plaid_service
    if not plaid_service.is_configured():
        return
    try:
        plaid_service.sync_transactions()
        plaid_service.sync_holdings()
        plaid_service.sync_balances()
        log.info("Plaid auto-sync complete")
    except Exception as e:
        log.error(f"Plaid auto-sync failed: {e}")


def _coinbase_sync_job():
    """Background job to sync Coinbase data every 4 hours."""
    import asyncio
    from app.services import coinbase_service
    if not coinbase_service.is_configured():
        return
    try:
        asyncio.run(coinbase_service.sync_coinbase())
        log.info("Coinbase auto-sync complete")
    except Exception as e:
        log.error(f"Coinbase auto-sync failed: {e}")


def _btc_address_sync_job():
    """Background job to refresh on-chain BTC balances every 4 hours."""
    import asyncio
    from app.services import btc_service
    from app.database import get_db

    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT id, btc_address FROM accounts WHERE btc_address IS NOT NULL"
            ).fetchall()

        if not rows:
            return

        btc_price = asyncio.run(btc_service.get_btc_price()).usd

        for row in rows:
            try:
                info = asyncio.run(btc_service.get_address_info(row["btc_address"]))
                value_usd = info.balance_btc * btc_price
                with get_db() as conn:
                    conn.execute(
                        "DELETE FROM holdings WHERE account_id = ? AND asset = 'BTC'",
                        (row["id"],),
                    )
                    conn.execute(
                        """INSERT INTO holdings (account_id, asset, quantity, current_value)
                           VALUES (?, 'BTC', ?, ?)""",
                        (row["id"], info.balance_btc, value_usd),
                    )
                    conn.execute(
                        "UPDATE accounts SET last_import_date = datetime('now') WHERE id = ?",
                        (row["id"],),
                    )
            except Exception as e:
                log.error(f"BTC address sync failed for {row['btc_address']}: {e}")

        log.info(f"BTC address auto-sync complete ({len(rows)} addresses)")
    except Exception as e:
        log.error(f"BTC address auto-sync failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()

    has_jobs = False

    from app.services import plaid_service
    if plaid_service.is_configured():
        scheduler.add_job(_plaid_sync_job, "interval", hours=4, id="plaid_sync")
        has_jobs = True
        log.info("Plaid auto-sync scheduled (every 4 hours)")

    from app.services import coinbase_service
    if coinbase_service.is_configured():
        scheduler.add_job(_coinbase_sync_job, "interval", hours=4, id="coinbase_sync")
        has_jobs = True
        log.info("Coinbase auto-sync scheduled (every 4 hours)")

    scheduler.add_job(_btc_address_sync_job, "interval", hours=4, id="btc_address_sync")
    has_jobs = True
    log.info("BTC address auto-sync scheduled (every 4 hours)")

    if has_jobs:
        scheduler.start()

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.app_name,
    description="Personal Financial Intelligence System",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(accounts_router, prefix="/api")
app.include_router(imports_router, prefix="/api")
app.include_router(btc_router, prefix="/api")
app.include_router(portfolio_router, prefix="/api")
app.include_router(tax_router, prefix="/api")
app.include_router(email_router, prefix="/api")
app.include_router(scenarios_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(plaid_router, prefix="/api")
app.include_router(coinbase_router, prefix="/api")
