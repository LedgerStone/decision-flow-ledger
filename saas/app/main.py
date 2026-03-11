"""
DecisionLedger SaaS — Main application
Multi-tenant auditable decision workflows as a service.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_pool, close_pool
from app.routers import tenants, decisions, approvals, audit, blockchain, webhooks, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(
    title="DecisionLedger API",
    description="Multi-tenant auditable decision workflows backed by blockchain",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router)
app.include_router(tenants.router)
app.include_router(decisions.router)
app.include_router(approvals.router)
app.include_router(audit.router)
app.include_router(blockchain.router)
app.include_router(webhooks.router)


@app.get("/")
async def root():
    return {
        "service": "DecisionLedger",
        "description": "Auditable decision workflows as a service",
        "version": "0.1.0",
        "docs": "/docs",
    }
