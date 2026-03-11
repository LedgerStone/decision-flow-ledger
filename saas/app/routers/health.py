"""
DecisionLedger SaaS — Health check
"""

from fastapi import APIRouter

from app.database import get_pool

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
    }
