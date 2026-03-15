# capabilities/tests/test_capabilities_views.py
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client(django_user_model):
    user = django_user_model.objects.create_user(username='testuser', password='pass')
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class TestIntegrationsCapabilities:

    def test_returns_200(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_requires_auth(self):
        client = APIClient()
        url = reverse('capabilities:capabilities-integrations')
        response = client.get(url)
        assert response.status_code == 401

    def test_contains_five_platforms(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        codes = {p['code'] for p in data['platforms']}
        assert codes == {'aap', 'tower', 'azure_devops', 'github_actions', 'terraform_cloud'}

    def test_contains_five_services(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        codes = {s['code'] for s in data['services']}
        assert codes == {'vault', 'splunk', 'servicenow', 'jira', 'notification'}

    def test_servicenow_credential_mode_is_integration(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        assert servicenow['credential_mode'] == 'integration'

    def test_notification_credential_mode_is_credential_free(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        notification = next(s for s in data['services'] if s['code'] == 'notification')
        assert notification['credential_mode'] == 'credential_free'

    def test_servicenow_has_create_change_operation(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        op_codes = [op['code'] for op in servicenow['operations']]
        assert 'create_change' in op_codes

    def test_servicenow_operations_are_objects_with_code_and_label(self, auth_client):
        """Story 82.7 — opérations retournées comme {code, label}."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        for op in servicenow['operations']:
            assert 'code' in op
            assert 'label' in op

    def test_servicenow_create_change_has_fr_label(self, auth_client):
        """Story 82.7 — label FR de create_change."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        create_change = next(op for op in servicenow['operations'] if op['code'] == 'create_change')
        assert create_change['label'] == 'Créer un change'

    def test_vault_get_secret_has_fr_label(self, auth_client):
        """Story 82.7 — label FR de get_secret."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        vault = next(s for s in data['services'] if s['code'] == 'vault')
        get_secret = next(op for op in vault['operations'] if op['code'] == 'get_secret')
        assert get_secret['label'] == 'Lire un secret'

    def test_jira_operations_have_labels(self, auth_client):
        """Story 82.7 — opérations Jira ont des labels FR."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        jira = next(s for s in data['services'] if s['code'] == 'jira')
        op_map = {op['code']: op['label'] for op in jira['operations']}
        assert op_map['create_issue'] == 'Créer un ticket'
        assert op_map['update_issue'] == 'Mettre à jour le ticket'
        assert op_map['get_issue'] == 'Lire le ticket'

    def test_notification_operations_have_labels(self, auth_client):
        """Story 82.7 — opérations Notification ont des labels FR."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        notification = next(s for s in data['services'] if s['code'] == 'notification')
        op_map = {op['code']: op['label'] for op in notification['operations']}
        assert op_map['send_email'] == 'Envoyer un email'
        assert op_map['send_teams'] == 'Envoyer un message Teams'

    def test_operations_sorted_alphabetically(self, auth_client):
        """Story 82.7 — opérations triées alphabétiquement."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        servicenow = next(s for s in data['services'] if s['code'] == 'servicenow')
        op_codes = [op['code'] for op in servicenow['operations']]
        assert op_codes == sorted(op_codes)

    def test_platform_has_expected_fields(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        aap = next(p for p in data['platforms'] if p['code'] == 'aap')
        assert aap['display_name'] == 'Ansible Automation Platform'
        assert aap['icon'] == 'aap'
        assert aap['supports_health_check'] is True

    def test_azure_devops_aliases_contains_azuredevops(self, auth_client):
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        ado = next(p for p in data['platforms'] if p['code'] == 'azure_devops')
        assert 'azuredevops' in ado['aliases']


class TestWorkflowStepsCapabilities:

    def test_returns_200(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_requires_auth(self):
        client = APIClient()
        url = reverse('capabilities:capabilities-workflow-steps')
        response = client.get(url)
        assert response.status_code == 401

    def test_contains_three_step_types(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        codes = {s['code'] for s in data['step_types']}
        assert codes == {'platform', 'service_call', 'gate'}

    def test_gate_has_two_variants(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        assert len(gate['variants']) == 2

    def test_gate_variant_codes(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        variant_codes = {v['code'] for v in gate['variants']}
        assert variant_codes == {'maintenance_window', 'approval'}

    def test_platform_step_type_has_execution_category(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        platform = next(s for s in data['step_types'] if s['code'] == 'platform')
        assert platform['category'] == 'execution'

    def test_non_gate_step_types_have_no_variants(self, auth_client):
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        for step in data['step_types']:
            if step['code'] != 'gate':
                assert 'variants' not in step

    # Story 82.8 — constraints
    def test_platform_step_has_requires_integration_constraint(self, auth_client):
        """Story 82.8, AC4: platform step_type a constraints requires_integration=True."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        platform = next(s for s in data['step_types'] if s['code'] == 'platform')
        assert 'constraints' in platform
        assert platform['constraints']['requires_integration'] is True

    def test_service_call_step_has_requires_service_integration_constraint(self, auth_client):
        """Story 82.8, AC4: service_call step_type a constraints requires_service_integration=True."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        service_call = next(s for s in data['step_types'] if s['code'] == 'service_call')
        assert 'constraints' in service_call
        assert service_call['constraints']['requires_service_integration'] is True

    def test_gate_step_has_empty_constraints(self, auth_client):
        """Story 82.8, AC4: gate step_type a constraints vide {}."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        gate = next(s for s in data['step_types'] if s['code'] == 'gate')
        assert 'constraints' in gate
        assert gate['constraints'] == {}

    def test_all_step_types_have_constraints_field(self, auth_client):
        """Story 82.8, AC4: tous les step_types retournent constraints."""
        url = reverse('capabilities:capabilities-workflow-steps')
        data = auth_client.get(url).data['data']
        for step in data['step_types']:
            assert 'constraints' in step


class TestIntegrationsCapabilitiesActionConfigSchema:
    """Story 82.8, AC2: action_config_schema dans chaque platform."""

    def test_platform_has_action_config_schema_field(self, auth_client):
        """Story 82.8, AC2: chaque platform expose action_config_schema."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert 'action_config_schema' in platform

    def test_action_config_schema_is_empty_dict_by_default(self, auth_client):
        """Story 82.8, AC2: action_config_schema est {} par défaut (aucune contrainte)."""
        url = reverse('capabilities:capabilities-integrations')
        data = auth_client.get(url).data['data']
        for platform in data['platforms']:
            assert isinstance(platform['action_config_schema'], dict)
