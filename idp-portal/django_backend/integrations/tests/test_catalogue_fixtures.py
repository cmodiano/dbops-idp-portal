"""
Story 24.1: Tests for catalogue fixtures loading.
"""

import pytest
from django.core.management import call_command

from integrations.models import IntegrationTypeCatalogue, IntegrationAction


@pytest.mark.django_db
class TestCatalogueFixtures:
    """Tests for loading the integration type catalogue fixtures."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_aap_type_created(self):
        aap = IntegrationTypeCatalogue.objects.get(code='aap')
        assert aap.name == 'Ansible Automation Platform'
        assert aap.is_active is True
        assert aap.version == '1.0'

    def test_servicenow_type_created(self):
        sn = IntegrationTypeCatalogue.objects.get(code='servicenow')
        assert sn.name == 'ServiceNow ITSM'
        assert sn.is_active is True

    def test_aap_has_4_actions(self):
        actions = IntegrationAction.objects.filter(integration_type__code='aap')
        assert actions.count() == 4
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == ['cancel_job', 'get_job_status', 'start_job', 'start_workflow']

    def test_servicenow_has_3_actions(self):
        actions = IntegrationAction.objects.filter(integration_type__code='servicenow')
        assert actions.count() == 3
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == ['create_change', 'get_change_status', 'update_change']

    def test_aap_start_job_has_required_params(self):
        action = IntegrationAction.objects.get(
            integration_type__code='aap', action_code='start_job'
        )
        params = action.get_required_params()
        assert 'properties' in params
        assert 'job_template_id' in params['properties']

    def test_servicenow_create_change_has_required_params(self):
        action = IntegrationAction.objects.get(
            integration_type__code='servicenow', action_code='create_change'
        )
        params = action.get_required_params()
        assert 'short_description' in params['properties']
        assert 'category' in params['properties']

    def test_all_actions_have_response_format(self):
        for action in IntegrationAction.objects.all():
            fmt = action.get_response_format()
            assert isinstance(fmt, dict)
