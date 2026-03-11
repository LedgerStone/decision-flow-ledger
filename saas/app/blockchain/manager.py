"""
DecisionLedger SaaS — Per-tenant blockchain manager
"""

import threading
from pathlib import Path

from app.blockchain.core import Blockchain
from app.config import settings


class TenantBlockchainManager:
    """Manages one Blockchain instance per tenant, lazily initialized and cached."""

    def __init__(self):
        self._chains: dict[str, Blockchain] = {}
        self._lock = threading.Lock()

    def get_chain(self, tenant_id: str) -> Blockchain:
        if tenant_id not in self._chains:
            with self._lock:
                if tenant_id not in self._chains:
                    chain_file = Path(settings.BLOCKCHAIN_DATA_DIR) / tenant_id / "chain.json"
                    self._chains[tenant_id] = Blockchain(
                        chain_file=chain_file,
                        difficulty=settings.BLOCKCHAIN_DIFFICULTY,
                        tenant_id=tenant_id,
                    )
        return self._chains[tenant_id]

    def remove_chain(self, tenant_id: str) -> None:
        with self._lock:
            self._chains.pop(tenant_id, None)


blockchain_manager = TenantBlockchainManager()
