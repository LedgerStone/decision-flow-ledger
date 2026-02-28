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
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Test data
INSERT INTO operators (username, role) VALUES
    ('alice', 'analyst'),
    ('bob', 'supervisor'),
    ('carol', 'judge');
