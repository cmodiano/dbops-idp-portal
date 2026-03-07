"""
Centralized guard for AUTH_DEV_BYPASS — Story 59.6 SEC-6.

Dev bypass (mock token, SAML skip) is only allowed when DEBUG=True.
When DEBUG=False, dev bypass must never create users or mint tokens regardless
of entrypoint (authentication.py mock token, saml.py GET /auth/saml/login).
"""

from django.conf import settings


def is_dev_bypass_allowed() -> bool:
    """Return True only when AUTH_DEV_BYPASS and DEBUG are both True.

    When DEBUG=False (production), returns False so dev bypass is never active.
    """
    return bool(
        getattr(settings, "AUTH_DEV_BYPASS", False)
        and getattr(settings, "DEBUG", False)
    )
