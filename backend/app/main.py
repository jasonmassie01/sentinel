import logging
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

log = logging.getLogger("sentinel")

app = FastAPI(
    title=settings.app_name,
    description="Personal Financial Intelligence System",
    version="0.1.0",
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


@app.on_event("startup")
async def startup():
    init_db()

    # Schedule automatic Plaid sync every 4 hours
    from app.services import plaid_service
    if plaid_service.is_configured():
        scheduler.add_job(_plaid_sync_job, "interval", hours=4, id="plaid_sync")
        scheduler.start()
        log.info("Plaid auto-sync scheduled (every 4 hours)")


@app.on_event("shutdown")
async def shutdown():
    if scheduler.running:
        scheduler.shutdown(wait=False)
