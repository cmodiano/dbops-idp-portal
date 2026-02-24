"""
Tests for executions/utils/rbac_helpers.py — get_allowed_action_ids_for_user.
Story 39.4 — Tâche 4.

Pattern d'import lazy : le code fait `import executions.utils as _eu` → patcher via
`patch('executions.utils.ProfileService')`.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase

from executions.utils.rbac_helpers import get_allowed_action_ids_for_user


# ============================================================================
# Helper factory
# ============================================================================

def _make_user(authenticated=True, user_id=1):
    user = MagicMock()
    user.is_authenticated = authenticated
    user.id = user_id
    return user


# ============================================================================
# Tâche 4.1 — user=None → set()
# ============================================================================

class TestGetAllowedActionIdsForUser(TestCase):
    """Tests for get_allowed_action_ids_for_user — all branches."""

    def test_none_user_returns_empty_set(self):
        """4.1: user=None → empty set()."""
        result = get_allowed_action_ids_for_user(None)
        self.assertEqual(result, set())

    # ----------------------------------------------------------------
    # Tâche 4.2 — user.is_authenticated=False → set()
    # ----------------------------------------------------------------
    def test_unauthenticated_user_returns_empty_set(self):
        """4.2: user.is_authenticated=False → empty set()."""
        user = _make_user(authenticated=False)
        result = get_allowed_action_ids_for_user(user)
        self.assertEqual(result, set())

    # ----------------------------------------------------------------
    # Tâche 4.3 — ProfileService lève exception → log warning + set()
    # ----------------------------------------------------------------
    def test_profile_service_exception_returns_empty_set(self):
        """4.3: ProfileService.get_cumulative_permissions raises → warning + set()."""
        user = _make_user()

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.side_effect = Exception("DB down")
                result = get_allowed_action_ids_for_user(user)

        self.assertEqual(result, set())

    # ----------------------------------------------------------------
    # Tâche 4.4 — permissions=None → set()
    # ----------------------------------------------------------------
    def test_permissions_none_returns_empty_set(self):
        """4.4: get_cumulative_permissions returns None → set()."""
        user = _make_user()

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.return_value = None
                result = get_allowed_action_ids_for_user(user)

        self.assertEqual(result, set())

    # ----------------------------------------------------------------
    # Tâche 4.5 — permissions sans action_permissions → set()
    # ----------------------------------------------------------------
    def test_permissions_without_action_permissions_returns_empty_set(self):
        """4.5: permissions without action_permissions key → set()."""
        user = _make_user()

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.return_value = {
                    'other_key': 'value'
                }
                result = get_allowed_action_ids_for_user(user)

        self.assertEqual(result, set())

    # ----------------------------------------------------------------
    # Tâche 4.6 — actions_type == 'all' → None
    # ----------------------------------------------------------------
    def test_actions_type_all_returns_none(self):
        """4.6: actions_type='all' → None (full access, no filtering)."""
        user = _make_user()
        permissions = {
            'action_permissions': [{'actions_type': 'all'}]
        }

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.return_value = permissions
                result = get_allowed_action_ids_for_user(user)

        self.assertIsNone(result)

    # ----------------------------------------------------------------
    # Tâche 4.7 — action_ids seulement (sans tag_patterns) → set des IDs
    # ----------------------------------------------------------------
    def test_action_ids_only_returns_set_of_ids(self):
        """4.7: action_ids only (no tag_patterns) → set of IDs."""
        user = _make_user()
        permissions = {
            'action_permissions': [
                {'actions_type': 'restricted', 'action_ids': [1, 2, 3], 'tag_patterns': []}
            ]
        }

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.return_value = permissions
                result = get_allowed_action_ids_for_user(user)

        self.assertEqual(result, {1, 2, 3})

    # ----------------------------------------------------------------
    # Tâche 4.8 — tag_patterns → résolution via ActionTag + union avec action_ids
    # ----------------------------------------------------------------
    def test_tag_patterns_resolved_to_action_ids(self):
        """4.8: tag_patterns → resolved via ActionTag.objects.filter(), unioned with action_ids."""
        from tests.factories import ActionFactory, TagFactory, ActionTagFactory
        action1 = ActionFactory(status='published')
        tag = TagFactory(name='oracle-rbac-test')
        ActionTagFactory(action=action1, tag=tag)

        user = _make_user()
        permissions = {
            'action_permissions': [
                {
                    'actions_type': 'restricted',
                    'action_ids': [],
                    'tag_patterns': ['oracle-rbac-test'],
                }
            ]
        }

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.return_value = permissions
                result = get_allowed_action_ids_for_user(user)

        self.assertIn(action1.id, result)

    # ----------------------------------------------------------------
    # Tâche 4.9 — plusieurs profils agrégés → union des IDs
    # ----------------------------------------------------------------
    def test_multiple_profiles_aggregated_returns_union(self):
        """4.9: Multiple permission entries → union of all IDs."""
        user = _make_user()
        permissions = {
            'action_permissions': [
                {'actions_type': 'restricted', 'action_ids': [1, 2], 'tag_patterns': []},
                {'actions_type': 'restricted', 'action_ids': [3, 4], 'tag_patterns': []},
            ]
        }

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.return_value = permissions
                result = get_allowed_action_ids_for_user(user)

        self.assertEqual(result, {1, 2, 3, 4})

    def test_empty_action_permissions_list_returns_empty_set(self):
        """4.5b: action_permissions is empty list → set()."""
        user = _make_user()

        with patch('core.auth_utils.get_user_ad_groups', return_value=[]):
            with patch('executions.utils.ProfileService') as MockPS:
                MockPS.return_value.get_cumulative_permissions.return_value = {
                    'action_permissions': []
                }
                result = get_allowed_action_ids_for_user(user)

        self.assertEqual(result, set())
