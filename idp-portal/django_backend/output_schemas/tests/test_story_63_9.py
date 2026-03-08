"""
Tests Story 63.9 — Déclarer les outputs par action.
AC #1: FK output_schema sur Action (migration + colonne Oracle)
AC #2: ActionSerializer expose output_schema_id (lecture + écriture + validation)
AC #3: get_available_variables utilise FK en priorité
AC #4: Nouveau endpoint GET /api/v1/output-schemas/actions/{id}/schema/
"""

import pytest
from django.db import connection
from rest_framework.test import APIClient

from catalog.models import Action, ActionItemType
from profiles.models import Profile
from tests.factories import UserFactory
from output_schemas.models import OutputSchema, SchemaType
from output_schemas.registry import schema_registry


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_admin_user(username='admin_63_9'):
    Profile.objects.get_or_create(
        name='DBOPS',
        defaults={'ad_group': 'CN=DBOPS', 'is_admin': 1, 'is_auditor': 0},
    )
    return UserFactory(username=username, profile='DBOPS')


def make_regular_user(username='user_63_9'):
    Profile.objects.get_or_create(
        name='DBA',
        defaults={'ad_group': 'CN=DBA', 'is_admin': 0, 'is_auditor': 0},
    )
    return UserFactory(username=username, profile='DBA')


def make_schema(name, target_name='flyway-migrate', output_fields=None, **kwargs):
    schema_json = {'output_fields': output_fields or []}
    return OutputSchema.objects.create(
        name=name, schema_type=SchemaType.ACTION, target_name=target_name,
        schema_json=schema_json, **kwargs,
    )


def make_action(name, **kwargs):
    return Action.objects.create(
        name=name, description='test', item_type=ActionItemType.ACTION,
        engine='Oracle', platform='AAP', **kwargs,
    )


def make_workflow(name, steps=None):
    return Action.objects.create(
        name=name, description='wf test', item_type=ActionItemType.WORKFLOW,
        execution_steps=steps or [],
    )


# ─── AC #1 — FK sur le modèle Action ────────────────────────────────────────

@pytest.mark.django_db
class TestMigration63_9:
    def test_action_has_output_schema_fk_field(self):
        """AC #1 : Le modèle Action a bien un champ output_schema FK."""
        schema = make_schema('schema-fk-check', target_name='my-action-fk')
        action = make_action('my-action-fk', output_schema=schema)
        action.refresh_from_db()
        assert action.output_schema_id == schema.pk

    def test_action_output_schema_null_by_default(self):
        """AC #1 : La FK output_schema est nullable par défaut."""
        action = make_action('my-action-null-fk')
        assert action.output_schema_id is None

    def test_output_schema_id_column_exists_via_introspection(self):
        """AC #1 : Colonne OUTPUT_SCHEMA_ID présente dans ACTIONS_CATALOG via connection.introspection."""
        table_name = Action._meta.db_table  # 'ACTIONS_CATALOG'
        columns = connection.introspection.get_table_description(connection.cursor(), table_name)
        column_names = [col.name.upper() for col in columns]
        assert 'OUTPUT_SCHEMA_ID' in column_names, (
            f"Colonne OUTPUT_SCHEMA_ID absente de {table_name}. Colonnes présentes : {column_names}"
        )


# ─── AC #2 — Serializer ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestActionSerializerOutputSchemaId:
    def setup_method(self):
        self.client = APIClient()
        self.admin = make_admin_user('admin63_9_ser')
        self.client.force_authenticate(user=self.admin)
        self.action = make_action('my-action-63-9-ser')

    def test_patch_output_schema_id_valid_returns_200(self):
        """AC #2 : PATCH avec output_schema_id valide → 200, valeur persistée."""
        schema = make_schema('schema-aap-63-9-ser', target_name='my-action-63-9-ser')
        response = self.client.patch(
            f'/api/v1/admin/actions/{self.action.pk}/',
            {'output_schema_id': schema.pk}, format='json',
        )
        assert response.status_code == 200, response.data
        self.action.refresh_from_db()
        assert self.action.output_schema_id == schema.pk

    def test_patch_output_schema_id_invalid_returns_400(self):
        """AC #2 : PATCH avec output_schema_id inexistant → 400."""
        response = self.client.patch(
            f'/api/v1/admin/actions/{self.action.pk}/',
            {'output_schema_id': 999999}, format='json',
        )
        assert response.status_code == 400

    def test_patch_output_schema_id_with_other_fields_persists(self):
        """Code Review Fix MEDIUM-5 : PATCH multi-champs incluant output_schema_id → champ persisté."""
        schema = make_schema('schema-multi-63-9-ser', target_name='my-action-63-9-ser')
        response = self.client.patch(
            f'/api/v1/admin/actions/{self.action.pk}/',
            {
                'output_schema_id': schema.pk,
                'description': 'updated description',
                'name': self.action.name,
                'engine': self.action.engine,
                'platform': self.action.platform,
            },
            format='json',
        )
        assert response.status_code == 200, response.data
        self.action.refresh_from_db()
        assert self.action.output_schema_id == schema.pk
        assert self.action.description == 'updated description'

    def test_patch_output_schema_id_null_allowed(self):
        """AC #2 : PATCH avec output_schema_id null → 200, champ null."""
        schema = make_schema('schema-null-63-9-ser', target_name='my-action-63-9-ser')
        self.action.output_schema = schema
        self.action.save()
        response = self.client.patch(
            f'/api/v1/admin/actions/{self.action.pk}/',
            {'output_schema_id': None}, format='json',
        )
        assert response.status_code == 200
        self.action.refresh_from_db()
        assert self.action.output_schema_id is None

    def test_action_detail_exposes_output_schema_id(self):
        """AC #2 : GET action expose output_schema_id."""
        schema = make_schema('schema-expose-63-9-ser', target_name='my-action-63-9-ser')
        self.action.output_schema = schema
        self.action.save()
        response = self.client.get(f'/api/v1/admin/actions/{self.action.pk}/')
        assert response.status_code == 200
        # Response is nested under 'data' key by the admin viewset
        action_data = response.data.get('data', response.data)
        assert action_data.get('output_schema_id') == schema.pk


# ─── AC #3 — get_available_variables : priorité FK ───────────────────────────

@pytest.mark.django_db
class TestGetAvailableVariablesWithFK:
    def setup_method(self):
        self.client = APIClient()
        self.user = make_regular_user('user63_9_avail')
        self.client.force_authenticate(user=self.user)
        schema_registry.invalidate()

    def teardown_method(self):
        schema_registry.invalidate()

    def test_get_available_variables_uses_fk_schema_when_present(self):
        """AC #3 : Action avec FK → variables du schéma FK retournées."""
        fk_schema = make_schema(
            'schema-fk-63-9-avail', target_name='ref-action-63-9-avail',
            output_fields=[{'name': 'fk_field', 'type': 'string', 'description': 'champ FK'}],
        )
        ref_action = make_action('ref-action-63-9-avail', output_schema=fk_schema)
        workflow = make_workflow('wf-fk-63-9-avail', steps=[{
            'step_id': 'step1', 'step_type': 'platform',
            'referenced_action_id': ref_action.pk, 'name': 'Étape ref', 'step_order': 1,
        }])
        response = self.client.get(
            f'/api/v1/output-schemas/workflows/{workflow.pk}/available-variables/'
        )
        assert response.status_code == 200
        assert len(response.data) > 0
        var_names = [v['name'] for v in response.data[0]['variables']]
        assert 'fk_field' in var_names

    def test_get_available_variables_fallback_name_when_no_fk(self):
        """AC #3 : Action sans FK → fallback par nom."""
        make_schema(
            'schema-name-63-9-avail', target_name='ref-action-no-fk-63-9-avail',
            output_fields=[{'name': 'name_field', 'type': 'string', 'description': 'champ nom'}],
        )
        schema_registry.invalidate()
        ref_action = make_action('ref-action-no-fk-63-9-avail')
        workflow = make_workflow('wf-name-63-9-avail', steps=[{
            'step_id': 'step2', 'step_type': 'platform',
            'referenced_action_id': ref_action.pk, 'name': 'Étape nom', 'step_order': 1,
        }])
        response = self.client.get(
            f'/api/v1/output-schemas/workflows/{workflow.pk}/available-variables/'
        )
        assert response.status_code == 200
        assert len(response.data) > 0
        var_names = [v['name'] for v in response.data[0]['variables']]
        assert 'name_field' in var_names


# ─── AC #4 — Endpoint GET /api/v1/output-schemas/actions/{id}/schema/ ────────

@pytest.mark.django_db
class TestGetActionOutputSchema:
    def setup_method(self):
        self.client = APIClient()
        self.user = make_regular_user('user63_9_ep')
        self.client.force_authenticate(user=self.user)
        schema_registry.invalidate()

    def teardown_method(self):
        schema_registry.invalidate()

    def test_endpoint_with_fk_returns_fk_schema(self):
        """AC #4 : Action avec FK → schema_type='fk', schema non-null."""
        fk_schema = make_schema(
            'schema-ep-fk-63-9', target_name='action-ep-fk-63-9',
            output_fields=[{'name': 'ep_field', 'type': 'string', 'description': 'champ FK endpoint'}],
        )
        action = make_action('action-ep-fk-63-9', output_schema=fk_schema)
        response = self.client.get(f'/api/v1/output-schemas/actions/{action.pk}/schema/')
        assert response.status_code == 200
        assert response.data['action_id'] == action.pk
        assert response.data['schema_type'] == 'fk'
        assert response.data['schema'] is not None
        assert 'output_fields' in response.data['schema']

    def test_endpoint_without_fk_fallback_by_name(self):
        """AC #4 : Action sans FK → schema_type='name', fallback par nom."""
        make_schema(
            'schema-ep-name-63-9', target_name='action-ep-name-63-9',
            output_fields=[{'name': 'ep_name_field', 'type': 'string', 'description': 'champ nom endpoint'}],
        )
        schema_registry.invalidate()
        action = make_action('action-ep-name-63-9')
        response = self.client.get(f'/api/v1/output-schemas/actions/{action.pk}/schema/')
        assert response.status_code == 200
        assert response.data['schema_type'] == 'name'
        assert response.data['schema'] is not None

    def test_endpoint_action_not_found_returns_404(self):
        """AC #4 : Action inexistante → 404."""
        response = self.client.get('/api/v1/output-schemas/actions/999999/schema/')
        assert response.status_code == 404
