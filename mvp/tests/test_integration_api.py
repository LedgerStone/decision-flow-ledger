"""
Integration tests — hit the live MVP API running in Docker on localhost:8000.
Requires: docker compose up in mvp/ with API_KEY=changeme-mvp-api-key

Tests each route individually for correct behavior and error handling.
"""

import pytest
import requests


# ─── Auth tests ──────────────────────────────────────────

class TestAuthentication:
    def test_health_no_auth_required(self, api_base):
        r = requests.get(f"{api_base}/health")
        assert r.status_code == 200
        assert r.json()["status"] in ("healthy", "degraded")

    def test_root_no_auth_required(self, api_base):
        r = requests.get(f"{api_base}/")
        assert r.status_code == 200
        assert "AIP-X" in r.json()["project"]

    def test_protected_route_rejects_missing_key(self, api_base):
        r = requests.get(f"{api_base}/queries")
        assert r.status_code == 422  # missing header

    def test_protected_route_rejects_wrong_key(self, api_base):
        r = requests.get(f"{api_base}/queries", headers={"X-Api-Key": "wrong-key"})
        assert r.status_code == 401

    def test_protected_route_accepts_valid_key(self, api_base, auth_header):
        r = requests.get(f"{api_base}/queries", headers=auth_header)
        assert r.status_code == 200


# ─── Health & root ───────────────────────────────────────

class TestHealthAndRoot:
    def test_health_has_database_field(self, api_base):
        r = requests.get(f"{api_base}/health")
        data = r.json()
        assert "database" in data
        assert data["database"] == "connected"

    def test_root_has_blockchain_info(self, api_base):
        r = requests.get(f"{api_base}/")
        data = r.json()
        assert "blockchain" in data
        assert "total_blocks" in data["blockchain"]
        assert data["version"] == "0.2.0"


# ─── Operators ───────────────────────────────────────────

class TestOperators:
    def test_list_operators(self, api_base, auth_header):
        r = requests.get(f"{api_base}/operators", headers=auth_header)
        assert r.status_code == 200
        ops = r.json()["operators"]
        assert len(ops) >= 5
        usernames = [o["username"] for o in ops]
        assert "alice" in usernames
        assert "bob" in usernames
        assert "carol" in usernames

    def test_operators_have_roles(self, api_base, auth_header):
        r = requests.get(f"{api_base}/operators", headers=auth_header)
        ops = r.json()["operators"]
        roles = {o["username"]: o["role"] for o in ops}
        assert roles["alice"] == "analyst"
        assert roles["bob"] == "supervisor"
        assert roles["carol"] == "judge"


# ─── Query submit ────────────────────────────────────────

class TestQuerySubmit:
    def test_submit_valid_query(self, api_base, auth_header):
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT 1 FROM test_integration",
            "reason": "Integration test",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "pending"
        assert "query_id" in data
        assert "query_hash" in data
        assert "blockchain" in data
        assert data["blockchain"]["block_index"] >= 1

    def test_submit_unknown_operator_404(self, api_base, auth_header):
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "nonexistent_user",
            "query_text": "SELECT 1",
            "reason": "test",
        })
        assert r.status_code == 404

    def test_submit_missing_fields_422(self, api_base, auth_header):
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
        })
        assert r.status_code == 422


# ─── Query approve ───────────────────────────────────────

class TestQueryApprove:
    def _submit_query(self, api_base, auth_header):
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT * FROM approve_test",
            "reason": "Approval test",
        })
        return r.json()["query_id"]

    def test_approve_valid(self, api_base, auth_header):
        qid = self._submit_query(api_base, auth_header)
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "bob",
            "decision": "approved",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["decision"] == "approved"
        assert data["approvals_so_far"] >= 1

    def test_approve_invalid_decision_400(self, api_base, auth_header):
        qid = self._submit_query(api_base, auth_header)
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "bob",
            "decision": "maybe",
        })
        assert r.status_code == 400

    def test_analyst_cannot_approve_403(self, api_base, auth_header):
        qid = self._submit_query(api_base, auth_header)
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "alice",  # analyst role
            "decision": "approved",
        })
        assert r.status_code == 403

    def test_duplicate_vote_400(self, api_base, auth_header):
        qid = self._submit_query(api_base, auth_header)
        requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid, "approver_username": "bob", "decision": "approved",
        })
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid, "approver_username": "bob", "decision": "approved",
        })
        assert r.status_code == 400
        assert "already voted" in r.json()["detail"]

    def test_nonexistent_query_404(self, api_base, auth_header):
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": 999999,
            "approver_username": "bob",
            "decision": "approved",
        })
        assert r.status_code == 404


# ─── Query execute ───────────────────────────────────────

class TestQueryExecute:
    def test_execute_unapproved_query_400(self, api_base, auth_header):
        # Submit a query (pending)
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT 1 FROM exec_test",
            "reason": "Exec test",
        })
        qid = r.json()["query_id"]
        r = requests.post(f"{api_base}/query/execute", headers=auth_header, json={
            "query_id": qid,
            "executor_username": "bob",
        })
        assert r.status_code == 400
        assert "pending" in r.json()["detail"]

    def test_execute_nonexistent_query_404(self, api_base, auth_header):
        r = requests.post(f"{api_base}/query/execute", headers=auth_header, json={
            "query_id": 999999,
            "executor_username": "bob",
        })
        assert r.status_code == 404


# ─── Ledger routes ───────────────────────────────────────

class TestLedger:
    def test_get_ledger(self, api_base, auth_header):
        r = requests.get(f"{api_base}/ledger", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "ledger" in data
        assert "total_entries" in data

    def test_verify_ledger(self, api_base, auth_header):
        r = requests.get(f"{api_base}/ledger/verify", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["status"] in ("VERIFIED", "empty", "TAMPERED")


# ─── Blockchain routes ───────────────────────────────────

class TestBlockchainRoutes:
    def test_get_blockchain(self, api_base, auth_header):
        r = requests.get(f"{api_base}/blockchain", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "chain" in data
        assert data["total_blocks"] >= 1

    def test_blockchain_stats(self, api_base, auth_header):
        r = requests.get(f"{api_base}/blockchain/stats", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "total_blocks" in data
        assert "difficulty" in data

    def test_blockchain_verify(self, api_base, auth_header):
        r = requests.get(f"{api_base}/blockchain/verify", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["status"] in ("VERIFIED", "TAMPERED")

    def test_get_block_genesis(self, api_base, auth_header):
        r = requests.get(f"{api_base}/blockchain/block/0", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["index"] == 0

    def test_get_block_not_found(self, api_base, auth_header):
        r = requests.get(f"{api_base}/blockchain/block/999999", headers=auth_header)
        assert r.status_code == 404

    def test_get_transaction_not_found(self, api_base, auth_header):
        r = requests.get(f"{api_base}/blockchain/tx/nonexistent", headers=auth_header)
        assert r.status_code == 404

    def test_blockchain_query_trail(self, api_base, auth_header):
        r = requests.get(f"{api_base}/blockchain/query/1", headers=auth_header)
        assert r.status_code == 200
        assert "events" in r.json()


# ─── Integrity ───────────────────────────────────────────

class TestIntegrity:
    def test_cross_verify(self, api_base, auth_header):
        r = requests.get(f"{api_base}/integrity", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert "overall_status" in data
        assert "cross_check" in data


# ─── Queries listing ─────────────────────────────────────

class TestQueriesListing:
    def test_list_queries(self, api_base, auth_header):
        r = requests.get(f"{api_base}/queries", headers=auth_header)
        assert r.status_code == 200
        assert "queries" in r.json()

    def test_get_query_detail(self, api_base, auth_header):
        # Submit one to be sure there's at least one
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT 1 FROM detail_test",
            "reason": "Detail test",
        })
        qid = r.json()["query_id"]
        r = requests.get(f"{api_base}/queries/{qid}", headers=auth_header)
        assert r.status_code == 200
        data = r.json()
        assert data["query"]["id"] == qid
        assert "approvals" in data
        assert "blockchain_trail" in data

    def test_get_nonexistent_query_404(self, api_base, auth_header):
        r = requests.get(f"{api_base}/queries/999999", headers=auth_header)
        assert r.status_code == 404
