"""
Unit tests for core/permissions.py — DBOPSProfilePermission.

Story 22.1: CRIT-1 fix — verify Profile.objects.find_by_ad_groups() is used
instead of the non-existent service.get_profiles_by_ad_groups().
"""

import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError

from core.permissions import DBOPSProfilePermission


def _make_user(**kwargs):
    """Create a mock user with specified attributes."""
    user = MagicMock()
    user.is_authenticated = kwargs.get("is_authenticated", True)
    user.id = kwargs.get("id", 1)
    user.is_superuser = kwargs.get("is_superuser", False)

    # Remove default mock attributes so hasattr checks work correctly
    if "profile" not in kwargs:
        del user.profile
    else:
        user.profile = kwargs["profile"]

    if "profiles" not in kwargs:
        del user.profiles
    else:
        user.profiles = kwargs["profiles"]

    if "ad_groups" not in kwargs:
        del user.ad_groups
    else:
        user.ad_groups = kwargs["ad_groups"]

    return user


def _make_request(user):
    """Create a mock request with given user."""
    request = MagicMock()
    request.user = user
    return request


# Patch target: the Profile model imported inside has_permission (lazy import)
FIND_BY_AD_GROUPS = "profiles.models.ProfileManager.find_by_ad_groups"


@pytest.mark.unit
class TestDBOPSProfilePermissionAdGroups:
    """Tests for AD group-based profile resolution (Story 22.1 CRIT-1)."""

    def test_dbops_permission_with_ad_groups(self):
        """AC#4: User with DBOPS AD group gets access via find_by_ad_groups."""
        user = _make_user(ad_groups=["GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        mock_profile = MagicMock()
        mock_profile.name = "DBOPS"

        with patch(FIND_BY_AD_GROUPS, return_value=[mock_profile]) as mock_find:
            result = permission.has_permission(request, MagicMock())

        assert result is True
        mock_find.assert_called_once_with(["GRP-IDP-DBOPS"])

    def test_dbops_permission_no_matching_profile(self):
        """AC#4: User with non-DBOPS AD group is denied."""
        user = _make_user(ad_groups=["GRP-IDP-VIEWER"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        mock_profile = MagicMock()
        mock_profile.name = "VIEWER"

        with patch(FIND_BY_AD_GROUPS, return_value=[mock_profile]):
            result = permission.has_permission(request, MagicMock())

        assert result is False

    def test_dbops_permission_empty_ad_groups(self):
        """AC#4: User with empty ad_groups list is denied."""
        user = _make_user(ad_groups=[])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with patch(FIND_BY_AD_GROUPS, return_value=[]):
            result = permission.has_permission(request, MagicMock())

        assert result is False

    def test_dbops_permission_calls_find_by_ad_groups_not_service(self):
        """AC#1: Verify Profile.objects.find_by_ad_groups is called, NOT ProfileService."""
        user = _make_user(ad_groups=["GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        mock_profile = MagicMock()
        mock_profile.name = "DBOPS"

        with patch(FIND_BY_AD_GROUPS, return_value=[mock_profile]) as mock_find:
            permission.has_permission(request, MagicMock())

        mock_find.assert_called_once()

    def test_dbops_permission_db_error_denies_access(self):
        """AC#2: DatabaseError is caught and access is denied (not masked as AttributeError)."""
        user = _make_user(ad_groups=["GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with patch(FIND_BY_AD_GROUPS, side_effect=OperationalError("DB unavailable")):
            result = permission.has_permission(request, MagicMock())

        # Access denied when DB is unavailable (safe denial)
        assert result is False

    def test_dbops_permission_attribute_error_not_caught(self):
        """AC#2: AttributeError is NOT masked — it propagates."""
        user = _make_user(ad_groups=["GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with patch(FIND_BY_AD_GROUPS, side_effect=AttributeError("bug in code")):
            with pytest.raises(AttributeError, match="bug in code"):
                permission.has_permission(request, MagicMock())

    def test_dbops_permission_multiple_profiles_one_dbops(self):
        """User with multiple profiles, one being DBOPS, gets access."""
        user = _make_user(ad_groups=["GRP-IDP-VIEWER", "GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        viewer = MagicMock()
        viewer.name = "VIEWER"
        dbops = MagicMock()
        dbops.name = "DBOPS"

        with patch(FIND_BY_AD_GROUPS, return_value=[viewer, dbops]):
            result = permission.has_permission(request, MagicMock())

        assert result is True

    def test_dbops_permission_case_insensitive_name(self):
        """DBOPS name matching is case-insensitive."""
        user = _make_user(ad_groups=["GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        mock_profile = MagicMock()
        mock_profile.name = "Dbops"  # Mixed case

        with patch(FIND_BY_AD_GROUPS, return_value=[mock_profile]):
            result = permission.has_permission(request, MagicMock())

        assert result is True


@pytest.mark.unit
class TestDBOPSProfilePermissionBasic:
    """Tests for basic permission scenarios."""

    def test_unauthenticated_user_denied(self):
        """Unauthenticated user is denied."""
        user = _make_user(is_authenticated=False)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        result = permission.has_permission(request, MagicMock())

        assert result is False

    def test_user_with_dbops_profile_string(self):
        """User with profile='dbops' string gets access."""
        user = _make_user(profile="dbops")
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        result = permission.has_permission(request, MagicMock())

        assert result is True

    def test_superuser_fallback_when_no_profile_match(self):
        """Superuser gets access as fallback when no profile matches."""
        user = _make_user(is_superuser=True)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        result = permission.has_permission(request, MagicMock())

        assert result is True

    def test_non_superuser_no_profile_denied(self):
        """Non-superuser without any profile is denied."""
        user = _make_user(is_superuser=False)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        result = permission.has_permission(request, MagicMock())

        assert result is False

    def test_ad_groups_non_list_treated_as_empty(self):
        """If ad_groups is not a list, it's treated as empty."""
        user = _make_user(ad_groups="not-a-list")
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with patch(FIND_BY_AD_GROUPS, return_value=[]) as mock_find:
            result = permission.has_permission(request, MagicMock())

        assert result is False
        mock_find.assert_called_once_with([])

    def test_ad_groups_none_treated_as_empty(self):
        """If ad_groups is None, it's treated as empty list."""
        user = _make_user(ad_groups=None)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with patch(FIND_BY_AD_GROUPS, return_value=[]) as mock_find:
            result = permission.has_permission(request, MagicMock())

        assert result is False
        mock_find.assert_called_once_with([])
