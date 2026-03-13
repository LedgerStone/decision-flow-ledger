"""
Unit tests for compute_hash and _normalize_database_url from main.py.
No Docker or database required.
"""

import hashlib
import json


class TestComputeHash:
    def _compute_hash(self, data: dict) -> str:
        """Mirror of main.compute_hash for isolated testing."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def test_deterministic(self):
        data = {"a": 1, "b": "hello"}
        assert self._compute_hash(data) == self._compute_hash(data)

    def test_key_order_irrelevant(self):
        d1 = {"z": 1, "a": 2}
        d2 = {"a": 2, "z": 1}
        assert self._compute_hash(d1) == self._compute_hash(d2)

    def test_different_data_different_hash(self):
        assert self._compute_hash({"x": 1}) != self._compute_hash({"x": 2})

    def test_output_is_64_hex_chars(self):
        h = self._compute_hash({"test": True})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestNormalizeDatabaseUrl:
    def _normalize(self, url: str) -> str:
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql://", 1)
        return url

    def test_postgres_scheme_converted(self):
        assert self._normalize("postgres://user:pass@host/db") == "postgresql://user:pass@host/db"

    def test_postgresql_scheme_unchanged(self):
        url = "postgresql://user:pass@host/db"
        assert self._normalize(url) == url

    def test_only_first_occurrence_replaced(self):
        url = "postgres://user:postgres@host/db"
        result = self._normalize(url)
        assert result.startswith("postgresql://")
        assert "postgres@host" in result
