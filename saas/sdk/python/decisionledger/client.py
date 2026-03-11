"""
DecisionLedger Python SDK
"""

import httpx


class DecisionLedgerClient:
    """Client for the DecisionLedger SaaS API."""

    def __init__(self, api_key: str, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    def _handle(self, resp: httpx.Response) -> dict:
        resp.raise_for_status()
        return resp.json()

    # ─── Decisions ─────────────────────────────────────────

    def create_decision(
        self,
        decision_type: str,
        title: str,
        payload: dict,
        reason: str,
        created_by: str,
        required_approvals: int | None = None,
    ) -> dict:
        body = {
            "decision_type": decision_type,
            "title": title,
            "payload": payload,
            "reason": reason,
            "created_by": created_by,
        }
        if required_approvals is not None:
            body["required_approvals"] = required_approvals
        with httpx.Client() as c:
            return self._handle(c.post(self._url("/decisions/"), headers=self._headers, json=body))

    def get_decision(self, decision_id: str) -> dict:
        with httpx.Client() as c:
            return self._handle(c.get(self._url(f"/decisions/{decision_id}"), headers=self._headers))

    def list_decisions(self, status: str | None = None, decision_type: str | None = None) -> dict:
        params = {}
        if status:
            params["status"] = status
        if decision_type:
            params["decision_type"] = decision_type
        with httpx.Client() as c:
            return self._handle(c.get(self._url("/decisions/"), headers=self._headers, params=params))

    def execute_decision(self, decision_id: str, executor: str) -> dict:
        with httpx.Client() as c:
            return self._handle(c.post(
                self._url(f"/decisions/{decision_id}/execute"),
                headers=self._headers,
                json={"executor": executor},
            ))

    def cancel_decision(self, decision_id: str, cancelled_by: str, reason: str | None = None) -> dict:
        body = {"cancelled_by": cancelled_by}
        if reason:
            body["reason"] = reason
        with httpx.Client() as c:
            return self._handle(c.post(
                self._url(f"/decisions/{decision_id}/cancel"),
                headers=self._headers,
                json=body,
            ))

    # ─── Approvals ─────────────────────────────────────────

    def approve(self, decision_id: str, approver: str, comment: str | None = None) -> dict:
        body = {"decision_id": decision_id, "approver": approver, "decision": "approved"}
        if comment:
            body["comment"] = comment
        with httpx.Client() as c:
            return self._handle(c.post(self._url("/approvals/"), headers=self._headers, json=body))

    def reject(self, decision_id: str, approver: str, comment: str | None = None) -> dict:
        body = {"decision_id": decision_id, "approver": approver, "decision": "rejected"}
        if comment:
            body["comment"] = comment
        with httpx.Client() as c:
            return self._handle(c.post(self._url("/approvals/"), headers=self._headers, json=body))

    # ─── Audit ─────────────────────────────────────────────

    def get_audit_trail(self, decision_id: str | None = None) -> dict:
        path = f"/audit/decision/{decision_id}" if decision_id else "/audit/"
        with httpx.Client() as c:
            return self._handle(c.get(self._url(path), headers=self._headers))

    def verify_integrity(self) -> dict:
        with httpx.Client() as c:
            return self._handle(c.get(self._url("/audit/integrity"), headers=self._headers))

    # ─── Blockchain ────────────────────────────────────────

    def get_blockchain(self) -> dict:
        with httpx.Client() as c:
            return self._handle(c.get(self._url("/blockchain/"), headers=self._headers))

    def verify_blockchain(self) -> dict:
        with httpx.Client() as c:
            return self._handle(c.get(self._url("/blockchain/verify"), headers=self._headers))

    # ─── Webhooks ──────────────────────────────────────────

    def register_webhook(self, url: str, events: list[str]) -> dict:
        with httpx.Client() as c:
            return self._handle(c.post(
                self._url("/webhooks/"),
                headers=self._headers,
                json={"url": url, "events": events},
            ))
