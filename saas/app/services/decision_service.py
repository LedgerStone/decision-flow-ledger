"""
DecisionLedger SaaS — Decision service
Manages the decision lifecycle: create -> approve -> execute/cancel
"""

import json
from datetime import datetime, timezone

from app.blockchain.manager import blockchain_manager
from app.config import settings
from app.services.audit_service import compute_hash, record_event
from app.webhooks.dispatcher import dispatch_event


async def create_decision(conn, tenant_id: str, data: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    required = data.get("required_approvals") or settings.DEFAULT_APPROVALS_REQUIRED

    decision_data = {
        "tenant_id": tenant_id,
        "decision_type": data["decision_type"],
        "title": data["title"],
        "payload": data["payload"],
        "reason": data["reason"],
        "created_by": data["created_by"],
        "timestamp": now,
    }
    decision_hash = compute_hash(decision_data)

    row = await conn.fetchrow(
        "INSERT INTO decisions "
        "(tenant_id, decision_type, title, payload, reason, decision_hash, required_approvals, created_by) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id, status, created_at",
        tenant_id,
        data["decision_type"],
        data["title"],
        json.dumps(data["payload"]),
        data["reason"],
        decision_hash,
        required,
        data["created_by"],
    )
    decision_id = str(row["id"])

    # Audit entry
    audit = await record_event(
        conn, tenant_id, decision_id,
        "decision.submitted", data["created_by"],
        {"decision_hash": decision_hash, "decision_type": data["decision_type"]},
    )

    # Blockchain
    chain = blockchain_manager.get_chain(tenant_id)
    block = chain.force_mine_single({
        "type": "decision.submitted",
        "decision_id": decision_id,
        "decision_type": data["decision_type"],
        "created_by": data["created_by"],
        "decision_hash": decision_hash,
        "pg_entry_hash": audit["entry_hash"],
    })

    # Webhook
    await dispatch_event(conn, tenant_id, "decision.submitted", {
        "decision_id": decision_id,
        "decision_type": data["decision_type"],
        "title": data["title"],
        "created_by": data["created_by"],
    })

    return {
        "id": decision_id,
        "status": row["status"],
        "decision_hash": decision_hash,
        "required_approvals": required,
        "created_at": str(row["created_at"]),
        "blockchain": {
            "block_index": block.index,
            "block_hash": block.hash,
            "merkle_root": block.merkle,
            "nonce": block.nonce,
        },
    }


async def get_decision(conn, tenant_id: str, decision_id: str) -> dict | None:
    row = await conn.fetchrow(
        "SELECT id, decision_type, title, payload, reason, status, decision_hash, "
        "required_approvals, created_by, created_at, updated_at "
        "FROM decisions WHERE tenant_id = $1 AND id = $2",
        tenant_id, decision_id,
    )
    if not row:
        return None

    approvals = await conn.fetch(
        "SELECT id, approver, decision, comment, created_at "
        "FROM approvals WHERE tenant_id = $1 AND decision_id = $2 ORDER BY created_at ASC",
        tenant_id, decision_id,
    )

    chain = blockchain_manager.get_chain(tenant_id)
    bc_trail = chain.get_transactions_for_decision(decision_id)

    return {
        "id": str(row["id"]),
        "decision_type": row["decision_type"],
        "title": row["title"],
        "payload": json.loads(row["payload"]) if row["payload"] else {},
        "reason": row["reason"],
        "status": row["status"],
        "decision_hash": row["decision_hash"],
        "required_approvals": row["required_approvals"],
        "created_by": row["created_by"],
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]) if row["updated_at"] else None,
        "approvals": [
            {
                "id": str(a["id"]),
                "approver": a["approver"],
                "decision": a["decision"],
                "comment": a["comment"],
                "created_at": str(a["created_at"]),
            }
            for a in approvals
        ],
        "blockchain_trail": bc_trail,
    }


async def list_decisions(
    conn, tenant_id: str,
    status: str | None = None,
    decision_type: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    conditions = ["tenant_id = $1"]
    params: list = [tenant_id]
    idx = 2

    if status:
        conditions.append(f"status = ${idx}")
        params.append(status)
        idx += 1
    if decision_type:
        conditions.append(f"decision_type = ${idx}")
        params.append(decision_type)
        idx += 1

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    count_row = await conn.fetchrow(f"SELECT COUNT(*) as total FROM decisions WHERE {where}", *params)
    total = count_row["total"]

    params.extend([per_page, offset])
    rows = await conn.fetch(
        f"SELECT id, decision_type, title, status, decision_hash, required_approvals, "
        f"created_by, created_at FROM decisions WHERE {where} "
        f"ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
        *params,
    )

    return {
        "decisions": [
            {
                "id": str(r["id"]),
                "decision_type": r["decision_type"],
                "title": r["title"],
                "status": r["status"],
                "decision_hash": r["decision_hash"],
                "required_approvals": r["required_approvals"],
                "created_by": r["created_by"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


async def execute_decision(conn, tenant_id: str, decision_id: str, executor: str) -> dict:
    row = await conn.fetchrow(
        "SELECT status, decision_hash, created_by FROM decisions WHERE tenant_id = $1 AND id = $2",
        tenant_id, decision_id,
    )
    if not row:
        return {"error": "Decision not found", "status_code": 404}
    if row["status"] != "approved":
        return {"error": f"Decision is '{row['status']}', only 'approved' decisions can be executed", "status_code": 400}

    await conn.execute(
        "UPDATE decisions SET status = 'executed', updated_at = NOW() WHERE tenant_id = $1 AND id = $2",
        tenant_id, decision_id,
    )

    audit = await record_event(
        conn, tenant_id, decision_id,
        "decision.executed", executor,
        {"decision_hash": row["decision_hash"], "original_creator": row["created_by"]},
    )

    chain = blockchain_manager.get_chain(tenant_id)
    block = chain.force_mine_single({
        "type": "decision.executed",
        "decision_id": decision_id,
        "executor": executor,
        "decision_hash": row["decision_hash"],
        "pg_entry_hash": audit["entry_hash"],
    })

    await dispatch_event(conn, tenant_id, "decision.executed", {
        "decision_id": decision_id,
        "executor": executor,
    })

    return {
        "id": decision_id,
        "status": "executed",
        "executor": executor,
        "blockchain": {
            "block_index": block.index,
            "block_hash": block.hash,
            "merkle_root": block.merkle,
            "nonce": block.nonce,
        },
    }


async def cancel_decision(conn, tenant_id: str, decision_id: str, cancelled_by: str, reason: str | None = None) -> dict:
    row = await conn.fetchrow(
        "SELECT status FROM decisions WHERE tenant_id = $1 AND id = $2",
        tenant_id, decision_id,
    )
    if not row:
        return {"error": "Decision not found", "status_code": 404}
    if row["status"] not in ("pending",):
        return {"error": f"Decision is '{row['status']}', only 'pending' decisions can be cancelled", "status_code": 400}

    await conn.execute(
        "UPDATE decisions SET status = 'cancelled', updated_at = NOW() WHERE tenant_id = $1 AND id = $2",
        tenant_id, decision_id,
    )

    audit = await record_event(
        conn, tenant_id, decision_id,
        "decision.cancelled", cancelled_by,
        {"cancel_reason": reason},
    )

    chain = blockchain_manager.get_chain(tenant_id)
    block = chain.force_mine_single({
        "type": "decision.cancelled",
        "decision_id": decision_id,
        "cancelled_by": cancelled_by,
        "cancel_reason": reason,
        "pg_entry_hash": audit["entry_hash"],
    })

    return {
        "id": decision_id,
        "status": "cancelled",
        "blockchain": {
            "block_index": block.index,
            "block_hash": block.hash,
        },
    }
