"""
Story 24.4 (AC2, AC3, AC6, AC10): Tests for migrate_integrations management command.
"""

import json
import pytest
from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from integrations.models import Integration, IntegrationStatus, IntegrationTypeCatalogue
from core.models import AuditLog, AuditActionType


@pytest.mark.django_db
class TestMigrateIntegrationsAutoCommand(TestCase):

    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='servicenow', name='ServiceNow', version='1.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='terraform', name='Terraform', version='1.0', is_active=False
        )

    def test_migrate_integrations_auto_updates_status(self):
        """AC2: --auto updates status based on catalogue validation."""
        # Integration with deprecated type but still marked VALID
        integration = Integration.objects.create(
            type='terraform', name='TF Cloud', base_url='https://tf.example.com',
            status=IntegrationStatus.VALID,
        )

        out = StringIO()
        call_command('migrate_integrations', '--auto', stdout=out)
        output = out.getvalue()

        integration.refresh_from_db()
        assert integration.status == IntegrationStatus.DEPRECATED
        assert 'MIGRÉ' in output

        # Verify audit entry
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
            entity_id=integration.id,
        ).first()
        assert audit is not None
        details = audit.get_details()
        assert details['old_status'] == IntegrationStatus.VALID
        assert details['new_status'] == IntegrationStatus.DEPRECATED

    def test_migrate_integrations_auto_invalid(self):
        """AC2: Unknown type becomes INVALID."""
        integration = Integration.objects.create(
            type='unknown_type', name='Unknown Int', base_url='https://u.example.com',
            status=IntegrationStatus.VALID,
        )

        out = StringIO()
        call_command('migrate_integrations', '--auto', stdout=out)

        integration.refresh_from_db()
        assert integration.status == IntegrationStatus.INVALID

    def test_migrate_integrations_no_updates_needed(self):
        """AC2: When all integrations are already correct, no changes."""
        Integration.objects.create(
            type='aap', name='AAP Ok', base_url='https://aap.example.com',
            status=IntegrationStatus.VALID,
        )

        out = StringIO()
        call_command('migrate_integrations', '--auto', stdout=out)
        output = out.getvalue()

        assert 'Aucune migration nécessaire' in output
        assert AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED
        ).count() == 0

    def test_migrate_integrations_transactional(self):
        """AC2: Verify all changes happen atomically."""
        Integration.objects.create(
            type='terraform', name='TF 1', base_url='https://tf1.example.com',
            status=IntegrationStatus.VALID,
        )
        Integration.objects.create(
            type='unknown_type', name='Unknown 1', base_url='https://u1.example.com',
            status=IntegrationStatus.VALID,
        )

        out = StringIO()
        call_command('migrate_integrations', '--auto', stdout=out)

        # Both should be updated
        assert Integration.objects.get(name='TF 1').status == IntegrationStatus.DEPRECATED
        assert Integration.objects.get(name='Unknown 1').status == IntegrationStatus.INVALID

    def test_no_option_shows_error(self):
        """Should show error if neither --auto nor --mark-legacy specified."""
        out = StringIO()
        err = StringIO()
        call_command('migrate_integrations', stdout=out, stderr=err)
        assert 'spécifiez --auto' in err.getvalue()


@pytest.mark.django_db
class TestMigrateIntegrationsMarkLegacy(TestCase):

    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )

    def test_mark_legacy_invalid_integrations(self):
        """AC3: --mark-legacy adds _legacy: true to config of INVALID integrations."""
        integration = Integration.objects.create(
            type='jenkins', name='Jenkins Legacy', base_url='https://j.example.com',
            status=IntegrationStatus.INVALID,
            config=json.dumps({'timeout': 30}),
        )

        out = StringIO()
        call_command('migrate_integrations', '--mark-legacy', stdout=out)
        output = out.getvalue()

        integration.refresh_from_db()
        config = integration.get_config()
        assert config['_legacy'] is True
        assert config['timeout'] == 30  # Existing config preserved
        assert 'LEGACY' in output

        # Verify audit
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_MARKED_LEGACY,
            entity_id=integration.id,
        ).first()
        assert audit is not None

    def test_mark_legacy_no_invalid(self):
        """AC3: No INVALID integrations → nothing to mark."""
        Integration.objects.create(
            type='aap', name='AAP Valid', base_url='https://aap.example.com',
            status=IntegrationStatus.VALID,
        )

        out = StringIO()
        call_command('migrate_integrations', '--mark-legacy', stdout=out)
        output = out.getvalue()

        assert 'Aucune intégration invalide' in output

    def test_mark_legacy_warns_about_workflows(self):
        """AC3: Detect actions using legacy integrations and warn."""
        from tests.factories import ActionFactory

        integration = Integration.objects.create(
            type='jenkins', name='Jenkins Dep', base_url='https://j.example.com',
            status=IntegrationStatus.INVALID,
        )
        action = ActionFactory(name='Deploy CI', integration=integration)

        out = StringIO()
        call_command('migrate_integrations', '--mark-legacy', stdout=out)
        output = out.getvalue()

        assert 'Deploy CI' in output
        assert 'ACTION REQUISE' in output

    def test_mark_legacy_null_config(self):
        """AC3: Integration with no config gets _legacy added."""
        integration = Integration.objects.create(
            type='jenkins', name='Jenkins NoConfig', base_url='https://j.example.com',
            status=IntegrationStatus.INVALID,
            config=None,
        )

        out = StringIO()
        call_command('migrate_integrations', '--mark-legacy', stdout=out)

        integration.refresh_from_db()
        config = integration.get_config()
        assert config['_legacy'] is True


@pytest.mark.django_db
class TestMigrateIntegrationsDryRun(TestCase):

    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='terraform', name='Terraform', version='1.0', is_active=False
        )

    def test_dry_run_no_changes(self):
        """AC10: --dry-run shows what would change without modifying DB."""
        integration = Integration.objects.create(
            type='terraform', name='TF DryRun', base_url='https://tf.example.com',
            status=IntegrationStatus.VALID,
        )

        out = StringIO()
        call_command('migrate_integrations', '--auto', '--dry-run', stdout=out)
        output = out.getvalue()

        assert 'DRY-RUN' in output
        assert 'TF DryRun' in output
        assert 'seraient mises à jour' in output

        # DB should NOT be updated
        integration.refresh_from_db()
        assert integration.status == IntegrationStatus.VALID

        # No audit entries
        assert AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
        ).count() == 0

    def test_dry_run_mark_legacy_no_changes(self):
        """AC10: --mark-legacy --dry-run does not modify config."""
        integration = Integration.objects.create(
            type='unknown', name='Unknown DryRun', base_url='https://u.example.com',
            status=IntegrationStatus.INVALID,
            config=json.dumps({'timeout': 30}),
        )

        out = StringIO()
        call_command('migrate_integrations', '--mark-legacy', '--dry-run', stdout=out)
        output = out.getvalue()

        assert 'DRY-RUN' in output

        integration.refresh_from_db()
        config = integration.get_config()
        assert '_legacy' not in config

        # No audit entries
        assert AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_MARKED_LEGACY,
        ).count() == 0
