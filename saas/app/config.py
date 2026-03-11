"""
DecisionLedger SaaS — Configuration
"""

import logging
from pathlib import Path

from pydantic_settings import BaseSettings

logger = logging.getLogger("decisionledger.config")


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://admin:admin123@localhost:5432/decisionledger"
    ADMIN_SECRET: str = "changeme-admin-secret"
    BLOCKCHAIN_DATA_DIR: str = "/data/blockchain"
    BLOCKCHAIN_DIFFICULTY: int = 4
    DEFAULT_APPROVALS_REQUIRED: int = 2
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_MAX_RETRIES: int = 3

    class Config:
        env_file = ".env"

    @property
    def normalized_database_url(self) -> str:
        """Railway may set DATABASE_URL with postgres:// scheme."""
        url = self.DATABASE_URL
        if url.startswith("postgres://") and not url.startswith("postgresql://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def resolved_blockchain_dir(self) -> str:
        """Return a writable blockchain directory, falling back to /tmp."""
        primary = Path(self.BLOCKCHAIN_DATA_DIR)
        try:
            primary.mkdir(parents=True, exist_ok=True)
            test_file = primary / ".write_test"
            test_file.write_text("ok")
            test_file.unlink()
            return str(primary)
        except OSError:
            fallback = "/tmp/blockchain"
            Path(fallback).mkdir(parents=True, exist_ok=True)
            logger.warning("Primary blockchain dir %s not writable, falling back to %s", primary, fallback)
            return fallback


settings = Settings()
