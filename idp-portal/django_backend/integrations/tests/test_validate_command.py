"""
Story 24.3: Tests for validate_integrations management command.
"""

import pytest
from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from integrations.models import Integration, IntegrationStatus, IntegrationTypeCatalogue


@pytest.mark.django_db
class TestValidateIntegrationsCommand(TestCase):

    def setUp(self):
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='old_type', name='Old', version='1.0', is_active=False
        )

    def test_command_reports_valid_integrations(self):
        Integration.objects.create(
            type='aap', name='Valid', base_url='https://aap.example.com'
        )
        out = StringIO()
        call_command('validate_integrations', stdout=out)
        output = out.getvalue()
        assert 'Valid: 1' in output
        assert 'All integrations validated successfully' in output

    def test_command_exit_code_1_if_invalid(self):
        Integration.objects.create(
            type='nonexistent', name='Invalid', base_url='https://inv.example.com'
        )
        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command('validate_integrations', stdout=out)
        assert exc_info.value.code == 1

    def test_command_dry_run_does_not_update_db(self):
        Integration.objects.create(
            type='old_type', name='DryRun', base_url='https://dep.example.com',
            status=IntegrationStatus.VALID,
        )
        out = StringIO()
        call_command('validate_integrations', '--dry-run', stdout=out)
        output = out.getvalue()
        assert 'DRY-RUN' in output
        assert 'Deprecated: 1' in output
        # DB should NOT be updated
        assert Integration.objects.get(name='DryRun').status == IntegrationStatus.VALID

    def test_command_reports_deprecated(self):
        Integration.objects.create(
            type='old_type', name='Dep', base_url='https://dep.example.com'
        )
        out = StringIO()
        call_command('validate_integrations', stdout=out)
        output = out.getvalue()
        assert 'Deprecated: 1' in output
