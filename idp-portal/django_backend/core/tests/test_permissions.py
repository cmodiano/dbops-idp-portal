"""
Unit tests for core/permissions.py — DBOPSProfilePermission + IsDBAOrDBOPS.

Story 22.1: CRIT-1 fix — verify Profile.objects.find_by_ad_groups() is used
instead of the non-existent service.get_profiles_by_ad_groups().

Story 26.8: IsDBAOrDBOPS permission — replaces fragile _is_dba_or_dbops() pattern.
"""

import pytest
from unittest.mock import MagicMock, patch
from django.db import OperationalError
from django.test import override_settings

from core.permissions import DBOPSProfilePermission, IsDBAOrDBOPS


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

    def test_superuser_without_profile_denied_in_production(self):
        """Story 22.2 AC#5: Superuser without DBOPS profile is denied when
        ALLOW_SUPERUSER_FALLBACK=False (production default)."""
        user = _make_user(is_superuser=True)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with override_settings(ALLOW_SUPERUSER_FALLBACK=False):
            result = permission.has_permission(request, MagicMock())

        assert result is False

    def test_superuser_without_profile_allowed_in_dev(self):
        """Story 22.2 AC#5: Superuser without DBOPS profile is allowed when
        ALLOW_SUPERUSER_FALLBACK=True (dev mode)."""
        user = _make_user(is_superuser=True)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with override_settings(ALLOW_SUPERUSER_FALLBACK=True):
            result = permission.has_permission(request, MagicMock())

        assert result is True

    def test_superuser_with_profile_always_allowed(self):
        """Story 22.2 AC#5: Superuser with DBOPS profile is always allowed,
        regardless of ALLOW_SUPERUSER_FALLBACK setting."""
        user = _make_user(is_superuser=True, profile="dbops")
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        # Allowed with fallback disabled
        with override_settings(ALLOW_SUPERUSER_FALLBACK=False):
            result = permission.has_permission(request, MagicMock())
        assert result is True

        # Also allowed with fallback enabled
        with override_settings(ALLOW_SUPERUSER_FALLBACK=True):
            result = permission.has_permission(request, MagicMock())
        assert result is True

    def test_superuser_fallback_logs_warning(self):
        """Story 22.2 AC#5: Superuser fallback logs WARNING (not INFO) when used."""
        user = _make_user(is_superuser=True)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        with override_settings(ALLOW_SUPERUSER_FALLBACK=True):
            with patch("core.permissions.logger") as mock_logger:
                result = permission.has_permission(request, MagicMock())

        assert result is True
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert call_args[0][0] == "security_rbac_bypass_superuser_fallback"

    def test_superuser_fallback_logs_debug_mode(self):
        """Story 22.2 HIGH-5: Verify debug_mode field in log (True in dev, False in prod)."""
        user = _make_user(is_superuser=True)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        # Test dev mode (DEBUG=True)
        with override_settings(ALLOW_SUPERUSER_FALLBACK=True, DEBUG=True):
            with patch("core.permissions.logger") as mock_logger:
                result = permission.has_permission(request, MagicMock())

        assert result is True
        call_kwargs = mock_logger.warning.call_args[1]
        assert call_kwargs['debug_mode'] is True

        # Test production mode (DEBUG=False)
        with override_settings(ALLOW_SUPERUSER_FALLBACK=True, DEBUG=False):
            with patch("core.permissions.logger") as mock_logger:
                result = permission.has_permission(request, MagicMock())

        assert result is True
        call_kwargs = mock_logger.warning.call_args[1]
        assert call_kwargs['debug_mode'] is False

    def test_default_superuser_fallback_disabled_in_test_settings(self):
        """Story 22.2 HIGH-3: Verify ALLOW_SUPERUSER_FALLBACK=False in test_settings.py by default."""
        from django.conf import settings
        # NO @override_settings — verify the actual default from test_settings.py
        assert settings.ALLOW_SUPERUSER_FALLBACK is False, (
            "test_settings.py MUST have ALLOW_SUPERUSER_FALLBACK = False by default (fail-secure)"
        )

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


# ============================================================================
# IsDBAOrDBOPS (Story 26.8)
# ============================================================================

@pytest.mark.unit
class TestIsDBAOrDBOPSHasPermission:
    """Tests for IsDBAOrDBOPS.has_permission() — view-level permission."""

    def test_has_permission_dbops(self):
        """User with profile='dbops' gets access."""
        user = _make_user(profile="dbops")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is True

    def test_has_permission_dba(self):
        """User with profile='dba' gets access."""
        user = _make_user(profile="dba")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is True

    def test_has_permission_dba_applicatif(self):
        """User with profile='dba_applicatif' gets access."""
        user = _make_user(profile="dba_applicatif")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is True

    def test_has_permission_dba_infrastructure(self):
        """User with profile='dba_infrastructure' gets access."""
        user = _make_user(profile="dba_infrastructure")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is True

    def test_has_permission_business_denied(self):
        """User with profile='business' is denied."""
        user = _make_user(profile="business")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is False

    def test_has_permission_dba_readonly_denied(self):
        """CRITICAL: dba_readonly must NOT be accepted (was the bug with startswith)."""
        user = _make_user(profile="dba_readonly")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is False

    def test_has_permission_case_insensitive(self):
        """Profile matching is case-insensitive."""
        user = _make_user(profile="DBOPS")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is True

        user2 = _make_user(profile="DBA_Applicatif")
        request2 = _make_request(user2)
        assert IsDBAOrDBOPS().has_permission(request2, None) is True

    def test_has_permission_via_profiles_m2m(self):
        """User gets access via profiles M2M relation."""
        profile_obj = MagicMock()
        profile_obj.name = "dba"
        profiles_qs = MagicMock()
        profiles_qs.all.return_value = [profile_obj]

        user = _make_user(profile=None, profiles=profiles_qs)
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is True

    def test_has_permission_via_ad_groups(self):
        """User gets access via AD groups → Profile resolution."""
        user = _make_user(profile=None, ad_groups=['AD_DBOPS_GROUP'])
        request = _make_request(user)

        mock_profile = MagicMock()
        mock_profile.name = "dbops"
        with patch(FIND_BY_AD_GROUPS, return_value=[mock_profile]):
            assert IsDBAOrDBOPS().has_permission(request, None) is True

    def test_has_permission_unauthenticated(self):
        """Unauthenticated user is denied."""
        user = _make_user(is_authenticated=False)
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is False

    def test_has_permission_none_profile(self):
        """User with no profile/profiles/ad_groups is denied."""
        user = _make_user(profile=None, ad_groups=[])
        request = _make_request(user)
        with patch(FIND_BY_AD_GROUPS, return_value=[]):
            assert IsDBAOrDBOPS().has_permission(request, None) is False

    def test_has_permission_whitespace_profile(self):
        """User with whitespace-only profile is denied (empty string after strip by getattr)."""
        user = _make_user(profile="   ")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is False

    def test_has_permission_empty_ad_groups(self):
        """User with empty ad_groups list is denied."""
        user = _make_user(profile=None, ad_groups=[])
        request = _make_request(user)
        with patch(FIND_BY_AD_GROUPS, return_value=[]):
            assert IsDBAOrDBOPS().has_permission(request, None) is False

    def test_has_permission_db_error_denies_access(self):
        """DB error during ad_groups resolution denies access (safe denial)."""
        user = _make_user(profile=None, ad_groups=["GRP-DBA"])
        request = _make_request(user)
        with patch(FIND_BY_AD_GROUPS, side_effect=OperationalError("DB unavailable")):
            assert IsDBAOrDBOPS().has_permission(request, None) is False

    def test_has_permission_database_profile(self):
        """CRITICAL: 'database' profile must NOT be accepted (was possible with startswith('dba'))."""
        user = _make_user(profile="database")
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is False


@pytest.mark.unit
class TestIsDBAOrDBOPSHasObjectPermission:
    """Tests for IsDBAOrDBOPS.has_object_permission() — object-level permission."""

    def test_has_object_permission_admin(self):
        """Admin (DBA/DBOPS profile) can access any object."""
        user = _make_user(profile="dbops", id=1)
        request = _make_request(user)
        obj = MagicMock()
        obj.user_id = 999  # Different owner
        assert IsDBAOrDBOPS().has_object_permission(request, None, obj) is True

    def test_has_object_permission_owner(self):
        """Owner can access their own object."""
        user = _make_user(profile="business", id=42)
        request = _make_request(user)
        obj = MagicMock()
        obj.user_id = 42  # Same owner
        assert IsDBAOrDBOPS().has_object_permission(request, None, obj) is True

    def test_has_object_permission_denied(self):
        """Non-owner non-admin is denied."""
        user = _make_user(profile="business", id=1)
        request = _make_request(user)
        obj = MagicMock()
        obj.user_id = 999  # Different owner
        assert IsDBAOrDBOPS().has_object_permission(request, None, obj) is False

    def test_has_object_permission_owner_via_user_attr(self):
        """Owner check falls back to obj.user.id when obj.user_id is None."""
        user = _make_user(profile="business", id=42)
        request = _make_request(user)
        obj = MagicMock(spec=[])
        obj.user_id = None
        obj_user = MagicMock()
        obj_user.id = 42
        obj.user = obj_user
        assert IsDBAOrDBOPS().has_object_permission(request, None, obj) is True

    @pytest.mark.parametrize("profile", ["dbops", "dba", "dba_applicatif", "dba_infrastructure"])
    def test_has_object_permission_each_admin_profile(self, profile):
        """Story 26.12 AC#3: Each admin profile can access any object (non-owner)."""
        user = _make_user(profile=profile, id=1)
        request = _make_request(user)
        obj = MagicMock()
        obj.user_id = 999  # Different owner
        assert IsDBAOrDBOPS().has_object_permission(request, None, obj) is True

    @pytest.mark.parametrize("profile", ["business", "viewer", "dba_readonly"])
    def test_has_object_permission_non_owner_non_admin_profiles(self, profile):
        """Story 26.12 AC#3: Non-admin profiles cannot access other users' objects."""
        user = _make_user(profile=profile, id=1)
        request = _make_request(user)
        obj = MagicMock()
        obj.user_id = 999
        assert IsDBAOrDBOPS().has_object_permission(request, None, obj) is False

    def test_has_object_permission_no_user_id_or_user(self):
        """Edge case: Object with neither user_id nor user attribute is denied."""
        user = _make_user(profile="business", id=42)
        request = _make_request(user)
        obj = MagicMock(spec=[])  # No attributes at all
        assert IsDBAOrDBOPS().has_object_permission(request, None, obj) is False
