"""
DecisionLedger SaaS — Audit service
Handles hash-chained audit entries in PostgreSQL.
"""

import hashlib
import json
from datetime import datetime, timezone


def compute_hash(data: dict) -> str:
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


async def get_last_entry_hash(conn, tenant_id: str) -> str | None:
    row = await conn.fetchrow(
        "SELECT entry_hash FROM audit_entries WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 1",
        tenant_id,
    )
    return row["entry_hash"] if row else None


async def record_event(
    conn,
    tenant_id: str,
    decision_id: str | None,
    event_type: str,
    actor: str,
    metadata: dict | None = None,
) -> dict:
    """Append an event to the audit ledger with hash chaining."""
    now = datetime.now(timezone.utc).isoformat()
    previous_hash = await get_last_entry_hash(conn, tenant_id)

    entry_data = {
        "tenant_id": tenant_id,
        "decision_id": decision_id,
        "event_type": event_type,
        "actor": actor,
        "metadata": metadata or {},
        "previous_hash": previous_hash,
        "timestamp": now,
    }
    entry_hash = compute_hash(entry_data)

    row = await conn.fetchrow(
        "INSERT INTO audit_entries (tenant_id, decision_id, event_type, actor, entry_hash, previous_hash, metadata) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id, created_at",
        tenant_id,
        decision_id,
        event_type,
        actor,
        entry_hash,
        previous_hash,
        json.dumps(metadata or {}),
    )

    return {
        "id": str(row["id"]),
        "entry_hash": entry_hash,
        "previous_hash": previous_hash,
    }


async def get_audit_trail(conn, tenant_id: str, decision_id: str | None = None) -> list[dict]:
    if decision_id:
        rows = await conn.fetch(
            "SELECT id, decision_id, event_type, actor, entry_hash, previous_hash, metadata, created_at "
            "FROM audit_entries WHERE tenant_id = $1 AND decision_id = $2 ORDER BY created_at ASC",
            tenant_id, decision_id,
        )
    else:
        rows = await conn.fetch(
            "SELECT id, decision_id, event_type, actor, entry_hash, previous_hash, metadata, created_at "
            "FROM audit_entries WHERE tenant_id = $1 ORDER BY created_at ASC",
            tenant_id,
        )

    return [
        {
            "id": str(r["id"]),
            "decision_id": str(r["decision_id"]) if r["decision_id"] else None,
            "event_type": r["event_type"],
            "actor": r["actor"],
            "entry_hash": r["entry_hash"],
            "previous_hash": r["previous_hash"],
            "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            "created_at": str(r["created_at"]),
        }
        for r in rows
    ]


async def verify_audit_chain(conn, tenant_id: str) -> dict:
    rows = await conn.fetch(
        "SELECT id, entry_hash, previous_hash FROM audit_entries "
        "WHERE tenant_id = $1 ORDER BY created_at ASC",
        tenant_id,
    )

    if not rows:
        return {"status": "empty", "message": "No audit entries yet."}

    issues = []
    for i in range(1, len(rows)):
        expected_prev = rows[i - 1]["entry_hash"]
        actual_prev = rows[i]["previous_hash"]
        if actual_prev != expected_prev:
            issues.append(f"Chain broken at entry {rows[i]['id']}")

    if issues:
        return {"status": "TAMPERED", "issues": issues}
    return {
        "status": "VERIFIED",
        "message": f"Audit chain intact — {len(rows)} entries verified.",
        "entries_checked": len(rows),
    }
