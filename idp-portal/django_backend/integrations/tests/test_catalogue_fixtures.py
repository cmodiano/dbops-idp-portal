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

    # ------------------------------------------------------------------
    # Story 27.10: Jira catalogue fixture tests (AC5)
    # ------------------------------------------------------------------

    def test_jira_type_created(self):
        """AC5: IntegrationTypeCatalogue jira exists after loaddata."""
        jira = IntegrationTypeCatalogue.objects.get(code='jira')
        assert jira.name == 'Jira'
        assert jira.is_active is True
        assert jira.version == '1.0'

    def test_jira_has_4_actions(self):
        """AC5: 4 IntegrationAction for jira."""
        actions = IntegrationAction.objects.filter(integration_type__code='jira')
        assert actions.count() == 4
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == ['add_comment', 'create_issue', 'get_issue', 'update_issue']

    def test_jira_create_issue_required_params_valid_json_schema(self):
        """AC5: required_params is valid JSON Schema."""
        action = IntegrationAction.objects.get(
            integration_type__code='jira', action_code='create_issue'
        )
        params = action.get_required_params()
        assert params['type'] == 'object'
        assert 'properties' in params
        assert 'project_key' in params['properties']
        assert 'issue_type' in params['properties']
        assert 'summary' in params['properties']
        assert params.get('required') == ['project_key', 'issue_type', 'summary']

    def test_jira_create_issue_optional_params_valid_json_schema(self):
        """AC5: optional_params is valid JSON Schema."""
        action = IntegrationAction.objects.get(
            integration_type__code='jira', action_code='create_issue'
        )
        params = action.get_optional_params()
        assert params['type'] == 'object'
        assert 'properties' in params
        assert 'description' in params['properties']
        assert 'assignee' in params['properties']
        assert 'labels' in params['properties']

    def test_jira_actions_response_format_valid(self):
        """AC5: response_format is valid JSON for all jira actions."""
        actions = IntegrationAction.objects.filter(integration_type__code='jira')
        for action in actions:
            fmt = action.get_response_format()
            assert isinstance(fmt, dict), f"Invalid response_format for {action.action_code}"
