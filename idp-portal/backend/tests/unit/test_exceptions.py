"""Tests for exception hierarchy (AC #8)."""

from app.core.exceptions import (
    IdpError,
    UnauthorizedError,
    NotFoundError,
    ForbiddenError,
    PlatformError,
    VaultError,
    ServiceNowError,
)


def test_idp_error_base():
    err = IdpError(500, "INTERNAL", "something broke", {"key": "val"})
    assert err.status_code == 500
    assert err.code == "INTERNAL"
    assert err.message == "something broke"
    assert err.details == {"key": "val"}


def test_idp_error_default_details():
    err = IdpError(500, "INTERNAL", "msg")
    assert err.details == {}


def test_unauthorized_error():
    err = UnauthorizedError("INVALID_TOKEN", "Token invalid")
    assert err.status_code == 401
    assert isinstance(err, IdpError)


def test_not_found_error():
    err = NotFoundError("USER_NOT_FOUND", "User not found")
    assert err.status_code == 404
    assert isinstance(err, IdpError)


def test_forbidden_error():
    err = ForbiddenError("ACCESS_DENIED", "Forbidden")
    assert err.status_code == 403
    assert isinstance(err, IdpError)


def test_platform_error():
    err = PlatformError("AAP_UNREACHABLE", "AAP down")
    assert err.status_code == 502
    assert isinstance(err, IdpError)


def test_vault_error():
    err = VaultError("VAULT_TIMEOUT", "Vault timeout")
    assert err.status_code == 502
    assert isinstance(err, IdpError)


def test_servicenow_error():
    err = ServiceNowError("SNOW_ERROR", "ServiceNow failed")
    assert err.status_code == 502
    assert isinstance(err, IdpError)
