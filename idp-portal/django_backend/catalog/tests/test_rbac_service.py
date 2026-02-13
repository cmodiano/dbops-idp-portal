"""
Tests for CatalogRBACService.

Story 26.3 - AC7: Unit tests for the extracted RBAC service.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

from catalog.rbac_service import CatalogRBACService


class TestGetPermissions:
    """Tests for CatalogRBACService.get_permissions()."""

    def setup_method(self):
        self.service = CatalogRBACService()

    def test_returns_none_if_user_is_none(self):
        """get_permissions returns None when user is None."""
        result = self.service.get_permissions(None)
        assert result is None

    def test_returns_none_if_user_not_authenticated(self):
        """get_permissions returns None when user is not authenticated."""
        user = MagicMock()
        user.is_authenticated = False
        result = self.service.get_permissions(user)
        assert result is None

    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_returns_none_if_profile_service_raises(self, mock_ad_groups, mock_ps_class):
        """get_permissions returns None and logs warning on ProfileService failure."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.side_effect = ConnectionError("down")

        with patch('catalog.rbac_service.logger') as mock_logger:
            result = self.service.get_permissions(user)

        assert result is None
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args[1]
        assert call_kwargs.get('exc_info') is True
        assert call_kwargs.get('error_type') == 'ConnectionError'
        assert 'correlation_id' in call_kwargs

    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_returns_none_if_no_permissions(self, mock_ad_groups, mock_ps_class):
        """get_permissions returns None when ProfileService returns no permissions."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {}

        result = self.service.get_permissions(user)
        assert result is None

    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_returns_none_if_no_action_permissions(self, mock_ad_groups, mock_ps_class):
        """get_permissions returns None when action_permissions is empty."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {
            'action_permissions': []
        }

        result = self.service.get_permissions(user)
        assert result is None

    @patch('inventory.services.InventoryService')
    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_actions_type_all_with_default_environments(self, mock_ad_groups, mock_ps_class, mock_inv_class):
        """get_permissions returns actions_type='all' with environments from inventory."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {'actions_type': 'all'}
            ]
        }
        mock_inv_class.return_value.list_environments.return_value = ['dev', 'prod', 'staging']

        result = self.service.get_permissions(user)

        assert result is not None
        assert result['actions_type'] == 'all'
        assert result['action_ids'] == []
        assert result['tag_patterns'] == []
        assert result['environments'] == ['dev', 'prod', 'staging']

    @patch('inventory.services.InventoryService')
    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_actions_type_all_fallback_environments(self, mock_ad_groups, mock_ps_class, mock_inv_class):
        """get_permissions uses fallback environments when InventoryService fails."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {'actions_type': 'all'}
            ]
        }
        mock_inv_class.return_value.list_environments.side_effect = Exception("inventory down")

        with patch('catalog.rbac_service.logger'):
            result = self.service.get_permissions(user)

        assert result is not None
        assert result['actions_type'] == 'all'
        assert sorted(result['environments']) == ['dev', 'prod', 'staging']

    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_actions_type_pattern_with_tag_patterns(self, mock_ad_groups, mock_ps_class):
        """get_permissions returns actions_type='pattern' when tag_patterns exist."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {
                    'actions_type': 'pattern',
                    'action_ids': [1, 2],
                    'tag_patterns': ['db-*', 'infra-prod'],
                    'environments': ['dev', 'prod']
                }
            ]
        }

        result = self.service.get_permissions(user)

        assert result is not None
        assert result['actions_type'] == 'pattern'
        assert result['action_ids'] == [1, 2]
        assert result['tag_patterns'] == ['db-*', 'infra-prod']
        assert result['environments'] == ['dev', 'prod']

    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_actions_type_list_with_action_ids_only(self, mock_ad_groups, mock_ps_class):
        """get_permissions returns actions_type='list' with action_ids only."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {
                    'actions_type': 'list',
                    'action_ids': [5, 3, 1],
                    'tag_patterns': [],
                    'environments': ['staging']
                }
            ]
        }

        result = self.service.get_permissions(user)

        assert result is not None
        assert result['actions_type'] == 'list'
        assert result['action_ids'] == [1, 3, 5]  # Sorted
        assert result['tag_patterns'] == []
        assert result['environments'] == ['staging']

    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_multi_profile_aggregation(self, mock_ad_groups, mock_ps_class):
        """get_permissions aggregates permissions across multiple profiles."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {
                    'actions_type': 'list',
                    'action_ids': [1, 2],
                    'tag_patterns': [],
                    'environments': ['dev']
                },
                {
                    'actions_type': 'pattern',
                    'action_ids': [3],
                    'tag_patterns': ['db-*'],
                    'environments': ['prod']
                }
            ]
        }

        result = self.service.get_permissions(user)

        assert result is not None
        assert result['actions_type'] == 'pattern'  # tag_patterns present
        assert result['action_ids'] == [1, 2, 3]
        assert result['tag_patterns'] == ['db-*']
        assert result['environments'] == ['dev', 'prod']

    @patch('catalog.rbac_service.ProfileService')
    @patch('catalog.rbac_service.get_user_ad_groups')
    def test_multi_profile_all_overrides_list(self, mock_ad_groups, mock_ps_class):
        """get_permissions actions_type='all' overrides 'list' when multi-profile (MEDIUM-3 fix)."""
        user = MagicMock()
        user.is_authenticated = True
        user.id = 1
        mock_ad_groups.return_value = ['group1']
        mock_ps_class.return_value.get_cumulative_permissions.return_value = {
            'action_permissions': [
                {
                    'actions_type': 'list',
                    'action_ids': [1, 2],
                    'tag_patterns': [],
                    'environments': ['dev']
                },
                {
                    'actions_type': 'all',  # This should override
                    'action_ids': [],
                    'tag_patterns': [],
                    'environments': ['prod']
                }
            ]
        }

        # Note: InventoryService is NOT called when environments are explicitly provided
        result = self.service.get_permissions(user)

        assert result is not None
        assert result['actions_type'] == 'all'  # 'all' overrides 'list'
        assert result['action_ids'] == [1, 2]  # Still aggregates action_ids from other profiles
        assert result['tag_patterns'] == []
        # Environments are aggregated from both profiles (union)
        assert sorted(result['environments']) == ['dev', 'prod']


class TestFilterActions:
    """Tests for CatalogRBACService.filter_actions()."""

    def setup_method(self):
        self.service = CatalogRBACService()

    def test_returns_all_if_permissions_none(self):
        """filter_actions returns all actions when permissions is None."""
        actions = [{'id': 1}, {'id': 2}]
        result = self.service.filter_actions(actions, None)
        assert result == actions

    def test_returns_all_if_actions_type_all(self):
        """filter_actions returns all actions when actions_type is 'all'."""
        actions = [{'id': 1}, {'id': 2}]
        permissions = {'actions_type': 'all'}
        result = self.service.filter_actions(actions, permissions)
        assert result == actions

    def test_filter_by_action_ids(self):
        """filter_actions filters by action_ids."""
        actions = [{'id': 1}, {'id': 2}, {'id': 3}]
        permissions = {
            'actions_type': 'list',
            'action_ids': [1, 3],
            'tag_patterns': [],
        }
        result = self.service.filter_actions(actions, permissions)
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['id'] == 3

    def test_filter_by_tag_patterns(self):
        """filter_actions filters by tag_patterns."""
        actions = [
            {'id': 1, 'tags': ['db-oracle', 'infra']},
            {'id': 2, 'tags': ['web', 'frontend']},
            {'id': 3, 'tags': ['infra']},
        ]
        permissions = {
            'actions_type': 'pattern',
            'action_ids': [],
            'tag_patterns': ['infra'],
        }
        result = self.service.filter_actions(actions, permissions)
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['id'] == 3

    def test_filter_union_action_ids_and_tag_patterns(self):
        """filter_actions returns union of action_ids and tag_patterns matches."""
        actions = [
            {'id': 1, 'tags': ['web']},
            {'id': 2, 'tags': ['db']},
            {'id': 3, 'tags': ['infra']},
        ]
        permissions = {
            'actions_type': 'pattern',
            'action_ids': [1],
            'tag_patterns': ['infra'],
        }
        result = self.service.filter_actions(actions, permissions)
        assert len(result) == 2
        ids = [a['id'] for a in result]
        assert 1 in ids
        assert 3 in ids

    def test_filter_with_action_objects(self):
        """filter_actions works with Action-like objects."""
        action1 = MagicMock()
        action1.id = 1
        action1._prefetched_objects_cache = {}
        action1.actiontag_set = MagicMock()
        action1.actiontag_set.all.return_value = []

        action2 = MagicMock()
        action2.id = 2
        action2._prefetched_objects_cache = {}
        action2.actiontag_set = MagicMock()
        action2.actiontag_set.all.return_value = []

        permissions = {
            'actions_type': 'list',
            'action_ids': [2],
            'tag_patterns': [],
        }
        result = self.service.filter_actions([action1, action2], permissions)
        assert len(result) == 1
        assert result[0].id == 2

    def test_filter_with_prefetched_tags(self):
        """filter_actions uses prefetched tags from _prefetched_objects_cache."""
        tag_mock = MagicMock()
        tag_mock.tag.name = 'db-oracle'

        action1 = MagicMock()
        action1.id = 1
        action1._prefetched_objects_cache = {'actiontag_set': [tag_mock]}
        action1.actiontag_set = MagicMock()
        action1.actiontag_set.all.return_value = [tag_mock]

        action2 = MagicMock()
        action2.id = 2
        action2._prefetched_objects_cache = {'actiontag_set': []}
        action2.actiontag_set = MagicMock()
        action2.actiontag_set.all.return_value = []

        permissions = {
            'actions_type': 'pattern',
            'action_ids': [],
            'tag_patterns': ['db-oracle'],
        }
        result = self.service.filter_actions([action1, action2], permissions)
        assert len(result) == 1
        assert result[0].id == 1

    def test_filter_with_dicts_no_tags(self):
        """filter_actions handles dicts with no tags key."""
        actions = [{'id': 1}, {'id': 2}]
        permissions = {
            'actions_type': 'pattern',
            'action_ids': [],
            'tag_patterns': ['infra'],
        }
        result = self.service.filter_actions(actions, permissions)
        assert len(result) == 0

    def test_filter_empty_list(self):
        """filter_actions returns empty list for empty input."""
        permissions = {
            'actions_type': 'list',
            'action_ids': [1],
            'tag_patterns': [],
        }
        result = self.service.filter_actions([], permissions)
        assert result == []

    def test_filter_no_match(self):
        """filter_actions returns empty list when nothing matches."""
        actions = [{'id': 1, 'tags': ['web']}, {'id': 2, 'tags': ['api']}]
        permissions = {
            'actions_type': 'list',
            'action_ids': [99],
            'tag_patterns': ['infra'],
        }
        result = self.service.filter_actions(actions, permissions)
        assert len(result) == 0

    def test_filter_invalid_permissions_type_returns_all(self):
        """filter_actions returns all actions when permissions is invalid type (MEDIUM-2 fix)."""
        actions = [{'id': 1}, {'id': 2}]
        # Pass invalid permissions type (string instead of dict)
        with patch('catalog.rbac_service.logger') as mock_logger:
            result = self.service.filter_actions(actions, "invalid_permissions")

        assert result == actions  # Defensive: treat as no restrictions
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args[1]
        assert call_kwargs.get('permissions_type') == 'str'
        assert 'correlation_id' in call_kwargs


class TestCheckAction:
    """Tests for CatalogRBACService.check_action()."""

    def setup_method(self):
        self.service = CatalogRBACService()

    def test_returns_true_if_permissions_none(self):
        """check_action returns True when permissions is None (no restrictions)."""
        result = self.service.check_action({'id': 1}, None)
        assert result is True

    def test_returns_true_if_actions_type_all(self):
        """check_action returns True when actions_type is 'all'."""
        permissions = {'actions_type': 'all'}
        result = self.service.check_action({'id': 1}, permissions)
        assert result is True

    def test_returns_true_if_action_id_matches(self):
        """check_action returns True when action_id is in allowed list."""
        permissions = {
            'actions_type': 'list',
            'action_ids': [1, 5],
            'tag_patterns': [],
        }
        result = self.service.check_action({'id': 5}, permissions)
        assert result is True

    def test_returns_true_if_tag_matches(self):
        """check_action returns True when a tag matches tag_patterns."""
        permissions = {
            'actions_type': 'pattern',
            'action_ids': [],
            'tag_patterns': ['db-oracle'],
        }
        result = self.service.check_action({'id': 1, 'tags': ['db-oracle', 'infra']}, permissions)
        assert result is True

    def test_returns_false_if_no_match(self):
        """check_action returns False when neither action_id nor tags match."""
        permissions = {
            'actions_type': 'list',
            'action_ids': [99],
            'tag_patterns': ['other-tag'],
        }
        result = self.service.check_action({'id': 1, 'tags': ['web']}, permissions)
        assert result is False

    def test_with_action_object(self):
        """check_action works with Action-like objects."""
        action = MagicMock()
        action.id = 5
        action._prefetched_objects_cache = {}
        action.actiontag_set = MagicMock()
        action.actiontag_set.all.return_value = []

        permissions = {
            'actions_type': 'list',
            'action_ids': [5],
            'tag_patterns': [],
        }
        result = self.service.check_action(action, permissions)
        assert result is True

    def test_with_dict(self):
        """check_action works with dict action."""
        permissions = {
            'actions_type': 'list',
            'action_ids': [3],
            'tag_patterns': [],
        }
        result = self.service.check_action({'id': 3}, permissions)
        assert result is True
