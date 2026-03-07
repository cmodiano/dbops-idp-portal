# profiles/tests/test_profile_audit_changes.py
import pytest
from unittest.mock import patch, MagicMock
from profiles.services import ProfileService
from profiles.models import Profile


@pytest.mark.django_db
class TestProfileAuditChanges:
    """Story 61.3 — PROFILE_UPDATED doit inclure changes dans details."""

    def _make_profile(self, **kwargs):
        defaults = {
            'name': 'Test Profile',
            'description': 'Desc',
            'ad_group': 'GRP-TEST',
            'is_admin': 0,
            'is_auditor': 0,
            'is_approver': 0,
        }
        defaults.update(kwargs)
        return Profile.objects.create(**defaults)

    def _make_user(self):
        mock_user = MagicMock()
        mock_user.id = 1
        return mock_user

    @patch('profiles.services.AuditService.create_entry')
    def test_name_change_appears_in_changes(self, mock_audit):
        profile = self._make_profile(name='Old Name')
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'name': 'New Name'}, user)
        mock_audit.assert_called_once()
        details = mock_audit.call_args.kwargs['details']
        assert 'changes' in details
        assert details['name'] == 'New Name'
        assert details['changes']['name']['old'] == 'Old Name'
        assert details['changes']['name']['new'] == 'New Name'

    @patch('profiles.services.AuditService.create_entry')
    def test_description_change_appears_in_changes(self, mock_audit):
        profile = self._make_profile(description='Old Desc')
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'description': 'New Desc'}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes['description']['old'] == 'Old Desc'
        assert changes['description']['new'] == 'New Desc'

    @patch('profiles.services.AuditService.create_entry')
    def test_ad_group_change_appears_in_changes(self, mock_audit):
        profile = self._make_profile(ad_group='GRP-OLD')
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'ad_group': 'GRP-NEW'}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes['ad_group']['old'] == 'GRP-OLD'
        assert changes['ad_group']['new'] == 'GRP-NEW'

    @patch('profiles.services.AuditService.create_entry')
    def test_is_admin_change_tracked_as_int(self, mock_audit):
        profile = self._make_profile(is_admin=0)
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'is_admin': True}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes['is_admin']['old'] == 0
        assert changes['is_admin']['new'] == 1

    @patch('profiles.services.AuditService.create_entry')
    def test_is_auditor_change_tracked(self, mock_audit):
        profile = self._make_profile(is_auditor=0)
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'is_auditor': True}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes['is_auditor']['old'] == 0
        assert changes['is_auditor']['new'] == 1

    @patch('profiles.services.AuditService.create_entry')
    def test_is_approver_change_tracked(self, mock_audit):
        profile = self._make_profile(is_approver=0)
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'is_approver': True}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes['is_approver']['old'] == 0
        assert changes['is_approver']['new'] == 1

    @patch('profiles.services.AuditService.create_entry')
    def test_unchanged_field_not_in_changes(self, mock_audit):
        profile = self._make_profile(name='Same Name')
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'name': 'Same Name'}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes == {}  # old == new → filtré

    @patch('profiles.services.AuditService.create_entry')
    def test_no_audit_without_user(self, mock_audit):
        profile = self._make_profile()
        ProfileService().update_profile(profile.id, {'name': 'New Name'}, user=None)
        mock_audit.assert_not_called()

    @patch('profiles.services.AuditService.create_entry')
    def test_multiple_fields_change_appear_in_changes(self, mock_audit):
        """MEDIUM-1 : plusieurs champs modifiés simultanément → tous présents dans changes."""
        profile = self._make_profile(name='Old Name', is_admin=0)
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'name': 'New Name', 'is_admin': True}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes['name']['old'] == 'Old Name'
        assert changes['name']['new'] == 'New Name'
        assert changes['is_admin']['old'] == 0
        assert changes['is_admin']['new'] == 1

    @patch('profiles.services.AuditService.create_entry')
    def test_description_cleared_to_none_appears_in_changes(self, mock_audit):
        """MEDIUM-2 : effacement de description (→ None) tracé dans changes."""
        profile = self._make_profile(description='Old Desc')
        user = self._make_user()
        ProfileService().update_profile(profile.id, {'description': None}, user)
        mock_audit.assert_called_once()
        changes = mock_audit.call_args.kwargs['details']['changes']
        assert changes['description']['old'] == 'Old Desc'
        assert changes['description']['new'] is None
