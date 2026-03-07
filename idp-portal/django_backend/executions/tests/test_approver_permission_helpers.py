"""Tests unitaires pour les helpers _check_approver_permission — Story 58.4 AC3."""
from __future__ import annotations

from unittest.mock import MagicMock

from django.test import TestCase

# Ces fonctions seront ajoutées à approval_views.py
from executions.views.approval_views import (
    _get_user_profile_ids,
    _is_user_approver,
    _check_approver_permission,
)


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
    """Tests pour _get_user_profile_ids."""

    def test_returns_id_from_orm_profile(self):
        user = _make_user(profile_id=42, is_approver=True)
        result = _get_user_profile_ids(user)
        self.assertIn(42, result)

    def test_returns_empty_when_no_profile(self):
        user = _make_user()
        result = _get_user_profile_ids(user)
        self.assertEqual(result, set())

    def test_returns_ids_from_m2m_profiles(self):
        p1 = MagicMock()
        p1.id = 1
        p2 = MagicMock()
        p2.id = 2
        user = _make_user(profile_id=None, profiles_m2m=[p1, p2])
        result = _get_user_profile_ids(user)
        self.assertIn(1, result)
        self.assertIn(2, result)

    def test_combines_orm_and_m2m(self):
        p_m2m = MagicMock()
        p_m2m.id = 99
        user = _make_user(profile_id=42, is_approver=True, profiles_m2m=[p_m2m])
        result = _get_user_profile_ids(user)
        self.assertIn(42, result)
        self.assertIn(99, result)


class TestIsUserApprover(TestCase):
    """Tests pour _is_user_approver."""

    def test_returns_true_when_orm_profile_is_approver(self):
        user = _make_user(profile_id=1, is_approver=True)
        self.assertTrue(_is_user_approver(user))

    def test_returns_false_when_orm_profile_not_approver(self):
        user = _make_user(profile_id=1, is_approver=False)
        self.assertFalse(_is_user_approver(user))

    def test_returns_false_when_no_profile(self):
        user = _make_user()
        self.assertFalse(_is_user_approver(user))

    def test_returns_true_when_m2m_profile_is_approver(self):
        p = MagicMock()
        p.is_approver_bool = True
        user = _make_user(profiles_m2m=[p])
        self.assertTrue(_is_user_approver(user))

    def test_returns_false_when_m2m_profile_not_approver(self):
        p = MagicMock()
        p.is_approver_bool = False
        user = _make_user(profiles_m2m=[p])
        self.assertFalse(_is_user_approver(user))


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

    def test_fallback_user_with_is_approver_returns_true(self):
        """Sans approver_profile_ids et user avec is_approver=True → True."""
        user = _make_user(profile_id=1, is_approver=True)
        step_config = {}
        self.assertTrue(_check_approver_permission(user, step_config))

    def test_fallback_user_without_is_approver_returns_false(self):
        """Sans approver_profile_ids et user sans is_approver → False."""
        user = _make_user(profile_id=1, is_approver=False)
        step_config = {}
        self.assertFalse(_check_approver_permission(user, step_config))

    def test_empty_list_triggers_fallback(self):
        """approver_profile_ids=[] → fallback vers is_approver."""
        user = _make_user(profile_id=1, is_approver=True)
        step_config = {'approver_profile_ids': []}
        self.assertTrue(_check_approver_permission(user, step_config))

    def test_null_approver_profile_ids_triggers_fallback(self):
        """approver_profile_ids=null → fallback vers is_approver."""
        user = _make_user(profile_id=1, is_approver=True)
        step_config = {'approver_profile_ids': None}
        self.assertTrue(_check_approver_permission(user, step_config))

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
