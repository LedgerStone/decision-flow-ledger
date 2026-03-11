"""
DecisionLedger SaaS — Webhook dispatcher
Sends HMAC-signed event payloads to registered webhook endpoints.
"""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def compute_signature(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


async def dispatch_event(conn, tenant_id: str, event_type: str, payload: dict):
    """Send event to all matching active webhooks for the tenant."""
    rows = await conn.fetch(
        "SELECT id, url, secret, events FROM webhook_endpoints "
        "WHERE tenant_id = $1 AND is_active = true",
        tenant_id,
    )

    for wh in rows:
        events = json.loads(wh["events"]) if isinstance(wh["events"], str) else wh["events"]
        if event_type not in events and "*" not in events:
            continue

        body = json.dumps({
            "event": event_type,
            "tenant_id": tenant_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }, sort_keys=True, default=str)

        signature = compute_signature(wh["secret"], body)

        response_status = None
        try:
            async with httpx.AsyncClient(timeout=settings.WEBHOOK_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    wh["url"],
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-DecisionLedger-Signature": f"sha256={signature}",
                        "X-DecisionLedger-Event": event_type,
                    },
                )
                response_status = resp.status_code
        except Exception as e:
            logger.warning(f"Webhook delivery failed for {wh['url']}: {e}")
            response_status = 0

        # Record delivery
        await conn.execute(
            "INSERT INTO webhook_deliveries (webhook_id, tenant_id, event_type, payload, response_status) "
            "VALUES ($1, $2, $3, $4, $5)",
            wh["id"], tenant_id, event_type, body, response_status,
        )
