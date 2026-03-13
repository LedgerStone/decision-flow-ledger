"""
AIP-X — Accountable Intelligence Platform
Immutable Ledger API (MVP) with Blockchain Layer
"""

import hashlib
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import hmac

import psycopg2
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os

from blockchain import Blockchain

logger = logging.getLogger("aipx")


def _normalize_database_url(url: str) -> str:
    """Railway may set DATABASE_URL with postgres:// scheme; psycopg2 requires postgresql://."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = _normalize_database_url(
    os.getenv("DATABASE_URL", "postgresql://admin:admin123@localhost:5432/coredb")
)

API_KEY = os.getenv("API_KEY", "")


def verify_api_key(x_api_key: str = Header()):
    """Validate the API key sent via X-Api-Key header."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY not configured on server")
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True


def _resolve_blockchain_dir() -> Path:
    """Return a writable blockchain data directory, falling back to /tmp."""
    primary = Path(os.getenv("BLOCKCHAIN_DATA_DIR", "/data/blockchain"))
    try:
        primary.mkdir(parents=True, exist_ok=True)
        test_file = primary / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        return primary
    except OSError:
        fallback = Path("/tmp/blockchain")
        fallback.mkdir(parents=True, exist_ok=True)
        logger.warning("Primary blockchain dir %s not writable, falling back to %s", primary, fallback)
        return fallback


def _run_init_sql():
    """Run init.sql against the database on startup (idempotent)."""
    init_path = Path(__file__).parent / "init.sql"
    if not init_path.exists():
        logger.warning("init.sql not found at %s, skipping schema migration", init_path)
        return
    sql = init_path.read_text()
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        logger.info("init.sql executed successfully")
    except Exception as e:
        logger.error("Failed to run init.sql: %s", e)


blockchain_dir = _resolve_blockchain_dir()
# Initialize blockchain with resolved directory
blockchain = Blockchain(chain_file=blockchain_dir / "chain.json")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_init_sql()
    yield


app = FastAPI(
    title="AIP-X Ledger API",
    description="Open-source accountable intelligence platform — immutable audit ledger backed by blockchain",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


def compute_hash(data: dict) -> str:
    """Compute SHA-256 hash of a dictionary."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def get_last_ledger_hash(conn) -> Optional[str]:
    """Get the hash of the last ledger entry (for chaining in PostgreSQL)."""
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


class ExecuteRequest(BaseModel):
    query_id: int
    executor_username: str


# ─── Routes ───────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check endpoint for Railway."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
    }


@app.get("/")
def root():
    stats = blockchain.stats()
    return {
        "project": "AIP-X — Accountable Intelligence Platform",
        "status": "MVP running",
        "version": "0.2.0",
        "blockchain": {
            "total_blocks": stats["total_blocks"],
            "total_transactions": stats["total_transactions"],
            "last_block_hash": stats["last_block_hash"],
        },
        "docs": "/docs",
    }


@app.post("/query/submit")
def submit_query(req: QueryRequest, _auth: bool = Depends(verify_api_key)):
    """Submit a new query. Goes into 'pending' state, requires approval.
    The submission is recorded both in PostgreSQL and on the blockchain."""
    conn = get_db()
    cur = conn.cursor()

    # Get operator
    cur.execute("SELECT id, role FROM operators WHERE username = %s", (req.operator_username,))
    op = cur.fetchone()
    if not op:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Operator not found")
    operator_id = op[0]

    now = datetime.now(timezone.utc).isoformat()

    # Compute query hash
    query_data = {
        "operator": req.operator_username,
        "query": req.query_text,
        "reason": req.reason,
        "timestamp": now,
    }
    query_hash = compute_hash(query_data)

    # Insert query into PostgreSQL
    cur.execute(
        "INSERT INTO queries (operator_id, query_text, reason, query_hash) VALUES (%s, %s, %s, %s) RETURNING id",
        (operator_id, req.query_text, req.reason, query_hash),
    )
    query_id = cur.fetchone()[0]

    # Write to PostgreSQL audit ledger (backward compatibility)
    previous_hash = get_last_ledger_hash(conn)
    ledger_entry = {
        "query_id": query_id,
        "event": "submitted",
        "actor": req.operator_username,
        "query_hash": query_hash,
        "previous_hash": previous_hash,
        "timestamp": now,
    }
    entry_hash = compute_hash(ledger_entry)

    cur.execute(
        "INSERT INTO audit_ledger (query_id, event_type, actor, entry_hash, previous_hash) VALUES (%s, %s, %s, %s, %s)",
        (query_id, "submitted", req.operator_username, entry_hash, previous_hash),
    )

    conn.commit()
    cur.close()
    conn.close()

    # Write to blockchain (immutable)
    block = blockchain.force_mine_single({
        "type": "query_submitted",
        "query_id": query_id,
        "operator": req.operator_username,
        "query_hash": query_hash,
        "reason": req.reason,
        "pg_entry_hash": entry_hash,
    })

    return {
        "query_id": query_id,
        "status": "pending",
        "query_hash": query_hash,
        "ledger_entry_hash": entry_hash,
        "blockchain": {
            "block_index": block.index,
            "block_hash": block.hash,
            "merkle_root": block.merkle,
            "nonce": block.nonce,
        },
        "message": "Query submitted and recorded on blockchain. Awaiting multi-signature approval.",
    }


@app.post("/query/approve")
def approve_query(req: ApprovalRequest, _auth: bool = Depends(verify_api_key)):
    """Approve or reject a query. Requires supervisor or judge role.
    Decision is recorded on the blockchain."""
    conn = get_db()
    cur = conn.cursor()

    if req.decision not in ("approved", "rejected"):
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    # Verify approver exists and has right role
    cur.execute("SELECT role FROM operators WHERE username = %s", (req.approver_username,))
    approver = cur.fetchone()
    if not approver:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Approver not found")
    if approver[0] not in ("supervisor", "judge"):
        cur.close()
        conn.close()
        raise HTTPException(status_code=403, detail="Only supervisors or judges can approve queries")

    # Check query exists and is pending
    cur.execute("SELECT status FROM queries WHERE id = %s", (req.query_id,))
    query_row = cur.fetchone()
    if not query_row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Query not found")
    if query_row[0] not in ("pending",):
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail=f"Query is already '{query_row[0]}', cannot approve/reject")

    # Check if approver already voted on this query
    cur.execute(
        "SELECT id FROM approvals WHERE query_id = %s AND approver = %s",
        (req.query_id, req.approver_username),
    )
    if cur.fetchone():
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="This approver has already voted on this query")

    # Record approval
    cur.execute(
        "INSERT INTO approvals (query_id, approver, decision) VALUES (%s, %s, %s)",
        (req.query_id, req.approver_username, req.decision),
    )

    # Count approvals and rejections
    cur.execute(
        "SELECT COUNT(*) FROM approvals WHERE query_id = %s AND decision = 'approved'",
        (req.query_id,),
    )
    approval_count = cur.fetchone()[0]

    cur.execute(
        "SELECT COUNT(*) FROM approvals WHERE query_id = %s AND decision = 'rejected'",
        (req.query_id,),
    )
    rejection_count = cur.fetchone()[0]

    # Determine new status (2 approvals needed, or 2 rejections to deny)
    if rejection_count >= 2:
        new_status = "rejected"
    elif approval_count >= 2:
        new_status = "approved"
    else:
        new_status = "pending"

    cur.execute("UPDATE queries SET status = %s WHERE id = %s", (new_status, req.query_id))

    # Write to PostgreSQL audit ledger
    now = datetime.now(timezone.utc).isoformat()
    previous_hash = get_last_ledger_hash(conn)
    ledger_entry = {
        "query_id": req.query_id,
        "event": req.decision,
        "actor": req.approver_username,
        "approval_count": approval_count,
        "rejection_count": rejection_count,
        "previous_hash": previous_hash,
        "timestamp": now,
    }
    entry_hash = compute_hash(ledger_entry)

    cur.execute(
        "INSERT INTO audit_ledger (query_id, event_type, actor, entry_hash, previous_hash) VALUES (%s, %s, %s, %s, %s)",
        (req.query_id, req.decision, req.approver_username, entry_hash, previous_hash),
    )

    conn.commit()
    cur.close()
    conn.close()

    # Write to blockchain
    block = blockchain.force_mine_single({
        "type": f"query_{req.decision}",
        "query_id": req.query_id,
        "approver": req.approver_username,
        "approver_role": approver[0],
        "decision": req.decision,
        "approval_count": approval_count,
        "rejection_count": rejection_count,
        "resulting_status": new_status,
        "pg_entry_hash": entry_hash,
    })

    status_msg = {
        "approved": "Query approved and ready for execution!",
        "rejected": "Query has been rejected.",
        "pending": "Vote recorded. More signatures needed.",
    }

    return {
        "query_id": req.query_id,
        "decision": req.decision,
        "approvals_so_far": approval_count,
        "rejections_so_far": rejection_count,
        "status": new_status,
        "ledger_entry_hash": entry_hash,
        "blockchain": {
            "block_index": block.index,
            "block_hash": block.hash,
            "merkle_root": block.merkle,
            "nonce": block.nonce,
        },
        "message": status_msg.get(new_status, "Vote recorded."),
    }


@app.post("/query/execute")
def execute_query(req: ExecuteRequest, _auth: bool = Depends(verify_api_key)):
    """Execute an approved query. Only approved queries can be executed.
    Execution event is recorded on the blockchain."""
    conn = get_db()
    cur = conn.cursor()

    # Verify executor
    cur.execute("SELECT role FROM operators WHERE username = %s", (req.executor_username,))
    executor = cur.fetchone()
    if not executor:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Executor not found")

    # Check query is approved
    cur.execute(
        "SELECT q.id, q.query_text, q.query_hash, q.status, o.username "
        "FROM queries q JOIN operators o ON q.operator_id = o.id WHERE q.id = %s",
        (req.query_id,),
    )
    query = cur.fetchone()
    if not query:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Query not found")
    if query[3] != "approved":
        cur.close()
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=f"Query status is '{query[3]}'. Only 'approved' queries can be executed.",
        )

    # Mark as executed
    cur.execute("UPDATE queries SET status = 'executed' WHERE id = %s", (req.query_id,))

    # Write to PostgreSQL audit ledger
    now = datetime.now(timezone.utc).isoformat()
    previous_hash = get_last_ledger_hash(conn)
    ledger_entry = {
        "query_id": req.query_id,
        "event": "executed",
        "actor": req.executor_username,
        "query_hash": query[2],
        "original_operator": query[4],
        "previous_hash": previous_hash,
        "timestamp": now,
    }
    entry_hash = compute_hash(ledger_entry)

    cur.execute(
        "INSERT INTO audit_ledger (query_id, event_type, actor, entry_hash, previous_hash) VALUES (%s, %s, %s, %s, %s)",
        (req.query_id, "executed", req.executor_username, entry_hash, previous_hash),
    )

    # Record execution details
    cur.execute(
        "INSERT INTO query_executions (query_id, executor, result_hash) VALUES (%s, %s, %s) RETURNING id",
        (req.query_id, req.executor_username, entry_hash),
    )
    execution_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    # Write to blockchain
    block = blockchain.force_mine_single({
        "type": "query_executed",
        "query_id": req.query_id,
        "execution_id": execution_id,
        "executor": req.executor_username,
        "query_hash": query[2],
        "original_operator": query[4],
        "pg_entry_hash": entry_hash,
    })

    return {
        "query_id": req.query_id,
        "execution_id": execution_id,
        "status": "executed",
        "executor": req.executor_username,
        "ledger_entry_hash": entry_hash,
        "blockchain": {
            "block_index": block.index,
            "block_hash": block.hash,
            "merkle_root": block.merkle,
            "nonce": block.nonce,
        },
        "message": "Query executed successfully. Event permanently recorded on blockchain.",
    }


# ─── Ledger Routes (PostgreSQL) ──────────────────────────

@app.get("/ledger")
def get_ledger(_auth: bool = Depends(verify_api_key)):
    """View the full PostgreSQL audit ledger (for oversight bodies)."""
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
            "timestamp": str(row[6]),
        })

    return {"ledger": ledger, "total_entries": len(ledger)}


def _verify_ledger_internal():
    """Internal ledger verification logic (no auth, reusable)."""
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
        expected_prev = rows[i - 1][1]
        actual_prev = rows[i][2]
        if actual_prev != expected_prev:
            issues.append(f"Chain broken between entry {rows[i-1][0]} and {rows[i][0]}")

    if issues:
        return {"status": "TAMPERED", "issues": issues}
    return {"status": "VERIFIED", "message": f"PostgreSQL ledger chain intact — {len(rows)} entries verified."}


@app.get("/ledger/verify")
def verify_ledger(_auth: bool = Depends(verify_api_key)):
    """Verify the integrity of the PostgreSQL ledger chain."""
    return _verify_ledger_internal()


# ─── Blockchain Routes ───────────────────────────────────

@app.get("/blockchain")
def get_blockchain(_auth: bool = Depends(verify_api_key)):
    """View the full blockchain (immutable, independent from PostgreSQL)."""
    chain = blockchain.get_full_chain()
    return {
        "chain": chain,
        "total_blocks": len(chain),
        "total_transactions": sum(len(b["transactions"]) for b in chain),
    }


@app.get("/blockchain/stats")
def blockchain_stats(_auth: bool = Depends(verify_api_key)):
    """Get blockchain statistics."""
    return blockchain.stats()


@app.get("/blockchain/verify")
def verify_blockchain(_auth: bool = Depends(verify_api_key)):
    """Full blockchain integrity verification: hash chain, proof-of-work, merkle roots."""
    return blockchain.verify_chain()


@app.get("/blockchain/block/{index}")
def get_block(index: int, _auth: bool = Depends(verify_api_key)):
    """Get a specific block by index."""
    block = blockchain.get_block(index)
    if block is None:
        raise HTTPException(status_code=404, detail=f"Block {index} not found")
    return block


@app.get("/blockchain/tx/{tx_hash}")
def get_transaction(tx_hash: str, _auth: bool = Depends(verify_api_key)):
    """Look up a transaction by its hash."""
    result = blockchain.get_transaction_by_hash(tx_hash)
    if result is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@app.get("/blockchain/query/{query_id}")
def get_blockchain_query_trail(query_id: int, _auth: bool = Depends(verify_api_key)):
    """Get the full blockchain trail for a specific query (all events)."""
    results = blockchain.get_transactions_for_query(query_id)
    return {
        "query_id": query_id,
        "events": results,
        "total_events": len(results),
    }


@app.get("/integrity")
def cross_verify(_auth: bool = Depends(verify_api_key)):
    """Cross-verify PostgreSQL ledger against blockchain for consistency."""
    pg_result = _verify_ledger_internal()
    bc_result = blockchain.verify_chain()

    pg_ok = pg_result.get("status") in ("VERIFIED", "empty")
    bc_ok = bc_result.get("status") == "VERIFIED"

    # Count transactions in blockchain that reference PG hashes
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT entry_hash FROM audit_ledger ORDER BY id ASC")
    pg_hashes = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()

    bc_pg_hashes = set()
    for block in blockchain.chain:
        for tx in block.transactions:
            if "pg_entry_hash" in tx:
                bc_pg_hashes.add(tx["pg_entry_hash"])

    # Check if all PG hashes exist on blockchain
    missing_on_chain = pg_hashes - bc_pg_hashes
    orphaned_on_chain = bc_pg_hashes - pg_hashes

    overall = "VERIFIED" if (pg_ok and bc_ok and not missing_on_chain) else "INCONSISTENT"

    return {
        "overall_status": overall,
        "postgresql_ledger": pg_result,
        "blockchain": bc_result,
        "cross_check": {
            "pg_entries": len(pg_hashes),
            "blockchain_references": len(bc_pg_hashes),
            "missing_on_blockchain": len(missing_on_chain),
            "orphaned_on_blockchain": len(orphaned_on_chain),
        },
        "message": (
            "Both ledgers are consistent and verified."
            if overall == "VERIFIED"
            else "Inconsistency detected between PostgreSQL and blockchain. Investigation required."
        ),
    }


# ─── Queries ─────────────────────────────────────────────

@app.get("/queries")
def get_queries(_auth: bool = Depends(verify_api_key)):
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

    return {
        "queries": [
            {
                "id": r[0],
                "operator": r[1],
                "query_text": r[2],
                "reason": r[3],
                "status": r[4],
                "query_hash": r[5],
                "created_at": str(r[6]),
            }
            for r in rows
        ]
    }


@app.get("/queries/{query_id}")
def get_query_detail(query_id: int, _auth: bool = Depends(verify_api_key)):
    """Get full details for a query, including approvals and blockchain trail."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT q.id, o.username, q.query_text, q.reason, q.status, q.query_hash, q.created_at
        FROM queries q
        JOIN operators o ON q.operator_id = o.id
        WHERE q.id = %s
    """, (query_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Query not found")

    # Get approvals
    cur.execute(
        "SELECT approver, decision, timestamp FROM approvals WHERE query_id = %s ORDER BY id ASC",
        (query_id,),
    )
    approvals = [
        {"approver": r[0], "decision": r[1], "timestamp": str(r[2])}
        for r in cur.fetchall()
    ]

    # Get execution if any
    cur.execute(
        "SELECT id, executor, result_hash, executed_at FROM query_executions WHERE query_id = %s",
        (query_id,),
    )
    exec_row = cur.fetchone()
    execution = None
    if exec_row:
        execution = {
            "execution_id": exec_row[0],
            "executor": exec_row[1],
            "result_hash": exec_row[2],
            "executed_at": str(exec_row[3]),
        }

    cur.close()
    conn.close()

    # Get blockchain trail
    bc_trail = blockchain.get_transactions_for_query(query_id)

    return {
        "query": {
            "id": row[0],
            "operator": row[1],
            "query_text": row[2],
            "reason": row[3],
            "status": row[4],
            "query_hash": row[5],
            "created_at": str(row[6]),
        },
        "approvals": approvals,
        "execution": execution,
        "blockchain_trail": bc_trail,
    }


@app.get("/operators")
def get_operators(_auth: bool = Depends(verify_api_key)):
    """List all operators."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, role, created_at FROM operators ORDER BY id ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {
        "operators": [
            {"id": r[0], "username": r[1], "role": r[2], "created_at": str(r[3])}
            for r in rows
        ]
    }
