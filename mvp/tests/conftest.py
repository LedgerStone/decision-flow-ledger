"""
Shared fixtures for MVP tests.

- Unit tests: use tmp_path blockchain, no DB needed
- Integration/E2E tests: hit the live API on localhost:8000 via the Docker container
"""

import os
import sys
from pathlib import Path

import pytest

# Add mvp/ to sys.path so we can import blockchain directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API_BASE = "http://localhost:8000"
API_KEY = os.getenv("API_KEY", "changeme-mvp-api-key")
AUTH_HEADER = {"X-Api-Key": API_KEY}


@pytest.fixture
def api_base():
    return API_BASE


@pytest.fixture
def auth_header():
    return dict(AUTH_HEADER)


@pytest.fixture
def fresh_blockchain(tmp_path):
    """Create a fresh Blockchain instance in a temp directory (no Docker needed)."""
    from blockchain import Blockchain

    chain_file = tmp_path / "test_chain.json"
    bc = Blockchain(chain_file=chain_file, difficulty=2)  # low difficulty for speed
    return bc
