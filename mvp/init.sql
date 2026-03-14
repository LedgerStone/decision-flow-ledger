-- AIP-X Core Database Schema

-- Operators (users of the system)
CREATE TABLE IF NOT EXISTS operators (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL, -- analyst, supervisor, judge
    created_at TIMESTAMP DEFAULT NOW()
);

-- Queries submitted to the system
CREATE TABLE IF NOT EXISTS queries (
    id SERIAL PRIMARY KEY,
    operator_id INT REFERENCES operators(id),
    query_text TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT DEFAULT 'pending', -- pending, approved, rejected, executed
    query_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Immutable audit ledger (append-only)
CREATE TABLE IF NOT EXISTS audit_ledger (
    id SERIAL PRIMARY KEY,
    query_id INT REFERENCES queries(id),
    event_type TEXT NOT NULL, -- submitted, approved, rejected, executed
    actor TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    previous_hash TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Approvals (multi-signature workflow)
CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    query_id INT REFERENCES queries(id),
    approver TEXT NOT NULL,
    decision TEXT NOT NULL, -- approved, rejected
    timestamp TIMESTAMP DEFAULT NOW(),
    -- Prevent duplicate votes
    UNIQUE(query_id, approver)
);

-- Query executions (post-approval)
CREATE TABLE IF NOT EXISTS query_executions (
    id SERIAL PRIMARY KEY,
    query_id INT REFERENCES queries(id) UNIQUE,
    executor TEXT NOT NULL,
    result_hash TEXT,
    executed_at TIMESTAMP DEFAULT NOW()
);

-- ─── Immutability protections ────────────────────────────

-- Prevent UPDATE on audit_ledger
CREATE OR REPLACE FUNCTION prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_ledger is immutable: UPDATE operations are forbidden';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_update_audit ON audit_ledger;
CREATE TRIGGER no_update_audit
    BEFORE UPDATE ON audit_ledger
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_update();

-- Prevent DELETE on audit_ledger
CREATE OR REPLACE FUNCTION prevent_audit_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_ledger is immutable: DELETE operations are forbidden';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_delete_audit ON audit_ledger;
CREATE TRIGGER no_delete_audit
    BEFORE DELETE ON audit_ledger
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_delete();

-- Prevent UPDATE on approvals
CREATE OR REPLACE FUNCTION prevent_approval_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'approvals table is immutable: UPDATE operations are forbidden';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_update_approvals ON approvals;
CREATE TRIGGER no_update_approvals
    BEFORE UPDATE ON approvals
    FOR EACH ROW
    EXECUTE FUNCTION prevent_approval_update();

-- Prevent DELETE on approvals
DROP TRIGGER IF EXISTS no_delete_approvals ON approvals;
CREATE TRIGGER no_delete_approvals
    BEFORE DELETE ON approvals
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_delete();

-- Blockchain blocks (persisted to survive redeploys)
CREATE TABLE IF NOT EXISTS blockchain_blocks (
    id SERIAL PRIMARY KEY,
    block_index INT UNIQUE NOT NULL,
    block_data JSONB NOT NULL,
    block_hash TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Prevent UPDATE on blockchain_blocks
CREATE OR REPLACE FUNCTION prevent_blockchain_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'blockchain_blocks is immutable: UPDATE operations are forbidden';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_update_blockchain ON blockchain_blocks;
CREATE TRIGGER no_update_blockchain
    BEFORE UPDATE ON blockchain_blocks
    FOR EACH ROW
    EXECUTE FUNCTION prevent_blockchain_update();

-- Prevent DELETE on blockchain_blocks
DROP TRIGGER IF EXISTS no_delete_blockchain ON blockchain_blocks;
CREATE TRIGGER no_delete_blockchain
    BEFORE DELETE ON blockchain_blocks
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_delete();

-- ─── Test data ───────────────────────────────────────────

INSERT INTO operators (username, role) VALUES
    ('alice', 'analyst'),
    ('bob', 'supervisor'),
    ('carol', 'judge'),
    ('dave', 'supervisor'),
    ('eve', 'analyst');
