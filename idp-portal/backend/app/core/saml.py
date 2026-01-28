"""SAML 2.0 SP configuration and utilities for python3-saml."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from app.core.config import settings


def _read_cert_file(path: str) -> str:
    """Read a certificate or key file, return empty string if path is empty."""
    if not path:
        return ""
    return Path(path).read_text().strip()


def get_saml_settings() -> dict:
    """Build the python3-saml settings dict from application config."""
    return {
        "strict": True,
        "debug": settings.app_debug,
        "sp": {
            "entityId": settings.saml_sp_entity_id,
            "assertionConsumerService": {
                "url": settings.saml_sp_acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "x509cert": _read_cert_file(settings.saml_sp_cert_path),
            "privateKey": _read_cert_file(settings.saml_sp_key_path),
        },
        "idp": {
            "entityId": settings.saml_idp_entity_id,
            "singleSignOnService": {
                "url": settings.saml_idp_sso_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": {
                "url": settings.saml_idp_slo_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": _read_cert_file(settings.saml_idp_cert_path),
        },
    }


def _prepare_fastapi_request(request: Request) -> dict:
    """Convert a FastAPI Request into the dict format expected by python3-saml."""
    url = request.url
    return {
        "https": "on" if url.scheme == "https" else "off",
        "http_host": url.hostname or "localhost",
        "server_port": str(url.port or (443 if url.scheme == "https" else 80)),
        "script_name": str(url.path),
        "get_data": dict(request.query_params),
        "post_data": {},  # POST data must be passed separately after form parsing
    }


def create_saml_auth(request: Request, post_data: dict | None = None) -> OneLogin_Saml2_Auth:
    """Create a OneLogin_Saml2_Auth instance from a FastAPI request."""
    req = _prepare_fastapi_request(request)
    if post_data:
        req["post_data"] = post_data
    return OneLogin_Saml2_Auth(req, get_saml_settings())
