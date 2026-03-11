"""
DecisionLedger SaaS — Configuration
"""

from pydantic_settings import BaseSettings


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


settings = Settings()
