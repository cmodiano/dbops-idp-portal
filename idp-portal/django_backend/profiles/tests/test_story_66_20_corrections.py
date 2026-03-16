"""
Tests pour les corrections de la story 66-20 (revue qualité module profiles).

Couvre :
- PROF-MED-01 : update_profile() passe correlation_id à AuditService
- PROF-MED-02 : set_action_permissions() et set_target_permissions() créent un audit trail
- PROF-MED-03 : ProfileBoolFieldsMixin — DRY to_representation partagé
- PROF-HIGH-01 : get_cumulative_permissions() — boucle unique (both action+target in one pass)
"""
import pytest
from unittest.mock import patch, MagicMock

from django.test import TestCase

from profiles.models import Profile
from profiles.serializers import (
    ProfileBoolFieldsMixin,
    ProfileSerializer,
    ProfileListSerializer,
)
from profiles.services import ProfileService
from core.models import AuditActionType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(**kwargs):
    defaults = {'name': 'Story-66-20', 'ad_group': 'GRP-TEST-6620'}
    defaults.update(kwargs)
    return Profile.objects.create(**defaults)


def _make_mock_user(uid=99):
    user = MagicMock()
    user.id = uid
    return user


# ---------------------------------------------------------------------------
# PROF-MED-01 : correlation_id dans update_profile()
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestUpdateProfileCorrelationId(TestCase):
    """PROF-MED-01 — update_profile() doit passer correlation_id à AuditService."""

    @patch('profiles.services.get_correlation_id', return_value='corr-abc-123')
    @patch('profiles.services.AuditService.create_entry')
    def test_update_profile_passes_correlation_id(self, mock_audit, mock_corr):
        profile = _make_profile(name='OrigName-MED01')
        user = _make_mock_user()

        ProfileService().update_profile(profile.id, {'name': 'NewName-MED01'}, user=user)

        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert kwargs.get('correlation_id') == 'corr-abc-123', (
            "update_profile() doit passer correlation_id=get_correlation_id() à AuditService.create_entry()"
        )

    @patch('profiles.services.get_correlation_id', return_value='corr-xyz-789')
    @patch('profiles.services.AuditService.create_entry')
    def test_update_profile_no_user_no_audit(self, mock_audit, mock_corr):
        """Sans user, aucun appel audit (comportement existant inchangé)."""
        profile = _make_profile(name='NoUserProfile-MED01')
        ProfileService().update_profile(profile.id, {'name': 'Changed'}, user=None)
        mock_audit.assert_not_called()


# ---------------------------------------------------------------------------
# PROF-MED-02 : audit trail dans set_action_permissions() et set_target_permissions()
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPermissionsAuditTrail(TestCase):
    """PROF-MED-02 — set_action/target_permissions() doivent créer un audit trail."""

    @patch('profiles.services.get_correlation_id', return_value='corr-perm-001')
    @patch('profiles.services.AuditService.create_entry')
    def test_set_action_permissions_creates_audit_with_user(self, mock_audit, mock_corr):
        profile = _make_profile(name='AuditActionPerm')
        user = _make_mock_user(uid=42)

        ProfileService().set_action_permissions(
            profile.id, {'actions_type': 'all'}, user=user
        )

        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert str(user.id) == kwargs.get('user_id')
        assert kwargs.get('action_type') == AuditActionType.PROFILE_UPDATED
        assert kwargs.get('entity_id') == profile.id
        assert kwargs.get('correlation_id') == 'corr-perm-001'
        details = kwargs.get('details', {})
        assert details.get('action') == 'set_action_permissions'

    @patch('profiles.services.AuditService.create_entry')
    def test_set_action_permissions_no_audit_without_user(self, mock_audit):
        profile = _make_profile(name='NoAuditActionPerm')
        ProfileService().set_action_permissions(
            profile.id, {'actions_type': 'all'}, user=None
        )
        mock_audit.assert_not_called()

    @patch('profiles.services.get_correlation_id', return_value='corr-perm-002')
    @patch('profiles.services.AuditService.create_entry')
    def test_set_target_permissions_creates_audit_with_user(self, mock_audit, mock_corr):
        profile = _make_profile(name='AuditTargetPerm')
        user = _make_mock_user(uid=55)

        ProfileService().set_target_permissions(
            profile.id, {'targets_type': 'all'}, user=user
        )

        mock_audit.assert_called_once()
        kwargs = mock_audit.call_args.kwargs
        assert str(user.id) == kwargs.get('user_id')
        assert kwargs.get('action_type') == AuditActionType.PROFILE_UPDATED
        assert kwargs.get('entity_id') == profile.id
        assert kwargs.get('correlation_id') == 'corr-perm-002'
        details = kwargs.get('details', {})
        assert details.get('action') == 'set_target_permissions'

    @patch('profiles.services.AuditService.create_entry')
    def test_set_target_permissions_no_audit_without_user(self, mock_audit):
        profile = _make_profile(name='NoAuditTargetPerm')
        ProfileService().set_target_permissions(
            profile.id, {'targets_type': 'all'}, user=None
        )
        mock_audit.assert_not_called()

    @patch('profiles.services.get_correlation_id', return_value='corr-upsert')
    @patch('profiles.services.AuditService.create_entry')
    def test_set_action_permissions_upsert_audit_created_flag(self, mock_audit, mock_corr):
        """Le flag 'created' dans details reflète le type d'opération (création vs mise à jour)."""
        profile = _make_profile(name='UpsertAuditPerm')
        user = _make_mock_user()
        service = ProfileService()

        # Première création
        service.set_action_permissions(profile.id, {'actions_type': 'all'}, user=user)
        first_call_details = mock_audit.call_args.kwargs['details']
        assert first_call_details['created'] is True

        # Deuxième appel = mise à jour
        service.set_action_permissions(profile.id, {'actions_type': 'list', 'action_ids': [1]}, user=user)
        second_call_details = mock_audit.call_args.kwargs['details']
        assert second_call_details['created'] is False


# ---------------------------------------------------------------------------
# PROF-MED-03 : ProfileBoolFieldsMixin — DRY to_representation
# ---------------------------------------------------------------------------

class TestProfileBoolFieldsMixin(TestCase):
    """PROF-MED-03 — ProfileBoolFieldsMixin convertit is_admin/is_auditor/is_approver."""

    def _make_mock_instance(self, is_admin=0, is_auditor=0, is_approver=1):
        instance = MagicMock()
        instance.is_admin = is_admin
        instance.is_auditor = is_auditor
        instance.is_approver = is_approver
        return instance

    def test_mixin_converts_int_to_bool(self):
        """ProfileBoolFieldsMixin convertit is_admin/is_auditor/is_approver int→bool via to_representation réel."""
        # Utiliser ProfileBoolFieldsMixin.to_representation() directement via un sous-serializer
        # qui fournit un super() correct (dict avec valeurs int brutes).
        class MockBaseSerializer:
            def to_representation(self, instance):
                return {
                    'is_admin': instance.is_admin,
                    'is_auditor': instance.is_auditor,
                    'is_approver': instance.is_approver,
                }

        class TestSerializer(ProfileBoolFieldsMixin, MockBaseSerializer):
            pass

        serializer = TestSerializer()
        instance = self._make_mock_instance(is_admin=1, is_auditor=0, is_approver=1)
        result = serializer.to_representation(instance)

        assert result['is_admin'] is True, "is_admin=1 doit être converti en True"
        assert result['is_auditor'] is False, "is_auditor=0 doit être converti en False"
        assert result['is_approver'] is True, "is_approver=1 doit être converti en True"

        # Vérifier aussi le cas is_admin=0
        instance2 = self._make_mock_instance(is_admin=0, is_auditor=1, is_approver=0)
        result2 = serializer.to_representation(instance2)
        assert result2['is_admin'] is False
        assert result2['is_auditor'] is True
        assert result2['is_approver'] is False

    def test_mixin_used_by_profile_serializer(self):
        """ProfileSerializer hérite de ProfileBoolFieldsMixin (DRY, PROF-MED-03)."""
        assert issubclass(ProfileSerializer, ProfileBoolFieldsMixin), (
            "ProfileSerializer doit hériter de ProfileBoolFieldsMixin"
        )

    def test_mixin_used_by_profile_list_serializer(self):
        """ProfileListSerializer hérite de ProfileBoolFieldsMixin (DRY, PROF-MED-03)."""
        assert issubclass(ProfileListSerializer, ProfileBoolFieldsMixin), (
            "ProfileListSerializer doit hériter de ProfileBoolFieldsMixin"
        )


# ---------------------------------------------------------------------------
# PROF-HIGH-01 : get_cumulative_permissions() — boucle unique
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestCumulativePermissionsSinglePass(TestCase):
    """PROF-HIGH-01 — get_cumulative_permissions() collecte action+target en une seule boucle."""

    def test_collects_both_action_and_target_permissions(self):
        """Les permissions action ET target sont collectées pour le même profil."""
        profile = _make_profile(name='CumulBothPerms')
        ProfileService().set_action_permissions(profile.id, {'actions_type': 'all'})
        ProfileService().set_target_permissions(profile.id, {'targets_type': 'list', 'target_names': ['srv-01']})

        result = ProfileService().get_cumulative_permissions(user_id=1, ad_groups=['GRP-TEST-6620'])
        assert len(result['action_permissions']) == 1
        assert result['action_permissions'][0]['actions_type'] == 'all'
        assert len(result['target_permissions']) == 1
        assert result['target_permissions'][0]['targets_type'] == 'list'
        assert 'srv-01' in result['target_permissions'][0]['target_names']

    def test_admin_without_explicit_permission_gets_full_access(self):
        """Profile is_admin=1 sans permission explicite → accès complet action ET target."""
        _make_profile(name='AdminNoPerms', is_admin=1)

        result = ProfileService().get_cumulative_permissions(user_id=1, ad_groups=['GRP-TEST-6620'])
        assert len(result['action_permissions']) == 1
        assert result['action_permissions'][0]['actions_type'] == 'all'
        assert len(result['target_permissions']) == 1
        assert result['target_permissions'][0]['targets_type'] == 'all'
