"""Tests for application configuration (AC #7)."""

from app.core.config import Settings


def test_default_oracle_settings():
    s = Settings()
    assert s.oracle_dsn == "localhost:1521/FREEPDB1"
    assert s.oracle_user == "idp_app"
    assert s.oracle_min_pool == 2
    assert s.oracle_max_pool == 10


def test_default_cors_origin():
    s = Settings()
    assert s.cors_origins == ["http://localhost:5173"]
    assert s.cors_origin == "http://localhost:5173"
    assert s.frontend_base_url == "http://localhost:5173"
