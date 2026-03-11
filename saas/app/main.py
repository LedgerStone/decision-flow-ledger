"""
DecisionLedger SaaS — Main application
Multi-tenant auditable decision workflows as a service.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_pool, close_pool
from app.routers import tenants, decisions, approvals, audit, blockchain, webhooks, health

logger = logging.getLogger("decisionledger")


def _normalize_database_url(url: str) -> str:
    """Railway may set DATABASE_URL with postgres:// scheme; asyncpg requires postgresql://."""
    if url.startswith("postgres://") and not url.startswith("postgresql://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


async def _run_init_sql():
    """Run init.sql against the database on startup (idempotent)."""
    init_path = Path(__file__).resolve().parent.parent / "init.sql"
    if not init_path.exists():
        logger.warning("init.sql not found at %s, skipping schema migration", init_path)
        return
    sql = init_path.read_text()
    db_url = _normalize_database_url(settings.DATABASE_URL)
    try:
        conn = await asyncpg.connect(db_url)
        await conn.execute(sql)
        await conn.close()
        logger.info("init.sql executed successfully")
    except Exception as e:
        logger.error("Failed to run init.sql: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    await _run_init_sql()
    yield
    await close_pool()


app = FastAPI(
    title="DecisionLedger API",
    description="Multi-tenant auditable decision workflows backed by blockchain",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(tenants.router)
app.include_router(decisions.router)
app.include_router(approvals.router)
app.include_router(audit.router)
app.include_router(blockchain.router)
app.include_router(webhooks.router)


@app.get("/")
async def root():
    return {
        "service": "DecisionLedger",
        "description": "Auditable decision workflows as a service",
        "version": "0.1.0",
        "docs": "/docs",
    }
