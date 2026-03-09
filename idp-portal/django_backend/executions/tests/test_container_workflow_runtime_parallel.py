"""
Tests d'intégration pour l'exécution parallèle dans ContainerWorkflowRuntime — Story 65.2

Couvre:
- AC1/AC2/AC3: Résolution des sub-steps depuis _step_lookup_by_id
- AC2: Exécution parallèle via ThreadPoolExecutor
- AC3: Attente de tous les sub-steps (as_completed)
- AC4: Thread-safety de _step_outputs avec _step_outputs_lock
- AC5: Routing on_all_success_step_id
- AC6: Routing on_any_error_step_id / fail si absent
- AC7: Pré-allocation step_order (unique_together respecté)
- AC8: Les membres du parallel_group sont skippés dans la boucle séquentielle
- AC9: Intégration avec handlers platform
- AC10: Tests succès total, échec partiel, cancellation, thread-safety, double-exécution
"""

import pytest
from unittest.mock import patch

from executions.container_workflow_runtime import ContainerWorkflowRuntime
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus,
)
from catalog.models import ActionStatus, ActionItemType
from tests.factories import UserFactory, ActionFactory


TEST_ENVIRONMENT = 'developpement'


def _make_parallel_workflow(action_a_id, action_b_id, action_c_id,
                             on_all_success='step-c', on_any_error=None):
    """Workflow: [parallel_group(A, B)] → [C] avec routing configurable."""
    return [
        {
            "order": 1,
            "step_id": "pg-1",
            "step_type": "parallel_group",
            "name": "Parallel Group",
            "parallel_steps": ["step-a", "step-b"],
            "on_all_success_step_id": on_all_success,
            "on_any_error_step_id": on_any_error,
        },
        {
            "order": 2,
            "step_id": "step-a",
            "step_type": "platform",
            "name": "Action A",
            "referenced_action_id": action_a_id,
        },
        {
            "order": 3,
            "step_id": "step-b",
            "step_type": "platform",
            "name": "Action B",
            "referenced_action_id": action_b_id,
        },
        {
            "order": 4,
            "step_id": "step-c",
            "step_type": "platform",
            "name": "Action C",
            "referenced_action_id": action_c_id,
        },
    ]


@pytest.mark.django_db(transaction=True)
class TestParallelGroupAllSuccess:
    """AC1, AC2, AC3, AC5, AC8 — Succès total, routing on_all_success_step_id."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_success_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="Action B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="Parallel Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_parallel_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
            ),
            created_by=self.user,
        )

    def _create_execution(self):
        return Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_parallel_group_all_success_workflow_completed(self, mock_audit):
        """AC5: Tous les sub-steps COMPLETED → workflow COMPLETED, step-c exécuté."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        # step-a, step-b (via parallel), step-c (via routing) → 3 child executions
        assert len(runtime.child_executions) == 3

    @patch('executions.container_workflow_runtime.AuditService')
    def test_parallel_group_creates_execution_steps_for_sub_steps(self, mock_audit):
        """AC7: Un ExecutionStep est créé pour chaque sub-step avec step_order unique."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # step-a et step-b exécutés via le groupe, step-c après routing
        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        assert steps.count() == 3

        # step_order doit être unique (unique_together respecté)
        orders = list(steps.values_list('step_order', flat=True))
        assert len(orders) == len(set(orders)), "Les step_order doivent être uniques"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_member_steps_not_double_executed(self, mock_audit):
        """AC8: step-a et step-b exécutés une seule fois (pas de double exécution)."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # Vérifier que action_a et action_b ont chacun exactement 1 child execution
        children_a = Execution.objects.filter(
            action=self.action_a, parent_execution=execution
        )
        children_b = Execution.objects.filter(
            action=self.action_b, parent_execution=execution
        )
        assert children_a.count() == 1, "Action A exécutée exactement une fois"
        assert children_b.count() == 1, "Action B exécutée exactement une fois"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_c_executed_after_group_via_routing(self, mock_audit):
        """AC5: step-c exécuté via on_all_success_step_id après le parallel_group."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # Action C doit avoir une child execution
        children_c = Execution.objects.filter(
            action=self.action_c, parent_execution=execution
        )
        assert children_c.count() == 1, "Action C exécutée après routing on_all_success"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_lookup_built_correctly(self, mock_audit):
        """AC1: _step_lookup_by_id est construit depuis workflow_steps."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)

        assert 'pg-1' in runtime._step_lookup_by_id
        assert 'step-a' in runtime._step_lookup_by_id
        assert 'step-b' in runtime._step_lookup_by_id
        assert 'step-c' in runtime._step_lookup_by_id

    @patch('executions.container_workflow_runtime.AuditService')
    def test_member_step_ids_populated(self, mock_audit):
        """AC8: _member_step_ids contient step-a et step-b."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)

        assert 'step-a' in runtime._member_step_ids
        assert 'step-b' in runtime._member_step_ids
        assert 'pg-1' not in runtime._member_step_ids
        assert 'step-c' not in runtime._member_step_ids


@pytest.mark.django_db(transaction=True)
class TestParallelGroupOneFailureNoErrorRouting:
    """AC6: Si un sub-step échoue et on_any_error_step_id est absent → FAILED."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_fail_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # Workflow avec step-b référençant un ID inexistant → FAILED
        self.workflow_action = ActionFactory(
            name="Failing Parallel Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1,
                    "step_id": "pg-1",
                    "step_type": "parallel_group",
                    "name": "Parallel Group",
                    "parallel_steps": ["step-a", "step-b"],
                    "on_all_success_step_id": "step-c",
                    "on_any_error_step_id": None,
                },
                {
                    "order": 2,
                    "step_id": "step-a",
                    "step_type": "platform",
                    "name": "Action A",
                    "referenced_action_id": self.action_a.id,
                },
                {
                    "order": 3,
                    "step_id": "step-b",
                    "step_type": "platform",
                    "name": "Action B — inexistante",
                    "referenced_action_id": 999999,  # N'existe pas → FAILED
                },
                {
                    "order": 4,
                    "step_id": "step-c",
                    "step_type": "platform",
                    "name": "Action C",
                    "referenced_action_id": self.action_c.id,
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_one_sub_step_failure_no_error_routing_returns_failed(self, mock_audit):
        """AC6: on_any_error_step_id absent → workflow FAILED."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_c_not_executed_on_parallel_failure(self, mock_audit):
        """AC6: step-c ne doit pas être exécuté si le parallel_group a échoué."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # Action C ne doit pas avoir de child execution
        children_c = Execution.objects.filter(
            action=self.action_c, parent_execution=execution
        )
        assert children_c.count() == 0, "Action C ne doit pas être exécutée après échec"


@pytest.mark.django_db(transaction=True)
class TestParallelGroupErrorRouting:
    """AC6: on_any_error_step_id défini → routing vers step d'erreur."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_error_routing_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_error = ActionFactory(
            name="Error Handler", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # step-b référence un ID inexistant → FAILED dans parallel_group
        self.workflow_action = ActionFactory(
            name="Error Routing Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1,
                    "step_id": "pg-1",
                    "step_type": "parallel_group",
                    "name": "Parallel Group",
                    "parallel_steps": ["step-a", "step-b"],
                    "on_all_success_step_id": None,
                    "on_any_error_step_id": "step-error",
                },
                {
                    "order": 2,
                    "step_id": "step-a",
                    "step_type": "platform",
                    "name": "Action A",
                    "referenced_action_id": self.action_a.id,
                },
                {
                    "order": 3,
                    "step_id": "step-b",
                    "step_type": "platform",
                    "name": "Action B — inexistante",
                    "referenced_action_id": 999999,
                },
                {
                    "order": 4,
                    "step_id": "step-error",
                    "step_type": "platform",
                    "name": "Error Handler",
                    "referenced_action_id": self.action_error.id,
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_error_routing_executes_error_step(self, mock_audit):
        """AC6: on_any_error_step_id → step d'erreur exécuté."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        # Le workflow exécute step-error via on_any_error_step_id, qui réussit → COMPLETED
        result = runtime.run_sync()

        # step-error réussit → COMPLETED final
        assert result == ExecutionStatus.COMPLETED

        # Vérifier que action_error a été exécuté
        children_error = Execution.objects.filter(
            action=self.action_error, parent_execution=execution
        )
        assert children_error.count() == 1, "Le step d'erreur doit être exécuté"


@pytest.mark.django_db(transaction=True)
class TestParallelGroupStepOutputsThreadSafety:
    """AC4: _step_outputs après exécution parallèle."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_outputs_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="Action B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="Outputs Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_parallel_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_outputs_contains_sub_steps_after_group(self, mock_audit):
        """AC4: _step_outputs contient les entrées pour step-a et step-b après le groupe."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # _step_outputs doit contenir les entrées des sub-steps
        assert 'step-a' in runtime._step_outputs, "_step_outputs doit contenir step-a"
        assert 'step-b' in runtime._step_outputs, "_step_outputs doit contenir step-b"


@pytest.mark.django_db(transaction=True)
class TestParallelGroupLockInfrastructure:
    """Interface checks for _step_outputs_lock and _step_lock (no concurrency stress)."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_lock_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="Action B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="Lock Test Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_parallel_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_outputs_lock_exists(self, mock_audit):
        """_step_outputs_lock exposes lock interface (acquire/release)."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        assert hasattr(runtime._step_outputs_lock, "acquire") and callable(
            getattr(runtime._step_outputs_lock, "acquire")
        ), "_step_outputs_lock must expose lock behavior (acquire/release)"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_lock_exists(self, mock_audit):
        """_step_lock exposes lock interface for step_order pre-allocation."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        assert hasattr(runtime._step_lock, "acquire") and callable(
            getattr(runtime._step_lock, "acquire")
        ), "_step_lock must expose lock behavior (acquire/release)"


@pytest.mark.django_db(transaction=True)
class TestParallelGroupCancellation:
    """AC3: Cancellation détectée après exécution parallèle → CANCELLED."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_cancel_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="Action B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="Cancel Parallel Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_parallel_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.is_cancelled')
    def test_cancellation_after_parallel_group_returns_cancelled(self, mock_is_cancelled, mock_audit):
        """AC3: Cancellation détectée après le parallel_group → CANCELLED (step-c skippé)."""
        call_count = {'n': 0}

        def is_cancelled_side_effect(execution_id):
            """Call sequence: (1) before pg-1 → not cancelled; (2) before step-c (after routing) → cancelled."""
            call_count['n'] += 1
            return call_count['n'] > 1

        mock_is_cancelled.side_effect = is_cancelled_side_effect

        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.CANCELLED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.CANCELLED

        # step-c ne doit pas avoir été exécuté
        children_c = Execution.objects.filter(
            action=self.action_c, parent_execution=execution
        )
        assert children_c.count() == 0, "Action C ne doit pas être exécutée si annulé"


@pytest.mark.django_db(transaction=True)
class TestParallelGroupNoOnAllSuccessRouting:
    """AC5: Si on_all_success_step_id est absent → continue séquentiellement."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_no_routing_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="Action B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # Pas de on_all_success_step_id — continue au step suivant dans steps_to_execute
        self.workflow_action = ActionFactory(
            name="No Routing Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_parallel_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
                on_all_success=None,  # Pas de routing explicite
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_success_routing_continues_sequentially(self, mock_audit):
        """AC5: Sans on_all_success_step_id, passe au step suivant dans la liste filtrée."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        # step-c est le step suivant dans steps_to_execute (après pg-1) → exécuté
        assert result == ExecutionStatus.COMPLETED
        children_c = Execution.objects.filter(
            action=self.action_c, parent_execution=execution
        )
        assert children_c.count() == 1, "Action C exécutée séquentiellement après le groupe"


@pytest.mark.django_db(transaction=True)
class TestParallelGroupEmptySteps:
    """Cas limite : parallel_steps vide → COMPLETED immédiat, routing on_all_success_step_id effectué."""

    def setup_method(self):
        self.user = UserFactory(username="parallel_empty_user")
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # parallel_group avec parallel_steps vide → retourne COMPLETED sans rien exécuter
        self.workflow_action = ActionFactory(
            name="Empty Parallel Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1,
                    "step_id": "pg-empty",
                    "step_type": "parallel_group",
                    "name": "Empty Parallel Group",
                    "parallel_steps": [],
                    "on_all_success_step_id": "step-c",
                    "on_any_error_step_id": None,
                },
                {
                    "order": 2,
                    "step_id": "step-c",
                    "step_type": "platform",
                    "name": "Action C",
                    "referenced_action_id": self.action_c.id,
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_empty_parallel_group_returns_completed_and_routes(self, mock_audit):
        """parallel_steps vide → COMPLETED, on_all_success_step_id suivi normalement."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        children_c = Execution.objects.filter(
            action=self.action_c, parent_execution=execution
        )
        assert children_c.count() == 1, "step-c exécuté via routing après groupe vide"
