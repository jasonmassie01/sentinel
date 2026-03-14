from fastapi import APIRouter
from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "healthy",
        "service": "sentinel",
        "version": "0.1.0",
        "database": db_status,
    }
