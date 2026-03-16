"""
Tests Story 77.2 — Préserver les types natifs dans input_mapping

AC1 : expression pure {{ steps.X.Y }} avec valeur list/dict → type natif Python
AC2 : template mixte → string (comportement actuel)
AC3 : test end-to-end — extra_vars.databases reçu comme list Python par le handler
"""
import pytest
from unittest.mock import patch

from executions.models import (
    Execution,
    ExecutionStatus,
)
from executions.container_workflow_runtime import ContainerWorkflowRuntime
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory


TEST_ENVIRONMENT = 'developpement'


# ---------------------------------------------------------------------------
# AC3 — Test d'intégration end-to-end avec ContainerWorkflowRuntime
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAC3EndToEndNativeTypes:
    """
    AC3 : extra_vars.databases via {{ steps.discovery.databases }} reçu comme list Python.

    Vérifie que le handler en aval (service_call) reçoit bien une liste,
    pas la représentation string "['DB1', 'DB2']".
    """

    def setup_method(self):
        self.user = UserFactory()

    @patch('executions.container_workflow_runtime.AuditService')
    def test_service_call_receives_list_from_input_mapping(self, mock_audit):
        """
        AC3 : step service_call avec input_mapping databases: {{ steps.discovery.databases }}
        reçoit une liste Python dans resolved_params, pas une string.
        """
        from django.test import override_settings

        # Capturer les resolved_params passés au 2e handler
        captured_resolved_params: dict = {}

        call_count = [0]

        def mock_execute_side_effect(step_config, resolved_params, execution, step, correlation_id=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # Premier appel : discovery step
                return {
                    'status': ExecutionStatus.COMPLETED,
                    'raw_output': {'databases': ['DB1', 'DB2'], 'host': 'server1'},
                }
            else:
                # Deuxième appel : patch step — capturer les resolved_params
                captured_resolved_params.update(resolved_params)
                return {
                    'status': ExecutionStatus.COMPLETED,
                    'raw_output': {'result': 'patched'},
                }

        workflow_action = ActionFactory(
            name="Native Types E2E Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    'order': 1,
                    'name': 'Discovery Step',
                    'step_id': 'discovery',
                    'step_type': 'service_call',
                    'integration_type': 'servicenow',
                    'operation': 'create_change',
                    'output_mapping': {
                        'databases': '$.databases',
                    },
                    'on_success_step_ids': ['patch-step'],
                },
                {
                    'order': 2,
                    'name': 'Patch Step',
                    'step_id': 'patch-step',
                    'step_type': 'service_call',
                    'integration_type': 'servicenow',
                    'operation': 'create_change',
                    'input_mapping': {
                        'extra_vars': {
                            'databases': '{{ steps.discovery.databases }}',
                        },
                    },
                },
            ],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

        with override_settings(
            SIMULATE_EXECUTION_DEV=False,
            SIMULATE_EXECUTION_STEP_DURATION=0,
        ):
            with patch(
                'executions.step_handlers.service_call_handler.ServiceCallHandler.execute',
                side_effect=mock_execute_side_effect,
            ):
                runtime = ContainerWorkflowRuntime(execution)
                runtime.run_sync()

        # Vérifier que les deux steps ont été exécutés
        assert call_count[0] == 2, f"Attendu 2 appels au handler, reçu {call_count[0]}"

        # Vérifier que extra_vars.databases est bien une liste dans resolved_params
        extra_vars = captured_resolved_params.get('extra_vars', {})
        databases = extra_vars.get('databases')

        assert databases == ['DB1', 'DB2'], (
            f"AC3 : extra_vars.databases doit être ['DB1', 'DB2'], reçu: {databases!r} (type: {type(databases).__name__})"
        )
        assert isinstance(databases, list), (
            f"AC3 : extra_vars.databases doit être une list, reçu: {type(databases).__name__}"
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_gate_resume_preserves_list_type_in_step_outputs(self, mock_audit):
        """
        AC3 (task 5.3) : extracted_output contenant une liste → resolver préserve le type
        après resume d'une gate.
        """
        from executions.template_resolver import StepTemplateResolver

        # Simuler les step_outputs comme reconstruit après resume depuis extracted_output
        step_outputs = {
            'discovery': {
                'databases': ['DB1', 'DB2'],
                'count': 2,
            }
        }

        resolver = StepTemplateResolver(step_outputs)
        result = resolver.resolve({
            'extra_vars': {
                'databases': '{{ steps.discovery.databases }}',
                'count': '{{ steps.discovery.count }}',
                'label': 'Patching {{ steps.discovery.count }} bases',
            }
        })

        # databases doit être une liste native
        assert result['extra_vars']['databases'] == ['DB1', 'DB2']
        assert isinstance(result['extra_vars']['databases'], list)

        # count doit être un entier natif
        assert result['extra_vars']['count'] == 2
        assert isinstance(result['extra_vars']['count'], int)

        # label est un template mixte → string
        assert result['extra_vars']['label'] == 'Patching 2 bases'
        assert isinstance(result['extra_vars']['label'], str)
