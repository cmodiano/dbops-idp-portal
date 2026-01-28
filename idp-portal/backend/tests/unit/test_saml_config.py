"""Tests for SAML configuration and settings."""

from app.core.config import Settings
from app.core.saml import get_saml_settings, _prepare_fastapi_request


def test_jwt_settings_defaults():
    """Verify JWT defaults in Settings."""
    s = Settings()
    assert s.jwt_algorithm == "HS256"
    assert s.jwt_access_token_expire_minutes == 30
    assert s.jwt_refresh_token_expire_hours == 8
    assert s.jwt_secret_key == "change-me-in-production"


def test_saml_settings_defaults():
    """Verify SAML defaults in Settings."""
    s = Settings()
    assert s.saml_sp_entity_id == "https://idp-portal.example.com/metadata"
    assert s.saml_sp_acs_url == "http://localhost:8000/api/v1/auth/saml/callback"
    assert s.saml_idp_entity_id == "https://idp.example.com/entity"
    assert s.saml_idp_sso_url == "https://idp.example.com/sso"
    assert s.saml_idp_slo_url == "https://idp.example.com/slo"
    assert s.saml_idp_cert_path == ""
    assert s.saml_sp_key_path == ""
    assert s.saml_sp_cert_path == ""


def test_auth_dev_bypass_default():
    """Verify dev bypass is off by default."""
    s = Settings()
    assert s.auth_dev_bypass is False


def test_get_saml_settings_structure():
    """Verify get_saml_settings returns correct structure."""
    result = get_saml_settings()
    assert "strict" in result
    assert result["strict"] is True
    assert "sp" in result
    assert "idp" in result


def test_get_saml_settings_sp():
    """Verify SP configuration in SAML settings."""
    result = get_saml_settings()
    sp = result["sp"]
    assert sp["entityId"] == "https://idp-portal.example.com/metadata"
    assert sp["assertionConsumerService"]["url"] == "http://localhost:8000/api/v1/auth/saml/callback"
    assert sp["assertionConsumerService"]["binding"] == "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"


def test_get_saml_settings_idp():
    """Verify IdP configuration in SAML settings."""
    result = get_saml_settings()
    idp = result["idp"]
    assert idp["entityId"] == "https://idp.example.com/entity"
    assert idp["singleSignOnService"]["url"] == "https://idp.example.com/sso"
    assert idp["singleSignOnService"]["binding"] == "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
    assert idp["singleLogoutService"]["url"] == "https://idp.example.com/slo"


def test_prepare_fastapi_request_https():
    """Verify HTTPS request conversion."""
    from unittest.mock import MagicMock
    from starlette.datastructures import URL, QueryParams

    request = MagicMock()
    request.url = URL("https://portal.example.com:443/api/v1/auth/saml/callback?foo=bar")
    request.query_params = QueryParams("foo=bar")

    result = _prepare_fastapi_request(request)
    assert result["https"] == "on"
    assert result["http_host"] == "portal.example.com"
    assert result["server_port"] == "443"
    assert result["get_data"] == {"foo": "bar"}


def test_prepare_fastapi_request_http():
    """Verify HTTP request conversion."""
    from unittest.mock import MagicMock
    from starlette.datastructures import URL, QueryParams

    request = MagicMock()
    request.url = URL("http://localhost:8000/api/v1/auth/saml/login")
    request.query_params = QueryParams("")

    result = _prepare_fastapi_request(request)
    assert result["https"] == "off"
    assert result["http_host"] == "localhost"
    assert result["server_port"] == "8000"
