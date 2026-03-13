"""
End-to-end tests — full decision workflow against the live API.
Requires: docker compose up in mvp/ with API_KEY=changeme-mvp-api-key

Tests the complete lifecycle:
  submit → approve (2x) → execute → verify ledger + blockchain
"""

import requests


class TestFullApprovalWorkflow:
    """Submit → 2 approvals → execute → verify everything."""

    def test_complete_lifecycle(self, api_base, auth_header):
        # 1. Submit query
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT * FROM e2e_full_lifecycle_test",
            "reason": "E2E full lifecycle test",
        })
        assert r.status_code == 200
        submit_data = r.json()
        qid = submit_data["query_id"]
        assert submit_data["status"] == "pending"
        submit_block = submit_data["blockchain"]["block_index"]

        # 2. First approval (bob - supervisor) → still pending
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "bob",
            "decision": "approved",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["approvals_so_far"] == 1
        assert data["status"] == "pending"

        # 3. Second approval (carol - judge) → approved
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "carol",
            "decision": "approved",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["approvals_so_far"] == 2
        assert data["status"] == "approved"

        # 4. Execute
        r = requests.post(f"{api_base}/query/execute", headers=auth_header, json={
            "query_id": qid,
            "executor_username": "dave",
        })
        assert r.status_code == 200
        exec_data = r.json()
        assert exec_data["status"] == "executed"
        assert "execution_id" in exec_data
        exec_block = exec_data["blockchain"]["block_index"]

        # 5. Verify query detail shows full trail
        r = requests.get(f"{api_base}/queries/{qid}", headers=auth_header)
        assert r.status_code == 200
        detail = r.json()
        assert detail["query"]["status"] == "executed"
        assert len(detail["approvals"]) == 2
        assert detail["execution"] is not None
        assert detail["execution"]["executor"] == "dave"
        assert len(detail["blockchain_trail"]) >= 3  # submit + 2 approvals + execute

        # 6. Verify blockchain trail for this query
        r = requests.get(f"{api_base}/blockchain/query/{qid}", headers=auth_header)
        assert r.status_code == 200
        trail = r.json()
        assert trail["total_events"] >= 4  # submit, approve x2, execute
        event_types = [e["transaction"]["type"] for e in trail["events"]]
        assert "query_submitted" in event_types
        assert "query_approved" in event_types
        assert "query_executed" in event_types

        # 7. Verify ledger integrity
        r = requests.get(f"{api_base}/ledger/verify", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["status"] == "VERIFIED"

        # 8. Verify blockchain integrity
        r = requests.get(f"{api_base}/blockchain/verify", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["status"] == "VERIFIED"

        # 9. Cross-verify
        r = requests.get(f"{api_base}/integrity", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["overall_status"] == "VERIFIED"


class TestRejectionWorkflow:
    """Submit → 2 rejections → verify rejected status."""

    def test_rejection_lifecycle(self, api_base, auth_header):
        # Submit
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "eve",
            "query_text": "SELECT * FROM e2e_rejection_test",
            "reason": "E2E rejection test",
        })
        assert r.status_code == 200
        qid = r.json()["query_id"]

        # First rejection
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "bob",
            "decision": "rejected",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "pending"

        # Second rejection → rejected
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "carol",
            "decision": "rejected",
        })
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"

        # Cannot execute a rejected query
        r = requests.post(f"{api_base}/query/execute", headers=auth_header, json={
            "query_id": qid,
            "executor_username": "dave",
        })
        assert r.status_code == 400

        # Verify detail
        r = requests.get(f"{api_base}/queries/{qid}", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["query"]["status"] == "rejected"


class TestDoubleExecutionPrevented:
    """After executing, a second execute must fail."""

    def test_cannot_execute_twice(self, api_base, auth_header):
        # Submit
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT * FROM e2e_double_exec_test",
            "reason": "E2E double exec test",
        })
        qid = r.json()["query_id"]

        # Approve x2
        for approver in ("bob", "carol"):
            requests.post(f"{api_base}/query/approve", headers=auth_header, json={
                "query_id": qid, "approver_username": approver, "decision": "approved",
            })

        # Execute
        r = requests.post(f"{api_base}/query/execute", headers=auth_header, json={
            "query_id": qid, "executor_username": "dave",
        })
        assert r.status_code == 200

        # Try again
        r = requests.post(f"{api_base}/query/execute", headers=auth_header, json={
            "query_id": qid, "executor_username": "dave",
        })
        assert r.status_code == 400
        assert "executed" in r.json()["detail"]


class TestApproveAfterApproval:
    """Cannot approve an already-approved query."""

    def test_cannot_vote_after_approval(self, api_base, auth_header):
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT * FROM e2e_late_vote_test",
            "reason": "E2E late vote test",
        })
        qid = r.json()["query_id"]

        # Approve x2 → status becomes approved
        for approver in ("bob", "carol"):
            requests.post(f"{api_base}/query/approve", headers=auth_header, json={
                "query_id": qid, "approver_username": approver, "decision": "approved",
            })

        # Third approver tries to vote → should fail (no longer pending)
        r = requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid,
            "approver_username": "dave",
            "decision": "approved",
        })
        assert r.status_code == 400
        assert "already" in r.json()["detail"].lower()


class TestLedgerGrowsCorrectly:
    """Verify ledger entries are appended for each event."""

    def test_ledger_entries_count(self, api_base, auth_header):
        # Get current ledger count
        r = requests.get(f"{api_base}/ledger", headers=auth_header)
        initial_count = r.json()["total_entries"]

        # Submit a query → +1 ledger entry
        r = requests.post(f"{api_base}/query/submit", headers=auth_header, json={
            "operator_username": "alice",
            "query_text": "SELECT * FROM e2e_ledger_count_test",
            "reason": "Ledger count test",
        })
        qid = r.json()["query_id"]

        r = requests.get(f"{api_base}/ledger", headers=auth_header)
        assert r.json()["total_entries"] == initial_count + 1

        # Approve → +1 ledger entry
        requests.post(f"{api_base}/query/approve", headers=auth_header, json={
            "query_id": qid, "approver_username": "bob", "decision": "approved",
        })

        r = requests.get(f"{api_base}/ledger", headers=auth_header)
        assert r.json()["total_entries"] == initial_count + 2
