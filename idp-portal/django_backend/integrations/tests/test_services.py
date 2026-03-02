"""
Tests for integrations services (IntegrationService).
Story 20.5: Fixed method names, audit assertions, added edge cases.
"""

import pytest
from django.test import TestCase
from integrations.models import Integration
from integrations.services import IntegrationService
from core.models import AuditLog, AuditActionType, AuditEntityType
from tests.factories import UserFactory


@pytest.mark.django_db
class TestIntegrationServiceCreate(TestCase):
    """Tests for IntegrationService.create_integration()."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')

    def test_create_integration_with_user_and_audit(self):
        """create_integration() with user creates audit entry."""
        data = {
            'type': 'aap',
            'name': 'Test AAP',
            'base_url': 'https://aap.example.com',
            'config': {'api_key': 'test123'}
        }

        integration = self.service.create_integration(data, user=self.user)

        self.assertIsNotNone(integration.id)
        self.assertEqual(integration.name, 'Test AAP')
        self.assertEqual(integration.type, 'aap')
        self.assertEqual(integration.get_config(), {'api_key': 'test123'})

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration.id,
            action_type=AuditActionType.INTEGRATION_CREATED
        ).first()
        self.assertIsNotNone(audit)

    def test_create_integration_without_user_no_audit(self):
        """create_integration() without user creates no audit."""
        data = {
            'type': 'servicenow',
            'name': 'Test SN',
            'base_url': 'https://sn.example.com',
        }

        integration = self.service.create_integration(data)

        self.assertIsNotNone(integration.id)
        audit_count = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration.id,
        ).count()
        self.assertEqual(audit_count, 0)

    def test_create_integration_without_config(self):
        """create_integration() without config field works."""
        data = {
            'type': 'terraform',
            'name': 'Terraform',
            'base_url': 'https://tf.example.com',
        }

        integration = self.service.create_integration(data)
        self.assertIsNotNone(integration.id)
        self.assertIsNone(integration.get_config())

    def test_create_integration_duplicate_name_raises(self):
        """create_integration() with duplicate name raises ValueError."""
        Integration.objects.create(
            type='aap', name='Duplicate', base_url='https://a.com'
        )

        with self.assertRaises(ValueError) as ctx:
            self.service.create_integration({
                'type': 'aap',
                'name': 'Duplicate',
                'base_url': 'https://b.com',
            })
        self.assertIn("existe déjà", str(ctx.exception))

    def test_create_integration_optional_fields(self):
        """create_integration() stores optional fields correctly."""
        data = {
            'type': 'aap',
            'name': 'Full AAP',
            'base_url': 'https://aap.example.com',
            'credential_ref': 'vault:aap-creds',
            'icon': '/static/icons/aap.png',
            'auth_flow': 'token',
            'token_url': 'https://aap.example.com/api/v2/tokens/',
        }

        integration = self.service.create_integration(data)
        self.assertEqual(integration.credential_ref, 'vault:aap-creds')
        self.assertEqual(integration.icon, '/static/icons/aap.png')
        self.assertEqual(integration.auth_flow, 'token')
        self.assertEqual(integration.token_url, 'https://aap.example.com/api/v2/tokens/')


@pytest.mark.django_db
class TestIntegrationServiceRead(TestCase):
    """Tests for IntegrationService read methods."""

    def setUp(self):
        self.service = IntegrationService()
        self.integration = Integration.objects.create(
            type='aap', name='AAP Integration', base_url='https://aap.example.com'
        )

    def test_get_by_id(self):
        """get_by_id() retrieves integration."""
        result = self.service.get_by_id(self.integration.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.integration.id)

    def test_get_by_id_not_found(self):
        """get_by_id() returns None for non-existent ID."""
        result = self.service.get_by_id(99999)
        self.assertIsNone(result)

    def test_get_by_type(self):
        """get_by_type() retrieves integration by type."""
        result = self.service.get_by_type('aap')
        self.assertIsNotNone(result)
        self.assertEqual(result.type, 'aap')

    def test_get_by_type_not_found(self):
        """get_by_type() returns None for non-existent type."""
        result = self.service.get_by_type('nonexistent')
        self.assertIsNone(result)

    def test_list_all(self):
        """list_all() returns all integrations."""
        Integration.objects.create(
            type='servicenow', name='SN', base_url='https://sn.com'
        )
        result = self.service.list_all()
        self.assertEqual(result.count(), 2)

    def test_list_all_filter_by_type(self):
        """list_all() with type filter returns matching integrations."""
        Integration.objects.create(
            type='servicenow', name='SN', base_url='https://sn.com'
        )
        result = self.service.list_all(integration_type='aap')
        self.assertEqual(result.count(), 1)
        self.assertEqual(result.first().type, 'aap')

    def test_list_all_empty(self):
        """list_all() returns empty queryset when no integrations."""
        Integration.objects.all().delete()
        result = self.service.list_all()
        self.assertEqual(result.count(), 0)


@pytest.mark.django_db
class TestIntegrationServiceUpdate(TestCase):
    """Tests for IntegrationService.update_integration()."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.integration = Integration.objects.create(
            type='aap', name='Original', base_url='https://aap.example.com'
        )

    def test_update_integration(self):
        """update_integration() updates fields."""
        updated = self.service.update_integration(
            self.integration.id,
            {'name': 'Updated Name', 'base_url': 'https://new.com'},
            user=self.user
        )
        self.assertEqual(updated.name, 'Updated Name')
        self.assertEqual(updated.base_url, 'https://new.com')

    def test_update_integration_with_audit(self):
        """update_integration() with user creates audit."""
        self.service.update_integration(
            self.integration.id, {'name': 'Audited'}, user=self.user
        )
        audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=self.integration.id,
            action_type=AuditActionType.INTEGRATION_UPDATED
        ).first()
        self.assertIsNotNone(audit)

    def test_update_integration_not_found(self):
        """update_integration() returns None for non-existent ID."""
        result = self.service.update_integration(99999, {'name': 'X'})
        self.assertIsNone(result)

    def test_update_integration_partial(self):
        """update_integration() only updates provided fields."""
        updated = self.service.update_integration(
            self.integration.id, {'name': 'Changed'}
        )
        self.assertEqual(updated.name, 'Changed')
        self.assertEqual(updated.base_url, 'https://aap.example.com')

    def test_update_integration_config(self):
        """update_integration() updates config JSON."""
        updated = self.service.update_integration(
            self.integration.id, {'config': {'key': 'value'}}
        )
        self.assertEqual(updated.get_config(), {'key': 'value'})

    def test_update_integration_duplicate_name_raises(self):
        """update_integration() with duplicate name raises ValueError."""
        Integration.objects.create(
            type='servicenow', name='Taken', base_url='https://sn.com'
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.update_integration(
                self.integration.id, {'name': 'Taken'}
            )
        self.assertIn("existe déjà", str(ctx.exception))


@pytest.mark.django_db
class TestIntegrationServiceDelete(TestCase):
    """Tests for IntegrationService.delete_integration(). Story 31.2."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.integration = Integration.objects.create(
            type='aap', name='To Delete', base_url='https://aap.example.com'
        )

    def test_delete_integration_no_linked_actions(self):
        """delete_integration() without linked actions returns dict with disabled_actions_count=0."""
        result = self.service.delete_integration(self.integration.id, user=self.user)
        self.assertEqual(result, {'deleted': True, 'disabled_actions_count': 0})
        self.assertFalse(Integration.objects.filter(id=self.integration.id).exists())

    def test_delete_integration_with_audit(self):
        """delete_integration() with user creates INTEGRATION_DELETED audit with disabled_actions_count."""
        integration_id = self.integration.id
        self.service.delete_integration(integration_id, user=self.user)
        audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration_id,
            action_type=AuditActionType.INTEGRATION_DELETED
        ).first()
        self.assertIsNotNone(audit)
        details = audit.get_details()
        self.assertIn('disabled_actions_count', details)
        self.assertEqual(details['disabled_actions_count'], 0)

    def test_delete_integration_not_found(self):
        """delete_integration() returns False for non-existent ID."""
        result = self.service.delete_integration(99999)
        self.assertFalse(result)

    def test_delete_integration_with_linked_actions_disables_them(self):
        """delete_integration() with linked actions disables them and returns count."""
        from catalog.models import Action, ActionStatus
        action1 = Action.objects.create(
            name='Action 1', integration=self.integration, engine='aap', platform='aap',
        )
        action2 = Action.objects.create(
            name='Action 2', integration=self.integration, engine='aap', platform='aap',
        )

        result = self.service.delete_integration(self.integration.id, user=self.user)

        self.assertEqual(result, {'deleted': True, 'disabled_actions_count': 2})
        # Integration is deleted
        self.assertFalse(Integration.objects.filter(id=self.integration.id).exists())
        # Actions are disabled (status + updated_at only); deleted_at/deletion_reason stay NULL
        action1.refresh_from_db()
        action2.refresh_from_db()
        self.assertEqual(action1.status, ActionStatus.DISABLED)
        self.assertEqual(action2.status, ActionStatus.DISABLED)
        self.assertIsNone(action1.deleted_at)
        self.assertIsNone(action2.deleted_at)
        self.assertIsNone(action1.deletion_reason)
        self.assertIsNone(action2.deletion_reason)
        self.assertIsNotNone(action1.updated_at)
        self.assertIsNotNone(action2.updated_at)
        # integration_id is SET_NULL after integration.delete()
        self.assertIsNone(action1.integration_id)
        self.assertIsNone(action2.integration_id)

    def test_delete_integration_with_linked_actions_audit_per_action(self):
        """delete_integration() creates ACTION_DISABLED_INTEGRATION_DELETED audit for each action."""
        from catalog.models import Action
        action1 = Action.objects.create(
            name='Audited Action', integration=self.integration, engine='aap', platform='aap',
        )

        self.service.delete_integration(self.integration.id, user=self.user)

        # Audit for action disabled
        action_audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.ACTION,
            entity_id=action1.id,
            action_type=AuditActionType.ACTION_DISABLED_INTEGRATION_DELETED,
        ).first()
        self.assertIsNotNone(action_audit)
        details = action_audit.get_details()
        self.assertEqual(details['action_name'], 'Audited Action')
        self.assertEqual(details['reason'], 'integration_deleted')

    def test_delete_integration_audit_includes_disabled_count(self):
        """INTEGRATION_DELETED audit includes disabled_actions_count in details."""
        from catalog.models import Action
        Action.objects.create(
            name='A1', integration=self.integration, engine='aap', platform='aap',
        )
        Action.objects.create(
            name='A2', integration=self.integration, engine='aap', platform='aap',
        )

        self.service.delete_integration(self.integration.id, user=self.user)

        audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=self.integration.id,
            action_type=AuditActionType.INTEGRATION_DELETED,
        ).first()
        self.assertIsNotNone(audit)
        details = audit.get_details()
        self.assertEqual(details['disabled_actions_count'], 2)

    def test_delete_integration_already_disabled_actions(self):
        """delete_integration() with already disabled actions still counts them; does not overwrite soft-delete fields."""
        from catalog.models import Action, ActionStatus
        from django.utils import timezone
        action = Action.objects.create(
            name='Already Disabled', integration=self.integration,
            engine='aap', platform='aap',
            status=ActionStatus.DISABLED, deleted_at=timezone.now(),
            deletion_reason='Previously disabled',
        )

        result = self.service.delete_integration(self.integration.id, user=self.user)

        self.assertEqual(result['disabled_actions_count'], 1)
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.DISABLED)
        # Service only sets status and updated_at; existing soft-delete fields unchanged
        self.assertIsNotNone(action.deleted_at)
        self.assertEqual(action.deletion_reason, 'Previously disabled')


@pytest.mark.django_db
class TestIntegrationServiceValidation(TestCase):
    """Tests for IntegrationService.validate_config_json_schema()."""

    def setUp(self):
        self.service = IntegrationService()

    def test_validate_inventory_db_valid(self):
        """validate_config_json_schema() accepts valid inventory_db config."""
        result = self.service.validate_config_json_schema(
            {'schema': 'DBOPS_INVENTORY', 'table': 'SERVERS'},
            'inventory_db'
        )
        self.assertTrue(result)

    def test_validate_inventory_db_not_dict(self):
        """validate_config_json_schema() rejects non-dict for inventory_db."""
        from core.exceptions import InvalidStateError
        with self.assertRaises(InvalidStateError) as ctx:
            self.service.validate_config_json_schema("not a dict", 'inventory_db')
        self.assertEqual(ctx.exception.code, "INVALID_CONFIG")

    def test_validate_inventory_db_non_string_field(self):
        """validate_config_json_schema() rejects non-string schema/table."""
        from core.exceptions import InvalidStateError
        with self.assertRaises(InvalidStateError):
            self.service.validate_config_json_schema(
                {'schema': 123}, 'inventory_db'
            )

    def test_parse_config(self):
        """parse_config() returns deserialized JSON."""
        integration = Integration.objects.create(
            type='aap', name='Config Test', base_url='https://a.com'
        )
        integration.set_config({'key': 'value'})
        integration.save()

        result = self.service.parse_config(integration)
        self.assertEqual(result, {'key': 'value'})

    def test_parse_config_none(self):
        """parse_config() returns None when no config."""
        integration = Integration.objects.create(
            type='aap', name='No Config', base_url='https://a.com'
        )
        result = self.service.parse_config(integration)
        self.assertIsNone(result)


# ─── Story 48.2: Tests de non-régression N+1 / double saves ──────────────────


@pytest.mark.django_db
class TestCreateIntegrationSingleSave(TestCase):
    """Story 48.2 — NEW-BE-7 : create_integration() fusionne les saves post-create."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')

    def test_create_integration_with_config_stores_in_db(self):
        """create_integration() avec config stocke la config correctement en DB (1 seul save post-create)."""
        data = {
            'type': 'aap',
            'name': 'Integration Config Test 48.2',
            'base_url': 'https://aap48.example.com',
            'config': {'api_key': 'secret', 'timeout': 30},
        }
        integration = self.service.create_integration(data, user=self.user)

        self.assertIsNotNone(integration.id)
        # Config correctement persistée en DB
        integration.refresh_from_db()
        self.assertEqual(integration.get_config(), {'api_key': 'secret', 'timeout': 30})

    def test_create_integration_without_config_no_extra_save(self):
        """create_integration() sans config ni status change ne fait aucun save supplémentaire."""
        data = {
            'type': 'servicenow',
            'name': 'Integration No Extra Save 48.2',
            'base_url': 'https://sn48.example.com',
        }
        integration = self.service.create_integration(data)

        self.assertIsNotNone(integration.id)
        integration.refresh_from_db()
        self.assertIsNone(integration.get_config())

    def test_create_integration_with_config_max_one_extra_save(self):
        """NEW-BE-7 : create_integration() avec config effectue au plus 1 save() supplémentaire après l'INSERT."""
        from unittest.mock import patch

        data = {
            'type': 'aap',
            'name': 'Save Count Test 48.2',
            'base_url': 'https://aap48.example.com',
            'config': {'api_key': 'secret'},
        }

        save_call_count = 0
        original_save = Integration.save

        def counting_save(instance, *args, **kwargs):
            nonlocal save_call_count
            save_call_count += 1
            return original_save(instance, *args, **kwargs)

        with patch.object(Integration, 'save', counting_save):
            integration = self.service.create_integration(data, user=self.user)

        # 1 INSERT (objects.create) + au plus 1 UPDATE post-create (config + status fusionnés)
        self.assertLessEqual(
            save_call_count, 2,
            f"create_integration() avec config ne doit pas faire plus de 2 saves (actuel: {save_call_count})"
        )
        self.assertIsNotNone(integration.id)


@pytest.mark.django_db
class TestUpdateIntegrationSingleSave(TestCase):
    """Story 48.2 — NEW-BE-8 : update_integration() met à jour le status en un seul save."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.integration = Integration.objects.create(
            type='aap', name='Update Status Test 48.2', base_url='https://aap48.example.com'
        )

    def test_update_integration_status_reflected_in_db(self):
        """update_integration() calcule le status avant save — le status final est persisté en DB."""
        updated = self.service.update_integration(
            self.integration.id, {'name': 'Update Status Test 48.2 Renamed'}, user=self.user
        )
        # Vérifier persistance en DB (pas uniquement en mémoire)
        self.integration.refresh_from_db()
        self.assertEqual(self.integration.name, 'Update Status Test 48.2 Renamed')
        self.assertEqual(self.integration.status, updated.status)

    def test_update_integration_status_change_single_save(self):
        """NEW-BE-8 : quand validate_integration() retourne un statut différent, update_integration()
        calcule le status AVANT le save unique — pas de second save conditionnel."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        # Forcer un changement de statut : VALID → INVALID
        save_call_count = 0
        original_save = Integration.save

        def counting_save(instance, *args, **kwargs):
            nonlocal save_call_count
            save_call_count += 1
            return original_save(instance, *args, **kwargs)

        with patch.object(Integration, 'save', counting_save), \
             patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            updated = self.service.update_integration(
                self.integration.id, {'name': 'Status Change Single Save 48.2'}, user=self.user
            )

        # Le status calculé doit être persisté en DB
        self.assertEqual(updated.status, IntegrationStatus.INVALID)
        self.integration.refresh_from_db()
        self.assertEqual(self.integration.status, IntegrationStatus.INVALID)
        # Un seul save() (plus le calcul du status était AVANT le save)
        self.assertEqual(save_call_count, 1,
            f"update_integration() ne doit faire qu'1 save() même quand le status change (actuel: {save_call_count})")


@pytest.mark.django_db
class TestDeleteIconHelper(TestCase):
    """Tests for _delete_uploaded_icon() helper."""

    def test_delete_icon_ignores_non_static_icons_path(self):
        """Line 34: path not starting with /static/icons/ is ignored."""
        from integrations.services import _delete_uploaded_icon
        # Should not raise, no file operation attempted
        _delete_uploaded_icon('https://external.cdn.com/icon.png')
        _delete_uploaded_icon('/other/path/icon.png')
        _delete_uploaded_icon(None)

    def test_delete_icon_oserror_logged_not_raised(self):
        """Lines 39-40: OSError during file deletion is caught and logged."""
        from integrations.services import _delete_uploaded_icon
        from unittest.mock import patch, MagicMock

        # Mock Path.unlink to raise OSError
        with patch('integrations.services.Path') as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_cls.return_value = mock_path_instance
            # Make the / operator return a mock that has unlink raising OSError
            mock_icons_dir = MagicMock()
            mock_file = MagicMock()
            mock_file.unlink.side_effect = OSError("Permission denied")
            mock_path_instance.__truediv__ = MagicMock(return_value=mock_icons_dir)
            mock_icons_dir.__truediv__ = MagicMock(return_value=mock_file)

            # Should not raise
            _delete_uploaded_icon('/static/icons/some-icon.png')

    def test_delete_icon_empty_filename_returns_early(self):
        """Line 33: empty filename after removing prefix returns early."""
        from integrations.services import _delete_uploaded_icon
        # Path is /static/icons/ with no filename — returns early
        _delete_uploaded_icon('/static/icons/')


@pytest.mark.django_db
class TestDeleteIntegration3PlusActions(TestCase):
    """Story 48.2 — NEW-BE-6 : delete_integration() bulk update 3+ actions + audit par action."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.integration = Integration.objects.create(
            type='aap', name='Integration With 3 Actions 48.2', base_url='https://aap48.example.com'
        )

    def test_delete_integration_3_actions_all_disabled(self):
        """delete_integration() avec 3 actions liées les désactive toutes via bulk update."""
        from catalog.models import Action, ActionStatus
        actions = [
            Action.objects.create(
                name=f'Action {i} 48.2',
                integration=self.integration,
                engine='aap',
                platform='aap',
            )
            for i in range(1, 4)
        ]

        result = self.service.delete_integration(self.integration.id, user=self.user)

        self.assertEqual(result, {'deleted': True, 'disabled_actions_count': 3})
        for action in actions:
            action.refresh_from_db()
            self.assertEqual(action.status, ActionStatus.DISABLED)

    def test_delete_integration_3_actions_audit_per_action(self):
        """delete_integration() avec 3 actions crée un audit ACTION_DISABLED_INTEGRATION_DELETED par action."""
        from catalog.models import Action
        from core.models import AuditLog, AuditActionType, AuditEntityType
        actions = [
            Action.objects.create(
                name=f'Audit Action {i} 48.2',
                integration=self.integration,
                engine='aap',
                platform='aap',
            )
            for i in range(1, 4)
        ]

        self.service.delete_integration(self.integration.id, user=self.user)

        for action in actions:
            audit = AuditLog.objects.filter(
                entity_type=AuditEntityType.ACTION,
                entity_id=action.id,
                action_type=AuditActionType.ACTION_DISABLED_INTEGRATION_DELETED,
            ).first()
            self.assertIsNotNone(audit, f"Audit manquant pour action {action.name}")
            details = audit.get_details()
            self.assertEqual(details['reason'], 'integration_deleted')


# ─── Coverage gap tests — missing lines ──────────────────────────────────────


@pytest.mark.django_db
class TestCreateIntegrationSecretServiceIdValidation(TestCase):
    """Line 123: create_integration() raises ValueError for invalid secret_service_id."""

    def setUp(self):
        self.service = IntegrationService()

    def test_create_integration_invalid_secret_service_id_raises(self):
        """Line 123: secret_service_id FK not found raises ValueError."""
        data = {
            'type': 'aap',
            'name': 'Test With Secret',
            'base_url': 'https://aap.example.com',
            'secret_service_id': 999999,  # Non-existent FK
        }
        with self.assertRaises(ValueError) as ctx:
            self.service.create_integration(data)
        self.assertIn("999999", str(ctx.exception))

    def test_create_integration_valid_secret_service_id_works(self):
        """secret_service_id pointing to existing integration is accepted."""
        secret_integration = Integration.objects.create(
            type='vault', name='Vault Secret', base_url='https://vault.example.com'
        )
        data = {
            'type': 'aap',
            'name': 'Test With Valid Secret',
            'base_url': 'https://aap.example.com',
            'secret_service_id': secret_integration.id,
        }
        integration = self.service.create_integration(data)
        self.assertIsNotNone(integration.id)


@pytest.mark.django_db
class TestCreateIntegrationUpdatedAtField(TestCase):
    """Line 157: create_integration() ensures updated_at is in update_fields."""

    def setUp(self):
        self.service = IntegrationService()

    def test_create_integration_config_and_status_single_save_with_updated_at(self):
        """Line 157: when config is set and status changes, updated_at is appended once."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        data = {
            'type': 'aap',
            'name': 'Updated At Test',
            'base_url': 'https://aap.example.com',
            'config': {'key': 'value'},
        }

        update_fields_captured = []
        original_save = Integration.save

        def capturing_save(instance, *args, **kwargs):
            if 'update_fields' in kwargs:
                update_fields_captured.extend(kwargs['update_fields'])
            return original_save(instance, *args, **kwargs)

        with patch.object(Integration, 'save', capturing_save), \
             patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            integration = self.service.create_integration(data)

        # updated_at must be in update_fields
        self.assertIn('updated_at', update_fields_captured)
        self.assertIsNotNone(integration.id)


@pytest.mark.django_db
class TestUpdateIntegrationIconChange(TestCase):
    """Lines 256-269: update_integration() icon change path."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.integration = Integration.objects.create(
            type='aap',
            name='Icon Test Integration',
            base_url='https://aap.example.com',
            icon='/static/icons/old-icon.png',
        )

    def test_update_icon_calls_delete_old_icon(self):
        """Lines 256-263: when new icon != old icon, _delete_uploaded_icon is called."""
        from unittest.mock import patch

        with patch('integrations.services._delete_uploaded_icon') as mock_delete:
            updated = self.service.update_integration(
                self.integration.id,
                {'icon': '/static/icons/new-icon.png'},
            )
            mock_delete.assert_called_once_with('/static/icons/old-icon.png')
            self.assertEqual(updated.icon, '/static/icons/new-icon.png')

    def test_update_icon_same_value_no_delete(self):
        """Lines 260->262: when new icon == old icon, _delete_uploaded_icon is NOT called."""
        from unittest.mock import patch

        with patch('integrations.services._delete_uploaded_icon') as mock_delete:
            self.service.update_integration(
                self.integration.id,
                {'icon': '/static/icons/old-icon.png'},  # Same icon — no delete
            )
            mock_delete.assert_not_called()

    def test_update_icon_to_none_calls_delete(self):
        """Lines 265-266: setting icon to None triggers delete of old icon."""
        from unittest.mock import patch

        with patch('integrations.services._delete_uploaded_icon') as mock_delete:
            updated = self.service.update_integration(
                self.integration.id,
                {'icon': None},
            )
            mock_delete.assert_called_once_with('/static/icons/old-icon.png')
            self.assertIsNone(updated.icon)

    def test_update_auth_flow_and_token_url(self):
        """Lines 264-269: update auth_flow and token_url fields."""
        updated = self.service.update_integration(
            self.integration.id,
            {'auth_flow': 'oauth2', 'token_url': 'https://aap.example.com/token/'},
        )
        self.assertEqual(updated.auth_flow, 'oauth2')
        self.assertEqual(updated.token_url, 'https://aap.example.com/token/')


@pytest.mark.django_db
class TestUpdateIntegrationSecretServiceIdValidation(TestCase):
    """Line 275: update_integration() raises ValueError for invalid secret_service_id."""

    def setUp(self):
        self.service = IntegrationService()
        self.integration = Integration.objects.create(
            type='aap', name='Secret FK Test', base_url='https://aap.example.com'
        )

    def test_update_integration_invalid_secret_service_id_raises(self):
        """Line 275: secret_service_id FK not found in update raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.update_integration(
                self.integration.id,
                {'secret_service_id': 999999},
            )
        self.assertIn("999999", str(ctx.exception))

    def test_update_integration_secret_service_id_none_allowed(self):
        """Lines 270-277: setting secret_service_id to None is allowed."""
        updated = self.service.update_integration(
            self.integration.id,
            {'secret_service_id': None},
        )
        self.assertIsNone(updated.secret_service_id)

    def test_update_integration_valid_secret_service_id_accepted(self):
        """Line 274->276 false branch: valid secret_service_id FK → no error, update succeeds."""
        secret_integration = Integration.objects.create(
            type='vault', name='Valid Secret FK', base_url='https://vault.example.com'
        )
        updated = self.service.update_integration(
            self.integration.id,
            {'secret_service_id': secret_integration.id},
        )
        self.assertEqual(updated.secret_service_id, secret_integration.id)


@pytest.mark.django_db
class TestUpdateIntegrationStatusChangeAudit(TestCase):
    """Lines 287-318: update_integration() status change audit and non-valid status warning."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.integration = Integration.objects.create(
            type='aap', name='Status Audit Test', base_url='https://aap.example.com'
        )

    def test_update_creates_status_change_audit_when_status_changes(self):
        """Lines 299-310: when old_status != new computed_status, INTEGRATION_STATUS_UPDATED audit created."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService
        from core.models import AuditLog, AuditActionType, AuditEntityType

        # Force status to change from VALID to INVALID
        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            self.service.update_integration(
                self.integration.id,
                {'name': 'Status Changed'},
                user=self.user,
            )

        # Verify INTEGRATION_STATUS_UPDATED audit was created
        status_audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=self.integration.id,
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
        ).first()
        self.assertIsNotNone(status_audit)
        details = status_audit.get_details()
        self.assertIn('previous_status', details)
        self.assertIn('new_status', details)
        self.assertEqual(details['new_status'], IntegrationStatus.INVALID)

    def test_update_non_valid_status_appends_warning(self):
        """Lines 312-315: non-valid computed_status appends to warnings."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            updated = self.service.update_integration(
                self.integration.id,
                {'name': 'Non Valid Status'},
            )

        self.assertTrue(hasattr(updated, '_warnings'))
        self.assertTrue(len(updated._warnings) > 0)
        self.assertIn('non-valid', updated._warnings[0])

    def test_update_status_change_audit_without_user(self):
        """Lines 299-310: status-change audit uses 'system' as user_id when no user provided."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService
        from core.models import AuditLog, AuditActionType

        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            self.service.update_integration(
                self.integration.id,
                {'name': 'Status System Audit'},
                user=None,
            )

        status_audit = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
            entity_id=self.integration.id,
        ).first()
        self.assertIsNotNone(status_audit)
        self.assertEqual(status_audit.user_id, 'system')


@pytest.mark.django_db
class TestDeleteIntegrationWithIconAndNoUser(TestCase):
    """Lines 368->367, 388->400: delete with icon path and without user."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')

    def test_delete_integration_with_icon_deletes_file(self):
        """Lines 383-385 / 368->367: delete_integration() calls _delete_uploaded_icon for icon."""
        from unittest.mock import patch
        integration = Integration.objects.create(
            type='aap',
            name='Icon Delete Test',
            base_url='https://aap.example.com',
            icon='/static/icons/to-delete.png',
        )

        with patch('integrations.services._delete_uploaded_icon') as mock_delete:
            result = self.service.delete_integration(integration.id, user=self.user)

        self.assertEqual(result['deleted'], True)
        mock_delete.assert_called_once_with('/static/icons/to-delete.png')

    def test_delete_integration_without_user_no_audit(self):
        """Lines 388->400: delete_integration() without user creates no audit entries."""
        integration = Integration.objects.create(
            type='aap', name='No User Delete', base_url='https://aap.example.com'
        )
        integration_id = integration.id

        result = self.service.delete_integration(integration_id, user=None)

        self.assertEqual(result['deleted'], True)
        # No audit entries should have been created (no user)
        from core.models import AuditLog, AuditEntityType
        audit_count = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=integration_id,
        ).count()
        self.assertEqual(audit_count, 0)

    def test_delete_integration_with_linked_actions_no_user_no_action_audit(self):
        """Lines 367-380: delete with linked actions but no user — no per-action audit."""
        from catalog.models import Action
        from core.models import AuditLog, AuditActionType, AuditEntityType
        integration = Integration.objects.create(
            type='aap', name='Actions No User Delete', base_url='https://aap.example.com'
        )
        action = Action.objects.create(
            name='Linked Action', integration=integration, engine='aap', platform='aap',
        )

        result = self.service.delete_integration(integration.id, user=None)

        self.assertEqual(result['disabled_actions_count'], 1)
        # No action audit created (no user)
        action_audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.ACTION,
            entity_id=action.id,
            action_type=AuditActionType.ACTION_DISABLED_INTEGRATION_DELETED,
        ).first()
        self.assertIsNone(action_audit)


@pytest.mark.django_db
class TestCreateIntegrationStatusBranches(TestCase):
    """Lines 148->153, 153->160, 157, 161->167: create_integration() status and needs_save branches."""

    def setUp(self):
        self.service = IntegrationService()

    def test_create_integration_no_config_status_unchanged_no_extra_save(self):
        """Lines 148->153, 153->160, 161->167: no config, status unchanged → needs_save=False, no warning."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        data = {
            'type': 'aap',
            'name': 'No Save Branch Test',
            'base_url': 'https://aap.example.com',
            # No config
        }

        save_count = [0]
        original_save = Integration.save

        def counting_save(instance, *args, **kwargs):
            save_count[0] += 1
            return original_save(instance, *args, **kwargs)

        # Mock validate_integration to return VALID (same as default status)
        # so status doesn't change → needs_save stays False → no extra save
        with patch.object(Integration, 'save', counting_save), \
             patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.VALID):
            integration = self.service.create_integration(data)

        # Only 1 save (the INSERT from objects.create) since needs_save=False
        self.assertEqual(save_count[0], 1)
        self.assertIsNotNone(integration.id)
        # No warnings since status is VALID
        self.assertEqual(integration._warnings, [])

    def test_create_integration_config_only_updated_at_appended(self):
        """Line 157: config is set but status unchanged → updated_at appended since not yet in list."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        data = {
            'type': 'aap',
            'name': 'Updated At Append Test',
            'base_url': 'https://aap.example.com',
            'config': {'key': 'value'},
        }

        update_fields_used = []
        original_save = Integration.save

        def capturing_save(instance, *args, **kwargs):
            if 'update_fields' in kwargs:
                update_fields_used.extend(kwargs['update_fields'])
            return original_save(instance, *args, **kwargs)

        # Mock validate_integration to return VALID (same as default) — status unchanged
        # So: config needs_save=True, but 'updated_at' NOT in update_fields (no status change)
        # → line 157 appends updated_at
        with patch.object(Integration, 'save', capturing_save), \
             patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.VALID):
            _integration = self.service.create_integration(data)

        # updated_at should be in the update_fields (appended at line 157)
        self.assertIn('updated_at', update_fields_used)
        self.assertIn('config', update_fields_used)

    def test_create_integration_non_valid_status_appends_warning(self):
        """Lines 161->167: non-VALID computed_status creates a warning."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        data = {
            'type': 'aap',
            'name': 'Warning Branch Test',
            'base_url': 'https://aap.example.com',
        }

        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            integration = self.service.create_integration(data)

        self.assertTrue(hasattr(integration, '_warnings'))
        self.assertTrue(len(integration._warnings) > 0)

    def test_create_integration_valid_status_no_warning(self):
        """Lines 161->167 false branch: VALID computed_status → no warning."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        data = {
            'type': 'aap',
            'name': 'No Warning Branch Test',
            'base_url': 'https://aap.example.com',
        }

        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.VALID):
            integration = self.service.create_integration(data)

        self.assertEqual(integration._warnings, [])


@pytest.mark.django_db
class TestUpdateIntegrationTypeAndCredentialRef(TestCase):
    """Lines 247-248, 256-257: update_integration() type and credential_ref fields."""

    def setUp(self):
        self.service = IntegrationService()
        self.integration = Integration.objects.create(
            type='aap',
            name='Field Update Test',
            base_url='https://aap.example.com',
            credential_ref='old-cred',
        )

    def test_update_integration_type_field(self):
        """Lines 247-248: updating type field sets it correctly."""
        updated = self.service.update_integration(
            self.integration.id,
            {'type': 'servicenow'},
        )
        self.assertEqual(updated.type, 'servicenow')

    def test_update_integration_credential_ref_field(self):
        """Lines 256-257: updating credential_ref field sets it correctly."""
        updated = self.service.update_integration(
            self.integration.id,
            {'credential_ref': 'new-vault-ref'},
        )
        self.assertEqual(updated.credential_ref, 'new-vault-ref')

    def test_update_integration_credential_ref_to_none(self):
        """Lines 256-257: setting credential_ref to None."""
        updated = self.service.update_integration(
            self.integration.id,
            {'credential_ref': None},
        )
        self.assertIsNone(updated.credential_ref)


@pytest.mark.django_db
class TestUpdateIntegrationStatusChangeBranches(TestCase):
    """Lines 287->292, 299->312, 312->318: update_integration() status-change branches."""

    def setUp(self):
        self.service = IntegrationService()
        self.user = UserFactory(profile='dbops')
        self.integration = Integration.objects.create(
            type='aap',
            name='Status Branch Test',
            base_url='https://aap.example.com',
        )

    def test_update_status_changes_when_computed_differs(self):
        """Lines 287->292 true branch: status is updated when computed != current."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService

        # Force integration to VALID status first
        self.integration.status = IntegrationStatus.VALID
        self.integration.save(update_fields=['status', 'updated_at'])

        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            _updated = self.service.update_integration(
                self.integration.id,
                {'name': 'Status Changed Branch'},
            )

        self.integration.refresh_from_db()
        self.assertEqual(self.integration.status, IntegrationStatus.INVALID)

    def test_update_status_valid_no_warning_with_user(self):
        """Lines 312->318 false branch: VALID computed_status → no warning, but user audit created."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService
        from core.models import AuditLog, AuditActionType, AuditEntityType

        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.VALID):
            updated = self.service.update_integration(
                self.integration.id,
                {'name': 'Valid Status No Warning'},
                user=self.user,
            )

        # No warning since status is VALID
        self.assertEqual(updated._warnings, [])

        # INTEGRATION_UPDATED audit still created (user was provided)
        update_audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=self.integration.id,
            action_type=AuditActionType.INTEGRATION_UPDATED,
        ).first()
        self.assertIsNotNone(update_audit)

    def test_update_status_unchanged_no_status_audit(self):
        """Lines 287->292 false branch: when status does not change, no STATUS_UPDATED audit."""
        from unittest.mock import patch
        from integrations.validation_service import IntegrationValidationService
        from core.models import AuditLog, AuditActionType, AuditEntityType

        # First set a known status on the integration
        current_status = self.integration.status

        # Mock validate_integration to return the same status as current (no change)
        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=current_status):
            self.service.update_integration(
                self.integration.id,
                {'name': 'Status Unchanged Branch'},
                user=self.user,
            )

        status_audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=self.integration.id,
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
        ).first()
        # No status change → no status audit
        self.assertIsNone(status_audit)

    def test_update_non_valid_status_with_user_creates_both_audits(self):
        """Lines 312-325: non-valid status + user creates warning AND INTEGRATION_UPDATED audit."""
        from unittest.mock import patch
        from integrations.models import IntegrationStatus
        from integrations.validation_service import IntegrationValidationService
        from core.models import AuditLog, AuditActionType, AuditEntityType

        with patch.object(IntegrationValidationService, 'validate_integration',
                          return_value=IntegrationStatus.INVALID):
            updated = self.service.update_integration(
                self.integration.id,
                {'name': 'Both Audits Test'},
                user=self.user,
            )

        # Warning appended
        self.assertTrue(len(updated._warnings) > 0)

        # INTEGRATION_UPDATED audit created
        update_audit = AuditLog.objects.filter(
            entity_type=AuditEntityType.INTEGRATION,
            entity_id=self.integration.id,
            action_type=AuditActionType.INTEGRATION_UPDATED,
        ).first()
        self.assertIsNotNone(update_audit)
