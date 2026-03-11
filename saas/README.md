# DecisionLedger SaaS

Multi-tenant auditable decision workflows as a service, backed by an immutable blockchain.

## Architecture

```
saas/
├── app/
│   ├── main.py              FastAPI application
│   ├── config.py             Settings (env-based)
│   ├── database.py           Async connection pool with RLS
│   ├── auth/api_key.py       API key authentication (bcrypt)
│   ├── routers/              API endpoints
│   │   ├── tenants.py        Admin: tenant + API key management
│   │   ├── decisions.py      Decision CRUD + lifecycle
│   │   ├── approvals.py      Multi-sig approval workflow
│   │   ├── audit.py          Audit trail + cross-verification
│   │   ├── blockchain.py     Blockchain explorer
│   │   ├── webhooks.py       Webhook management
│   │   └── health.py         Health check
│   ├── services/             Business logic
│   ├── blockchain/           Per-tenant blockchain (PoW + Merkle)
│   └── webhooks/             HMAC-signed event dispatcher
├── sdk/python/               Python client SDK
├── init.sql                  Schema with RLS + immutability triggers
├── docker-compose.yml        PostgreSQL + API
└── Dockerfile
```

## Quick start

```bash
cd saas
docker compose up --build -d
# API runs on http://localhost:8001
# Docs at http://localhost:8001/docs
```

## Usage

### 1. Create a tenant (admin)

```bash
curl -X POST http://localhost:8001/api/v1/admin/tenants/ \
  -H "X-Admin-Secret: changeme-admin-secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "slug": "acme"}'
```

### 2. Generate an API key

```bash
curl -X POST http://localhost:8001/api/v1/admin/tenants/<TENANT_ID>/api-keys \
  -H "X-Admin-Secret: changeme-admin-secret" \
  -H "Content-Type: application/json" \
  -d '{"name": "production-key"}'
```

Save the returned `key` -- it won't be shown again.

### 3. Create a decision

```bash
curl -X POST http://localhost:8001/api/v1/decisions/ \
  -H "Authorization: Bearer dl_live_<YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "decision_type": "loan_approval",
    "title": "Loan #1234 for John Doe",
    "payload": {"amount": 50000, "currency": "EUR", "applicant": "john.doe@example.com"},
    "reason": "Standard loan application review",
    "created_by": "analyst@acme.com"
  }'
```

### 4. Approve (needs 2 signatures)

```bash
curl -X POST http://localhost:8001/api/v1/approvals/ \
  -H "Authorization: Bearer dl_live_<YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"decision_id": "<ID>", "approver": "manager@acme.com", "decision": "approved"}'

curl -X POST http://localhost:8001/api/v1/approvals/ \
  -H "Authorization: Bearer dl_live_<YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"decision_id": "<ID>", "approver": "director@acme.com", "decision": "approved"}'
```

### 5. Execute

```bash
curl -X POST http://localhost:8001/api/v1/decisions/<ID>/execute \
  -H "Authorization: Bearer dl_live_<YOUR_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"executor": "system@acme.com"}'
```

### 6. Verify integrity

```bash
curl http://localhost:8001/api/v1/audit/integrity \
  -H "Authorization: Bearer dl_live_<YOUR_KEY>"
```

## Python SDK

```python
from decisionledger import DecisionLedgerClient

client = DecisionLedgerClient(api_key="dl_live_...", base_url="http://localhost:8001")

# Create a decision
result = client.create_decision(
    decision_type="access_request",
    title="Database access for Project X",
    payload={"database": "production", "permissions": ["read"]},
    reason="Quarterly audit preparation",
    created_by="analyst@company.com",
)

# Approve
client.approve(result["id"], approver="manager@company.com")
client.approve(result["id"], approver="ciso@company.com")

# Verify
print(client.verify_integrity())
```

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/v1/admin/tenants/ | Admin | Create tenant |
| POST | /api/v1/admin/tenants/{id}/api-keys | Admin | Generate API key |
| DELETE | /api/v1/admin/tenants/{id}/api-keys/{kid} | Admin | Revoke key |
| GET | /api/v1/admin/tenants/ | Admin | List tenants |
| POST | /api/v1/decisions/ | API Key | Create decision |
| GET | /api/v1/decisions/ | API Key | List decisions |
| GET | /api/v1/decisions/{id} | API Key | Decision detail |
| POST | /api/v1/decisions/{id}/execute | API Key | Execute decision |
| POST | /api/v1/decisions/{id}/cancel | API Key | Cancel decision |
| POST | /api/v1/approvals/ | API Key | Submit vote |
| GET | /api/v1/audit/ | API Key | Full audit trail |
| GET | /api/v1/audit/decision/{id} | API Key | Decision audit trail |
| GET | /api/v1/audit/verify | API Key | Verify PG hash chain |
| GET | /api/v1/audit/integrity | API Key | Cross-verify PG + blockchain |
| GET | /api/v1/blockchain/ | API Key | Full blockchain |
| GET | /api/v1/blockchain/stats | API Key | Blockchain stats |
| GET | /api/v1/blockchain/verify | API Key | Verify blockchain |
| GET | /api/v1/blockchain/block/{idx} | API Key | Get block |
| GET | /api/v1/blockchain/tx/{hash} | API Key | Find transaction |
| GET | /api/v1/blockchain/decision/{id} | API Key | Decision BC trail |
| POST | /api/v1/webhooks/ | API Key | Register webhook |
| GET | /api/v1/webhooks/ | API Key | List webhooks |
| DELETE | /api/v1/webhooks/{id} | API Key | Deactivate webhook |
| GET | /api/v1/webhooks/{id}/deliveries | API Key | Delivery history |
| GET | /health | None | Health check |

## Security

- **Tenant isolation**: PostgreSQL Row-Level Security (RLS) enforced on all tenant tables
- **Immutability**: Database triggers prevent UPDATE/DELETE on audit entries and approvals
- **API keys**: bcrypt-hashed at rest, prefix-based lookup (no full table scan)
- **Blockchain**: Independent per-tenant chain with PoW and Merkle tree verification
- **Webhooks**: HMAC-SHA256 signed payloads (`X-DecisionLedger-Signature` header)
- **Cross-verification**: Detect inconsistencies between PostgreSQL and blockchain
