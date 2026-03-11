"""
Story 72.1 — Tests de propagation du correlation_id sur tout le cycle d'exécution.

AC1: Persistance sur Execution (champ correlation_id)
AC2: Propagation Celery trigger → poll
AC3: Propagation Celery gates
AC4: Propagation Celery polling
AC5: Cohérence audit
AC6: Rétrocompatibilité (NULL existant)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from tests.factories import UserFactory, ActionFactory, ExecutionFactory, ExecutionStepFactory
from executions.models import Execution, ExecutionStepStatus, ExecutionStepType
from executions.dtos import ExecutionRequest


# ---------------------------------------------------------------------------
# AC1 — Persistance du correlation_id sur Execution
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionCorrelationIdField(TestCase):
    """AC1: Le modèle Execution possède un champ correlation_id persisté."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()

    def test_execution_has_correlation_id_field(self):
        """Le modèle Execution a bien un champ correlation_id."""
        execution = ExecutionFactory(user=self.user, action=self.action)
        self.assertTrue(hasattr(execution, 'correlation_id'))

    def test_execution_correlation_id_nullable(self):
        """correlation_id est nullable — les exécutions sans corrélation sont valides."""
        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=None)
        self.assertIsNone(execution.correlation_id)

    def test_execution_correlation_id_persisted(self):
        """correlation_id est bien persisté en base et récupérable."""
        cid = "test-correlation-abc-123"
        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=cid)
        reloaded = Execution.objects.get(id=execution.id)
        self.assertEqual(reloaded.correlation_id, cid)

    def test_execution_correlation_id_max_length(self):
        """correlation_id accepte jusqu'à 64 caractères (VARCHAR2(64))."""
        cid = "x" * 64
        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=cid)
        reloaded = Execution.objects.get(id=execution.id)
        self.assertEqual(reloaded.correlation_id, cid)


@pytest.mark.django_db
class TestExecutionServiceCorrelationId(TestCase):
    """AC1: create_execution persiste le correlation_id depuis ExecutionRequest."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()
        self.action.integration = None
        self.action.save()

    def test_create_execution_persists_correlation_id(self):
        """_create_execution_atomic doit persister request.correlation_id sur l'Execution."""
        from executions.services import ExecutionService

        cid = "req-correlation-xyz-456"
        request = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            correlation_id=cid,
        )
        svc = ExecutionService()
        execution = svc._create_execution_atomic(request)
        reloaded = Execution.objects.get(id=execution.id)
        self.assertEqual(reloaded.correlation_id, cid)

    def test_create_execution_without_correlation_id(self):
        """AC6: create_execution sans correlation_id crée une Execution avec NULL."""
        from executions.services import ExecutionService

        request = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            correlation_id=None,
        )
        svc = ExecutionService()
        execution = svc._create_execution_atomic(request)
        reloaded = Execution.objects.get(id=execution.id)
        self.assertIsNone(reloaded.correlation_id)


# ---------------------------------------------------------------------------
# AC2 + AC4 — Propagation trigger → poll
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTriggerPropagatesCorrelationId(TestCase):
    """AC2: trigger_platform_job passe correlation_id dans kwargs de poll_platform_job_status."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()

    def test_trigger_passes_correlation_id_to_poll(self):
        """trigger_platform_job doit passer correlation_id dans les kwargs du poll."""
        from integrations.models import Integration
        import executions.tasks.trigger as trigger_module

        cid = "trigger-cid-789"
        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=cid)
        step = ExecutionStepFactory(
            execution=execution,
            step_type=ExecutionStepType.PLATFORM,
            status=ExecutionStepStatus.RUNNING,
        )

        # Mock integration
        integration = MagicMock(spec=Integration)
        integration.id = 1
        integration.type = 'aap'
        integration.base_url = 'https://aap.example.com'
        integration.credential_ref = 'vault/aap'
        integration.auth_flow = 'token'
        integration.get_config.return_value = {}

        # Mock adapter trigger result
        mock_adapter = MagicMock()
        mock_adapter.trigger = MagicMock(return_value={'platform_job_id': 'job-42'})

        mock_poll_apply = MagicMock()

        # get_platform_queue est importé localement depuis polling dans trigger_platform_job
        with patch('adapters.get_platform_adapter', return_value=mock_adapter), \
             patch('adapters.utils.build_auth_headers', return_value={}), \
             patch('asgiref.sync.async_to_sync', side_effect=lambda f: f), \
             patch('integrations.models.Integration.objects.get', return_value=integration), \
             patch('executions.models.ExecutionStep.objects.get', return_value=step), \
             patch('executions.tasks.polling.get_platform_queue', return_value='default'), \
             patch('executions.tasks.polling.poll_platform_job_status') as mock_poll_task:
            mock_poll_task.apply_async = mock_poll_apply
            trigger_module.trigger_platform_job(
                execution_step_id=step.id,
                execution_id=execution.id,
                integration_id=integration.id,
                trigger_kwargs={'correlation_id': cid, 'template_id': 42},
            )

        # Vérifier que poll_platform_job_status.apply_async a été appelé avec correlation_id
        mock_poll_apply.assert_called_once()
        call_kwargs = mock_poll_apply.call_args
        kwargs = call_kwargs.kwargs.get('kwargs', {})
        self.assertEqual(kwargs.get('correlation_id'), cid)


@pytest.mark.django_db
class TestPollReceivesCorrelationId(TestCase):
    """AC4: poll_platform_job_status reçoit et utilise correlation_id en kwarg."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()

    def test_poll_uses_kwarg_correlation_id_when_provided(self):
        """poll_platform_job_status utilise le correlation_id passé en kwarg."""
        from executions.tasks import poll_platform_job_status

        cid = "poll-cid-kwarg-001"
        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=cid)

        mock_status_data = {'status': 'RUNNING', 'aap_status': 'running'}
        mock_logs_data = {'content': 'log line', 'complete': False}

        mock_adapter = MagicMock()
        mock_adapter.get_status = MagicMock(return_value=mock_status_data)
        mock_adapter.get_job_logs = MagicMock(return_value=mock_logs_data)

        mock_apply = MagicMock()

        with patch('executions.tasks.polling.get_platform_queue', return_value='default'), \
             patch('adapters.get_platform_adapter', return_value=mock_adapter), \
             patch('adapters.utils.build_auth_headers_from_credentials', return_value={}), \
             patch('executions.tasks.polling._update_execution_from_poll'), \
             patch('executions.tasks.polling._broadcast_execution_update'), \
             patch('asgiref.sync.async_to_sync', side_effect=lambda f: f), \
             patch('executions.tasks.polling.poll_platform_job_status.apply_async', mock_apply):

            poll_platform_job_status(
                execution_id=execution.id,
                platform_job_id='job-123',
                platform_type='aap',
                correlation_id=cid,
            )

        # Vérifier que correlation_id est propagé dans le re-schedule
        mock_apply.assert_called_once()
        reschedule_kwargs = mock_apply.call_args.kwargs.get('kwargs', {})
        self.assertEqual(reschedule_kwargs.get('correlation_id'), cid)

    def test_poll_falls_back_to_execution_correlation_id(self):
        """AC4: Si correlation_id absent du kwarg, le récupérer depuis Execution.

        On vérifie que le correlation_id est résolu depuis Execution.correlation_id
        en inspectant l'appel à _tasks._update_execution_from_poll via le module tasks.
        """
        from executions.tasks import poll_platform_job_status
        import executions.tasks as tasks_module

        cid = "execution-stored-cid-002"
        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=cid)

        mock_status_data = {'status': 'RUNNING'}
        mock_logs_data = {'content': 'in progress', 'complete': False}

        mock_adapter = MagicMock()
        mock_adapter.get_status = MagicMock(return_value=mock_status_data)
        mock_adapter.get_job_logs = MagicMock(return_value=mock_logs_data)

        mock_apply = MagicMock()

        with patch('executions.tasks.polling.get_platform_queue', return_value='default'), \
             patch('adapters.get_platform_adapter', return_value=mock_adapter), \
             patch('adapters.utils.build_auth_headers_from_credentials', return_value={}), \
             patch.object(tasks_module, '_update_execution_from_poll') as mock_update, \
             patch.object(tasks_module, '_broadcast_execution_update'), \
             patch('executions.tasks.polling.poll_platform_job_status.apply_async', mock_apply), \
             patch('asgiref.sync.async_to_sync', side_effect=lambda f: f):

            poll_platform_job_status(
                execution_id=execution.id,
                platform_job_id='job-456',
                platform_type='aap',
                # Pas de correlation_id en kwarg → doit le récupérer depuis Execution
            )

        # Vérifier que _update_execution_from_poll a reçu le bon correlation_id
        mock_update.assert_called_once()
        update_kwargs = mock_update.call_args.kwargs
        self.assertEqual(update_kwargs.get('correlation_id'), cid)


# ---------------------------------------------------------------------------
# AC3 — Propagation Celery gates
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGatesCorrelationId(TestCase):
    """AC3: evaluate_waiting_gates utilise execution.correlation_id pour logs/audit."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()

    def test_gate_uses_execution_correlation_id(self):
        """evaluate_waiting_gates utilise step.execution.correlation_id."""
        from executions.tasks.gates import evaluate_waiting_gates
        from executions.models import ExecutionStatus
        import executions.gate_evaluator as gate_evaluator_module

        cid = "gate-cid-003"
        execution = ExecutionFactory(
            user=self.user,
            action=self.action,
            status=ExecutionStatus.RUNNING,
            correlation_id=cid,
        )
        step = ExecutionStepFactory(
            execution=execution,
            step_type=ExecutionStepType.GATE,
            status=ExecutionStepStatus.WAITING,
        )
        step.set_output({'gate_conditions': [{'type': 'approval_granted'}]})
        step.save()

        mock_gate_status = {'all_satisfied': True, 'timeout_triggered': False}

        mock_evaluator_instance = MagicMock()
        mock_evaluator_instance.evaluate.return_value = (True, mock_gate_status)

        with patch.object(gate_evaluator_module, 'GateEvaluator', return_value=mock_evaluator_instance), \
             patch('executions.tasks.gates._transition_step_to_running') as mock_transition:

            evaluate_waiting_gates()

            # Vérifier que _transition_step_to_running a été appelé avec le bon correlation_id
            mock_transition.assert_called_once()
            call_args = mock_transition.call_args
            # _transition_step_to_running(step, gate_status, correlation_id)
            # Le 3e argument positionnel est le correlation_id
            passed_cid = call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get('correlation_id')
            self.assertEqual(passed_cid, cid)


# ---------------------------------------------------------------------------
# AC5 — Cohérence audit : correlation_id non nul dans les entrées d'audit
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAuditCorrelationIdConsistency(TestCase):
    """AC5: Les entrées d'audit créées pendant le cycle incluent correlation_id."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()
        self.action.integration = None
        self.action.save()

    def test_execution_submitted_audit_has_correlation_id(self):
        """L'entrée audit EXECUTION_SUBMITTED inclut le correlation_id."""
        from executions.services import ExecutionService
        from core.services import AuditService

        cid = "audit-cid-submitted-004"
        request = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            correlation_id=cid,
        )
        svc = ExecutionService()

        with patch.object(AuditService, 'create_entry') as mock_audit:
            svc._create_execution_atomic(request)
            mock_audit.assert_called_once()
            audit_kwargs = mock_audit.call_args.kwargs
            self.assertEqual(audit_kwargs.get('correlation_id'), cid)


# ---------------------------------------------------------------------------
# AC6 — Rétrocompatibilité : exécutions existantes sans correlation_id
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBackwardCompatibility(TestCase):
    """AC6: Les exécutions existantes sans correlation_id continuent de fonctionner."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()

    def test_existing_execution_without_correlation_id_is_valid(self):
        """Une Execution sans correlation_id (NULL) est valide et fonctionnelle."""
        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=None)
        self.assertIsNotNone(execution.id)
        self.assertIsNone(execution.correlation_id)

    def test_poll_with_null_execution_correlation_id(self):
        """poll_platform_job_status fonctionne si Execution.correlation_id est NULL."""

        execution = ExecutionFactory(user=self.user, action=self.action, correlation_id=None)

        mock_status_data = {'status': 'COMPLETED'}
        mock_logs_data = {'content': 'done', 'complete': True}

        mock_adapter = MagicMock()
        mock_adapter.get_status = MagicMock(return_value=mock_status_data)
        mock_adapter.get_job_logs = MagicMock(return_value=mock_logs_data)

        from executions.tasks import poll_platform_job_status

        with patch('executions.tasks.polling.get_platform_queue', return_value='default'), \
             patch('adapters.get_platform_adapter', return_value=mock_adapter), \
             patch('adapters.utils.build_auth_headers_from_credentials', return_value={}), \
             patch('executions.tasks.polling._update_execution_from_poll'), \
             patch('executions.tasks.polling._broadcast_execution_update'), \
             patch('executions.tasks.polling._forward_platform_logs_to_splunk'), \
             patch('asgiref.sync.async_to_sync', side_effect=lambda f: f):

            # Ne doit pas lever d'exception
            result = poll_platform_job_status(
                execution_id=execution.id,
                platform_job_id='job-null-cid',
                platform_type='aap',
            )

        self.assertIn(result.get('outcome'), ('complete', 'polling', 'error'))


# ---------------------------------------------------------------------------
# AC — Recherche par correlation_id retourne soumission + complétion
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSearchByCorrelationIdReturnsFullCycle(TestCase):
    """AC: Recherche par correlation_id retourne soumission + complétion pour une même exécution."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()
        self.action.integration = None
        self.action.save()

    def test_search_correlation_id_returns_submitted_and_completed(self):
        """GET /audit/executions?correlation_id=X retourne SUBMITTED et COMPLETED."""
        from executions.services import ExecutionService
        from executions.models import ExecutionStatus
        from audit.views import AuditExecutionsView
        from rest_framework.test import APIRequestFactory, force_authenticate

        cid = "search-cycle-cid-001"
        request = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            correlation_id=cid,
        )
        svc = ExecutionService()
        execution = svc._create_execution_atomic(request)

        # Transition SUBMITTED -> RUNNING -> COMPLETED (crée audits avec correlation_id)
        svc.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))
        svc.update_status(execution.id, ExecutionStatus.COMPLETED, str(self.user.id))

        # Recherche par correlation_id
        rf = APIRequestFactory()
        req = rf.get(f"/api/v1/audit/executions/?correlation_id={cid}")
        req.user = self.user
        req.user.is_authenticated = True
        force_authenticate(req, user=self.user)

        with patch("audit.views.is_auditor_user", return_value=True):
            response = AuditExecutionsView.as_view()(req)

        self.assertEqual(response.status_code, 200)
        data = response.data.get("data", [])
        action_types = {e.get("action_type") for e in data}
        self.assertIn("EXECUTION_SUBMITTED", action_types)
        self.assertIn("EXECUTION_COMPLETED", action_types)
        for entry in data:
            self.assertEqual(entry.get("correlation_id"), cid)
