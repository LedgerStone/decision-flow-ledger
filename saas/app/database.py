"""
DecisionLedger SaaS — Async database layer with tenant isolation (RLS)
"""

import re
import asyncpg
from contextlib import asynccontextmanager

from app.config import settings

_pool: asyncpg.Pool | None = None


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(settings.DATABASE_URL, min_size=2, max_size=20)


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized")
    return _pool


@asynccontextmanager
async def tenant_connection(tenant_id: str):
    """Acquire a connection with RLS tenant context set."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Validate UUID format to prevent injection in SET command
        if not re.match(r'^[0-9a-f\-]{36}$', tenant_id):
            raise ValueError("Invalid tenant_id format")
        await conn.execute(f"SET app.current_tenant = '{tenant_id}'")
        yield conn


@asynccontextmanager
async def admin_connection():
    """Acquire a connection without tenant context (for admin operations)."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
