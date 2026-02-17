# Accountable Intelligence Platform (AIP-X)

*Open-source data intelligence inspired by Palantir — with accountability built in.*  
AIP-X is a modular platform where every query, analysis, and AI-assisted decision can produce an *immutable, cryptographically verifiable audit trail* (without publishing sensitive data).

> Not “data on-chain”.  
> *Accountability on-chain (or append-only ledger), data kept inside a secure perimeter.*

---

## Why this exists

Modern intelligence / investigation / high-stakes analytics platforms are powerful, but often operate like black boxes:
- Queries can be executed with limited oversight.
- Audit logs can be incomplete, hard to verify, or altered after the fact.
- AI recommendations can be hard to explain and hard to contest.

AIP-X aims to enable Palantir-level workflows while structurally reducing abuse by design:
- Immutable logging (append-only, tamper-evident).
- Policy-gated queries (RBAC + justification).
- Multi-approval workflows for sensitive actions.
- Optional cryptographic proofs (ZK) for “this was authorized” without revealing sensitive details.

---

## Core features (MVP-focused)

- *Controlled queries*: requests validated by policy before execution (role, purpose, scope).
- *Immutable query ledger*: hash + timestamp + actor + reason + decision (approved/denied), append-only.
- *Multi-signature governance (optional)*: sensitive queries require N-of-M approvals.
- *Graph investigations (Gotham-like)*: entity relationships, link analysis, fraud/network patterns.
- *AI assistant (AIP-like, optional)*: RAG over approved data + citations to sources + traceable actions.

---

## Tech stack (intended)

### Data integration / processing (Foundry-like)
- Apache NiFi (data flows, ingestion)
- Airbyte (connectors/ELT)
- dbt (transformations)
- Apache Spark (scale processing)
- Trino/Presto (federated SQL)

### Graph analytics (Gotham-like)
- Neo4j Community OR Apache AGE (PostgreSQL graph extension)
- NetworkX (algorithms), optional Gephi/Cytoscape (visual exploration)

### Audit ledger (accountability layer)
- PostgreSQL (audit schema, hashing, retention)
- Optional permissioned ledger: Hyperledger Fabric (or similar)
- Optional evidence store: S3-compatible / MinIO / IPFS (only for non-sensitive artifacts)

### AI layer (AIP-like)
- LangChain (or equivalent orchestration)
- Qdrant / Weaviate (vector store)
- Ollama (local LLMs) + optional OpenAI/others (configurable)
- SHAP/LIME (explainability where applicable)

### Security / governance
- Keycloak (IAM, OIDC)
- HashiCorp Vault (secrets)
- Optional ZK tooling: snarkjs (proofs for authorization claims)

---

## Getting started (placeholder)

> This repo is in early development. The goal is a one-command local demo.

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- Node.js 18+ (if you enable ZK tooling)

### Run (planned)
```bash
git clone https://github.com/<org>/<repo>.git
cd <repo>
docker compose up -d
