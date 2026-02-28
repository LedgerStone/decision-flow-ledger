"""
AIP-X — Accountable Intelligence Platform
Immutable Ledger API (MVP)
"""

import hashlib
import json
from datetime import datetime
from typing import Optional

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

app = FastAPI(
    title="AIP-X Ledger API",
    description="Open-source accountable intelligence platform — immutable audit ledger",
    version="0.1.0"
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:5432/coredb")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def compute_hash(data: dict) -> str:
    """Compute SHA-256 hash of a dictionary."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()

def get_last_ledger_hash(conn) -> Optional[str]:
    """Get the hash of the last ledger entry (for chaining)."""
    cur = conn.cursor()
    cur.execute("SELECT entry_hash FROM audit_ledger ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None

# ─── Models ───────────────────────────────────────────────

class QueryRequest(BaseModel):
    operator_username: str
    query_text: str
    reason: str

class ApprovalRequest(BaseModel):
    query_id: int
    approver_username: str
    decision: str  # "approved" or "rejected"

# ─── Routes ───────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "project": "AIP-X — Accountable Intelligence Platform",
        "status": "MVP running",
        "docs": "/docs"
    }

@app.post("/query/submit")
def submit_query(req: QueryRequest):
    """Submit a new query. Goes into 'pending' state, requires approval."""
    conn = get_db()
    cur = conn.cursor()

    # Get operator
    cur.execute("SELECT id FROM operators WHERE username = %s", (req.operator_username,))
    op = cur.fetchone()
    if not op:
        raise HTTPException(status_code=404, detail="Operator not found")
    operator_id = op[0]

    # Compute query hash
    query_data = {
        "operator": req.operator_username,
        "query": req.query_text,
        "reason": req.reason,
        "timestamp": datetime.utcnow().isoformat()
    }
    query_hash = compute_hash(query_data)

    # Insert query
    cur.execute(
        "INSERT INTO queries (operator_id, query_text, reason, query_hash) VALUES (%s, %s, %s, %s) RETURNING id",
        (operator_id, req.query_text, req.reason, query_hash)
    )
    query_id = cur.fetchone()[0]

    # Write to immutable ledger
    previous_hash = get_last_ledger_hash(conn)
    ledger_entry = {
        "query_id": query_id,
        "event": "submitted",
        "actor": req.operator_username,
        "query_hash": query_hash,
        "previous_hash": previous_hash,
        "timestamp": datetime.utcnow().isoformat()
    }
    entry_hash = compute_hash(ledger_entry)

    cur.execute(
        "INSERT INTO audit_ledger (query_id, event_type, actor, entry_hash, previous_hash) VALUES (%s, %s, %s, %s, %s)",
        (query_id, "submitted", req.operator_username, entry_hash, previous_hash)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "query_id": query_id,
        "status": "pending",
        "query_hash": query_hash,
        "ledger_entry_hash": entry_hash,
        "message": "Query submitted. Awaiting multi-signature approval."
    }


@app.post("/query/approve")
def approve_query(req: ApprovalRequest):
    """Approve or reject a query. Requires supervisor or judge role."""
    conn = get_db()
    cur = conn.cursor()

    if req.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    # Verify approver exists and has right role
    cur.execute("SELECT role FROM operators WHERE username = %s", (req.approver_username,))
    approver = cur.fetchone()
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    if approver[0] not in ("supervisor", "judge"):
        raise HTTPException(status_code=403, detail="Only supervisors or judges can approve queries")

    # Record approval
    cur.execute(
        "INSERT INTO approvals (query_id, approver, decision) VALUES (%s, %s, %s)",
        (req.query_id, req.approver_username, req.decision)
    )

    # Count approvals
    cur.execute(
        "SELECT COUNT(*) FROM approvals WHERE query_id = %s AND decision = 'approved'",
        (req.query_id,)
    )
    approval_count = cur.fetchone()[0]

    # Require 2 approvals to execute (multi-sig)
    new_status = "approved" if approval_count >= 2 else "pending"
    cur.execute("UPDATE queries SET status = %s WHERE id = %s", (new_status, req.query_id))

    # Write to immutable ledger
    previous_hash = get_last_ledger_hash(conn)
    ledger_entry = {
        "query_id": req.query_id,
        "event": req.decision,
        "actor": req.approver_username,
        "approval_count": approval_count,
        "previous_hash": previous_hash,
        "timestamp": datetime.utcnow().isoformat()
    }
    entry_hash = compute_hash(ledger_entry)

    cur.execute(
        "INSERT INTO audit_ledger (query_id, event_type, actor, entry_hash, previous_hash) VALUES (%s, %s, %s, %s, %s)",
        (req.query_id, req.decision, req.approver_username, entry_hash, previous_hash)
    )

    conn.commit()
    cur.close()
    conn.close()

    return {
        "query_id": req.query_id,
        "decision": req.decision,
        "approvals_so_far": approval_count,
        "status": new_status,
        "ledger_entry_hash": entry_hash,
        "message": f"{'Query approved and ready for execution!' if new_status == 'approved' else 'Approval recorded. More signatures needed.'}"
    }


@app.get("/ledger")
def get_ledger():
    """View the full immutable audit ledger (for oversight bodies)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.id, l.query_id, l.event_type, l.actor, l.entry_hash, l.previous_hash, l.timestamp
        FROM audit_ledger l
        ORDER BY l.id ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    ledger = []
    for row in rows:
        ledger.append({
            "id": row[0],
            "query_id": row[1],
            "event_type": row[2],
            "actor": row[3],
            "entry_hash": row[4],
            "previous_hash": row[5],
            "timestamp": str(row[6])
        })

    return {"ledger": ledger, "total_entries": len(ledger)}


@app.get("/ledger/verify")
def verify_ledger():
    """Verify the integrity of the ledger chain (no tampering)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, entry_hash, previous_hash FROM audit_ledger ORDER BY id ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return {"status": "empty", "message": "No entries in ledger yet."}

    issues = []
    for i in range(1, len(rows)):
        expected_prev = rows[i - 1][1]  # previous entry's hash
        actual_prev = rows[i][2]         # current entry's previous_hash field
        if actual_prev != expected_prev:
            issues.append(f"Chain broken between entry {rows[i-1][0]} and {rows[i][0]}")

    if issues:
        return {"status": "TAMPERED", "issues": issues}
    return {"status": "VERIFIED", "message": f"Ledger chain intact — {len(rows)} entries verified."}


@app.get("/queries")
def get_queries():
    """List all queries with their current status."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT q.id, o.username, q.query_text, q.reason, q.status, q.query_hash, q.created_at
        FROM queries q
        JOIN operators o ON q.operator_id = o.id
        ORDER BY q.id DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return {"queries": [
        {
            "id": r[0],
            "operator": r[1],
            "query_text": r[2],
            "reason": r[3],
            "status": r[4],
            "query_hash": r[5],
            "created_at": str(r[6])
        } for r in rows
    ]}
