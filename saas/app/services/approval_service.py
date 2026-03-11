"""
DecisionLedger SaaS — Approval service
Multi-signature approval/rejection workflow.
"""

from app.blockchain.manager import blockchain_manager
from app.services.audit_service import record_event
from app.webhooks.dispatcher import dispatch_event


async def submit_approval(conn, tenant_id: str, data: dict) -> dict:
    decision_id = data["decision_id"]
    approver = data["approver"]
    vote = data["decision"]
    comment = data.get("comment")

    if vote not in ("approved", "rejected"):
        return {"error": "Decision must be 'approved' or 'rejected'", "status_code": 400}

    # Check decision exists and is pending
    row = await conn.fetchrow(
        "SELECT status, required_approvals FROM decisions WHERE tenant_id = $1 AND id = $2",
        tenant_id, decision_id,
    )
    if not row:
        return {"error": "Decision not found", "status_code": 404}
    if row["status"] != "pending":
        return {"error": f"Decision is '{row['status']}', cannot vote on it", "status_code": 400}

    required = row["required_approvals"]

    # Check duplicate vote
    existing = await conn.fetchrow(
        "SELECT id FROM approvals WHERE tenant_id = $1 AND decision_id = $2 AND approver = $3",
        tenant_id, decision_id, approver,
    )
    if existing:
        return {"error": "This approver has already voted on this decision", "status_code": 400}

    # Record vote
    await conn.execute(
        "INSERT INTO approvals (tenant_id, decision_id, approver, decision, comment) "
        "VALUES ($1, $2, $3, $4, $5)",
        tenant_id, decision_id, approver, vote, comment,
    )

    # Count votes
    approval_count = await conn.fetchval(
        "SELECT COUNT(*) FROM approvals WHERE tenant_id = $1 AND decision_id = $2 AND decision = 'approved'",
        tenant_id, decision_id,
    )
    rejection_count = await conn.fetchval(
        "SELECT COUNT(*) FROM approvals WHERE tenant_id = $1 AND decision_id = $2 AND decision = 'rejected'",
        tenant_id, decision_id,
    )

    # Determine new status
    if rejection_count >= required:
        new_status = "rejected"
    elif approval_count >= required:
        new_status = "approved"
    else:
        new_status = "pending"

    if new_status != "pending":
        await conn.execute(
            "UPDATE decisions SET status = $1, updated_at = NOW() WHERE tenant_id = $2 AND id = $3",
            new_status, tenant_id, decision_id,
        )

    # Audit
    audit = await record_event(
        conn, tenant_id, decision_id,
        f"approval.{vote}", approver,
        {
            "vote": vote,
            "comment": comment,
            "approval_count": approval_count,
            "rejection_count": rejection_count,
            "resulting_status": new_status,
        },
    )

    # Blockchain
    chain = blockchain_manager.get_chain(tenant_id)
    block = chain.force_mine_single({
        "type": f"approval.{vote}",
        "decision_id": decision_id,
        "approver": approver,
        "vote": vote,
        "approval_count": approval_count,
        "rejection_count": rejection_count,
        "resulting_status": new_status,
        "pg_entry_hash": audit["entry_hash"],
    })

    # Webhooks
    await dispatch_event(conn, tenant_id, f"approval.{vote}", {
        "decision_id": decision_id,
        "approver": approver,
        "vote": vote,
        "resulting_status": new_status,
    })
    if new_status in ("approved", "rejected"):
        await dispatch_event(conn, tenant_id, f"decision.{new_status}", {
            "decision_id": decision_id,
            "approval_count": approval_count,
            "rejection_count": rejection_count,
        })

    status_msg = {
        "approved": "Decision approved and ready for execution.",
        "rejected": "Decision has been rejected.",
        "pending": "Vote recorded. More signatures needed.",
    }

    return {
        "decision_id": decision_id,
        "vote": vote,
        "approvals": approval_count,
        "rejections": rejection_count,
        "required": required,
        "status": new_status,
        "blockchain": {
            "block_index": block.index,
            "block_hash": block.hash,
            "merkle_root": block.merkle,
            "nonce": block.nonce,
        },
        "message": status_msg.get(new_status, "Vote recorded."),
    }
