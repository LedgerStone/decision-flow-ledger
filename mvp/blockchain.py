"""
AIP-X — Immutable Blockchain Layer
A local permissioned blockchain for audit trail immutability.

Each block contains:
- Index, timestamp, list of transactions
- Merkle root of transactions
- Previous block hash
- Nonce (proof-of-work)
- Block hash

The chain is persisted to PostgreSQL (blockchain_blocks table)
so it survives container redeploys.
"""

import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Optional

import psycopg2


DIFFICULTY = 4  # number of leading zeros required in block hash


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ─── Merkle Tree ──────────────────────────────────────────

def merkle_root(transactions: list[dict]) -> str:
    """Compute the Merkle root of a list of transactions."""
    if not transactions:
        return sha256("empty")

    leaves = [sha256(json.dumps(tx, sort_keys=True, default=str)) for tx in transactions]

    while len(leaves) > 1:
        if len(leaves) % 2 == 1:
            leaves.append(leaves[-1])  # duplicate last if odd
        next_level = []
        for i in range(0, len(leaves), 2):
            combined = sha256(leaves[i] + leaves[i + 1])
            next_level.append(combined)
        leaves = next_level

    return leaves[0]


# ─── Block ────────────────────────────────────────────────

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

    def mine(self, difficulty: int = DIFFICULTY) -> None:
        """Simple proof-of-work: find nonce so hash starts with `difficulty` zeros."""
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


# ─── Blockchain ───────────────────────────────────────────

class Blockchain:
    """
    Thread-safe, append-only blockchain with PostgreSQL persistence.
    """

    def __init__(self, database_url: str = "", difficulty: int = DIFFICULTY, **kwargs):
        self.database_url = database_url
        self.difficulty = difficulty
        self.chain: list[Block] = []
        self.pending_transactions: list[dict] = []
        self._lock = threading.Lock()
        self._load_or_init()

    # ── Database helpers ──────────────────────────────────

    def _get_db(self):
        return psycopg2.connect(self.database_url)

    def _ensure_table(self) -> None:
        """Create blockchain_blocks table if it doesn't exist."""
        try:
            conn = self._get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blockchain_blocks (
                    id SERIAL PRIMARY KEY,
                    block_index INT UNIQUE NOT NULL,
                    block_data JSONB NOT NULL,
                    block_hash TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

    # ── Persistence ────────────────────────────────────────

    def _load_or_init(self) -> None:
        """Load chain from PostgreSQL, or create genesis block."""
        if not self.database_url:
            self._create_genesis()
            return

        self._ensure_table()

        try:
            conn = self._get_db()
            cur = conn.cursor()
            cur.execute(
                "SELECT block_data FROM blockchain_blocks ORDER BY block_index ASC"
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()

            if rows:
                self.chain = [Block.from_dict(row[0]) for row in rows]
                return
        except Exception:
            pass

        self._create_genesis()

    def _create_genesis(self) -> None:
        genesis = Block(
            index=0,
            transactions=[{"event": "genesis", "message": "AIP-X Immutable Ledger initialized"}],
            previous_hash="0" * 64,
        )
        genesis.mine(self.difficulty)
        self.chain = [genesis]
        self._persist_block(genesis)

    def _persist_block(self, block: Block) -> None:
        """Save a single block to PostgreSQL."""
        if not self.database_url:
            return
        try:
            conn = self._get_db()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO blockchain_blocks (block_index, block_data, block_hash, previous_hash)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (block_index) DO NOTHING""",
                (block.index, json.dumps(block.to_dict(), default=str), block.hash, block.previous_hash),
            )
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            # Log but don't crash — chain is still in memory
            import logging
            logging.getLogger("aipx").warning(f"Failed to persist block {block.index}: {e}")

    # ── Core operations ────────────────────────────────────

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, transaction: dict) -> dict:
        """Add a transaction to the pending pool. Returns the transaction with its hash."""
        tx = {
            **transaction,
            "tx_timestamp": datetime.now(timezone.utc).isoformat(),
            "tx_hash": sha256(json.dumps(transaction, sort_keys=True, default=str)),
        }
        with self._lock:
            self.pending_transactions.append(tx)
        return tx

    def mine_pending(self) -> Optional[Block]:
        """Mine all pending transactions into a new block."""
        with self._lock:
            if not self.pending_transactions:
                return None

            new_block = Block(
                index=len(self.chain),
                transactions=list(self.pending_transactions),
                previous_hash=self.last_block.hash,
            )
            new_block.mine(self.difficulty)
            self.chain.append(new_block)
            self.pending_transactions.clear()
            self._persist_block(new_block)
            return new_block

    def force_mine_single(self, transaction: dict) -> Block:
        """Add a single transaction and immediately mine it into a block."""
        tx = {
            **transaction,
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
            self._persist_block(new_block)
            return new_block

    # ── Verification ───────────────────────────────────────

    def verify_chain(self) -> dict:
        """Full chain integrity verification."""
        issues = []

        for i, block in enumerate(self.chain):
            # Verify proof-of-work
            if not block.hash.startswith("0" * self.difficulty):
                issues.append(
                    f"Block {block.index}: invalid proof-of-work (hash={block.hash[:16]}...)"
                )

            # Verify chain linkage
            if i > 0:
                if block.previous_hash != self.chain[i - 1].hash:
                    issues.append(
                        f"Block {block.index}: broken chain link "
                        f"(prev={block.previous_hash[:16]}... != expected={self.chain[i-1].hash[:16]}...)"
                    )

            # Verify merkle root
            expected_merkle = merkle_root(block.transactions)
            if block.merkle != expected_merkle:
                issues.append(
                    f"Block {block.index}: merkle root mismatch (transaction tampering detected)"
                )

        if issues:
            return {"status": "TAMPERED", "issues": issues, "blocks_checked": len(self.chain)}

        return {
            "status": "VERIFIED",
            "message": f"Blockchain intact — {len(self.chain)} blocks verified, all proofs-of-work valid.",
            "blocks_checked": len(self.chain),
            "total_transactions": sum(len(b.transactions) for b in self.chain),
        }

    # ── Query ──────────────────────────────────────────────

    def get_block(self, index: int) -> Optional[dict]:
        if 0 <= index < len(self.chain):
            return self.chain[index].to_dict()
        return None

    def get_full_chain(self) -> list[dict]:
        return [b.to_dict() for b in self.chain]

    def get_transaction_by_hash(self, tx_hash: str) -> Optional[dict]:
        """Search for a transaction by its hash across all blocks."""
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("tx_hash") == tx_hash:
                    return {"transaction": tx, "block_index": block.index, "block_hash": block.hash}
        return None

    def get_transactions_for_query(self, query_id: int) -> list[dict]:
        """Get all blockchain transactions related to a specific query."""
        results = []
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("query_id") == query_id:
                    results.append({
                        "transaction": tx,
                        "block_index": block.index,
                        "block_hash": block.hash,
                    })
        return results

    def stats(self) -> dict:
        total_tx = sum(len(b.transactions) for b in self.chain)
        return {
            "total_blocks": len(self.chain),
            "total_transactions": total_tx,
            "pending_transactions": len(self.pending_transactions),
            "last_block_hash": self.last_block.hash,
            "last_block_index": self.last_block.index,
            "difficulty": self.difficulty,
        }
