"""
Tests for output_schemas views.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
Story 63.2 - Registre des Schémas & Résolution (endpoints discovery).
"""

import pytest
import yaml
from rest_framework.test import APIClient

from catalog.models import Action, ActionItemType
from idp_auth.models import User
from output_schemas.models import OutputSchema, SchemaType
from output_schemas.registry import schema_registry


def make_schema(name, schema_type=SchemaType.ACTION, target_name='flyway-migrate', **kwargs):
    defaults = {'schema_json': {'output_fields': []}}
    defaults.update(kwargs)
    return OutputSchema.objects.create(name=name, schema_type=schema_type, target_name=target_name, **defaults)


@pytest.mark.django_db
class TestOutputSchemaViewSetPublic:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_list_returns_200(self):
        make_schema('schema-a')
        make_schema('schema-b', schema_type=SchemaType.INTEGRATION, target_name='servicenow', operation='create_change')
        response = self.client.get('/api/v1/output-schemas/')
        assert response.status_code == 200

    def test_list_contains_schemas(self):
        make_schema('schema-c')
        response = self.client.get('/api/v1/output-schemas/')
        # CustomPageNumberPagination uses 'data' key
        names = [r['name'] for r in response.data['data']]
        assert 'schema-c' in names

    def test_list_pagination_keys(self):
        response = self.client.get('/api/v1/output-schemas/')
        assert response.status_code == 200
        assert 'data' in response.data
        assert 'pagination' in response.data

    def test_detail_returns_200(self):
        schema = make_schema('schema-d')
        response = self.client.get(f'/api/v1/output-schemas/{schema.pk}/')
        assert response.status_code == 200
        assert response.data['name'] == 'schema-d'

    def test_detail_404_not_found(self):
        response = self.client.get('/api/v1/output-schemas/99999/')
        assert response.status_code == 404

    def test_filter_by_schema_type(self):
        make_schema('action-schema', schema_type=SchemaType.ACTION, target_name='aap-run')
        make_schema('integ-schema', schema_type=SchemaType.INTEGRATION, target_name='servicenow', operation='op')
        response = self.client.get('/api/v1/output-schemas/?schema_type=action')
        results = response.data['data']
        assert all(r['schema_type'] == 'action' for r in results)

    def test_filter_by_target_name(self):
        make_schema('schema-aap', schema_type=SchemaType.ACTION, target_name='aap')
        make_schema('schema-flyway', schema_type=SchemaType.ACTION, target_name='flyway')
        response = self.client.get('/api/v1/output-schemas/?target_name=aap')
        results = response.data['data']
        assert all(r['target_name'] == 'aap' for r in results)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get('/api/v1/output-schemas/')
        assert response.status_code == 401

    def test_write_not_allowed(self):
        response = self.client.post('/api/v1/output-schemas/', data={}, format='json')
        assert response.status_code == 405

    def test_put_not_allowed(self):
        schema = make_schema('schema-put')
        response = self.client.put(f'/api/v1/output-schemas/{schema.pk}/', data={}, format='json')
        assert response.status_code == 405

    def test_delete_not_allowed(self):
        schema = make_schema('schema-del')
        response = self.client.delete(f'/api/v1/output-schemas/{schema.pk}/')
        assert response.status_code == 405


@pytest.mark.django_db
class TestAdminExportView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin', profile='DBOPS')
        self.non_admin = User.objects.create(username='nonstaff', profile='DBA')

    def test_export_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get('/api/v1/admin/output-schemas/export/yaml/')
        assert response.status_code == 403

    def test_export_returns_yaml(self):
        make_schema('export-schema')
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/output-schemas/export/yaml/')
        assert response.status_code == 200
        parsed = yaml.safe_load(response.content)
        assert 'items' in parsed

    def test_export_empty_returns_empty_items(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/output-schemas/export/yaml/')
        assert response.status_code == 200
        parsed = yaml.safe_load(response.content)
        assert parsed['items'] == []


@pytest.mark.django_db
class TestAdminSyncView:
    VALID_YAML = """items:
  - apiVersion: idp/v1
    kind: OutputSchema
    metadata:
      name: sync-schema-1
      schema_type: action
      target_name: flyway-migrate
      operation: null
    spec:
      inherits_from: null
      output_fields:
        - name: result
          type: string
"""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin2', profile='DBOPS')
        self.non_admin = User.objects.create(username='nonstaff2', profile='DBA')

    def test_sync_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 403

    def test_sync_additive_creates_schemas(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 200
        data = response.data['data']
        assert data['created'] == 1
        assert OutputSchema.objects.filter(name='sync-schema-1').exists()

    def test_sync_invalid_mode_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/?mode=invalid',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 400

    def test_sync_no_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/',
            data={},
            format='multipart'
        )
        assert response.status_code == 400

    def test_sync_full_mode_removes_absent(self):
        make_schema('will-be-deleted', target_name='old')
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/?mode=full',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 200
        data = response.data['data']
        assert data['deleted'] == 1
        assert not OutputSchema.objects.filter(name='will-be-deleted').exists()


# ---------------------------------------------------------------------------
# Story 63.2: Tests pour les endpoints discovery
# ---------------------------------------------------------------------------


def make_workflow(name, steps=None):
    """Créer une Action de type workflow pour les tests."""
    return Action.objects.create(
        name=name,
        item_type=ActionItemType.WORKFLOW,
        execution_steps=steps or [],
    )


def make_action_catalog(name, platform='AAP'):
    """Créer une Action de type action pour les tests."""
    return Action.objects.create(
        name=name,
        item_type=ActionItemType.ACTION,
        platform=platform,
    )


@pytest.mark.django_db
class TestGetStepOutputSchema:
    """Tests pour GET /api/v1/output-schemas/workflows/{id}/steps/{step_id}/output-schema/"""

    def setup_method(self):
        schema_registry.invalidate()
        self.client = APIClient()
        self.user = User.objects.create(username='testuser-discovery', profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_step_platform_with_schema(self):
        """AC4: Step platform avec schéma — retourne le schéma résolu."""
        ref_action = make_action_catalog('flyway-migrate-v2')
        workflow = make_workflow('wf-test-platform', steps=[
            {
                'step_id': 'step-1',
                'step_type': 'platform',
                'name': 'Flyway Migrate',
                'referenced_action_id': ref_action.id,
            }
        ])
        OutputSchema.objects.create(
            name='flyway-migrate-v2-schema',
            schema_type=SchemaType.ACTION,
            target_name='flyway-migrate-v2',
            schema_json={'output_fields': [{'name': 'migrations_applied', 'type': 'integer'}]},
        )
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/step-1/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['step_id'] == 'step-1'
        assert response.data['step_type'] == 'platform'
        assert response.data['schema'] is not None
        assert response.data['schema']['output_fields'][0]['name'] == 'migrations_applied'

    def test_step_service_call_with_schema(self):
        """AC4: Step service_call — retourne le schéma résolu."""
        workflow = make_workflow('wf-test-service-call', steps=[
            {
                'step_id': 'step-sn',
                'step_type': 'service_call',
                'name': 'Create Change',
                'integration_type': 'servicenow',
                'operation': 'create_change',
            }
        ])
        OutputSchema.objects.create(
            name='sn-create-change-schema',
            schema_type=SchemaType.INTEGRATION,
            target_name='servicenow',
            operation='create_change',
            schema_json={'output_fields': [{'name': 'change_number', 'type': 'string'}]},
        )
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/step-sn/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['step_id'] == 'step-sn'
        assert response.data['schema'] is not None
        assert response.data['schema']['output_fields'][0]['name'] == 'change_number'

    def test_step_gate_no_schema(self):
        """AC4: Step gate (pas de schéma) — retourne schema=null."""
        workflow = make_workflow('wf-test-gate', steps=[
            {
                'step_id': 'gate-1',
                'step_type': 'gate',
                'name': 'Approval Gate',
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/gate-1/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['step_id'] == 'gate-1'
        assert response.data['schema'] is None

    def test_workflow_not_found_returns_404(self):
        """AC4: Workflow inexistant → 404."""
        url = '/api/v1/output-schemas/workflows/99999/steps/step-1/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 404

    def test_step_not_found_returns_404(self):
        """AC4: Step inexistant dans le workflow → 404."""
        workflow = make_workflow('wf-test-step-missing', steps=[
            {'step_id': 'step-existing', 'step_type': 'gate', 'name': 'Gate'}
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/step-inexistant/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 404

    def test_requires_authentication(self):
        """AC4: Endpoint protégé — 401 sans authentification."""
        self.client.force_authenticate(user=None)
        url = '/api/v1/output-schemas/workflows/1/steps/step-1/output-schema/'
        response = self.client.get(url)
        assert response.status_code in (401, 403)

    def test_step_platform_without_schema_falls_back_to_aap_convention(self):
        """AC1: Step platform sans schéma action → fallback convention AAP."""
        OutputSchema.objects.create(
            name='aap-standard',
            schema_type=SchemaType.PLATFORM_CONVENTION,
            target_name='aap',
            schema_json={'output_fields': [
                {'name': 'platform_job_id', 'type': 'string'},
                {'name': 'job_status', 'type': 'string'},
            ]},
        )
        ref_action = make_action_catalog('action-sans-schema')
        workflow = make_workflow('wf-fallback-platform', steps=[
            {
                'step_id': 'step-aap',
                'step_type': 'platform',
                'name': 'AAP Step',
                'referenced_action_id': ref_action.id,
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/step-aap/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['step_id'] == 'step-aap'
        assert response.data['schema'] is not None
        field_names = [f['name'] for f in response.data['schema']['output_fields']]
        assert 'platform_job_id' in field_names
        assert 'job_status' in field_names

    def test_step_platform_without_schema_no_convention_returns_null(self):
        """AC1 condition 3: Step platform sans schéma action ET sans convention AAP → schema:null."""
        ref_action = make_action_catalog('action-sans-schema-ni-convention')
        workflow = make_workflow('wf-no-convention-step', steps=[
            {
                'step_id': 'step-aap',
                'step_type': 'platform',
                'name': 'AAP Step',
                'referenced_action_id': ref_action.id,
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/step-aap/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['step_id'] == 'step-aap'
        assert response.data['schema'] is None

    def test_step_platform_action_does_not_exist_falls_back_to_aap_convention(self):
        """AC1 + Tâche 1 subtask: Action.DoesNotExist → schema null (pas d'action pour résoudre la plateforme)."""
        OutputSchema.objects.create(
            name='aap-standard',
            schema_type=SchemaType.PLATFORM_CONVENTION,
            target_name='aap',
            schema_json={'output_fields': [
                {'name': 'platform_job_id', 'type': 'string'},
                {'name': 'job_status', 'type': 'string'},
            ]},
        )
        ref_action = make_action_catalog('action-to-delete')
        deleted_id = ref_action.id
        ref_action.delete()
        workflow = make_workflow('wf-action-deleted', steps=[
            {
                'step_id': 'step-aap',
                'step_type': 'platform',
                'name': 'AAP Step',
                'referenced_action_id': deleted_id,
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/step-aap/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['step_id'] == 'step-aap'
        # Action supprimée → pas d'objet Action pour résoudre la plateforme → schema null
        assert response.data['schema'] is None

    def test_step_platform_no_referenced_action_falls_back_to_aap_convention(self):
        """Dev Notes: Step platform sans referenced_action_id → schema null (pas d'action pour résoudre la plateforme)."""
        OutputSchema.objects.create(
            name='aap-standard',
            schema_type=SchemaType.PLATFORM_CONVENTION,
            target_name='aap',
            schema_json={'output_fields': [
                {'name': 'platform_job_id', 'type': 'string'},
                {'name': 'job_status', 'type': 'string'},
            ]},
        )
        workflow = make_workflow('wf-platform-no-ref', steps=[
            {
                'step_id': 'step-aap',
                'step_type': 'platform',
                'name': 'AAP Step',
                # pas de referenced_action_id
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/steps/step-aap/output-schema/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data['step_id'] == 'step-aap'
        # Pas de referenced_action_id → pas d'action pour résoudre la plateforme → schema null
        assert response.data['schema'] is None


@pytest.mark.django_db
class TestGetAvailableVariables:
    """Tests pour GET /api/v1/output-schemas/workflows/{id}/available-variables/"""

    def setup_method(self):
        schema_registry.invalidate()
        self.client = APIClient()
        self.user = User.objects.create(username='testuser-vars', profile='DBA')
        self.client.force_authenticate(user=self.user)

    def test_workflow_with_multiple_steps(self):
        """AC5: Retourne les variables de tous les steps schématisés."""
        ref_action = make_action_catalog('terraform-plan-test')
        workflow = make_workflow('wf-multi-steps', steps=[
            {
                'step_id': 'step-1',
                'step_type': 'platform',
                'name': 'Terraform Plan',
                'referenced_action_id': ref_action.id,
            },
            {
                'step_id': 'step-2',
                'step_type': 'gate',
                'name': 'Approval',
            },
        ])
        OutputSchema.objects.create(
            name='terraform-plan-schema',
            schema_type=SchemaType.ACTION,
            target_name='terraform-plan-test',
            schema_json={'output_fields': [
                {'name': 'plan_output', 'type': 'string', 'description': 'Terraform plan'},
                {'name': 'resource_count', 'type': 'integer', 'description': 'Resources to change'},
            ]},
        )
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/available-variables/'
        response = self.client.get(url)
        assert response.status_code == 200
        result = response.data
        # Seul step-1 a un schéma, step-2 (gate) est exclu
        assert len(result) == 1
        assert result[0]['step_id'] == 'step-1'
        assert result[0]['step_name'] == 'Terraform Plan'
        var_names = [v['name'] for v in result[0]['variables']]
        assert 'plan_output' in var_names
        assert 'resource_count' in var_names

    def test_workflow_without_schemas(self):
        """AC5: Workflow sans aucun step schématisé — retourne liste vide."""
        workflow = make_workflow('wf-no-schemas', steps=[
            {'step_id': 'gate-1', 'step_type': 'gate', 'name': 'Gate'},
            {'step_id': 'gate-2', 'step_type': 'gate', 'name': 'Gate 2'},
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/available-variables/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == []

    def test_workflow_not_found_returns_404(self):
        """AC5: Workflow inexistant → 404."""
        url = '/api/v1/output-schemas/workflows/99998/available-variables/'
        response = self.client.get(url)
        assert response.status_code == 404

    def test_requires_authentication(self):
        """AC5: Endpoint protégé — 401/403 sans authentification."""
        self.client.force_authenticate(user=None)
        url = '/api/v1/output-schemas/workflows/1/available-variables/'
        response = self.client.get(url)
        assert response.status_code in (401, 403)

    def test_available_variables_platform_falls_back_to_aap_convention(self):
        """AC2: Step platform sans schéma action → variables AAP dans le résultat."""
        OutputSchema.objects.create(
            name='aap-standard',
            schema_type=SchemaType.PLATFORM_CONVENTION,
            target_name='aap',
            schema_json={'output_fields': [
                {'name': 'platform_job_id', 'type': 'string'},
                {'name': 'job_status', 'type': 'string'},
            ]},
        )
        ref_action = make_action_catalog('aap-action-no-schema')
        workflow = make_workflow('wf-fallback-vars', steps=[
            {
                'step_id': 'step-aap',
                'step_type': 'platform',
                'name': 'AAP Run',
                'referenced_action_id': ref_action.id,
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/available-variables/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]['step_id'] == 'step-aap'
        var_names = [v['name'] for v in response.data[0]['variables']]
        assert 'platform_job_id' in var_names
        assert 'job_status' in var_names

    def test_available_variables_platform_no_convention_excluded(self):
        """AC2: Step platform sans schéma action NI convention AAP → step exclu."""
        ref_action = make_action_catalog('aap-action-truly-no-schema')
        workflow = make_workflow('wf-no-convention', steps=[
            {
                'step_id': 'step-aap',
                'step_type': 'platform',
                'name': 'AAP Run',
                'referenced_action_id': ref_action.id,
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/available-variables/'
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.data == []

    def test_available_variables_platform_no_referenced_action_falls_back_to_convention(self):
        """Dev Notes: Step platform sans referenced_action_id → step exclu (pas d'action pour résoudre la plateforme)."""
        OutputSchema.objects.create(
            name='aap-standard',
            schema_type=SchemaType.PLATFORM_CONVENTION,
            target_name='aap',
            schema_json={'output_fields': [
                {'name': 'platform_job_id', 'type': 'string'},
                {'name': 'job_status', 'type': 'string'},
            ]},
        )
        workflow = make_workflow('wf-vars-no-ref', steps=[
            {
                'step_id': 'step-aap',
                'step_type': 'platform',
                'name': 'AAP Run',
                # pas de referenced_action_id
            }
        ])
        url = f'/api/v1/output-schemas/workflows/{workflow.id}/available-variables/'
        response = self.client.get(url)
        assert response.status_code == 200
        # Pas de referenced_action_id → pas d'action pour résoudre la plateforme → step exclu
        assert response.data == []
