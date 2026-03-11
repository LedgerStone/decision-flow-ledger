"""
DecisionLedger SaaS — Tenant management (admin-only)
"""

from fastapi import APIRouter, HTTPException, Header

from app.config import settings
from app.database import admin_connection
from app.auth.api_key import generate_api_key
from app.schemas.schemas import TenantCreate, ApiKeyCreate

router = APIRouter(prefix="/api/v1/admin/tenants", tags=["admin"])


async def verify_admin(x_admin_secret: str = Header()):
    if x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@router.post("/")
async def create_tenant(req: TenantCreate, x_admin_secret: str = Header()):
    await verify_admin(x_admin_secret)

    async with admin_connection() as conn:
        existing = await conn.fetchrow("SELECT id FROM tenants WHERE slug = $1", req.slug)
        if existing:
            raise HTTPException(status_code=409, detail="Tenant slug already exists")

        row = await conn.fetchrow(
            "INSERT INTO tenants (name, slug) VALUES ($1, $2) RETURNING id, created_at",
            req.name, req.slug,
        )

    return {
        "id": str(row["id"]),
        "name": req.name,
        "slug": req.slug,
        "created_at": str(row["created_at"]),
    }


@router.post("/{tenant_id}/api-keys")
async def create_api_key(tenant_id: str, req: ApiKeyCreate, x_admin_secret: str = Header()):
    await verify_admin(x_admin_secret)

    raw_key, prefix, key_hash = generate_api_key()

    async with admin_connection() as conn:
        tenant = await conn.fetchrow("SELECT id FROM tenants WHERE id = $1", tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        row = await conn.fetchrow(
            "INSERT INTO api_keys (tenant_id, key_hash, prefix, name, scopes) "
            "VALUES ($1, $2, $3, $4, $5) RETURNING id, created_at",
            tenant_id, key_hash, prefix, req.name, req.scopes,
        )

    return {
        "id": str(row["id"]),
        "key": raw_key,
        "prefix": prefix,
        "name": req.name,
        "scopes": req.scopes,
        "created_at": str(row["created_at"]),
        "warning": "Store this key securely. It will not be shown again.",
    }


@router.delete("/{tenant_id}/api-keys/{key_id}")
async def revoke_api_key(tenant_id: str, key_id: str, x_admin_secret: str = Header()):
    await verify_admin(x_admin_secret)

    async with admin_connection() as conn:
        result = await conn.execute(
            "UPDATE api_keys SET revoked_at = NOW() WHERE id = $1 AND tenant_id = $2 AND revoked_at IS NULL",
            key_id, tenant_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="API key not found or already revoked")

    return {"status": "revoked", "key_id": key_id}


@router.get("/")
async def list_tenants(x_admin_secret: str = Header()):
    await verify_admin(x_admin_secret)

    async with admin_connection() as conn:
        rows = await conn.fetch(
            "SELECT id, name, slug, is_active, created_at FROM tenants ORDER BY created_at DESC"
        )

    return {
        "tenants": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "slug": r["slug"],
                "is_active": r["is_active"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
    }
