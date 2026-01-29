"""Unit test fixtures. Story 2.12: default profile resolution so auth-dependent tests pass without DB."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.profile import ProfileResponse, CumulativePermissionsResponse


@pytest.fixture(autouse=True)
def mock_profile_resolution_for_auth(request):
    """Mock profile_repository.find_by_ad_groups and rbac_service.get_cumulative_permissions_cached (2.12).

    Any test that uses get_current_user (admin, catalog, profiles API) gets a default profile
    and cumulative permissions. Skipped for test_profile_repository (tests real find_by_ad_groups).
    """
    if "test_profile_repository" in request.module.__name__:
        yield
        return
    default_profile = ProfileResponse(
        id=1,
        name="DBOPS",
        description="",
        ad_group="dbops",
        is_admin=True,
        is_auditor=False,
        created_at=datetime(2026, 1, 28),
        updated_at=datetime(2026, 1, 28),
    )
    default_permissions = CumulativePermissionsResponse(
        actions_type="all",
        targets_type="all",
    )
    with (
        patch(
            "app.api.deps.profile_repository.find_by_ad_groups",
            new_callable=AsyncMock,
            return_value=[default_profile],
        ),
        patch(
            "app.api.deps.rbac_service.get_cumulative_permissions_cached",
            new_callable=AsyncMock,
            return_value=default_permissions,
        ),
    ):
        yield
