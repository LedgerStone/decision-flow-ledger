"""
Unit tests for the blockchain module.
No Docker or database required — pure Python logic.
"""

import json
import hashlib
from pathlib import Path

import pytest


# ─── Helper ──────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ─── Tests ───────────────────────────────────────────────

class TestSha256:
    def test_deterministic(self):
        from blockchain import sha256
        assert sha256("hello") == sha256("hello")

    def test_different_inputs(self):
        from blockchain import sha256
        assert sha256("a") != sha256("b")


class TestMerkleRoot:
    def test_single_transaction(self):
        from blockchain import merkle_root, sha256
        txs = [{"foo": "bar"}]
        root = merkle_root(txs)
        expected = sha256(json.dumps(txs[0], sort_keys=True, default=str))
        assert root == expected

    def test_empty_transactions(self):
        from blockchain import merkle_root, sha256
        root = merkle_root([])
        assert root == sha256("empty")

    def test_two_transactions(self):
        from blockchain import merkle_root, sha256
        txs = [{"a": 1}, {"b": 2}]
        root = merkle_root(txs)
        leaf0 = sha256(json.dumps(txs[0], sort_keys=True, default=str))
        leaf1 = sha256(json.dumps(txs[1], sort_keys=True, default=str))
        expected = sha256(leaf0 + leaf1)
        assert root == expected

    def test_odd_number_duplicates_last(self):
        from blockchain import merkle_root, sha256
        txs = [{"a": 1}, {"b": 2}, {"c": 3}]
        root = merkle_root(txs)
        # With 3 leaves, the last is duplicated → 4 leaves
        assert isinstance(root, str)
        assert len(root) == 64


class TestBlock:
    def test_creation(self):
        from blockchain import Block
        b = Block(index=0, transactions=[{"test": True}], previous_hash="0" * 64)
        assert b.index == 0
        assert b.previous_hash == "0" * 64
        assert len(b.hash) == 64

    def test_mine_produces_valid_pow(self):
        from blockchain import Block
        b = Block(index=1, transactions=[{"x": 1}], previous_hash="abc" * 21 + "a")
        b.mine(difficulty=2)
        assert b.hash.startswith("00")

    def test_to_dict_from_dict_roundtrip(self):
        from blockchain import Block
        b = Block(index=0, transactions=[{"event": "genesis"}], previous_hash="0" * 64)
        b.mine(difficulty=2)
        d = b.to_dict()
        b2 = Block.from_dict(d)
        assert b2.index == b.index
        assert b2.hash == b.hash
        assert b2.merkle == b.merkle
        assert b2.nonce == b.nonce

    def test_tampering_changes_hash(self):
        from blockchain import Block
        b = Block(index=0, transactions=[{"amount": 100}], previous_hash="0" * 64)
        original_hash = b.compute_hash()
        b.transactions[0]["amount"] = 999
        # merkle must be recomputed for the hash to actually change
        from blockchain import merkle_root
        b.merkle = merkle_root(b.transactions)
        assert b.compute_hash() != original_hash


class TestBlockchain:
    def test_genesis_block_created(self, fresh_blockchain):
        bc = fresh_blockchain
        assert len(bc.chain) == 1
        assert bc.chain[0].index == 0
        assert bc.chain[0].previous_hash == "0" * 64

    def test_genesis_has_valid_pow(self, fresh_blockchain):
        bc = fresh_blockchain
        assert bc.chain[0].hash.startswith("0" * bc.difficulty)

    def test_force_mine_single(self, fresh_blockchain):
        bc = fresh_blockchain
        block = bc.force_mine_single({"type": "test", "data": 42})
        assert block.index == 1
        assert block.hash.startswith("0" * bc.difficulty)
        assert block.previous_hash == bc.chain[0].hash
        assert len(block.transactions) == 1
        assert block.transactions[0]["type"] == "test"

    def test_add_transaction_and_mine_pending(self, fresh_blockchain):
        bc = fresh_blockchain
        tx = bc.add_transaction({"type": "pending_test"})
        assert "tx_hash" in tx
        assert len(bc.pending_transactions) == 1

        block = bc.mine_pending()
        assert block is not None
        assert block.index == 1
        assert len(bc.pending_transactions) == 0

    def test_mine_pending_empty_returns_none(self, fresh_blockchain):
        bc = fresh_blockchain
        assert bc.mine_pending() is None

    def test_chain_linkage(self, fresh_blockchain):
        bc = fresh_blockchain
        bc.force_mine_single({"a": 1})
        bc.force_mine_single({"b": 2})
        bc.force_mine_single({"c": 3})

        for i in range(1, len(bc.chain)):
            assert bc.chain[i].previous_hash == bc.chain[i - 1].hash

    def test_verify_chain_valid(self, fresh_blockchain):
        bc = fresh_blockchain
        bc.force_mine_single({"test": 1})
        bc.force_mine_single({"test": 2})
        result = bc.verify_chain()
        assert result["status"] == "VERIFIED"
        assert result["blocks_checked"] == 3

    def test_verify_chain_detects_tampered_merkle(self, fresh_blockchain):
        bc = fresh_blockchain
        bc.force_mine_single({"amount": 100})
        # Tamper with transaction data
        bc.chain[1].transactions[0]["amount"] = 999
        result = bc.verify_chain()
        assert result["status"] == "TAMPERED"

    def test_persistence(self, tmp_path):
        from blockchain import Blockchain
        chain_file = tmp_path / "persist_test.json"

        bc1 = Blockchain(chain_file=chain_file, difficulty=2)
        bc1.force_mine_single({"persist": True})
        assert len(bc1.chain) == 2

        # Load from same file
        bc2 = Blockchain(chain_file=chain_file, difficulty=2)
        assert len(bc2.chain) == 2
        assert bc2.chain[1].transactions[0]["persist"] is True

    def test_get_block(self, fresh_blockchain):
        bc = fresh_blockchain
        genesis = bc.get_block(0)
        assert genesis is not None
        assert genesis["index"] == 0
        assert bc.get_block(999) is None

    def test_get_full_chain(self, fresh_blockchain):
        bc = fresh_blockchain
        bc.force_mine_single({"x": 1})
        chain = bc.get_full_chain()
        assert len(chain) == 2
        assert all("hash" in b for b in chain)

    def test_get_transaction_by_hash(self, fresh_blockchain):
        bc = fresh_blockchain
        block = bc.force_mine_single({"lookup": "me"})
        tx_hash = block.transactions[0]["tx_hash"]
        result = bc.get_transaction_by_hash(tx_hash)
        assert result is not None
        assert result["block_index"] == 1
        assert bc.get_transaction_by_hash("nonexistent") is None

    def test_get_transactions_for_query(self, fresh_blockchain):
        bc = fresh_blockchain
        bc.force_mine_single({"query_id": 42, "type": "submitted"})
        bc.force_mine_single({"query_id": 42, "type": "approved"})
        bc.force_mine_single({"query_id": 99, "type": "submitted"})
        results = bc.get_transactions_for_query(42)
        assert len(results) == 2

    def test_stats(self, fresh_blockchain):
        bc = fresh_blockchain
        bc.force_mine_single({"s": 1})
        stats = bc.stats()
        assert stats["total_blocks"] == 2
        assert stats["total_transactions"] == 2  # genesis + 1
        assert stats["difficulty"] == 2
