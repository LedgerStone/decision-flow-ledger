"""
DecisionLedger SaaS — Audit trail endpoints
"""

import json

from fastapi import APIRouter, Depends, Query

from app.auth.api_key import verify_api_key
from app.blockchain.manager import blockchain_manager
from app.database import tenant_connection
from app.services import audit_service

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/")
async def get_audit_trail(auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        trail = await audit_service.get_audit_trail(conn, auth["tenant_id"])
    return {"entries": trail, "total": len(trail)}


@router.get("/decision/{decision_id}")
async def get_decision_audit(decision_id: str, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        trail = await audit_service.get_audit_trail(conn, auth["tenant_id"], decision_id)
    return {"decision_id": decision_id, "entries": trail, "total": len(trail)}


@router.get("/verify")
async def verify_audit_chain(auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        return await audit_service.verify_audit_chain(conn, auth["tenant_id"])


@router.get("/integrity")
async def cross_verify(auth: dict = Depends(verify_api_key)):
    """Cross-verify PostgreSQL audit trail against blockchain."""
    tenant_id = auth["tenant_id"]

    async with tenant_connection(tenant_id) as conn:
        pg_result = await audit_service.verify_audit_chain(conn, tenant_id)
        rows = await conn.fetch(
            "SELECT entry_hash FROM audit_entries WHERE tenant_id = $1", tenant_id
        )

    pg_hashes = {r["entry_hash"] for r in rows}

    chain = blockchain_manager.get_chain(tenant_id)
    bc_result = chain.verify_chain()

    bc_pg_hashes = set()
    for block in chain.chain:
        for tx in block.transactions:
            if "pg_entry_hash" in tx:
                bc_pg_hashes.add(tx["pg_entry_hash"])

    missing = pg_hashes - bc_pg_hashes
    pg_ok = pg_result.get("status") in ("VERIFIED", "empty")
    bc_ok = bc_result.get("status") == "VERIFIED"
    overall = "VERIFIED" if (pg_ok and bc_ok and not missing) else "INCONSISTENT"

    return {
        "overall_status": overall,
        "postgresql": pg_result,
        "blockchain": bc_result,
        "cross_check": {
            "pg_entries": len(pg_hashes),
            "blockchain_references": len(bc_pg_hashes),
            "missing_on_blockchain": len(missing),
        },
    }
