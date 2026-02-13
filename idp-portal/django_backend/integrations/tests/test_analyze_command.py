"""
Story 24.4 (AC1, AC6): Tests for analyze_integrations management command.
"""

import json
import os
import pytest
from django.test import TestCase
from django.core.management import call_command
from io import StringIO

from integrations.models import Integration, IntegrationStatus, IntegrationTypeCatalogue


@pytest.mark.django_db
class TestAnalyzeIntegrationsCommand(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Clean up any pre-existing JSON files before all tests
        import glob
        for f in glob.glob('logs/integrations/integration_analysis_*.json'):
            os.remove(f)

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

    def tearDown(self):
        # Clean up any generated JSON files (MEDIUM-1 FIX: now in logs/integrations/)
        import glob
        import shutil
        # Remove individual files
        for f in glob.glob('logs/integrations/integration_analysis_*.json'):
            os.remove(f)
        # Remove directory if empty
        if os.path.exists('logs/integrations') and not os.listdir('logs/integrations'):
            shutil.rmtree('logs')  # Remove logs/ if it's now empty

    def test_analyze_integrations_report_valid(self):
        Integration.objects.create(
            type='aap', name='AAP Dev', base_url='https://aap.dev.example.com'
        )
        Integration.objects.create(
            type='servicenow', name='ServiceNow ITSM', base_url='https://sn.example.com'
        )

        out = StringIO()
        call_command('analyze_integrations', stdout=out)
        output = out.getvalue()

        assert 'Valides' in output
        assert 'AAP Dev' in output
        assert 'ServiceNow ITSM' in output
        assert '2 types actifs' in output

    def test_analyze_integrations_report_deprecated(self):
        Integration.objects.create(
            type='terraform', name='Terraform Cloud', base_url='https://tf.example.com'
        )

        out = StringIO()
        call_command('analyze_integrations', stdout=out)
        output = out.getvalue()

        assert 'Dépréciées' in output
        assert 'Terraform Cloud' in output
        assert 'type déprécié' in output

    def test_analyze_integrations_report_invalid(self):
        Integration.objects.create(
            type='jenkins', name='Legacy Jenkins', base_url='https://jenkins.example.com'
        )

        out = StringIO()
        call_command('analyze_integrations', stdout=out)
        output = out.getvalue()

        assert 'Invalides' in output
        assert 'Legacy Jenkins' in output
        assert 'type inconnu' in output
        assert 'ATTENTION' in output

    def test_analyze_integrations_json_report(self):
        Integration.objects.create(
            type='aap', name='AAP Valid', base_url='https://aap.example.com'
        )
        Integration.objects.create(
            type='jenkins', name='Jenkins Invalid', base_url='https://jenkins.example.com'
        )

        out = StringIO()
        call_command('analyze_integrations', stdout=out)

        # Find the generated JSON file (MEDIUM-1 FIX: now in logs/integrations/)
        import glob
        json_files = glob.glob('logs/integrations/integration_analysis_*.json')
        assert len(json_files) == 1

        with open(json_files[0], 'r') as f:
            report = json.load(f)

        assert report['integrations_total'] == 2
        assert report['integrations_valid'] == 1
        assert report['integrations_invalid'] == 1
        assert len(report['details']['valid']) == 1
        assert len(report['details']['invalid']) == 1
        assert report['details']['valid'][0]['name'] == 'AAP Valid'
        assert report['details']['invalid'][0]['name'] == 'Jenkins Invalid'

    def test_analyze_integrations_no_data_modification(self):
        """Verify analyze command does NOT modify any integration data."""
        integration = Integration.objects.create(
            type='jenkins', name='Should Stay Valid', base_url='https://j.example.com',
            status=IntegrationStatus.VALID,
        )

        out = StringIO()
        call_command('analyze_integrations', stdout=out)

        integration.refresh_from_db()
        assert integration.status == IntegrationStatus.VALID  # NOT changed

    def test_analyze_integrations_mixed(self):
        """Full report with valid, deprecated, and invalid integrations."""
        Integration.objects.create(type='aap', name='AAP Ok', base_url='https://a.com')
        Integration.objects.create(type='terraform', name='TF Dep', base_url='https://b.com')
        Integration.objects.create(type='unknown_type', name='Unknown', base_url='https://c.com')

        out = StringIO()
        call_command('analyze_integrations', stdout=out)
        output = out.getvalue()

        assert '3 total' in output
        assert 'AAP Ok' in output
        assert 'TF Dep' in output
        assert 'Unknown' in output
