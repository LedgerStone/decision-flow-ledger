-- DecisionLedger SaaS — Multi-tenant schema with RLS

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Tenants ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── API Keys ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    key_hash TEXT NOT NULL,
    prefix TEXT NOT NULL,  -- first 8 hex chars for fast lookup
    name TEXT NOT NULL,
    scopes TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    revoked_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(prefix);

-- ─── Decisions ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    decision_type TEXT NOT NULL,
    title TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    reason TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, executed, cancelled
    decision_hash TEXT NOT NULL,
    required_approvals INT DEFAULT 2,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_decisions_tenant ON decisions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(tenant_id, decision_type);

-- ─── Approvals ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    decision_id UUID NOT NULL REFERENCES decisions(id),
    approver TEXT NOT NULL,
    decision TEXT NOT NULL,  -- approved, rejected
    comment TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(decision_id, approver)
);

CREATE INDEX IF NOT EXISTS idx_approvals_decision ON approvals(tenant_id, decision_id);

-- ─── Audit Entries (immutable) ───────────────────────────

CREATE TABLE IF NOT EXISTS audit_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    decision_id TEXT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    previous_hash TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_entries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_entries(tenant_id, decision_id);

-- ─── Webhook Endpoints ───────────────────────────────────

CREATE TABLE IF NOT EXISTS webhook_endpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    url TEXT NOT NULL,
    events JSONB DEFAULT '[]',
    secret TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_webhooks_tenant ON webhook_endpoints(tenant_id);

-- ─── Webhook Deliveries ──────────────────────────────────

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhook_endpoints(id),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    event_type TEXT NOT NULL,
    payload TEXT,
    response_status INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─── Immutability Triggers ───────────────────────────────

CREATE OR REPLACE FUNCTION prevent_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '% is immutable: UPDATE forbidden', TG_TABLE_NAME;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prevent_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '% is immutable: DELETE forbidden', TG_TABLE_NAME;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Audit entries: immutable
DROP TRIGGER IF EXISTS no_update_audit_entries ON audit_entries;
CREATE TRIGGER no_update_audit_entries BEFORE UPDATE ON audit_entries
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

DROP TRIGGER IF EXISTS no_delete_audit_entries ON audit_entries;
CREATE TRIGGER no_delete_audit_entries BEFORE DELETE ON audit_entries
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- Approvals: immutable
DROP TRIGGER IF EXISTS no_update_approvals ON approvals;
CREATE TRIGGER no_update_approvals BEFORE UPDATE ON approvals
    FOR EACH ROW EXECUTE FUNCTION prevent_update();

DROP TRIGGER IF EXISTS no_delete_approvals ON approvals;
CREATE TRIGGER no_delete_approvals BEFORE DELETE ON approvals
    FOR EACH ROW EXECUTE FUNCTION prevent_delete();

-- ─── Row-Level Security ──────────────────────────────────

ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_endpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY;

-- Policies: restrict rows to current tenant
CREATE POLICY tenant_isolation_decisions ON decisions
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_approvals ON approvals
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_audit ON audit_entries
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_webhooks ON webhook_endpoints
    USING (tenant_id::text = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_deliveries ON webhook_deliveries
    USING (tenant_id::text = current_setting('app.current_tenant', true));

-- Grant policies to the app user (admin in dev)
-- RLS is enforced for non-superusers. In production, use a dedicated app role.
-- For development with superuser, RLS must be forced:
ALTER TABLE decisions FORCE ROW LEVEL SECURITY;
ALTER TABLE approvals FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE webhook_endpoints FORCE ROW LEVEL SECURITY;
ALTER TABLE webhook_deliveries FORCE ROW LEVEL SECURITY;
