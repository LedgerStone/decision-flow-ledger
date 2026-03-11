"""
DecisionLedger SaaS — Blockchain core
Adapted from mvp/blockchain.py for per-tenant usage.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def merkle_root(transactions: list[dict]) -> str:
    if not transactions:
        return sha256("empty")

    leaves = [sha256(json.dumps(tx, sort_keys=True, default=str)) for tx in transactions]

    while len(leaves) > 1:
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])
        next_level = []
        for i in range(0, len(leaves), 2):
            next_level.append(sha256(leaves[i] + leaves[i + 1]))
        leaves = next_level

    return leaves[0]


class Block:
    def __init__(
        self,
        index: int,
        transactions: list[dict],
        previous_hash: str,
        timestamp: Optional[str] = None,
        nonce: int = 0,
        block_hash: Optional[str] = None,
    ):
        self.index = index
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.merkle = merkle_root(transactions)
        self.nonce = nonce
        self.hash = block_hash or self.compute_hash()

    def compute_hash(self) -> str:
        block_data = json.dumps(
            {
                "index": self.index,
                "transactions": self.transactions,
                "previous_hash": self.previous_hash,
                "timestamp": self.timestamp,
                "merkle_root": self.merkle,
                "nonce": self.nonce,
            },
            sort_keys=True,
            default=str,
        )
        return sha256(block_data)

    def mine(self, difficulty: int) -> None:
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.compute_hash()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "merkle_root": self.merkle,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        return cls(
            index=data["index"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
            block_hash=data["hash"],
        )


class Blockchain:
    def __init__(self, chain_file: Path, difficulty: int = 4, tenant_id: str = ""):
        self.chain_file = chain_file
        self.difficulty = difficulty
        self.tenant_id = tenant_id
        self.chain: list[Block] = []
        self._lock = threading.Lock()
        self._load_or_init()

    def _load_or_init(self) -> None:
        if self.chain_file.exists():
            try:
                data = json.loads(self.chain_file.read_text())
                self.chain = [Block.from_dict(b) for b in data]
                if self.chain:
                    return
            except (json.JSONDecodeError, KeyError):
                pass
        self._create_genesis()

    def _create_genesis(self) -> None:
        genesis = Block(
            index=0,
            transactions=[{
                "event": "genesis",
                "tenant_id": self.tenant_id,
                "message": "DecisionLedger blockchain initialized",
            }],
            previous_hash="0" * 64,
        )
        genesis.mine(self.difficulty)
        self.chain = [genesis]
        self._persist()

    def _persist(self) -> None:
        try:
            self.chain_file.parent.mkdir(parents=True, exist_ok=True)
            self.chain_file.write_text(
                json.dumps([b.to_dict() for b in self.chain], indent=2, default=str)
            )
        except OSError:
            # Fallback for Railway or read-only filesystems
            fallback = Path("/tmp/blockchain") / self.tenant_id / self.chain_file.name
            fallback.parent.mkdir(parents=True, exist_ok=True)
            fallback.write_text(
                json.dumps([b.to_dict() for b in self.chain], indent=2, default=str)
            )
            self.chain_file = fallback

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def force_mine_single(self, transaction: dict) -> Block:
        tx = {
            **transaction,
            "tenant_id": self.tenant_id,
            "tx_timestamp": datetime.now(timezone.utc).isoformat(),
            "tx_hash": sha256(json.dumps(transaction, sort_keys=True, default=str)),
        }
        with self._lock:
            new_block = Block(
                index=len(self.chain),
                transactions=[tx],
                previous_hash=self.last_block.hash,
            )
            new_block.mine(self.difficulty)
            self.chain.append(new_block)
            self._persist()
            return new_block

    def verify_chain(self) -> dict:
        issues = []
        for i, block in enumerate(self.chain):
            if not block.hash.startswith("0" * self.difficulty):
                issues.append(f"Block {block.index}: invalid proof-of-work")
            if i > 0 and block.previous_hash != self.chain[i - 1].hash:
                issues.append(f"Block {block.index}: broken chain link")
            if block.merkle != merkle_root(block.transactions):
                issues.append(f"Block {block.index}: merkle root mismatch")

        if issues:
            return {"status": "TAMPERED", "issues": issues, "blocks_checked": len(self.chain)}
        return {
            "status": "VERIFIED",
            "message": f"Blockchain intact — {len(self.chain)} blocks verified.",
            "blocks_checked": len(self.chain),
            "total_transactions": sum(len(b.transactions) for b in self.chain),
        }

    def get_block(self, index: int) -> Optional[dict]:
        if 0 <= index < len(self.chain):
            return self.chain[index].to_dict()
        return None

    def get_full_chain(self) -> list[dict]:
        return [b.to_dict() for b in self.chain]

    def get_transaction_by_hash(self, tx_hash: str) -> Optional[dict]:
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("tx_hash") == tx_hash:
                    return {"transaction": tx, "block_index": block.index, "block_hash": block.hash}
        return None

    def get_transactions_for_decision(self, decision_id: str) -> list[dict]:
        results = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("decision_id") == decision_id:
                    results.append({
                        "transaction": tx,
                        "block_index": block.index,
                        "block_hash": block.hash,
                    })
        return results

    def stats(self) -> dict:
        total_tx = sum(len(b.transactions) for b in self.chain)
        return {
            "tenant_id": self.tenant_id,
            "total_blocks": len(self.chain),
            "total_transactions": total_tx,
            "last_block_hash": self.last_block.hash,
            "last_block_index": self.last_block.index,
            "difficulty": self.difficulty,
        }
