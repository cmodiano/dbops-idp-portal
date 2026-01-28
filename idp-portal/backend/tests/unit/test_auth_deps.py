"""Tests for auth dependencies: SAML and JWT imports, and later auth module tests."""


def test_saml_import():
    """Verify python3-saml is importable."""
    from onelogin.saml2.auth import OneLogin_Saml2_Auth  # noqa: F401
    from onelogin.saml2.utils import OneLogin_Saml2_Utils  # noqa: F401


def test_jose_import():
    """Verify python-jose is importable."""
    from jose import jwt, JWTError  # noqa: F401
