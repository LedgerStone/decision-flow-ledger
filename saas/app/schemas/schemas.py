"""
DecisionLedger SaaS — Pydantic schemas
"""

from typing import Optional
from pydantic import BaseModel, HttpUrl


# ─── Tenant ───────────────────────────────────────────────

class TenantCreate(BaseModel):
    name: str
    slug: str


class ApiKeyCreate(BaseModel):
    name: str
    scopes: list[str] = ["decisions:write", "decisions:read", "audit:read", "blockchain:read", "webhooks:write"]


# ─── Decision ─────────────────────────────────────────────

class DecisionCreate(BaseModel):
    decision_type: str  # e.g. "loan_approval", "access_request"
    title: str
    payload: dict  # arbitrary JSON data
    reason: str
    created_by: str  # actor identity from client system
    required_approvals: Optional[int] = None  # defaults to tenant setting


class DecisionExecute(BaseModel):
    executor: str


class DecisionCancel(BaseModel):
    cancelled_by: str
    reason: Optional[str] = None


# ─── Approval ─────────────────────────────────────────────

class ApprovalCreate(BaseModel):
    decision_id: str
    approver: str
    decision: str  # "approved" or "rejected"
    comment: Optional[str] = None


# ─── Webhook ──────────────────────────────────────────────

class WebhookCreate(BaseModel):
    url: str
    events: list[str]  # e.g. ["decision.submitted", "decision.approved"]
