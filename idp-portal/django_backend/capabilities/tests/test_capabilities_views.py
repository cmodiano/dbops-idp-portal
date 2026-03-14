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
        assert 'create_change' in servicenow['operations']

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
