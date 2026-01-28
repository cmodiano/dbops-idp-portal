"""Tests for Pydantic models."""

from app.models.common import ErrorDetail, ErrorResponse, HealthStatus, PaginationMeta
from app.models.auth import UserProfile, TokenPayload


def test_error_detail():
    err = ErrorDetail(code="NOT_FOUND", message="Not found")
    assert err.code == "NOT_FOUND"
    assert err.details is None


def test_error_detail_with_details():
    err = ErrorDetail(code="X", message="Y", details={"id": 1})
    assert err.details == {"id": 1}


def test_error_response():
    resp = ErrorResponse(error=ErrorDetail(code="X", message="Y"))
    assert resp.error.code == "X"


def test_health_status():
    hs = HealthStatus(status="healthy", oracle="connected")
    assert hs.status == "healthy"


def test_pagination_meta():
    pm = PaginationMeta(page=1, page_size=20, total=100, total_pages=5)
    assert pm.total_pages == 5


def test_user_profile():
    up = UserProfile(id=1, username="marc", display_name="Marc D.", profile="dba_applicatif")
    assert up.profile == "dba_applicatif"


def test_user_profile_optional_display_name():
    up = UserProfile(id=1, username="marc", profile="dbops")
    assert up.display_name is None


def test_token_payload():
    tp = TokenPayload(sub="12345", username="marc", profile="dba_applicatif", exp=1700000000)
    assert tp.sub == "12345"
