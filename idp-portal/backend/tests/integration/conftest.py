"""Integration test fixtures. Requires Oracle (e.g. docker compose up -d oracle) and ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD."""

import os

import pytest


def _oracle_available() -> bool:
    """True if Oracle env vars are set (e.g. for Docker Oracle dev)."""
    return bool(
        os.environ.get("ORACLE_DSN")
        and os.environ.get("ORACLE_USER")
        and os.environ.get("ORACLE_PASSWORD")
    )


@pytest.fixture(scope="module")
def skip_if_no_oracle():
    """Skip integration tests when Oracle is not configured (e.g. CI without Oracle)."""
    if not _oracle_available():
        pytest.skip(
            "Oracle not configured: set ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD (e.g. docker compose up -d oracle)"
        )
