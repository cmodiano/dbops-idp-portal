"""
Story 69.1: Tests for technologies and included_actions derived fields.

Tests cover:
- Workflow with multi-engine actions → deduplicated technologies
- Workflow with single engine → single technology
- Simple action → technologies = [engine], included_actions = []
- Workflow with empty/null execution_steps
- Workflow with invalid referenced_action_id
- API list and detail endpoints include the new fields
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.throttling import SimpleRateThrottle

from catalog.models import Action, ActionStatus, ActionItemType
from catalog.serializers import ActionSerializer, ActionListSerializer
from reference.models import RefEngine
from tests.factories import UserFactory


@pytest.mark.django_db
class TestWorkflowTechnologiesAndIncludedActions(TestCase):
    """Unit tests for get_technologies and get_included_actions serializer methods."""

    def setUp(self):
        self.user = UserFactory(username='test69', profile='dba')

        # Create 2 engines
        self.engine_oracle = RefEngine.objects.create(
            code='oracle', label='Oracle Database', display_order=1
        )
        self.engine_sqlserver = RefEngine.objects.create(
            code='sqlserver', label='SQL Server', display_order=2
        )

        # Create 2 simple actions (one per engine)
        self.action_oracle = Action.objects.create(
            name='Oracle Backup',
            engine='oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
        )
        self.action_sqlserver = Action.objects.create(
            name='SQL Server Backup',
            engine='sqlserver',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            parameters_schema={'type': 'object', 'properties': {'db': {'type': 'string'}}},
        )

        # Create a workflow referencing both actions (multi-engine)
        self.workflow_multi = Action.objects.create(
            name='Multi-Engine Workflow',
            engine='',
            platform='',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            execution_steps=[
                {'order': 1, 'step_id': 's1', 'step_type': 'platform',
                 'referenced_action_id': self.action_oracle.id, 'name': 'Step Oracle'},
                {'order': 2, 'step_id': 's2', 'step_type': 'gate',
                 'gate_type': 'approval', 'name': 'Approval'},
                {'order': 3, 'step_id': 's3', 'step_type': 'platform',
                 'referenced_action_id': self.action_sqlserver.id, 'name': 'Step SQL'},
            ],
        )

        # Workflow referencing same engine twice (single-engine)
        self.workflow_single = Action.objects.create(
            name='Single-Engine Workflow',
            engine='',
            platform='',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            execution_steps=[
                {'order': 1, 'step_id': 's1', 'step_type': 'platform',
                 'referenced_action_id': self.action_oracle.id, 'name': 'Step 1'},
                {'order': 2, 'step_id': 's2', 'step_type': 'platform',
                 'referenced_action_id': self.action_oracle.id, 'name': 'Step 2'},
            ],
        )

    def _serialize_detail(self, obj):
        return ActionSerializer(obj).data

    def _serialize_list(self, obj):
        return ActionListSerializer(obj).data

    # --- technologies ---

    def test_workflow_technologies_multi_engines(self):
        """Workflow with actions using 2 different engines → 2 deduplicated codes."""
        data = self._serialize_detail(self.workflow_multi)
        techs = data['technologies']
        self.assertEqual(sorted(techs), ['oracle', 'sqlserver'])

    def test_workflow_technologies_single_engine(self):
        """Workflow with 2 steps referencing same engine → 1 code."""
        data = self._serialize_detail(self.workflow_single)
        self.assertEqual(data['technologies'], ['oracle'])

    def test_simple_action_technologies(self):
        """Simple action → technologies = [action.engine]."""
        data = self._serialize_detail(self.action_oracle)
        self.assertEqual(data['technologies'], ['oracle'])

    def test_simple_action_no_engine_technologies(self):
        """Simple action without engine → technologies = []."""
        action = Action.objects.create(
            name='No Engine', engine='', platform='AAP',
            item_type=ActionItemType.ACTION, status=ActionStatus.PUBLISHED,
            created_by=self.user,
        )
        data = self._serialize_detail(action)
        self.assertEqual(data['technologies'], [])

    # --- included_actions ---

    def test_workflow_included_actions(self):
        """Workflow → included_actions contains id, name, engine, parameters_schema in step order."""
        data = self._serialize_detail(self.workflow_multi)
        included = data['included_actions']
        self.assertEqual(len(included), 2)
        # First action (oracle)
        self.assertEqual(included[0]['id'], self.action_oracle.id)
        self.assertEqual(included[0]['name'], 'Oracle Backup')
        self.assertEqual(included[0]['engine'], 'oracle')
        self.assertIn('parameters_schema', included[0])
        # Second action (sqlserver)
        self.assertEqual(included[1]['id'], self.action_sqlserver.id)
        self.assertEqual(included[1]['name'], 'SQL Server Backup')
        self.assertEqual(included[1]['engine'], 'sqlserver')
        self.assertIn('parameters_schema', included[1])

    def test_simple_action_included_actions_empty(self):
        """Simple action → included_actions = []."""
        data = self._serialize_detail(self.action_oracle)
        self.assertEqual(data['included_actions'], [])

    # --- edge cases ---

    def test_workflow_empty_execution_steps(self):
        """Workflow with execution_steps=[] and real engine → technologies=[engine], included_actions=[]."""
        workflow = Action.objects.create(
            name='Empty Steps', engine='oracle', platform='',
            item_type=ActionItemType.WORKFLOW, status=ActionStatus.PUBLISHED,
            created_by=self.user, execution_steps=[],
        )
        data = self._serialize_detail(workflow)
        self.assertEqual(data['technologies'], ['oracle'])
        self.assertEqual(data['included_actions'], [])

    def test_workflow_empty_execution_steps_empty_engine(self):
        """Workflow with execution_steps=[] and engine='' (production case) → technologies=[], included_actions=[]."""
        workflow = Action.objects.create(
            name='Empty Steps No Engine', engine='', platform='',
            item_type=ActionItemType.WORKFLOW, status=ActionStatus.PUBLISHED,
            created_by=self.user, execution_steps=[],
        )
        data = self._serialize_detail(workflow)
        self.assertEqual(data['technologies'], [])
        self.assertEqual(data['included_actions'], [])

    def test_workflow_null_execution_steps(self):
        """Workflow with execution_steps=None → technologies=[engine], included_actions=[]."""
        workflow = Action.objects.create(
            name='Null Steps', engine='oracle', platform='',
            item_type=ActionItemType.WORKFLOW, status=ActionStatus.PUBLISHED,
            created_by=self.user, execution_steps=None,
        )
        data = self._serialize_detail(workflow)
        self.assertEqual(data['technologies'], ['oracle'])
        self.assertEqual(data['included_actions'], [])

    def test_workflow_invalid_referenced_action_id(self):
        """Workflow with non-existent referenced_action_id → action is ignored."""
        workflow = Action.objects.create(
            name='Invalid Ref', engine='', platform='',
            item_type=ActionItemType.WORKFLOW, status=ActionStatus.PUBLISHED,
            created_by=self.user,
            execution_steps=[
                {'order': 1, 'step_id': 's1', 'step_type': 'platform',
                 'referenced_action_id': self.action_oracle.id, 'name': 'Valid'},
                {'order': 2, 'step_id': 's2', 'step_type': 'platform',
                 'referenced_action_id': 999999, 'name': 'Invalid'},
            ],
        )
        data = self._serialize_detail(workflow)
        # Only the valid action should appear
        self.assertEqual(data['technologies'], ['oracle'])
        self.assertEqual(len(data['included_actions']), 1)
        self.assertEqual(data['included_actions'][0]['id'], self.action_oracle.id)

    # --- ActionListSerializer specifics ---

    def test_list_serializer_technologies(self):
        """ActionListSerializer also exposes technologies."""
        data = self._serialize_list(self.workflow_multi)
        self.assertIn('technologies', data)
        self.assertEqual(sorted(data['technologies']), ['oracle', 'sqlserver'])

    def test_list_serializer_included_actions_no_parameters_schema(self):
        """ActionListSerializer.included_actions excludes parameters_schema."""
        data = self._serialize_list(self.workflow_multi)
        included = data['included_actions']
        self.assertEqual(len(included), 2)
        for action_data in included:
            self.assertIn('id', action_data)
            self.assertIn('name', action_data)
            self.assertIn('engine', action_data)
            self.assertNotIn('parameters_schema', action_data)


@pytest.mark.django_db
@patch.object(SimpleRateThrottle, 'THROTTLE_RATES', {'catalog': '1000/min', 'anon': '1000/min', 'general_api': '1000/min'})
class TestCatalogAPITechnologiesActions(TestCase):
    """API-level tests for technologies and included_actions on catalog endpoints."""

    def setUp(self):
        from catalog.views._shared import _catalog_cache
        _catalog_cache.clear()

        self.client = APIClient()
        self.user = UserFactory(username='apitest69', profile='dba')

        self.engine = RefEngine.objects.create(
            code='oracle', label='Oracle', display_order=1
        )
        self.engine2 = RefEngine.objects.create(
            code='sqlserver', label='SQL Server', display_order=2
        )

        self.simple_action = Action.objects.create(
            name='Simple Oracle Action',
            engine='oracle', platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            parameters_schema={'type': 'object', 'properties': {'p1': {'type': 'string'}}},
        )
        self.ref_action = Action.objects.create(
            name='SQL Action',
            engine='sqlserver', platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            parameters_schema={'type': 'object', 'properties': {'p2': {'type': 'integer'}}},
        )
        self.workflow = Action.objects.create(
            name='Test Workflow',
            engine='', platform='',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.PUBLISHED,
            created_by=self.user,
            execution_steps=[
                {'order': 1, 'step_id': 's1', 'step_type': 'platform',
                 'referenced_action_id': self.simple_action.id, 'name': 'Step 1'},
                {'order': 2, 'step_id': 's2', 'step_type': 'platform',
                 'referenced_action_id': self.ref_action.id, 'name': 'Step 2'},
            ],
        )

    def test_api_catalog_list_includes_technologies_and_included_actions(self):
        """GET /catalog/actions/ → each action has technologies and included_actions."""
        response = self.client.get('/api/v1/catalog/actions/')
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        for item in data:
            self.assertIn('technologies', item)
            self.assertIn('included_actions', item)

        # Find workflow in response
        wf = next(i for i in data if i['id'] == self.workflow.id)
        self.assertEqual(sorted(wf['technologies']), ['oracle', 'sqlserver'])
        # included_actions present (catalog list uses ActionSerializer → includes parameters_schema)
        self.assertEqual(len(wf['included_actions']), 2)
        for action_data in wf['included_actions']:
            self.assertIn('id', action_data)
            self.assertIn('name', action_data)
            self.assertIn('engine', action_data)
            self.assertIn('parameters_schema', action_data)

        # Find simple action
        sa = next(i for i in data if i['id'] == self.simple_action.id)
        self.assertEqual(sa['technologies'], ['oracle'])
        self.assertEqual(sa['included_actions'], [])

    def test_api_catalog_detail_includes_included_actions(self):
        """GET /catalog/actions/{id} → response contains included_actions with parameters_schema."""
        response = self.client.get(f'/api/v1/catalog/actions/{self.workflow.id}/')
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertIn('included_actions', data)
        self.assertIn('technologies', data)

        included = data['included_actions']
        self.assertEqual(len(included), 2)
        # Detail view includes parameters_schema
        for action_data in included:
            self.assertIn('parameters_schema', action_data)
            self.assertIn('id', action_data)
            self.assertIn('name', action_data)
            self.assertIn('engine', action_data)
