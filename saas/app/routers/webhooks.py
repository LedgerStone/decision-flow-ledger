"""
DecisionLedger SaaS — Webhook management endpoints
"""

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException

from app.auth.api_key import verify_api_key
from app.database import tenant_connection
from app.schemas.schemas import WebhookCreate

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/")
async def register_webhook(req: WebhookCreate, auth: dict = Depends(verify_api_key)):
    wh_secret = secrets.token_hex(32)
    async with tenant_connection(auth["tenant_id"]) as conn:
        row = await conn.fetchrow(
            "INSERT INTO webhook_endpoints (tenant_id, url, events, secret) "
            "VALUES ($1, $2, $3, $4) RETURNING id, created_at",
            auth["tenant_id"], req.url, json.dumps(req.events), wh_secret,
        )
    return {
        "id": str(row["id"]),
        "url": req.url,
        "events": req.events,
        "secret": wh_secret,
        "created_at": str(row["created_at"]),
        "warning": "Store the secret securely. It is used to verify webhook signatures.",
    }


@router.get("/")
async def list_webhooks(auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        rows = await conn.fetch(
            "SELECT id, url, events, is_active, created_at "
            "FROM webhook_endpoints WHERE tenant_id = $1 ORDER BY created_at DESC",
            auth["tenant_id"],
        )
    return {
        "webhooks": [
            {
                "id": str(r["id"]),
                "url": r["url"],
                "events": json.loads(r["events"]) if isinstance(r["events"], str) else r["events"],
                "is_active": r["is_active"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
    }


@router.delete("/{webhook_id}")
async def deactivate_webhook(webhook_id: str, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        result = await conn.execute(
            "UPDATE webhook_endpoints SET is_active = false WHERE id = $1 AND tenant_id = $2",
            webhook_id, auth["tenant_id"],
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Webhook not found")
    return {"status": "deactivated", "webhook_id": webhook_id}


@router.get("/{webhook_id}/deliveries")
async def get_deliveries(webhook_id: str, auth: dict = Depends(verify_api_key)):
    async with tenant_connection(auth["tenant_id"]) as conn:
        rows = await conn.fetch(
            "SELECT id, event_type, response_status, created_at "
            "FROM webhook_deliveries WHERE webhook_id = $1 AND tenant_id = $2 "
            "ORDER BY created_at DESC LIMIT 100",
            webhook_id, auth["tenant_id"],
        )
    return {
        "deliveries": [
            {
                "id": str(r["id"]),
                "event_type": r["event_type"],
                "response_status": r["response_status"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ]
    }
