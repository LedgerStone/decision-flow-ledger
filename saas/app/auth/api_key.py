"""
DecisionLedger SaaS — API key authentication
Keys are formatted as dl_live_<prefix>_<secret>
The prefix (first 8 hex chars) is stored in plaintext for fast lookup.
The full key is SHA-256 hashed at rest.
"""

import hashlib
import hmac
import secrets

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.database import admin_connection

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of the API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (raw_key, prefix, key_hash)."""
    prefix = secrets.token_hex(4)  # 8 hex chars
    secret = secrets.token_hex(24)  # 48 hex chars
    raw_key = f"dl_live_{prefix}_{secret}"
    key_hash = _hash_key(raw_key)
    return raw_key, prefix, key_hash


async def verify_api_key(authorization: str = Security(api_key_header)) -> dict:
    """Verify an API key and return tenant context."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing API key")

    # Strip "Bearer " prefix if present
    key = authorization.removeprefix("Bearer ").strip()

    if not key.startswith("dl_live_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    # Extract prefix for lookup
    parts = key.split("_", 3)  # dl, live, prefix, secret
    if len(parts) != 4:
        raise HTTPException(status_code=401, detail="Invalid API key format")
    prefix = parts[2]

    async with admin_connection() as conn:
        row = await conn.fetchrow(
            "SELECT ak.id, ak.tenant_id, ak.key_hash, ak.name, ak.scopes, ak.revoked_at, "
            "t.name as tenant_name, t.slug, t.is_active "
            "FROM api_keys ak JOIN tenants t ON ak.tenant_id = t.id "
            "WHERE ak.prefix = $1",
            prefix,
        )

    if not row:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if row["revoked_at"] is not None:
        raise HTTPException(status_code=403, detail="API key has been revoked")

    if not row["is_active"]:
        raise HTTPException(status_code=403, detail="Tenant is inactive")

    if not hmac.compare_digest(_hash_key(key), row["key_hash"]):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return {
        "api_key_id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]),
        "tenant_name": row["tenant_name"],
        "tenant_slug": row["slug"],
        "key_name": row["name"],
        "scopes": row["scopes"],
    }
