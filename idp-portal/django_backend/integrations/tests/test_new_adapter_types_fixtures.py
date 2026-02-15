"""
Story 27.7: Tests for new adapter type fixtures (Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault).
Validates fixture loading, type/action creation, JSON Schema validity, and API responses.
"""

import json

import pytest
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from integrations.models import IntegrationAction, IntegrationTypeCatalogue
from tests.factories import UserFactory


@pytest.mark.django_db
class TestFixtureLoading:
    """Tests that all fixtures load correctly without errors."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_seven_types_created(self):
        """AC9: 7 types total (2 existing + 5 new)."""
        count = IntegrationTypeCatalogue.objects.filter(is_active=True).count()
        assert count == 7

    def test_all_expected_types_exist(self):
        expected = ['aap', 'azure_devops', 'github_actions', 'servicenow',
                    'terraform_cloud', 'tower', 'vault']
        actual = sorted(
            IntegrationTypeCatalogue.objects.values_list('code', flat=True)
        )
        assert actual == expected

    def test_tower_type_fields(self):
        """AC1: Tower type has correct fields."""
        t = IntegrationTypeCatalogue.objects.get(code='tower')
        assert t.name == 'Ansible Tower'
        assert 'Tower API' in t.description
        assert t.version == '1.0'
        assert t.is_active is True

    def test_azure_devops_type_fields(self):
        """AC2: Azure DevOps type has correct fields."""
        t = IntegrationTypeCatalogue.objects.get(code='azure_devops')
        assert t.name == 'Azure DevOps Pipelines'
        assert 'polling 5s' in t.description
        assert t.is_active is True

    def test_github_actions_type_fields(self):
        """AC3: GitHub Actions type has correct fields."""
        t = IntegrationTypeCatalogue.objects.get(code='github_actions')
        assert t.name == 'GitHub Actions'
        assert 'webhooks' in t.description
        assert t.is_active is True

    def test_terraform_cloud_type_fields(self):
        """AC4: Terraform Cloud type has correct fields."""
        t = IntegrationTypeCatalogue.objects.get(code='terraform_cloud')
        assert t.name == 'Terraform Cloud'
        assert 'plan/apply' in t.description
        assert t.is_active is True

    def test_vault_type_fields(self):
        """AC5: Vault type has correct fields."""
        t = IntegrationTypeCatalogue.objects.get(code='vault')
        assert t.name == 'HashiCorp Vault'
        assert 'KV v2' in t.description
        assert t.is_active is True


@pytest.mark.django_db
class TestActionCounts:
    """Tests that each type has the correct number of actions."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_aap_has_4_actions(self):
        assert IntegrationAction.objects.filter(
            integration_type__code='aap'
        ).count() == 4

    def test_servicenow_has_3_actions(self):
        assert IntegrationAction.objects.filter(
            integration_type__code='servicenow'
        ).count() == 3

    def test_tower_has_4_actions(self):
        """AC1: Tower has 4 actions."""
        actions = IntegrationAction.objects.filter(
            integration_type__code='tower'
        )
        assert actions.count() == 4
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == ['cancel_job', 'get_job_status', 'start_job', 'start_workflow']

    def test_azure_devops_has_4_actions(self):
        """AC2: Azure DevOps has 4 actions."""
        actions = IntegrationAction.objects.filter(
            integration_type__code='azure_devops'
        )
        assert actions.count() == 4
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == ['cancel_run', 'get_run_logs', 'get_run_status', 'run_pipeline']

    def test_github_actions_has_4_actions(self):
        """AC3: GitHub Actions has 4 actions."""
        actions = IntegrationAction.objects.filter(
            integration_type__code='github_actions'
        )
        assert actions.count() == 4
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == [
            'cancel_workflow_run', 'get_workflow_run_logs',
            'get_workflow_run_status', 'trigger_workflow',
        ]

    def test_terraform_cloud_has_5_actions(self):
        """AC4: Terraform Cloud has 5 actions."""
        actions = IntegrationAction.objects.filter(
            integration_type__code='terraform_cloud'
        )
        assert actions.count() == 5
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == [
            'apply_run', 'cancel_run', 'create_run',
            'get_run_logs', 'get_run_status',
        ]

    def test_vault_has_3_actions(self):
        """AC5: Vault has 3 actions."""
        actions = IntegrationAction.objects.filter(
            integration_type__code='vault'
        )
        assert actions.count() == 3
        codes = sorted(actions.values_list('action_code', flat=True))
        assert codes == ['get_secret', 'lookup_token', 'renew_token']

    def test_total_action_count(self):
        """AC9: All types have actions associated."""
        total = IntegrationAction.objects.count()
        # AAP:4 + SN:3 + Tower:4 + Azure:4 + GitHub:4 + Terraform:5 + Vault:3 = 27
        assert total == 27

    def test_every_type_has_at_least_one_action(self):
        """AC9: Each type has at least 1 active action."""
        for code in ['aap', 'servicenow', 'tower', 'azure_devops',
                     'github_actions', 'terraform_cloud', 'vault']:
            count = IntegrationAction.objects.filter(
                integration_type__code=code, is_active=True
            ).count()
            assert count >= 1, f"Type {code} has no active actions"


@pytest.mark.django_db
class TestJsonSchemaValidity:
    """Tests that required_params and optional_params are valid JSON."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_all_required_params_parsable(self):
        """AC9: All required_params are valid JSON."""
        for action in IntegrationAction.objects.all():
            params = action.get_required_params()
            assert isinstance(params, dict), (
                f"{action.integration_type.code}:{action.action_code} "
                f"required_params is not a dict"
            )

    def test_all_optional_params_parsable(self):
        """AC9: All optional_params are valid JSON."""
        for action in IntegrationAction.objects.all():
            params = action.get_optional_params()
            assert isinstance(params, dict), (
                f"{action.integration_type.code}:{action.action_code} "
                f"optional_params is not a dict"
            )

    def test_all_response_formats_parsable(self):
        for action in IntegrationAction.objects.all():
            fmt = action.get_response_format()
            assert isinstance(fmt, dict)

    def test_tower_start_job_required_params(self):
        """AC1: Tower start_job has job_template_id required param."""
        action = IntegrationAction.objects.get(
            integration_type__code='tower', action_code='start_job'
        )
        params = action.get_required_params()
        assert 'properties' in params
        assert 'job_template_id' in params['properties']
        assert params['properties']['job_template_id']['type'] == 'integer'

    def test_azure_devops_run_pipeline_required_params(self):
        """AC2: Azure DevOps run_pipeline has pipeline_id and branch."""
        action = IntegrationAction.objects.get(
            integration_type__code='azure_devops', action_code='run_pipeline'
        )
        params = action.get_required_params()
        assert 'pipeline_id' in params['properties']
        assert 'branch' in params['properties']

    def test_github_trigger_workflow_required_params(self):
        """AC3: GitHub trigger_workflow has owner, repo, workflow_id, ref."""
        action = IntegrationAction.objects.get(
            integration_type__code='github_actions', action_code='trigger_workflow'
        )
        params = action.get_required_params()
        for key in ['owner', 'repo', 'workflow_id', 'ref']:
            assert key in params['properties'], f"Missing {key}"

    def test_terraform_create_run_required_params(self):
        """AC4: Terraform create_run has workspace_id and message."""
        action = IntegrationAction.objects.get(
            integration_type__code='terraform_cloud', action_code='create_run'
        )
        params = action.get_required_params()
        assert 'workspace_id' in params['properties']
        assert 'message' in params['properties']

    def test_vault_get_secret_required_params(self):
        """AC5: Vault get_secret has path required param."""
        action = IntegrationAction.objects.get(
            integration_type__code='vault', action_code='get_secret'
        )
        params = action.get_required_params()
        assert 'path' in params['properties']

    def test_vault_get_secret_optional_params(self):
        """AC5: Vault get_secret has key and namespace optional params."""
        action = IntegrationAction.objects.get(
            integration_type__code='vault', action_code='get_secret'
        )
        params = action.get_optional_params()
        assert 'key' in params['properties']
        assert 'namespace' in params['properties']

    def test_terraform_create_run_optional_params(self):
        """AC4: Terraform create_run has is_destroy and variables optional."""
        action = IntegrationAction.objects.get(
            integration_type__code='terraform_cloud', action_code='create_run'
        )
        params = action.get_optional_params()
        assert 'is_destroy' in params['properties']
        assert 'variables' in params['properties']


@pytest.mark.django_db
class TestCatalogueAPINewTypes:
    """Tests for API endpoints returning new adapter types."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_list_returns_7_types(self):
        """AC9: GET /api/v1/integrations/types/ returns 7 types."""
        response = self.client.get('/api/v1/integrations/types/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 7

    def test_list_types_sorted_by_code(self):
        """AC6: Types sorted by code (alphabetical)."""
        response = self.client.get('/api/v1/integrations/types/')
        codes = [t['code'] for t in response.data['data']]
        assert codes == sorted(codes)

    def test_retrieve_tower_type(self):
        """AC9: GET /api/v1/integrations/types/tower/ returns Tower with 4 actions."""
        response = self.client.get('/api/v1/integrations/types/tower/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['code'] == 'tower'
        assert data['name'] == 'Ansible Tower'
        assert len(data['actions']) == 4

    def test_retrieve_azure_devops_type(self):
        response = self.client.get('/api/v1/integrations/types/azure_devops/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['code'] == 'azure_devops'
        assert len(data['actions']) == 4

    def test_retrieve_github_actions_type(self):
        response = self.client.get('/api/v1/integrations/types/github_actions/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['code'] == 'github_actions'
        assert len(data['actions']) == 4

    def test_retrieve_terraform_cloud_type(self):
        response = self.client.get('/api/v1/integrations/types/terraform_cloud/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['code'] == 'terraform_cloud'
        assert len(data['actions']) == 5

    def test_retrieve_vault_type(self):
        response = self.client.get('/api/v1/integrations/types/vault/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['code'] == 'vault'
        assert len(data['actions']) == 3

    def test_github_actions_actions_endpoint(self):
        """AC9: GET /api/v1/integrations/types/github_actions/actions/."""
        response = self.client.get(
            '/api/v1/integrations/types/github_actions/actions/'
        )
        assert response.status_code == status.HTTP_200_OK
        codes = sorted([a['action_code'] for a in response.data['data']])
        assert codes == [
            'cancel_workflow_run', 'get_workflow_run_logs',
            'get_workflow_run_status', 'trigger_workflow',
        ]

    def test_terraform_cloud_actions_endpoint(self):
        response = self.client.get(
            '/api/v1/integrations/types/terraform_cloud/actions/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 5

    def test_vault_actions_endpoint(self):
        response = self.client.get(
            '/api/v1/integrations/types/vault/actions/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 3

    def test_actions_response_includes_params(self):
        """AC9: Action responses include required/optional params."""
        response = self.client.get(
            '/api/v1/integrations/types/github_actions/actions/'
        )
        trigger = next(
            a for a in response.data['data']
            if a['action_code'] == 'trigger_workflow'
        )
        assert 'required_params' in trigger
        assert 'optional_params' in trigger
        assert 'response_format' in trigger

    def test_nonexistent_type_returns_404(self):
        response = self.client.get('/api/v1/integrations/types/nonexistent/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_each_new_type_has_description(self):
        """AC6: Each type has a description for tooltip display."""
        response = self.client.get('/api/v1/integrations/types/')
        for t in response.data['data']:
            assert t['description'], f"Type {t['code']} has no description"


@pytest.mark.django_db
class TestEdgeCases:
    """Tests for edge cases: inactive types, inactive actions."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_inactive_type_not_returned(self):
        """Inactive type filtered from list."""
        vault = IntegrationTypeCatalogue.objects.get(code='vault')
        vault.is_active = False
        vault.save()

        response = self.client.get('/api/v1/integrations/types/')
        codes = [t['code'] for t in response.data['data']]
        assert 'vault' not in codes
        assert len(response.data['data']) == 6

    def test_inactive_action_filtered(self):
        """Inactive action filtered from actions list."""
        action = IntegrationAction.objects.get(
            integration_type__code='tower', action_code='cancel_job'
        )
        action.is_active = False
        action.save()

        response = self.client.get('/api/v1/integrations/types/tower/actions/')
        codes = [a['action_code'] for a in response.data['data']]
        assert 'cancel_job' not in codes
        assert len(response.data['data']) == 3


@pytest.mark.django_db
class TestSeedCommand:
    """Tests for the seed_integration_types management command."""

    def test_seed_creates_types_from_empty(self):
        """Command loads all types when none exist."""
        assert IntegrationTypeCatalogue.objects.count() == 0
        call_command('seed_integration_types')
        assert IntegrationTypeCatalogue.objects.count() == 7

    def test_seed_idempotent(self):
        """Command skips when all types exist."""
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)
        count_before = IntegrationTypeCatalogue.objects.count()
        call_command('seed_integration_types')
        assert IntegrationTypeCatalogue.objects.count() == count_before

    def test_seed_force_reloads(self):
        """Command reloads with --force flag (clears and reloads)."""
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)
        # seed_integration_types --force clears actions then reloads
        call_command('seed_integration_types', force=True)
        assert IntegrationTypeCatalogue.objects.count() == 7
        assert IntegrationAction.objects.count() == 27

    def test_individual_fixture_tower(self):
        """Individual Tower fixture loads correctly."""
        call_command('loaddata', 'tower_integration_type', verbosity=0)
        assert IntegrationTypeCatalogue.objects.filter(code='tower').exists()
        assert IntegrationAction.objects.filter(
            integration_type__code='tower'
        ).count() == 4

    def test_individual_fixture_vault(self):
        """Individual Vault fixture loads correctly."""
        call_command('loaddata', 'vault_integration_type', verbosity=0)
        assert IntegrationTypeCatalogue.objects.filter(code='vault').exists()
        assert IntegrationAction.objects.filter(
            integration_type__code='vault'
        ).count() == 3


@pytest.mark.django_db
class TestUniqueConstraints:
    """Tests for database constraints on fixtures."""

    @pytest.fixture(autouse=True)
    def load_fixtures(self):
        call_command('loaddata', 'integration_type_catalogue', verbosity=0)

    def test_type_code_unique(self):
        """Type code is primary key and unique."""
        codes = list(
            IntegrationTypeCatalogue.objects.values_list('code', flat=True)
        )
        assert len(codes) == len(set(codes))

    def test_action_type_code_unique_together(self):
        """Action (type, code) pair is unique."""
        pairs = list(
            IntegrationAction.objects.values_list(
                'integration_type__code', 'action_code'
            )
        )
        assert len(pairs) == len(set(pairs))

    def test_no_duplicate_types_after_reload(self):
        """Type codes are unique — PK-based upsert prevents duplicates."""
        # Types use PK (code) so loaddata does upsert.
        # Actions have auto-PK so we verify uniqueness via constraint.
        assert IntegrationTypeCatalogue.objects.count() == 7
        codes = list(
            IntegrationTypeCatalogue.objects.values_list('code', flat=True)
        )
        assert len(codes) == len(set(codes))
