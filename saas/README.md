# DecisionLedger SaaS

Multi-tenant auditable decision workflows as a service.

## Status

In development. See the [main README](../README.md) for the full vision.

## Planned structure

```
saas/
├── api/            FastAPI multi-tenant backend
├── blockchain/     Managed blockchain service (per-tenant)
├── billing/        Stripe integration
├── dashboard/      Client-facing compliance dashboard
├── sdk/            Python/JS client SDKs
└── docker-compose.yml
```
