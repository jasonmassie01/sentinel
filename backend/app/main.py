from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api.health import router as health_router
from app.api.accounts import router as accounts_router

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


@app.on_event("startup")
async def startup():
    init_db()
