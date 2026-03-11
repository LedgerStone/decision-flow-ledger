# Decision Flow Ledger

*Open-source data intelligence with accountability built in.*

Every query, analysis, and AI-assisted decision produces an **immutable, cryptographically verifiable audit trail** — without publishing sensitive data.

> Not "data on-chain".
> *Accountability on-chain, data kept inside a secure perimeter.*

---

## Repository structure

```
decision-flow-ledger/
├── mvp/        AIP-X — internal intelligence platform
├── saas/       DecisionLedger — external SaaS for clients
└── docs/       Shared documentation and architecture
```

This repo contains **two distinct products** built on the same core principle: every decision must be traceable, auditable, and tamper-proof.

---

## mvp/ — AIP-X (Internal Platform)

**What it is:** A Palantir-inspired intelligence platform for organizations that handle sensitive data — law enforcement, counter-terrorism, healthcare, corporate investigations.

**Who it's for:** Internal deployment within a single organization. The platform runs inside the organization's secure perimeter.

**Key characteristics:**
- Self-hosted, air-gap compatible
- Blockchain-backed immutable audit ledger (local PoW chain + PostgreSQL)
- Multi-signature approval workflows (2-of-N) for query execution
- Cross-verification between PostgreSQL and blockchain
- Graph analytics (Neo4j) for relationship mapping
- Role-based access: analyst, supervisor, judge

**How to run:**
```bash
cd mvp
docker compose up --build -d
# API: http://localhost:8000
# Dashboard: open mvp/dashboard.html
```

**Current status:** MVP functional — blockchain layer, query lifecycle (submit > approve > execute), immutability triggers on DB, dashboard with blockchain explorer.

[More details](mvp/README.md)

---

## saas/ — DecisionLedger (External SaaS)

**What it is:** A multi-tenant SaaS platform that provides auditable decision workflows as a service. Companies integrate it into their existing systems to get compliance-ready audit trails.

**Who it's for:** External clients — enterprises, fintechs, healthcare providers, legal firms — anyone who needs to prove that decisions were made correctly and cannot be altered after the fact.

**Key characteristics:**
- Multi-tenant architecture with tenant isolation
- REST API and SDK for integration into existing workflows
- Managed blockchain — clients don't need to run infrastructure
- Compliance dashboards (GDPR, SOX, HIPAA audit readiness)
- Webhook notifications for approval workflows
- Usage-based billing

**Use cases:**
- **Fintech:** Prove loan approval decisions were policy-compliant
- **Healthcare:** Verify data access was authorized and GDPR-compliant
- **Legal:** Immutable chain of custody for digital evidence
- **HR:** Auditable hiring/termination decision trails
- **Regulated industries:** Any process where "who approved what, when, and why" matters

**Current status:** In development.

---

## How mvp and saas relate

| | **mvp/ (AIP-X)** | **saas/ (DecisionLedger)** |
|---|---|---|
| **Deployment** | Self-hosted, on-premise | Cloud-hosted, managed |
| **Users** | Internal teams within one org | Multiple external client orgs |
| **Tenancy** | Single-tenant | Multi-tenant |
| **Data model** | Full intelligence platform (queries, graph, AI) | Decision audit trails as a service |
| **Blockchain** | Local chain, full control | Managed chain, per-tenant isolation |
| **Integration** | Standalone platform with dashboard | API/SDK to plug into existing systems |
| **Scope** | Deep analytics + accountability | Accountability layer only |
| **License** | Open source | Open core (community + enterprise tiers) |

The **mvp** is the full intelligence platform — it's what you deploy when you *are* the organization doing investigations and analytics.

The **saas** extracts the accountability layer and offers it to *other* organizations as a service — they keep their existing tools and plug DecisionLedger in for the audit trail.

They share the same core blockchain and audit primitives, but serve fundamentally different purposes.

---

## Tech stack

### Core (shared)
- Python 3.11+, FastAPI
- PostgreSQL 15 (with immutability triggers)
- Custom blockchain (SHA-256, PoW, Merkle trees)
- Docker / Docker Compose

### mvp-specific
- Neo4j (graph analytics)
- Single-file dashboard (HTML/JS)

### saas-specific (planned)
- Multi-tenant PostgreSQL (schema-per-tenant or RLS)
- Redis (caching, rate limiting)
- Stripe (billing)
- OAuth2 / API keys for client auth

### Future (both)
- LangChain + Ollama (AI layer)
- Keycloak (IAM)
- Zero-knowledge proofs (snarkjs)
- IPFS (evidence storage)

---

## Getting started

### Prerequisites
- Docker + Docker Compose
- Python 3.11+

### Quick start (mvp)
```bash
git clone https://github.com/LedgerStone/decision-flow-ledger.git
cd decision-flow-ledger/mvp
docker compose up --build -d
```

---

## License

Apache 2.0

---

## Contact

- Email: decision.acc@gmail.com
- Twitter: @ELCOM439088
