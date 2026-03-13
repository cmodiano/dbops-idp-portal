"""
Story 78.10 — Tests for parity check management command.
AC4: JSON vs normalized table comparison for various workflow shapes.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from catalog.models import Action, ActionItemType, ActionStatus
from catalog.models_workflow_definition import (
    WorkflowStep,
)
from catalog.tests._workflow_definition_test_helpers import (
    create_unmanaged_tables,
    drop_unmanaged_tables,
)
from catalog.workflow_definition_repository import sync_from_json
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole


class ParityCheckCommandTests(TestCase):
    """Test check_workflow_definition_parity management command."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_unmanaged_tables()

    @classmethod
    def tearDownClass(cls):
        drop_unmanaged_tables()
        super().tearDownClass()

    def setUp(self):
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM, is_active=True,
        )
        self.ref_action = Action.objects.create(
            name='Referenced Action',
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.ACTION,
            status=ActionStatus.PUBLISHED,
        )

    def _create_workflow(self, name, steps):
        return Action.objects.create(
            name=name,
            engine='Oracle',
            platform='AAP',
            item_type=ActionItemType.WORKFLOW,
            status=ActionStatus.DRAFT,
            execution_steps=steps,
        )

    def test_parity_ok_linear_workflow(self):
        """Linear workflow: parity OK after sync."""
        wf = self._create_workflow('Linear WF', [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform',
             'referenced_action_id': self.ref_action.id, 'retry_enabled': False},
            {'order': 2, 'step_id': 's2', 'name': 'Step 2', 'step_type': 'platform',
             'referenced_action_id': self.ref_action.id, 'retry_enabled': False},
        ])
        sync_from_json(wf)

        out = StringIO()
        call_command('check_workflow_definition_parity', stdout=out)
        output = out.getvalue()
        self.assertIn('PARITY CHECK PASSED', output)

    def test_parity_ok_branched_workflow(self):
        """Branched workflow with success/error edges: parity OK."""
        wf = self._create_workflow('Branched WF', [
            {'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform',
             'on_success_step_ids': ['s2'], 'on_error_step_ids': ['s3'],
             'retry_enabled': False},
            {'order': 2, 'step_id': 's2', 'name': 'S2', 'step_type': 'platform',
             'retry_enabled': False},
            {'order': 3, 'step_id': 's3', 'name': 'S3', 'step_type': 'evaluation',
             'retry_enabled': False},
        ])
        sync_from_json(wf)

        out = StringIO()
        call_command('check_workflow_definition_parity', stdout=out)
        self.assertIn('PARITY CHECK PASSED', out.getvalue())

    def test_parity_ok_with_retry_conditions_mappings(self):
        """Workflow with retry, conditions, input/output mappings: parity OK."""
        wf = self._create_workflow('Complex WF', [
            {
                'order': 1, 'step_id': 's1', 'name': 'Complex Step',
                'step_type': 'service_call',
                'integration_type': 'servicenow', 'operation': 'create_change',
                'input_mapping': {'p1': '{{ prev }}'},
                'output_mapping': {'out': '$.data'},
                'condition': '{{ env == "prod" }}',
                'retry_enabled': True, 'retry_max_attempts': 3,
                'retry_interval_seconds': 60, 'retry_backoff_multiplier': 2.0,
                'join_policy': 'all_success',
            },
        ])
        sync_from_json(wf)

        out = StringIO()
        call_command('check_workflow_definition_parity', stdout=out)
        self.assertIn('PARITY CHECK PASSED', out.getvalue())

    def test_parity_fail_divergence_detected(self):
        """Divergence introduced voluntarily: detected by parity check."""
        wf = self._create_workflow('Divergent WF', [
            {'order': 1, 'step_id': 's1', 'name': 'Step 1', 'step_type': 'platform',
             'retry_enabled': False},
        ])
        sync_from_json(wf)

        # Manually alter the normalized data to introduce divergence
        step = WorkflowStep.objects.get(
            workflow_definition__action=wf, step_id='s1',
        )
        step.step_name = 'ALTERED NAME'
        step.save()

        out = StringIO()
        with self.assertRaises(SystemExit) as ctx:
            call_command('check_workflow_definition_parity', stdout=out)
        self.assertEqual(ctx.exception.code, 1)
        output = out.getvalue()
        self.assertIn('PARITY CHECK FAILED', output)
        self.assertIn('DIFF', output)

    def test_parity_skip_workflows_without_steps(self):
        """Workflows with no steps are skipped."""
        self._create_workflow('Empty WF', None)

        out = StringIO()
        call_command('check_workflow_definition_parity', stdout=out)
        output = out.getvalue()
        self.assertIn('Skipped:   1', output)
        self.assertIn('PARITY CHECK PASSED', output)

    def test_parity_verbose_output(self):
        """--verbose flag shows OK workflows."""
        wf = self._create_workflow('Verbose WF', [
            {'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform',
             'retry_enabled': False},
        ])
        sync_from_json(wf)

        out = StringIO()
        call_command('check_workflow_definition_parity', '--verbose', stdout=out)
        output = out.getvalue()
        self.assertIn('OK', output)
        self.assertIn('Verbose WF', output)

    def test_parity_ok_with_empty_arrays_and_nulls(self):
        """Parity OK when JSON has empty arrays and null values that normalized omits."""
        wf = self._create_workflow('EmptyArrays WF', [
            {
                'order': 1, 'step_id': 's1', 'name': 'S1', 'step_type': 'platform',
                'referenced_action_id': None,
                'on_success_step_ids': [],
                'on_error_step_ids': [],
                'retry_enabled': False,
                'integration_type': None,
                'operation': None,
            },
        ])
        sync_from_json(wf)

        out = StringIO()
        call_command('check_workflow_definition_parity', stdout=out)
        self.assertIn('PARITY CHECK PASSED', out.getvalue())
