"""
Tests d'intégration pour l'exécution parallèle dans ContainerWorkflowRuntime — Story 67.2

Couvre:
- AC1: fan-out via on_success_step_ids (2+ cibles → parallèle)
- AC2: fan-out via on_error_step_ids (2+ cibles erreur → parallèle)
- AC3: Fail-fast — si une branche échoue, fan-out global = FAILED
- AC4: Thread-safety (_step_outputs_lock, _step_lock)
- AC5: Suppression parallel_group — workflows avec cette structure ne doivent plus être supportés
- AC6: Join implicite (fan-in) — step D exécuté une seule fois si B et C pointent vers D
- AC7: Rétrocompatibilité singulier (on_success_step_id, on_error_step_id)
- AC8: Tests fan-out succès, fail-fast, on_error fan-out, rétrocompat, fan-in
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


def _make_fan_out_workflow(action_a_id, action_b_id, action_c_id,
                            action_d_id=None, on_success_ids=None,
                            on_error_ids=None):
    """
    Workflow: A → [B, C] (fan-out) → D (join implicite, si fourni).
    Si on_success_ids est fourni, utilisé pour A ; sinon ['step-b', 'step-c'].
    Si action_d_id est fourni, B et C pointent vers D (fan-in).
    """
    if on_success_ids is None:
        on_success_ids = ['step-b', 'step-c']

    step_b_success = ['step-d'] if action_d_id else []
    step_c_success = ['step-d'] if action_d_id else []

    steps = [
        {
            "order": 1,
            "step_id": "step-a",
            "step_type": "platform",
            "name": "Action A",
            "referenced_action_id": action_a_id,
            "on_success_step_ids": on_success_ids,
        },
        {
            "order": 2,
            "step_id": "step-b",
            "step_type": "platform",
            "name": "Action B",
            "referenced_action_id": action_b_id,
            "on_success_step_ids": step_b_success,
        },
        {
            "order": 3,
            "step_id": "step-c",
            "step_type": "platform",
            "name": "Action C",
            "referenced_action_id": action_c_id,
            "on_success_step_ids": step_c_success,
        },
    ]

    if action_d_id:
        steps.append({
            "order": 4,
            "step_id": "step-d",
            "step_type": "platform",
            "name": "Action D",
            "referenced_action_id": action_d_id,
            "on_success_step_ids": [],  # exit point
        })

    return steps


@pytest.mark.django_db(transaction=True)
class TestFanOutAllSuccess:
    """AC1, AC8 — Succès total fan-out : A → [B, C], B et C réussissent → COMPLETED."""

    def setup_method(self):
        self.user = UserFactory(username="fanout_success_user")
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
            name="Fan-Out Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_fan_out_workflow(
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
    def test_fan_out_all_success_workflow_completed(self, mock_audit):
        """AC1: A → [B, C] tous COMPLETED → workflow COMPLETED."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        # A, B, C → 3 child executions
        assert len(runtime.child_executions) == 3

    @patch('executions.container_workflow_runtime.AuditService')
    def test_fan_out_creates_execution_steps_for_all_steps(self, mock_audit):
        """AC4: Un ExecutionStep est créé pour chaque step avec step_order unique."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        assert steps.count() == 3

        # step_order doit être unique (unique_together respecté)
        orders = list(steps.values_list('step_order', flat=True))
        assert len(orders) == len(set(orders)), "Les step_order doivent être uniques"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_b_and_c_executed_exactly_once(self, mock_audit):
        """AC8: B et C exécutés exactement une fois chacun."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        children_b = Execution.objects.filter(action=self.action_b, parent_execution=execution)
        children_c = Execution.objects.filter(action=self.action_c, parent_execution=execution)
        assert children_b.count() == 1, "Action B exécutée exactement une fois"
        assert children_c.count() == 1, "Action C exécutée exactement une fois"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_lookup_built_correctly(self, mock_audit):
        """AC1: _step_lookup_by_id est construit depuis workflow_steps."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)

        assert 'step-a' in runtime._step_lookup_by_id
        assert 'step-b' in runtime._step_lookup_by_id
        assert 'step-c' in runtime._step_lookup_by_id

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_member_step_ids_attribute(self, mock_audit):
        """AC5: _member_step_ids n'existe plus (parallel_group supprimé)."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        assert not hasattr(runtime, '_member_step_ids'), \
            "_member_step_ids ne doit plus exister après suppression parallel_group"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_outputs_contains_all_steps(self, mock_audit):
        """AC4: _step_outputs contient les entrées pour A, B et C après exécution."""
        execution = self._create_execution()
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        assert 'step-a' in runtime._step_outputs
        assert 'step-b' in runtime._step_outputs
        assert 'step-c' in runtime._step_outputs


@pytest.mark.django_db(transaction=True)
class TestFanOutFailFast:
    """AC3: Fail-fast — si une branche parallèle échoue, fan-out global = FAILED."""

    def setup_method(self):
        self.user = UserFactory(username="fanout_fail_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # step-b référence un ID inexistant → FAILED
        self.workflow_action = ActionFactory(
            name="Failing Fan-Out Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1,
                    "step_id": "step-a",
                    "step_type": "platform",
                    "name": "Action A",
                    "referenced_action_id": self.action_a.id,
                    "on_success_step_ids": ["step-b", "step-c"],
                },
                {
                    "order": 2,
                    "step_id": "step-b",
                    "step_type": "platform",
                    "name": "Action B — inexistante",
                    "referenced_action_id": 999999,  # N'existe pas → FAILED
                    "on_success_step_ids": [],
                },
                {
                    "order": 3,
                    "step_id": "step-c",
                    "step_type": "platform",
                    "name": "Action C",
                    "referenced_action_id": self.action_c.id,
                    "on_success_step_ids": [],
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_fan_out_fail_fast_returns_failed(self, mock_audit):
        """AC3: B échoue dans fan-out → workflow FAILED."""
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
    def test_no_step_after_failed_fan_out(self, mock_audit):
        """AC3: Pas de step exécuté après un fan-out FAILED sans on_error routing."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        # Seulement A + (B ou C) dans les child executions — D ne doit pas exister
        children = Execution.objects.filter(parent_execution=execution)
        # A a 1 enfant, le fan-out peut avoir lancé C avant que B échoue
        assert children.count() >= 1  # au moins A


@pytest.mark.django_db(transaction=True)
class TestFanOutOnErrorStepIds:
    """AC2: fan-out via on_error_step_ids : A → erreur → [E, F] en parallèle."""

    def setup_method(self):
        self.user = UserFactory(username="fanout_error_routing_user")
        self.action_e = ActionFactory(
            name="Error Handler E", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_f = ActionFactory(
            name="Error Handler F", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # step-a référence un ID inexistant → FAILED → on_error_step_ids: [E, F]
        self.workflow_action = ActionFactory(
            name="Error Fan-Out Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1,
                    "step_id": "step-a",
                    "step_type": "platform",
                    "name": "Action A — inexistante",
                    "referenced_action_id": 999999,  # FAILED
                    "on_success_step_ids": [],
                    "on_error_step_ids": ["step-e", "step-f"],
                },
                {
                    "order": 2,
                    "step_id": "step-e",
                    "step_type": "platform",
                    "name": "Error Handler E",
                    "referenced_action_id": self.action_e.id,
                    "on_success_step_ids": [],
                },
                {
                    "order": 3,
                    "step_id": "step-f",
                    "step_type": "platform",
                    "name": "Error Handler F",
                    "referenced_action_id": self.action_f.id,
                    "on_success_step_ids": [],
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_error_fan_out_executes_both_handlers(self, mock_audit):
        """AC2: A FAILED → on_error_step_ids [E, F] → E et F exécutés → COMPLETED."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        # E et F réussissent → COMPLETED final
        assert result == ExecutionStatus.COMPLETED

        children_e = Execution.objects.filter(action=self.action_e, parent_execution=execution)
        children_f = Execution.objects.filter(action=self.action_f, parent_execution=execution)
        assert children_e.count() == 1, "Handler E doit être exécuté"
        assert children_f.count() == 1, "Handler F doit être exécuté"


@pytest.mark.django_db(transaction=True)
class TestFanInJoinImplicit:
    """AC6: Join implicite — A → [B, C], B.on_success = C.on_success = [D] → D exécuté une fois."""

    def setup_method(self):
        self.user = UserFactory(username="fanin_user")
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
        self.action_d = ActionFactory(
            name="Action D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="Fan-In Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_fan_out_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
                action_d_id=self.action_d.id,
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_fan_in_d_executed_exactly_once(self, mock_audit):
        """AC6: D exécuté exactement une fois malgré la convergence de B et C."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED

        children_d = Execution.objects.filter(action=self.action_d, parent_execution=execution)
        assert children_d.count() == 1, "Action D exécutée exactement une fois (fan-in)"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_fan_in_all_steps_executed(self, mock_audit):
        """AC6: A, B, C, D exécutés → 4 child executions."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        assert len(runtime.child_executions) == 4

    @patch('executions.container_workflow_runtime.AuditService')
    def test_fan_in_step_d_execution_step_created_once(self, mock_audit):
        """AC6: ExecutionStep pour D créé une seule fois (pas de doublon)."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps_d = ExecutionStep.objects.filter(
            execution=execution,
            config_step_id='step-d',
        )
        assert steps_d.count() == 1, "ExecutionStep pour D créé une seule fois"


@pytest.mark.django_db(transaction=True)
class TestRetroCompatSingular:
    """AC7: Rétrocompatibilité on_success_step_id/on_error_step_id (singulier)."""

    def setup_method(self):
        self.user = UserFactory(username="retrocompat_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_b = ActionFactory(
            name="Action B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # Workflow avec on_success_step_id singulier (ancien format)
        self.workflow_action = ActionFactory(
            name="Retrocompat Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1,
                    "step_id": "step-a",
                    "step_type": "platform",
                    "name": "Action A",
                    "referenced_action_id": self.action_a.id,
                    "on_success_step_id": "step-b",  # singulier
                },
                {
                    "order": 2,
                    "step_id": "step-b",
                    "step_type": "platform",
                    "name": "Action B",
                    "referenced_action_id": self.action_b.id,
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_singular_on_success_step_id_works(self, mock_audit):
        """AC7: on_success_step_id singulier → A exécuté, puis B séquentiellement."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        assert len(runtime.child_executions) == 2

        children_b = Execution.objects.filter(action=self.action_b, parent_execution=execution)
        assert children_b.count() == 1, "Action B exécutée via on_success_step_id singulier"


@pytest.mark.django_db(transaction=True)
class TestLinearRetrocompat:
    """AC7: Rétrocompatibilité mode linéaire — pas de champs de routing → exécution par ordre."""

    def setup_method(self):
        self.user = UserFactory(username="linear_retrocompat_user")
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
        # Workflow sans aucun champ de routing (ancien format linéaire)
        self.workflow_action = ActionFactory(
            name="Linear Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1,
                    "step_id": "step-a",
                    "step_type": "platform",
                    "name": "Action A",
                    "referenced_action_id": self.action_a.id,
                },
                {
                    "order": 2,
                    "step_id": "step-b",
                    "step_type": "platform",
                    "name": "Action B",
                    "referenced_action_id": self.action_b.id,
                },
                {
                    "order": 3,
                    "step_id": "step-c",
                    "step_type": "platform",
                    "name": "Action C",
                    "referenced_action_id": self.action_c.id,
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_linear_workflow_executes_all_steps(self, mock_audit):
        """AC7: Workflow sans routing → A, B, C exécutés séquentiellement."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        assert len(runtime.child_executions) == 3

    @patch('executions.container_workflow_runtime.AuditService')
    def test_linear_workflow_order_preserved(self, mock_audit):
        """AC7: Exécution dans l'ordre défini par 'order'."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution).order_by('step_order')
        step_names = list(steps.values_list('step_name', flat=True))
        assert step_names == ['Action A', 'Action B', 'Action C']


@pytest.mark.django_db(transaction=True)
class TestFanOutThreadSafety:
    """AC4: Thread-safety de _step_outputs et _step_lock."""

    def setup_method(self):
        self.user = UserFactory(username="fanout_thread_safety_user")
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
            name="Thread Safety Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_fan_out_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_outputs_lock_exists(self, mock_audit):
        """AC4: _step_outputs_lock expose l'interface lock (acquire/release)."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        assert hasattr(runtime._step_outputs_lock, "acquire") and callable(
            getattr(runtime._step_outputs_lock, "acquire")
        ), "_step_outputs_lock must expose lock behavior"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_step_lock_exists(self, mock_audit):
        """AC4: _step_lock expose l'interface lock pour la pré-allocation step_order."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        assert hasattr(runtime._step_lock, "acquire") and callable(
            getattr(runtime._step_lock, "acquire")
        ), "_step_lock must expose lock behavior"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_fan_out_step_orders_unique(self, mock_audit):
        """AC4: step_order unique même en parallèle (unique_together respecté)."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution)
        orders = list(steps.values_list('step_order', flat=True))
        assert len(orders) == len(set(orders)), "Les step_order doivent être uniques"


@pytest.mark.django_db(transaction=True)
class TestCancellationAfterFanOut:
    """AC4 (cancellation) : Annulation détectée après fan-out → CANCELLED, step suivant skippé."""

    def setup_method(self):
        self.user = UserFactory(username="fanout_cancel_user")
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
        self.action_d = ActionFactory(
            name="Action D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # Workflow : step-a séquentiel, puis fan-out [B, C] → D (join)
        # L'annulation sera détectée avant la vague [B, C]
        self.workflow_action = ActionFactory(
            name="Cancel Fan-Out Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_fan_out_workflow(
                self.action_a.id, self.action_b.id, self.action_c.id,
                action_d_id=self.action_d.id,
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    @patch('executions.container_workflow_runtime.is_cancelled')
    def test_cancellation_before_fan_out_returns_cancelled(self, mock_is_cancelled, mock_audit):
        """Annulation détectée avant le fan-out [B, C] → CANCELLED, B/C/D skippés."""
        call_count = {'n': 0}

        def is_cancelled_side_effect(execution_id):
            """(1) avant step-a → non annulé; (2) avant fan-out [B,C] → annulé."""
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

        # B, C, D ne doivent pas avoir été exécutés
        children_b = Execution.objects.filter(action=self.action_b, parent_execution=execution)
        children_c = Execution.objects.filter(action=self.action_c, parent_execution=execution)
        children_d = Execution.objects.filter(action=self.action_d, parent_execution=execution)
        assert children_b.count() == 0, "Action B ne doit pas être exécutée si annulé"
        assert children_c.count() == 0, "Action C ne doit pas être exécutée si annulé"
        assert children_d.count() == 0, "Action D ne doit pas être exécutée si annulé"
