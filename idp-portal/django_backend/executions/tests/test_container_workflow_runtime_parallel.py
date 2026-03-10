"""
Tests d'intégration pour l'exécution parallèle dans ContainerWorkflowRuntime — Story 67.2 / 67.3

Couvre:
- AC1: fan-out via on_success_step_ids (2+ cibles → parallèle)
- AC2: fan-out via on_error_step_ids (2+ cibles erreur → parallèle)
- AC3: Fail-fast — si une branche échoue sans on_error routing, fan-out global = FAILED
- AC4: Thread-safety (_step_outputs_lock, _step_lock)
- AC5: Suppression parallel_group — workflows avec cette structure ne doivent plus être supportés
- AC6: Join implicite (fan-in) — step D exécuté une seule fois si B et C pointent vers D
- AC7: Rétrocompatibilité (on_success_step_ids, on_error_step_ids)
- AC8: Tests fan-out succès, per-branch routing, on_error fan-out, rétrocompat, fan-in
Story 67.3:
- AC1: Routage par branche indépendant — B échoue, C continue
- AC5–8: join_policy (all_success, one_success, all_done, rétrocompat)
"""

import pytest
from unittest.mock import patch
from rest_framework.exceptions import ValidationError

from executions.container_workflow_runtime import ContainerWorkflowRuntime
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus,
)
from catalog.models import ActionStatus, ActionItemType
from catalog.validation import validate_workflow_steps
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
class TestFanOutPerBranchRouting:
    """
    Story 67.3 AC1: Routage par branche indépendant.
    A → [B(fail), C(success)] — B échoue → route vers on_error_step_ids ;
    C réussit → route vers on_success_step_ids. Les deux branches continuent indépendamment.
    """

    def setup_method(self):
        self.user = UserFactory(username="perbranch_user")
        self.action_a = ActionFactory(
            name="Action A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="Action C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_next = ActionFactory(
            name="Step Next", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_err = ActionFactory(
            name="Error Handler", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # step-b référence un ID inexistant → FAILED → route vers step-err
        # step-c réussit → route vers step-next
        self.workflow_action = ActionFactory(
            name="Per-Branch Routing Workflow",
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
                    "on_error_step_ids": ["step-err"],
                },
                {
                    "order": 3,
                    "step_id": "step-c",
                    "step_type": "platform",
                    "name": "Action C",
                    "referenced_action_id": self.action_c.id,
                    "on_success_step_ids": ["step-next"],
                },
                {
                    "order": 4,
                    "step_id": "step-next",
                    "step_type": "platform",
                    "name": "Step Next",
                    "referenced_action_id": self.action_next.id,
                    "on_success_step_ids": [],
                },
                {
                    "order": 5,
                    "step_id": "step-err",
                    "step_type": "platform",
                    "name": "Error Handler",
                    "referenced_action_id": self.action_err.id,
                    "on_success_step_ids": [],
                },
            ],
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_per_branch_b_fails_c_succeeds_both_continue(self, mock_audit):
        """Story 67.3 AC1: B échoue → step-err ; C réussit → step-next. Les deux exécutés."""
        execution = Execution.objects.create(
            action=self.workflow_action,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        # Le workflow se complète car chaque branche a un chemin valide
        assert result == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        children_err = Execution.objects.filter(action=self.action_err, parent_execution=execution)
        children_next = Execution.objects.filter(action=self.action_next, parent_execution=execution)
        assert children_err.count() == 1, "Error handler (step-err) doit être exécuté"
        assert children_next.count() == 1, "Step next doit être exécuté (C a réussi)"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_failed_branch_no_on_error_returns_failed(self, mock_audit):
        """AC3 (rétrocompat): B échoue sans on_error routing + C sans next → FAILED global."""
        # Workflow simplifié : B et C sans aucun routing suivant
        action_c2 = ActionFactory(
            name="Action C2", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        simple_workflow = ActionFactory(
            name="Simple Fail Workflow",
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
                    "referenced_action_id": 999999,  # FAILED, pas de on_error
                    "on_success_step_ids": [],
                },
                {
                    "order": 3,
                    "step_id": "step-c",
                    "step_type": "platform",
                    "name": "Action C",
                    "referenced_action_id": action_c2.id,
                    "on_success_step_ids": [],
                },
            ],
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=simple_workflow,
            user=self.user,
            environment=TEST_ENVIRONMENT,
            status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.FAILED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.FAILED


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
    """AC7: Rétrocompatibilité on_success_step_ids/on_error_step_ids (pluriel)."""

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
        # Workflow avec on_success_step_ids (format pluriel)
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
                    "on_success_step_ids": ["step-b"],
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
    def test_singular_on_success_step_ids_works(self, mock_audit):
        """AC7: on_success_step_ids → A exécuté, puis B séquentiellement."""
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
        assert children_b.count() == 1, "Action B exécutée via on_success_step_ids"


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


# ─── Story 67.3: join_policy tests ───────────────────────────────────────────


def _make_diamond_with_join_policy(
    action_a_id, action_b_id, action_c_id, action_d_id, action_err_id,
    join_policy: str,
) -> list[dict]:
    """
    Workflow diamond avec join_policy configurable pour D.
    A → [B(fail→err), C(success→D)]
    B → on_success → D ; on_error → step-err
    C → on_success → D
    D a join_policy configurée
    """
    return [
        {
            "order": 1, "step_id": "step-a", "step_type": "platform",
            "name": "A", "referenced_action_id": action_a_id,
            "on_success_step_ids": ["step-b", "step-c"],
        },
        {
            "order": 2, "step_id": "step-b", "step_type": "platform",
            "name": "B (will fail)", "referenced_action_id": action_b_id,
            "on_success_step_ids": ["step-d"],
            "on_error_step_ids": ["step-err"],
        },
        {
            "order": 3, "step_id": "step-c", "step_type": "platform",
            "name": "C (will succeed)", "referenced_action_id": action_c_id,
            "on_success_step_ids": ["step-d"],
        },
        {
            "order": 4, "step_id": "step-d", "step_type": "platform",
            "name": "D (join)", "referenced_action_id": action_d_id,
            "join_policy": join_policy,
            "on_success_step_ids": [],
        },
        {
            "order": 5, "step_id": "step-err", "step_type": "platform",
            "name": "Error Handler", "referenced_action_id": action_err_id,
            "on_success_step_ids": [],
        },
    ]


@pytest.mark.django_db(transaction=True)
class TestJoinPolicyAllSuccess:
    """Story 67.3 AC5: join_policy=all_success — D exécuté seulement si TOUS réussissent."""

    def setup_method(self):
        self.user = UserFactory(username="join_all_success_user")
        self.action_a = ActionFactory(
            name="A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_d = ActionFactory(
            name="D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_err = ActionFactory(
            name="Err", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="join_policy=all_success Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_with_join_policy(
                self.action_a.id,
                999999,  # action_b → FAILED
                self.action_c.id,
                self.action_d.id,
                self.action_err.id,
                join_policy='all_success',
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_all_success_b_fails_d_not_executed(self, mock_audit):
        """Story 67.3 AC5: B fail, C success, join_policy=all_success → D NON exécuté."""
        execution = Execution.objects.create(
            action=self.workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 0, \
            "D ne doit PAS être exécuté (all_success et B a échoué)"
        assert steps.filter(config_step_id='step-err').count() == 1, \
            "step-err doit être exécuté (B a échoué)"


@pytest.mark.django_db(transaction=True)
class TestJoinPolicyOneSuccess:
    """Story 67.3 AC6: join_policy=one_success — D exécuté dès qu'un prédécesseur réussit."""

    def setup_method(self):
        self.user = UserFactory(username="join_one_success_user")
        self.action_a = ActionFactory(
            name="A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_d = ActionFactory(
            name="D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_err = ActionFactory(
            name="Err", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="join_policy=one_success Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_with_join_policy(
                self.action_a.id,
                999999,  # action_b → FAILED
                self.action_c.id,
                self.action_d.id,
                self.action_err.id,
                join_policy='one_success',
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_one_success_b_fails_d_executed(self, mock_audit):
        """Story 67.3 AC6: B fail, C success, join_policy=one_success → D exécuté."""
        execution = Execution.objects.create(
            action=self.workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 1, \
            "D DOIT être exécuté (one_success et C a réussi)"
        assert steps.filter(config_step_id='step-err').count() == 1, \
            "step-err doit être exécuté (B a échoué)"


@pytest.mark.django_db(transaction=True)
class TestJoinPolicyAllDone:
    """Story 67.3 AC7: join_policy=all_done — D exécuté quand tous terminés (succès ou erreur)."""

    def setup_method(self):
        self.user = UserFactory(username="join_all_done_user")
        self.action_a = ActionFactory(
            name="A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_d = ActionFactory(
            name="D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_err = ActionFactory(
            name="Err", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.workflow_action = ActionFactory(
            name="join_policy=all_done Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_with_join_policy(
                self.action_a.id,
                999999,  # action_b → FAILED
                self.action_c.id,
                self.action_d.id,
                self.action_err.id,
                join_policy='all_done',
            ),
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_all_done_b_fails_d_executed(self, mock_audit):
        """Story 67.3 AC7: B fail, C success, join_policy=all_done → D exécuté."""
        execution = Execution.objects.create(
            action=self.workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        result = runtime.run_sync()

        assert result == ExecutionStatus.COMPLETED
        execution.refresh_from_db()
        assert execution.status == ExecutionStatus.COMPLETED

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 1, \
            "D DOIT être exécuté (all_done : tous terminés, peu importe le statut)"
        assert steps.filter(config_step_id='step-err').count() == 1, \
            "step-err doit être exécuté (B a échoué)"


@pytest.mark.django_db(transaction=True)
class TestJoinPolicyRetrocompat:
    """Story 67.3 AC8: Sans join_policy → comportement identique à all_success."""

    def setup_method(self):
        self.user = UserFactory(username="join_retrocompat_user")
        self.action_a = ActionFactory(
            name="A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_d = ActionFactory(
            name="D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_err = ActionFactory(
            name="Err", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        # Même diamond mais SANS join_policy sur step-d → défaut all_success
        steps_no_join_policy = [
            {
                "order": 1, "step_id": "step-a", "step_type": "platform",
                "name": "A", "referenced_action_id": self.action_a.id,
                "on_success_step_ids": ["step-b", "step-c"],
            },
            {
                "order": 2, "step_id": "step-b", "step_type": "platform",
                "name": "B (will fail)", "referenced_action_id": 999999,
                "on_success_step_ids": ["step-d"],
                "on_error_step_ids": ["step-err"],
            },
            {
                "order": 3, "step_id": "step-c", "step_type": "platform",
                "name": "C (will succeed)", "referenced_action_id": self.action_c.id,
                "on_success_step_ids": ["step-d"],
            },
            {
                "order": 4, "step_id": "step-d", "step_type": "platform",
                "name": "D (no join_policy)", "referenced_action_id": self.action_d.id,
                # Pas de join_policy → défaut all_success
                "on_success_step_ids": [],
            },
            {
                "order": 5, "step_id": "step-err", "step_type": "platform",
                "name": "Error Handler", "referenced_action_id": self.action_err.id,
                "on_success_step_ids": [],
            },
        ]
        self.workflow_action = ActionFactory(
            name="No join_policy Workflow (retrocompat)",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=steps_no_join_policy,
            created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_no_join_policy_behaves_like_all_success(self, mock_audit):
        """Story 67.3 AC8: Sans join_policy → D non exécuté (comme all_success, B a échoué)."""
        execution = Execution.objects.create(
            action=self.workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 0, \
            "D ne doit PAS être exécuté (pas de join_policy = all_success par défaut)"
        assert steps.filter(config_step_id='step-err').count() == 1, \
            "step-err doit être exécuté (B a échoué)"


# ─── Tests unitaires (sans DB) — validation et sérialisation ─────────────────


class TestJoinPolicyValidation:
    """Story 67.3 AC4: Validation join_policy dans validate_workflow_steps()."""

    def _make_steps(self, join_policy):
        return [
            {
                'step_id': 'step-a', 'step_type': 'platform',
                'referenced_action_id': 1,
                'on_success_step_ids': ['step-b'],
            },
            {
                'step_id': 'step-b', 'step_type': 'platform',
                'referenced_action_id': 2,
                'join_policy': join_policy,
                'on_success_step_ids': [],
            },
        ]

    def test_invalid_join_policy_raises_validation_error(self):
        """Story 67.3 AC4: join_policy invalide → ValidationError."""
        steps = self._make_steps('invalid_policy')
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert 'join_policy' in str(exc_info.value)
        assert 'invalid_policy' in str(exc_info.value)

    def test_valid_join_policy_all_success(self):
        """Story 67.3 AC4: join_policy=all_success → pas d'erreur."""
        validate_workflow_steps(self._make_steps('all_success'))

    def test_valid_join_policy_one_success(self):
        """Story 67.3 AC4: join_policy=one_success → pas d'erreur."""
        validate_workflow_steps(self._make_steps('one_success'))

    def test_valid_join_policy_all_done(self):
        """Story 67.3 AC4: join_policy=all_done → pas d'erreur."""
        validate_workflow_steps(self._make_steps('all_done'))

    def test_no_join_policy_valid(self):
        """Story 67.3 AC8: Absence de join_policy → pas d'erreur."""
        steps = [
            {
                'step_id': 'step-a', 'step_type': 'platform',
                'referenced_action_id': 1,
                'on_success_step_ids': [],
            },
        ]
        validate_workflow_steps(steps)

    def test_valid_join_policy_all_failed(self):
        """Story 67.8: join_policy=all_failed → pas d'erreur."""
        validate_workflow_steps(self._make_steps('all_failed'))

    def test_valid_join_policy_one_failed(self):
        """Story 67.8: join_policy=one_failed → pas d'erreur."""
        validate_workflow_steps(self._make_steps('one_failed'))

    def test_invalid_join_policy_all_fail_typo_raises(self):
        """Story 67.8: typo 'all_fail' → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_workflow_steps(self._make_steps('all_fail'))
        assert 'join_policy' in str(exc_info.value)
        assert 'all_fail' in str(exc_info.value)


@pytest.mark.django_db
class TestJoinPolicySerialization:
    """Story 67.3 AC3: Sérialisation join_policy dans get_workflow_steps()."""

    def test_join_policy_present_in_serializer_output(self):
        """Story 67.3 AC3: step avec join_policy → champ présent dans get_workflow_steps()."""
        from catalog.serializers import ActionSerializer

        user = UserFactory(username="join_serial_user")
        action_a = ActionFactory(
            name="Serial A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=user,
        )
        action_b = ActionFactory(
            name="Serial B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=user,
        )
        workflow_action = ActionFactory(
            name="join_policy Serial Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1, "step_id": "step-a", "step_type": "platform",
                    "name": "A", "referenced_action_id": action_a.id,
                    "on_success_step_ids": ["step-b"],
                },
                {
                    "order": 2, "step_id": "step-b", "step_type": "platform",
                    "name": "B", "referenced_action_id": action_b.id,
                    "join_policy": "one_success",
                    "on_success_step_ids": [],
                },
            ],
            created_by=user,
        )
        serializer = ActionSerializer(workflow_action)
        workflow_steps = serializer.data['workflow_steps']

        step_b = next(s for s in workflow_steps if s['step_id'] == 'step-b')
        assert 'join_policy' in step_b, "join_policy doit être présent dans le step sérialisé"
        assert step_b['join_policy'] == 'one_success'

    def test_step_without_join_policy_not_in_output(self):
        """Story 67.3 AC3: step sans join_policy → champ absent de l'output."""
        from catalog.serializers import ActionSerializer

        user = UserFactory(username="join_serial_absent_user")
        action_a = ActionFactory(
            name="Serial A2", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=user,
        )
        workflow_action = ActionFactory(
            name="No join_policy Serial Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1, "step_id": "step-a", "step_type": "platform",
                    "name": "A", "referenced_action_id": action_a.id,
                    "on_success_step_ids": [],
                },
            ],
            created_by=user,
        )
        serializer = ActionSerializer(workflow_action)
        workflow_steps = serializer.data['workflow_steps']

        step_a = next(s for s in workflow_steps if s['step_id'] == 'step-a')
        assert 'join_policy' not in step_a, "join_policy ne doit PAS être présent si absent du step"

    def test_join_policy_all_failed_present_in_output(self):
        """Story 67.8 AC3: step avec join_policy=all_failed → champ présent dans get_workflow_steps()."""
        from catalog.serializers import ActionSerializer

        user = UserFactory(username="join_all_failed_serial_user")
        action_a = ActionFactory(
            name="Serial AF-A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=user,
        )
        action_b = ActionFactory(
            name="Serial AF-B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=user,
        )
        workflow_action = ActionFactory(
            name="join_policy all_failed Serial Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1, "step_id": "step-a", "step_type": "platform",
                    "name": "A", "referenced_action_id": action_a.id,
                    "on_success_step_ids": ["step-b"],
                },
                {
                    "order": 2, "step_id": "step-b", "step_type": "platform",
                    "name": "B", "referenced_action_id": action_b.id,
                    "join_policy": "all_failed",
                    "on_success_step_ids": [],
                },
            ],
            created_by=user,
        )
        serializer = ActionSerializer(workflow_action)
        workflow_steps = serializer.data['workflow_steps']

        step_b = next(s for s in workflow_steps if s['step_id'] == 'step-b')
        assert 'join_policy' in step_b, "join_policy doit être présent dans le step sérialisé"
        assert step_b['join_policy'] == 'all_failed'

    def test_join_policy_one_failed_present_in_output(self):
        """Story 67.8 AC3: step avec join_policy=one_failed → champ présent dans get_workflow_steps()."""
        from catalog.serializers import ActionSerializer

        user = UserFactory(username="join_one_failed_serial_user")
        action_a = ActionFactory(
            name="Serial OF-A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=user,
        )
        action_b = ActionFactory(
            name="Serial OF-B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=user,
        )
        workflow_action = ActionFactory(
            name="join_policy one_failed Serial Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=[
                {
                    "order": 1, "step_id": "step-a", "step_type": "platform",
                    "name": "A", "referenced_action_id": action_a.id,
                    "on_success_step_ids": ["step-b"],
                },
                {
                    "order": 2, "step_id": "step-b", "step_type": "platform",
                    "name": "B", "referenced_action_id": action_b.id,
                    "join_policy": "one_failed",
                    "on_success_step_ids": [],
                },
            ],
            created_by=user,
        )
        serializer = ActionSerializer(workflow_action)
        workflow_steps = serializer.data['workflow_steps']

        step_b = next(s for s in workflow_steps if s['step_id'] == 'step-b')
        assert 'join_policy' in step_b, "join_policy doit être présent dans le step sérialisé"
        assert step_b['join_policy'] == 'one_failed'


# ─── Story 67.8: join_policy all_failed / one_failed tests ────────────────────


def _make_diamond_for_failed_policy(
    action_a_id, action_b_id, action_c_id, action_d_id,
    join_policy: str,
) -> list[dict]:
    """
    Workflow : A → [B, C] (fan-out)
    B → on_success → [] ; on_error → [step-d]
    C → on_success → [] ; on_error → [step-d]
    D a join_policy configurée, on_success_step_ids=[]
    """
    return [
        {
            "order": 1, "step_id": "step-a", "step_type": "platform",
            "name": "A", "referenced_action_id": action_a_id,
            "on_success_step_ids": ["step-b", "step-c"],
        },
        {
            "order": 2, "step_id": "step-b", "step_type": "platform",
            "name": "B", "referenced_action_id": action_b_id,
            "on_success_step_ids": [],
            "on_error_step_ids": ["step-d"],
        },
        {
            "order": 3, "step_id": "step-c", "step_type": "platform",
            "name": "C", "referenced_action_id": action_c_id,
            "on_success_step_ids": [],
            "on_error_step_ids": ["step-d"],
        },
        {
            "order": 4, "step_id": "step-d", "step_type": "platform",
            "name": "D (join failed)", "referenced_action_id": action_d_id,
            "join_policy": join_policy,
            "on_success_step_ids": [],
        },
    ]


@pytest.mark.django_db(transaction=True)
class TestJoinPolicyAllFailed:
    """Story 67.8 AC4: join_policy=all_failed — D exécuté seulement si TOUS les prédécesseurs ont échoué."""

    def setup_method(self):
        self.user = UserFactory(username="join_all_failed_user")
        self.action_a = ActionFactory(
            name="AF-A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="AF-C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_d = ActionFactory(
            name="AF-D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_all_failed_both_fail_d_executed(self, mock_audit):
        """Story 67.8 AC4: B FAILED + C FAILED → D exécuté (tous ont échoué)."""
        workflow_action = ActionFactory(
            name="all_failed both fail Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_for_failed_policy(
                self.action_a.id,
                999999,   # B → FAILED : ID inexistant → le step échoue au lancement
                999998,   # C → FAILED : ID inexistant → le step échoue au lancement
                self.action_d.id,
                join_policy='all_failed',
            ),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 1, \
            "D doit être exécuté (tous les prédécesseurs ont échoué)"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_all_failed_one_success_d_not_executed(self, mock_audit):
        """Story 67.8 AC4: B FAILED + C COMPLETED → D NON exécuté (pas tous en échec)."""
        workflow_action = ActionFactory(
            name="all_failed one success Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_for_failed_policy(
                self.action_a.id,
                999999,            # B → FAILED : ID inexistant → le step échoue au lancement
                self.action_c.id,  # C → COMPLETED (action existante et publiée)
                self.action_d.id,
                join_policy='all_failed',
            ),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 0, \
            "D ne doit PAS être exécuté (C a réussi — pas tous en échec)"


@pytest.mark.django_db(transaction=True)
class TestJoinPolicyOneFailed:
    """Story 67.8 AC5: join_policy=one_failed — D exécuté dès qu'au moins un prédécesseur a échoué."""

    def setup_method(self):
        self.user = UserFactory(username="join_one_failed_user")
        self.action_a = ActionFactory(
            name="OF-A", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_c = ActionFactory(
            name="OF-C", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        self.action_d = ActionFactory(
            name="OF-D", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )

    @patch('executions.container_workflow_runtime.AuditService')
    def test_one_failed_b_fails_d_executed(self, mock_audit):
        """Story 67.8 AC5: B FAILED + C COMPLETED → D exécuté (au moins un en échec)."""
        workflow_action = ActionFactory(
            name="one_failed b fails Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_for_failed_policy(
                self.action_a.id,
                999999,            # B → FAILED : ID inexistant → le step échoue au lancement
                self.action_c.id,  # C → COMPLETED (action existante et publiée)
                self.action_d.id,
                join_policy='one_failed',
            ),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 1, \
            "D doit être exécuté (B a échoué — au moins un en échec)"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_one_failed_both_fail_d_executed(self, mock_audit):
        """Story 67.8 AC5 (complément): B FAILED + C FAILED → D exécuté (au moins un en échec)."""
        workflow_action = ActionFactory(
            name="one_failed both fail Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_for_failed_policy(
                self.action_a.id,
                999999,   # B → FAILED : ID inexistant → le step échoue au lancement
                999998,   # C → FAILED : ID inexistant → le step échoue au lancement
                self.action_d.id,
                join_policy='one_failed',
            ),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 1, \
            "D doit être exécuté (B et C ont tous les deux échoué — au moins un en échec)"

    @patch('executions.container_workflow_runtime.AuditService')
    def test_one_failed_all_success_d_not_executed(self, mock_audit):
        """Story 67.8 AC5: B COMPLETED + C COMPLETED → D NON exécuté (aucun en échec)."""
        action_b = ActionFactory(
            name="OF-B", status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION, created_by=self.user,
        )
        workflow_action = ActionFactory(
            name="one_failed all success Workflow",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
            execution_steps=_make_diamond_for_failed_policy(
                self.action_a.id,
                action_b.id,       # B → COMPLETED (action existante)
                self.action_c.id,  # C → COMPLETED (action existante)
                self.action_d.id,
                join_policy='one_failed',
            ),
            created_by=self.user,
        )
        execution = Execution.objects.create(
            action=workflow_action, user=self.user,
            environment=TEST_ENVIRONMENT, status=ExecutionStatus.SUBMITTED,
        )
        runtime = ContainerWorkflowRuntime(execution)
        runtime.run_sync()

        steps = ExecutionStep.objects.filter(execution=execution)
        assert steps.filter(config_step_id='step-d').count() == 0, \
            "D ne doit PAS être exécuté (tous les prédécesseurs ont réussi)"
