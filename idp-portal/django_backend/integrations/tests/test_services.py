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
