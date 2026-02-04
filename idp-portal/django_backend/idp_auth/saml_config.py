"""
SAML 2.0 SP configuration for python3-saml.
Mirrors FastAPI implementation for contract parity.
"""

from pathlib import Path
from django.conf import settings


def _read_cert_file(path: str) -> str:
    """Read a certificate or key file, return empty string if path is empty.

    Handles FileNotFoundError gracefully - if cert file doesn't exist,
    returns empty string (for dev environments without certs).
    """
    if not path:
        return ""
    try:
        return Path(path).read_text().strip()
    except FileNotFoundError:
        # Cert file not found - log warning for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"SAML certificate file not found: {path} (dev mode?)")
        return ""


def get_saml_settings() -> dict:
    """Build the python3-saml settings dict from Django settings.

    Returns:
        dict: python3-saml configuration dictionary
    """
    return {
        "strict": True,
        "debug": settings.DEBUG,
        "sp": {
            "entityId": settings.SAML_SP_ENTITY_ID,
            "assertionConsumerService": {
                "url": settings.SAML_SP_ACS_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "x509cert": _read_cert_file(settings.SAML_SP_CERT_PATH),
            "privateKey": _read_cert_file(settings.SAML_SP_KEY_PATH),
        },
        "idp": {
            "entityId": settings.SAML_IDP_ENTITY_ID,
            "singleSignOnService": {
                "url": settings.SAML_IDP_SSO_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "singleLogoutService": {
                "url": settings.SAML_IDP_SLO_URL,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": _read_cert_file(settings.SAML_IDP_CERT_PATH),
        },
    }
