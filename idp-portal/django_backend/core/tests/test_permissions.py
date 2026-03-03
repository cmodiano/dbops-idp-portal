"""
Unit tests for core/permissions.py — AdminProfilePermission + IsAdminUser.

Backward-compat aliases: DBOPSProfilePermission = AdminProfilePermission, IsDBAOrDBOPS = IsAdminUser.

Story 22.1: CRIT-1 fix — verify Profile.objects.find_by_ad_groups() is used
instead of the non-existent service.get_profiles_by_ad_groups().

Story 26.8: IsAdminUser permission — replaces fragile _is_dba_or_dbops() pattern.
Story 56.4: Renaming DBOPSProfilePermission → AdminProfilePermission, IsDBAOrDBOPS → IsAdminUser.
           M2M and ad_groups paths now check Profile.is_admin_bool instead of profile name.
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
        """AC#4: User with admin AD group gets access via find_by_ad_groups (is_admin_bool=True)."""
        user = _make_user(ad_groups=["GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        mock_profile = MagicMock()
        mock_profile.name = "DBOPS"
        mock_profile.is_admin_bool = True  # Story 56.4: access granted via is_admin_bool, not name

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
        mock_profile.is_admin_bool = False  # Story 56.4: now checks is_admin_bool, not name

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
        mock_profile.is_admin_bool = True  # Story 56.4: explicit is_admin_bool check

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

    def test_dbops_permission_multiple_profiles_one_admin(self):
        """User with multiple profiles, one with is_admin=True, gets access."""
        user = _make_user(ad_groups=["GRP-IDP-VIEWER", "GRP-IDP-DBOPS"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        viewer = MagicMock()
        viewer.name = "VIEWER"
        viewer.is_admin_bool = False  # Story 56.4: non-admin profile must not grant access
        dbops = MagicMock()
        dbops.name = "DBOPS"
        dbops.is_admin_bool = True  # Story 56.4: admin flag grants access

        with patch(FIND_BY_AD_GROUPS, return_value=[viewer, dbops]):
            result = permission.has_permission(request, MagicMock())

        assert result is True

    def test_dbops_permission_ad_groups_is_admin_bool_true_grants_access(self):
        """Story 56.4: AD groups path grants access based on is_admin_bool, not profile name."""
        user = _make_user(ad_groups=["GRP-IDP-CUSTOM"])
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        mock_profile = MagicMock()
        mock_profile.name = "CUSTOM_ADMIN"  # Any name — only is_admin_bool matters
        mock_profile.is_admin_bool = True

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
        """User gets access via profiles M2M relation (is_admin_bool=True)."""
        profile_obj = MagicMock()
        profile_obj.name = "dba"
        profile_obj.is_admin_bool = True  # Story 56.4: M2M path checks is_admin_bool, not name
        profiles_qs = MagicMock()
        profiles_qs.all.return_value = [profile_obj]

        user = _make_user(profile=None, profiles=profiles_qs)
        request = _make_request(user)
        assert IsDBAOrDBOPS().has_permission(request, None) is True

    def test_has_permission_via_ad_groups(self):
        """User gets access via AD groups → Profile resolution (is_admin_bool=True)."""
        user = _make_user(profile=None, ad_groups=['AD_DBOPS_GROUP'])
        request = _make_request(user)

        mock_profile = MagicMock()
        mock_profile.name = "dbops"
        mock_profile.is_admin_bool = True  # Story 56.4: ad_groups path checks is_admin_bool, not name
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


# ============================================================================
# is_admin_user — missing branches (coverage story 55-3)
# ============================================================================

@pytest.mark.unit
class TestIsAdminUserMissingBranches:
    """Cover branches in is_admin_user() not yet exercised."""

    def test_ad_groups_non_list_normalized_to_empty(self):
        """Branch: ad_groups is not a list → normalized to [] (line 46)."""
        from core.permissions import is_admin_user
        user = _make_user(ad_groups="not-a-list")

        with patch(FIND_BY_AD_GROUPS, return_value=[]) as mock_find:
            result = is_admin_user(user)

        assert result is False
        mock_find.assert_called_once_with([])


@pytest.mark.unit
class TestDBOPSProfilePermissionMissingBranches:
    """Cover branches in DBOPSProfilePermission not yet exercised."""

    def test_profile_object_with_is_admin_bool(self):
        """Branch: profile is an ORM object with is_admin_bool=True (Story 56.4 path 1)."""
        profile_obj = MagicMock()
        profile_obj.name = "dbops"
        profile_obj.is_admin_bool = True  # Story 56.4: ORM object path checks is_admin_bool
        user = _make_user(profile=profile_obj)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        result = permission.has_permission(request, MagicMock())

        assert result is True

    def test_profile_object_with_is_admin_bool_false_denied(self):
        """Branch: profile ORM object with is_admin_bool=False is denied."""
        profile_obj = MagicMock()
        profile_obj.name = "dbops"
        profile_obj.is_admin_bool = False  # Even if name is 'dbops', is_admin_bool=False denies
        user = _make_user(profile=profile_obj)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        result = permission.has_permission(request, MagicMock())

        assert result is False

    def test_profiles_m2m_admin(self):
        """Branch: user.profiles M2M has a profile with is_admin_bool=True (Story 56.4 path 2)."""
        dbops_profile = MagicMock()
        dbops_profile.name = "dbops"
        dbops_profile.is_admin_bool = True  # Story 56.4: M2M path checks is_admin_bool, not name
        profiles_qs = MagicMock()
        profiles_qs.all.return_value = [dbops_profile]

        user = _make_user(profiles=profiles_qs)
        request = _make_request(user)
        permission = DBOPSProfilePermission()

        result = permission.has_permission(request, MagicMock())

        assert result is True


# ============================================================================
# _get_admin_profile_names — Story 56.4 (AC4)
# ============================================================================

@pytest.mark.unit
class TestGetAdminProfileNames:
    """Tests for _get_admin_profile_names() helper (Story 56.4 AC4)."""

    def test_returns_settings_value_when_defined(self):
        """AC4: Returns ADMIN_PROFILE_NAMES from settings when defined."""
        from core.permissions import _get_admin_profile_names
        custom = {'automation', 'operator'}
        with override_settings(ADMIN_PROFILE_NAMES=custom):
            result = _get_admin_profile_names()
        assert result == {'automation', 'operator'}

    def test_returns_default_fallback_when_not_defined(self):
        """AC4: Returns default set when ADMIN_PROFILE_NAMES is not defined in settings."""
        from core.permissions import _get_admin_profile_names
        from django.conf import settings as django_settings
        # Temporarily remove the setting to test fallback
        original = django_settings.ADMIN_PROFILE_NAMES
        del django_settings.ADMIN_PROFILE_NAMES
        try:
            result = _get_admin_profile_names()
        finally:
            django_settings.ADMIN_PROFILE_NAMES = original
        assert result == {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}

    def test_default_set_contains_all_legacy_profiles(self):
        """AC4: Default set includes all legacy admin profiles for backward compat."""
        from core.permissions import _get_admin_profile_names
        result = _get_admin_profile_names()
        assert 'dbops' in result
        assert 'dba' in result
        assert 'dba_applicatif' in result
        assert 'dba_infrastructure' in result


# ============================================================================
# ADMIN_PROFILE_NAMES custom — Story 56.4 (AC4 end-to-end)
# ============================================================================

@pytest.mark.unit
class TestAdminProfileNamesCustom:
    """AC4: SAML string path uses ADMIN_PROFILE_NAMES (configurable)."""

    def test_is_admin_user_accepts_custom_profile_name(self):
        """AC4: is_admin_user() accepts new admin profile name from custom ADMIN_PROFILE_NAMES."""
        from core.permissions import is_admin_user
        user = _make_user(profile="automation")
        with override_settings(ADMIN_PROFILE_NAMES={'automation', 'operator'}):
            result = is_admin_user(user)
        assert result is True

    def test_is_admin_user_rejects_old_profile_when_not_in_custom_set(self):
        """AC4: is_admin_user() rejects 'dbops' when ADMIN_PROFILE_NAMES is overridden."""
        from core.permissions import is_admin_user
        user = _make_user(profile="dbops")
        with override_settings(ADMIN_PROFILE_NAMES={'automation', 'operator'}):
            result = is_admin_user(user)
        assert result is False

    def test_admin_profile_permission_accepts_custom_profile_name(self):
        """AC4: AdminProfilePermission accepts new admin profile via custom ADMIN_PROFILE_NAMES."""
        user = _make_user(profile="operator")
        request = _make_request(user)
        permission = DBOPSProfilePermission()
        with override_settings(ADMIN_PROFILE_NAMES={'automation', 'operator'}):
            result = permission.has_permission(request, MagicMock())
        assert result is True

    def test_admin_profile_permission_case_insensitive_saml_string(self):
        """AC4 + AC1: SAML string profile matching is case-insensitive."""
        user = _make_user(profile="AUTOMATION")
        request = _make_request(user)
        permission = DBOPSProfilePermission()
        with override_settings(ADMIN_PROFILE_NAMES={'automation', 'operator'}):
            result = permission.has_permission(request, MagicMock())
        assert result is True


@pytest.mark.unit
class TestOptionalUserPermission:
    """Cover OptionalUserPermission.has_permission() (line 224)."""

    def test_allows_any_user(self):
        """OptionalUserPermission always returns True."""
        from core.permissions import OptionalUserPermission
        user = _make_user(is_authenticated=False)
        request = _make_request(user)
        permission = OptionalUserPermission()

        result = permission.has_permission(request, MagicMock())

        assert result is True

    def test_allows_authenticated_user(self):
        """OptionalUserPermission returns True for authenticated users too."""
        from core.permissions import OptionalUserPermission
        user = _make_user(is_authenticated=True)
        request = _make_request(user)
        permission = OptionalUserPermission()

        assert permission.has_permission(request, MagicMock()) is True
