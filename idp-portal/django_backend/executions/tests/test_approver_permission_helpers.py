"""Tests unitaires pour les helpers _check_approver_permission — Story 58.4 AC3."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.permissions import get_user_profile_ids
from executions.views.approval_views import _check_approver_permission


def _make_user(profile_id=None, is_approver=False, profiles_m2m=None, ad_groups=None):
    """Helper factory pour créer un user mock."""
    user = MagicMock()
    user.is_authenticated = True

    # Chemin 1 : Profile ORM direct
    if profile_id is not None:
        profile = MagicMock()
        profile.id = profile_id
        profile.is_approver_bool = is_approver
        user.profile = profile
    else:
        user.profile = None

    # Chemin 2 : M2M profiles (désactivé par défaut)
    if profiles_m2m is not None:
        profiles_mock = MagicMock()
        profiles_mock.all.return_value = profiles_m2m
        user.profiles = profiles_mock
    else:
        del user.profiles  # Remove attribute so hasattr returns False

    # Chemin 3 : ad_groups
    if ad_groups is not None:
        user.ad_groups = ad_groups
    else:
        del user.ad_groups

    return user


class TestGetUserProfileIds(TestCase):
    """Tests pour get_user_profile_ids."""

    def test_returns_id_from_orm_profile(self):
        user = _make_user(profile_id=42, is_approver=True)
        result = get_user_profile_ids(user)
        self.assertIn(42, result)

    def test_returns_empty_when_no_profile(self):
        user = _make_user()
        result = get_user_profile_ids(user)
        self.assertEqual(result, set())

    def test_returns_ids_from_m2m_profiles(self):
        p1 = MagicMock()
        p1.id = 1
        p2 = MagicMock()
        p2.id = 2
        user = _make_user(profile_id=None, profiles_m2m=[p1, p2])
        result = get_user_profile_ids(user)
        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_m2m_takes_precedence_over_orm_profile(self):
        """core.permissions uses first-match order: ad_groups > M2M > profile string > profile object.
        When user has both profile and profiles (M2M), M2M wins and only M2M IDs are returned."""
        p_m2m = MagicMock()
        p_m2m.id = 99
        user = _make_user(profile_id=42, is_approver=True, profiles_m2m=[p_m2m])
        result = get_user_profile_ids(user)
        self.assertEqual(result, {99})

    def test_returns_ids_from_ad_groups(self):
        """ad_groups (first in resolution order) → Profile.objects.find_by_ad_groups()."""
        p_ad = MagicMock()
        p_ad.id = 7
        user = _make_user(profile_id=None, ad_groups=['CN=Approvers,OU=Groups'])

        with patch('core.permissions.Profile') as mock_profile:
            mock_profile.objects.find_by_ad_groups.return_value = [p_ad]
            result = get_user_profile_ids(user)

        self.assertIn(7, result)
        mock_profile.objects.find_by_ad_groups.assert_called_once_with(['CN=Approvers,OU=Groups'])

    def test_no_profile_sources_returns_empty(self):
        """User with no profile, no profiles M2M, no ad_groups → empty set."""
        user = _make_user(profile_id=None)
        user.ad_groups = None

        result = get_user_profile_ids(user)

        self.assertEqual(result, set())


class TestCheckApproverPermission(TestCase):
    """Tests pour _check_approver_permission — Story 58.4 AC3."""

    def test_user_with_profile_in_approver_list_returns_true(self):
        """Avec approver_profile_ids=[1,2] et user ayant profil ID 1 → True."""
        user = _make_user(profile_id=1, is_approver=False)
        step_config = {'approver_profile_ids': [1, 2]}
        self.assertTrue(_check_approver_permission(user, step_config))

    def test_user_with_profile_not_in_approver_list_returns_false(self):
        """Avec approver_profile_ids=[1,2] et user ayant profil ID 3 → False."""
        user = _make_user(profile_id=3, is_approver=True)
        step_config = {'approver_profile_ids': [1, 2]}
        self.assertFalse(_check_approver_permission(user, step_config))

    def test_absent_approver_profile_ids_returns_false(self):
        """Story 59.1 SEC-1 : Sans approver_profile_ids → False (fail-secure)."""
        user = _make_user(profile_id=1, is_approver=True)
        step_config = {}
        self.assertFalse(_check_approver_permission(user, step_config))

    def test_fail_secure_no_profile_ids_non_approver_returns_false(self):
        """Story 59.1 SEC-1 : Sans approver_profile_ids et user sans is_approver → False (fail-secure)."""
        user = _make_user(profile_id=1, is_approver=False)
        step_config = {}
        self.assertFalse(_check_approver_permission(user, step_config))

    def test_empty_list_returns_false(self):
        """Story 59.1 SEC-1 : approver_profile_ids=[] → False (fail-secure, plus de fallback)."""
        user = _make_user(profile_id=1, is_approver=True)
        step_config = {'approver_profile_ids': []}
        self.assertFalse(_check_approver_permission(user, step_config))

    def test_null_approver_profile_ids_returns_false(self):
        """Story 59.1 SEC-1 : approver_profile_ids=null → False (fail-secure, plus de fallback)."""
        user = _make_user(profile_id=1, is_approver=True)
        step_config = {'approver_profile_ids': None}
        self.assertFalse(_check_approver_permission(user, step_config))

    def test_user_with_multiple_profiles_one_matches(self):
        """User avec plusieurs profils dont un correspond → True."""
        p1 = MagicMock()
        p1.id = 10
        p1.is_approver_bool = False
        p2 = MagicMock()
        p2.id = 2
        p2.is_approver_bool = False
        user = _make_user(profiles_m2m=[p1, p2])
        step_config = {'approver_profile_ids': [2, 3]}
        self.assertTrue(_check_approver_permission(user, step_config))
