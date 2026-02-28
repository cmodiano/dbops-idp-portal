"""
Tests for executions services (ExecutionService, SchedulingService).
"""

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.utils import timezone
from idp_auth.models import User
from catalog.models import Action
from executions.models import (
    Execution, ExecutionStep, ExecutionStatus, ExecutionTarget, TargetType,
)
from executions.dtos import ExecutionRequest
from executions.services import ExecutionService
from core.models import AuditLog
from tests.factories import (
    UserFactory, ActionFactory, IntegrationFactory, ExecutionFactory,
)
from integrations.models import IntegrationStatus


@pytest.mark.django_db
class TestExecutionService(TestCase):
    """Tests for ExecutionService."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status='published'
        )
        self.service = ExecutionService()

    def test_create_execution(self):
        """Test create_execution() creates execution with audit."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            parameters={'db_name': 'testdb'},
        )
        execution = self.service.create_execution(req)

        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.environment, 'dev')
        self.assertEqual(execution.status, ExecutionStatus.SUBMITTED)

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution.id,
            action_type='EXECUTION_SUBMITTED'
        ).first()
        self.assertIsNotNone(audit)

    def test_create_execution_with_steps(self):
        """Test create_execution_with_steps() creates execution and steps atomically."""
        steps_data = [
            {'step_order': 1, 'step_name': 'Step 1', 'step_type': 'manual'},
            {'step_order': 2, 'step_name': 'Step 2', 'step_type': 'manual'}
        ]

        execution = self.service.create_execution_with_steps(
            user=self.user,
            action=self.action,
            environment='dev',
            steps_data=steps_data
        )

        self.assertIsNotNone(execution.id)

        # Verify steps created
        steps = ExecutionStep.objects.filter(execution=execution)
        self.assertEqual(steps.count(), 2)

    def test_create_execution_with_steps_invalid_integration_audit_survives(self):
        """Story 24.4 AC4 via create_execution_with_steps: INVALID integration → audit entry persists.

        Validates that the fix for M-1 (removing @transaction.atomic from
        create_execution_with_steps) ensures the blocked-integration audit
        entry is NOT rolled back when BadRequestError is raised.
        """
        from core.exceptions import BadRequestError
        integration = IntegrationFactory(status=IntegrationStatus.INVALID)
        action = ActionFactory(integration=integration, status='published')

        with self.assertRaises(BadRequestError):
            self.service.create_execution_with_steps(
                user=self.user,
                action=action,
                environment='dev',
            )

        # Audit entry must survive the exception (not rolled back)
        audit = AuditLog.objects.filter(
            action_type='EXECUTION_BLOCKED_INVALID_INTEGRATION',
            entity_id=integration.id,
        ).first()
        self.assertIsNotNone(audit, "AC4 audit entry must persist outside of transaction")

        # No execution must have been created
        from executions.models import Execution
        self.assertEqual(Execution.objects.filter(action=action).count(), 0)

    def test_update_status(self):
        """Test update_status() updates status with validation."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )

        updated = self.service.update_status(
            execution.id,
            ExecutionStatus.RUNNING,
            str(self.user.id)
        )

        self.assertEqual(updated.status, ExecutionStatus.RUNNING)

        # Verify audit
        audit = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution.id,
            action_type='EXECUTION_RUNNING'
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 1.1 — _check_integration_status: pas d'intégration
    # ----------------------------------------------------------------
    def test_check_integration_status_no_integration_returns_none(self):
        """1.1: No integration on action → immediate return without error."""
        action = ActionFactory(integration=None, status='published')
        # Should not raise
        result = ExecutionService._check_integration_status(action, user_id=str(self.user.id))
        self.assertIsNone(result)

    # ----------------------------------------------------------------
    # Tâche 1.2 — _check_integration_status: INVALID → BadRequestError + audit
    # ----------------------------------------------------------------
    def test_check_integration_status_invalid_raises_bad_request(self):
        """1.2: INVALID integration → BadRequestError + audit entry."""
        from core.exceptions import BadRequestError
        integration = IntegrationFactory(status=IntegrationStatus.INVALID)
        action = ActionFactory(integration=integration, status='published')

        with self.assertRaises(BadRequestError) as ctx:
            ExecutionService._check_integration_status(action, user_id=str(self.user.id))

        self.assertEqual(ctx.exception.code, 'INVALID_INTEGRATION')

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_BLOCKED_INVALID_INTEGRATION',
            entity_id=integration.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 1.3 — _check_integration_status: DEPRECATED → warning + audit, pas d'exception
    # ----------------------------------------------------------------
    def test_check_integration_status_deprecated_logs_warning_and_creates_audit(self):
        """1.3: DEPRECATED integration → audit created, no exception raised."""
        integration = IntegrationFactory(status=IntegrationStatus.DEPRECATED)
        action = ActionFactory(integration=integration, status='published')

        # Should not raise
        ExecutionService._check_integration_status(action, user_id=str(self.user.id))

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_DEPRECATED_INTEGRATION_WARNING',
            entity_id=integration.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 1.4 — create_execution: requires_approval=True → PENDING_APPROVAL
    # ----------------------------------------------------------------
    def test_create_execution_requires_approval_creates_pending_approval(self):
        """1.4: requires_approval=True via _env_config → PENDING_APPROVAL + audit."""
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='prod',
            parameters={'_env_config': {'requires_approval': True}},
        )
        execution = self.service.create_execution(req)
        self.assertEqual(execution.status, ExecutionStatus.PENDING_APPROVAL)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_PENDING_APPROVAL',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 1.5 — create_execution: validated_targets (valid/invalid/no target_type)
    # ----------------------------------------------------------------
    def test_create_execution_with_validated_targets(self):
        """1.5: validated_targets → ExecutionTarget records created, invalid type → OTHER."""
        validated_targets = [
            {'name': 'server1', 'target_type': 'UNKNOWN_TYPE', 'environment': 'prod'},
            {'name': 'server2', 'target_type': 'server', 'environment': 'prod'},
            {'name': 'server3'},  # no target_type
        ]
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            validated_targets=validated_targets,
        )
        execution = self.service.create_execution(req)
        targets = ExecutionTarget.objects.filter(execution=execution)
        self.assertEqual(targets.count(), 3)

        # UNKNOWN_TYPE → TargetType.OTHER
        unknown = targets.get(target_name='server1')
        self.assertEqual(unknown.target_type, TargetType.OTHER)

        # 'server' is a valid TargetType
        server = targets.get(target_name='server2')
        self.assertEqual(server.target_type, TargetType.SERVER)

        # no target_type → TargetType.OTHER
        no_type = targets.get(target_name='server3')
        self.assertEqual(no_type.target_type, TargetType.OTHER)

    # ----------------------------------------------------------------
    # Tâche 1.6 — create_execution: delegated_referenced_action_ids → audit delegated=True
    # ----------------------------------------------------------------
    def test_create_execution_with_delegated_action_ids_audit(self):
        """1.6: delegated_referenced_action_ids → audit with delegated=True."""
        import json
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            delegated_referenced_action_ids=[10, 20, 30],
        )
        execution = self.service.create_execution(req)
        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)
        self.assertTrue(details.get('delegated'))
        self.assertEqual(details.get('referenced_action_ids'), [10, 20, 30])

    # ----------------------------------------------------------------
    # Tâche 1.7 — create_execution: workflow_step_parameters dans parameters → dans audit_details
    # ----------------------------------------------------------------
    def test_create_execution_workflow_step_parameters_in_audit(self):
        """1.7: workflow_step_parameters in parameters → key present in audit details."""
        import json
        wsp = {'1': {'parameters': {'db_name': 'testdb'}}}
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            parameters={'workflow_step_parameters': wsp},
        )
        execution = self.service.create_execution(req)
        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)
        details = json.loads(audit.details)
        self.assertIn('workflow_step_parameters', details)

    # ----------------------------------------------------------------
    # Tâche 1.8 — update_status: user_id invalide → ValueError
    # ----------------------------------------------------------------
    def test_update_status_invalid_user_id_raises_value_error(self):
        """1.8: Invalid user_id → ValueError('Invalid user_id')."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        with self.assertRaises(ValueError) as ctx:
            self.service.update_status(execution.id, ExecutionStatus.RUNNING, '99999999')
        self.assertIn('Invalid user_id', str(ctx.exception))

    # ----------------------------------------------------------------
    # Tâche 1.9 — update_status: execution introuvable → None
    # ----------------------------------------------------------------
    def test_update_status_execution_not_found_returns_none(self):
        """1.9: execution not found → returns None."""
        result = self.service.update_status(99999999, ExecutionStatus.RUNNING, str(self.user.id))
        self.assertIsNone(result)

    # ----------------------------------------------------------------
    # Tâche 1.10 — update_status: transition invalide → ValueError
    # ----------------------------------------------------------------
    def test_update_status_invalid_transition_raises_value_error(self):
        """1.10: Invalid transition (COMPLETED → RUNNING) → ValueError."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.COMPLETED,
        )
        with self.assertRaises(ValueError):
            self.service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))

    # ----------------------------------------------------------------
    # Tâche 1.11 — update_status: PENDING_APPROVAL → SUBMITTED interdit
    # ----------------------------------------------------------------
    def test_update_status_pending_approval_to_submitted_forbidden(self):
        """1.11: PENDING_APPROVAL → SUBMITTED is forbidden (security: AC22.12)."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        with self.assertRaises(ValueError):
            self.service.update_status(execution.id, ExecutionStatus.SUBMITTED, str(self.user.id))

    # ----------------------------------------------------------------
    # Tâche 1.12 — update_status: RUNNING → COMPLETED : completed_at mis à jour
    # ----------------------------------------------------------------
    def test_update_status_running_to_completed_sets_completed_at(self):
        """1.12: RUNNING → COMPLETED → completed_at set, status verified.
        Note: on_commit notification dispatch is tested in TestExecutionServiceCoverage
        using captureOnCommitCallbacks(execute=True)."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.RUNNING,
        )
        execution.started_at = timezone.now()
        execution.save()

        updated = self.service.update_status(
            execution.id, ExecutionStatus.COMPLETED, str(self.user.id)
        )

        self.assertEqual(updated.status, ExecutionStatus.COMPLETED)
        self.assertIsNotNone(updated.completed_at)

    # ----------------------------------------------------------------
    # Tâche 1.13 — update_status: RUNNING → FAILED : completed_at mis à jour
    # ----------------------------------------------------------------
    def test_update_status_running_to_failed_sets_completed_at(self):
        """1.13: RUNNING → FAILED → completed_at set, status verified.
        Note: on_commit notification dispatch is tested in TestExecutionServiceCoverage
        using captureOnCommitCallbacks(execute=True)."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.RUNNING,
        )
        execution.started_at = timezone.now()
        execution.save()

        updated = self.service.update_status(
            execution.id, ExecutionStatus.FAILED, str(self.user.id)
        )

        self.assertEqual(updated.status, ExecutionStatus.FAILED)
        self.assertIsNotNone(updated.completed_at)

    # ----------------------------------------------------------------
    # Tâche 1.14 — update_status: SUBMITTED → CANCELLED : completed_at mis à jour
    # ----------------------------------------------------------------
    def test_update_status_submitted_to_cancelled_sets_completed_at(self):
        """1.14: SUBMITTED → CANCELLED → completed_at set."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        updated = self.service.update_status(
            execution.id, ExecutionStatus.CANCELLED, str(self.user.id)
        )
        self.assertEqual(updated.status, ExecutionStatus.CANCELLED)
        self.assertIsNotNone(updated.completed_at)

    # ----------------------------------------------------------------
    # Tâche 1.15 — update_status: PENDING_APPROVAL → REJECTED : audit EXECUTION_REJECTED
    # ----------------------------------------------------------------
    def test_update_status_pending_approval_to_rejected_creates_audit(self):
        """1.15: PENDING_APPROVAL → REJECTED → audit EXECUTION_REJECTED created."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        updated = self.service.update_status(
            execution.id, ExecutionStatus.REJECTED, str(self.user.id)
        )
        self.assertEqual(updated.status, ExecutionStatus.REJECTED)

        audit = AuditLog.objects.filter(
            action_type='EXECUTION_REJECTED',
            entity_id=execution.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 1.16/1.17 — list_by_user: offset < 0 et limit <= 0
    # ----------------------------------------------------------------
    def test_list_by_user_negative_offset_raises_value_error(self):
        """1.16: offset < 0 → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.list_by_user(user_id=self.user.id, offset=-1)
        self.assertIn('offset', str(ctx.exception))

    def test_list_by_user_zero_limit_raises_value_error(self):
        """1.17: limit <= 0 → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.list_by_user(user_id=self.user.id, limit=0)
        self.assertIn('limit', str(ctx.exception))

    def test_list_by_user_negative_limit_raises_value_error(self):
        """1.17b: limit < 0 → ValueError."""
        with self.assertRaises(ValueError):
            self.service.list_by_user(user_id=self.user.id, limit=-5)

    # ----------------------------------------------------------------
    # Tâche 1.18 — list_by_user: tous les filtres
    # ----------------------------------------------------------------
    def test_list_by_user_with_all_filters(self):
        """1.18: All filters applied correctly."""
        # Create a known execution
        Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        date_from = timezone.now() - timedelta(hours=1)
        date_to = timezone.now() + timedelta(hours=1)

        qs = self.service.list_by_user(
            user_id=self.user.id,
            status=ExecutionStatus.SUBMITTED,
            environment='dev',
            action_id=self.action.id,
            date_from=date_from,
            date_to=date_to,
            limit=10,
            offset=0,
        )
        result = list(qs)
        self.assertGreaterEqual(len(result), 1)

    # ----------------------------------------------------------------
    # Tâche 1.19 — get_action_stats: action inexistante → ValueError
    # ----------------------------------------------------------------
    def test_get_action_stats_nonexistent_action_raises_value_error(self):
        """1.19: Non-existent action_id → ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.service.get_action_stats(action_id=99999999)
        self.assertIn('does not exist', str(ctx.exception))

    # ----------------------------------------------------------------
    # Tâche 1.20 — get_action_stats: aucune exécution → zeros
    # ----------------------------------------------------------------
    def test_get_action_stats_no_executions_returns_zeros(self):
        """1.20: No executions in period → dict with zeros/None."""
        stats = self.service.get_action_stats(action_id=self.action.id)
        self.assertEqual(stats['total_executions'], 0)
        self.assertEqual(stats['incidents_count'], 0)
        self.assertIsNone(stats['success_rate'])
        self.assertIsNone(stats['avg_execution_time_ms'])

    # ----------------------------------------------------------------
    # Tâche 1.21 — get_action_stats: COMPLETED + FAILED → success_rate calculé
    # ----------------------------------------------------------------
    def test_get_action_stats_with_completed_and_failed(self):
        """1.21: COMPLETED + FAILED → success_rate and avg_execution_time_ms calculated."""
        now = timezone.now()
        started = now - timedelta(seconds=10)

        ex1 = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.COMPLETED,
        )
        ex1.started_at = started
        ex1.completed_at = now
        ex1.save()

        Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.FAILED,
        )

        stats = self.service.get_action_stats(action_id=self.action.id)
        self.assertEqual(stats['total_executions'], 2)
        self.assertEqual(stats['incidents_count'], 1)
        self.assertIsNotNone(stats['success_rate'])
        self.assertEqual(stats['success_rate'], 50.0)
        self.assertIsNotNone(stats['avg_execution_time_ms'])

    # ----------------------------------------------------------------
    # Tâche 1.22 — launch_workflow: action=None → retour immédiat
    # ----------------------------------------------------------------
    def test_launch_workflow_no_action_returns_immediately(self):
        """1.22: execution.action is None → immediate return, no exception."""
        execution = MagicMock()
        execution.action = None
        # Should not raise
        ExecutionService.launch_workflow(execution)

    # ----------------------------------------------------------------
    # Tâche 1.23 — launch_workflow: item_type sans runtime → log debug, pas d'exception
    # ----------------------------------------------------------------
    def test_launch_workflow_no_runtime_registered_does_not_raise(self):
        """1.23: item_type without registered runtime → debug log, no exception."""
        execution = MagicMock()
        execution.action = MagicMock()
        execution.action.item_type = 'unknown_type_xyz'
        execution.id = 999

        with patch('executions.runtime_registry.runtime_registry.get', return_value=None):
            # Should not raise
            ExecutionService.launch_workflow(execution)


# ============================================================================
# Tests supplémentaires — couverture list_all, get_by_id, get_stats, step CRUD
# ============================================================================

@pytest.mark.django_db
class TestExecutionServiceCoverage(TestCase):
    """Tests supplémentaires couvrant list_all, get_by_id, get_stats, step CRUD, notifications."""

    def setUp(self):
        self.user = UserFactory(username='cov_tester')
        self.action = ActionFactory(status='published')
        self.service = ExecutionService()

    # ----------------------------------------------------------------
    # create_execution with source, ip_address, targets params
    # ----------------------------------------------------------------
    def test_create_execution_with_audit_fields(self):
        """create_execution with source, ip_address, targets → audit includes them."""
        import json
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='dev',
            source='api',
            ip_address='10.0.0.1',
            targets=['db-server-01', 'db-server-02'],
        )
        execution = self.service.create_execution(req)
        self.assertIsNotNone(execution.id)
        audit = AuditLog.objects.filter(
            action_type='EXECUTION_SUBMITTED',
            entity_id=execution.id,
        ).first()
        details = json.loads(audit.details)
        self.assertEqual(details.get('source'), 'api')
        self.assertEqual(details.get('ip_address'), '10.0.0.1')
        self.assertIn('targets', details)

    def test_create_execution_with_target_metadata(self):
        """create_execution with validated_targets having metadata dict → metadata_snapshot updated."""
        validated_targets = [
            {
                'name': 'db-server-1',
                'target_type': 'server',
                'environment': 'prod',
                'metadata': {'zone': 'us-east-1', 'os': 'linux'},
                'engine_type': 'oracle',
            }
        ]
        req = ExecutionRequest(
            user=self.user,
            action=self.action,
            environment='prod',
            validated_targets=validated_targets,
        )
        execution = self.service.create_execution(req)
        targets = ExecutionTarget.objects.filter(execution=execution)
        self.assertEqual(targets.count(), 1)

    # ----------------------------------------------------------------
    # create_execution_with_steps without steps_data (False branch)
    # ----------------------------------------------------------------
    def test_create_execution_with_steps_no_steps(self):
        """create_execution_with_steps with no steps_data → execution created, no steps."""
        execution = self.service.create_execution_with_steps(
            user=self.user,
            action=self.action,
            environment='dev',
            steps_data=None,
        )
        self.assertIsNotNone(execution.id)
        self.assertEqual(ExecutionStep.objects.filter(execution=execution).count(), 0)

    # ----------------------------------------------------------------
    # update_status — RUNNING with started_at already set (idempotent)
    # ----------------------------------------------------------------
    def test_update_status_running_started_at_already_set_is_idempotent(self):
        """RUNNING transition when started_at already set → started_at not overwritten."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        execution.started_at = timezone.now() - timedelta(minutes=5)
        execution.save()

        updated = self.service.update_status(execution.id, ExecutionStatus.RUNNING, str(self.user.id))
        self.assertEqual(updated.status, ExecutionStatus.RUNNING)
        self.assertIsNotNone(updated.started_at)

    # ----------------------------------------------------------------
    # update_status — COMPLETED with completed_at already set (idempotent)
    # ----------------------------------------------------------------
    def test_update_status_completed_at_already_set_is_idempotent(self):
        """RUNNING → COMPLETED when completed_at already set → not overwritten."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.RUNNING,
        )
        execution.started_at = timezone.now() - timedelta(minutes=5)
        execution.completed_at = timezone.now() - timedelta(minutes=2)
        execution.save()

        with patch('services.notification_service.NotificationService') as MockNotif:
            MockNotif.return_value.notify_execution_event = MagicMock()
            with self.captureOnCommitCallbacks(execute=True):
                updated = self.service.update_status(
                    execution.id, ExecutionStatus.COMPLETED, str(self.user.id)
                )
        self.assertEqual(updated.status, ExecutionStatus.COMPLETED)

    # ----------------------------------------------------------------
    # update_status — notification via on_commit (captureOnCommitCallbacks)
    # ----------------------------------------------------------------
    def test_update_status_completed_executes_notification_on_commit(self):
        """RUNNING → COMPLETED → on_commit notification fires."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.RUNNING,
        )
        execution.started_at = timezone.now() - timedelta(seconds=5)
        execution.save()

        with patch('services.notification_service.NotificationService') as MockNotif:
            mock_instance = MagicMock()
            MockNotif.return_value = mock_instance
            with self.captureOnCommitCallbacks(execute=True):
                updated = self.service.update_status(
                    execution.id, ExecutionStatus.COMPLETED, str(self.user.id)
                )

        self.assertEqual(updated.status, ExecutionStatus.COMPLETED)
        mock_instance.notify_execution_event.assert_called_once()

    def test_update_status_failed_executes_on_failure_notification(self):
        """RUNNING → FAILED → on_commit on_failure notification fires."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.RUNNING,
        )
        execution.started_at = timezone.now() - timedelta(seconds=5)
        execution.save()

        with patch('services.notification_service.NotificationService') as MockNotif:
            mock_instance = MagicMock()
            MockNotif.return_value = mock_instance
            with self.captureOnCommitCallbacks(execute=True):
                updated = self.service.update_status(
                    execution.id, ExecutionStatus.FAILED, str(self.user.id)
                )

        self.assertEqual(updated.status, ExecutionStatus.FAILED)
        call_kwargs = mock_instance.notify_execution_event.call_args[1]
        self.assertEqual(call_kwargs['event'], 'on_failure')

    def test_update_status_notification_failure_does_not_raise(self):
        """Notification failure inside on_commit → logged, no exception propagated."""
        execution = Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.RUNNING,
        )
        execution.started_at = timezone.now()
        execution.save()

        with patch('services.notification_service.NotificationService') as MockNotif:
            MockNotif.return_value.notify_execution_event.side_effect = Exception("notify failed")
            with self.captureOnCommitCallbacks(execute=True):
                updated = self.service.update_status(
                    execution.id, ExecutionStatus.COMPLETED, str(self.user.id)
                )
        self.assertEqual(updated.status, ExecutionStatus.COMPLETED)

    # ----------------------------------------------------------------
    # list_all — without and with filters
    # ----------------------------------------------------------------
    def test_list_all_no_filters_returns_all_executions(self):
        """list_all without filters → all executions returned with total count."""
        ExecutionFactory.create_batch(3, user=self.user, action=self.action, environment='dev')
        results, total = self.service.list_all()
        self.assertGreaterEqual(total, 3)
        self.assertIsInstance(results, list)

    def test_list_all_with_status_filter(self):
        """list_all with status filter."""
        ExecutionFactory(user=self.user, action=self.action, status=ExecutionStatus.COMPLETED)
        results, total = self.service.list_all(status=ExecutionStatus.COMPLETED)
        self.assertGreaterEqual(total, 1)

    def test_list_all_with_user_id_and_action_id_and_environment_filters(self):
        """list_all with user_id, action_id, environment filters."""
        ExecutionFactory(user=self.user, action=self.action, environment='staging')
        results, total = self.service.list_all(
            user_id=self.user.id,
            action_id=self.action.id,
            environment='staging',
        )
        self.assertGreaterEqual(total, 1)

    def test_list_all_with_date_filters(self):
        """list_all with date_from and date_to filters."""
        ExecutionFactory(user=self.user, action=self.action)
        date_from = timezone.now() - timedelta(hours=1)
        date_to = timezone.now() + timedelta(hours=1)
        results, total = self.service.list_all(date_from=date_from, date_to=date_to)
        self.assertGreaterEqual(total, 0)

    def test_list_all_with_pagination(self):
        """list_all with page=2, page_size=1 → second page."""
        ExecutionFactory.create_batch(3, user=self.user, action=self.action)
        results, total = self.service.list_all(page=2, page_size=1)
        self.assertGreaterEqual(total, 3)
        self.assertLessEqual(len(results), 1)

    # ----------------------------------------------------------------
    # get_by_id
    # ----------------------------------------------------------------
    def test_get_by_id_found_returns_execution(self):
        """get_by_id with valid id → execution returned."""
        execution = ExecutionFactory(user=self.user, action=self.action)
        result = self.service.get_by_id(execution.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, execution.id)

    def test_get_by_id_not_found_returns_none(self):
        """get_by_id with non-existent id → None."""
        result = self.service.get_by_id(99999999)
        self.assertIsNone(result)

    # ----------------------------------------------------------------
    # list_by_user without filters (covers False branches of conditionals)
    # ----------------------------------------------------------------
    def test_list_by_user_no_filters_returns_queryset(self):
        """list_by_user without filters → returns all executions for user."""
        Execution.objects.create(
            action=self.action, user=self.user, environment='dev',
            status=ExecutionStatus.SUBMITTED,
        )
        qs = self.service.list_by_user(user_id=self.user.id)
        result = list(qs)
        self.assertGreaterEqual(len(result), 1)

    def test_list_by_user_with_limit_only(self):
        """list_by_user with limit=2 → slices queryset."""
        for _ in range(3):
            Execution.objects.create(
                action=self.action, user=self.user, environment='dev',
                status=ExecutionStatus.SUBMITTED,
            )
        qs = self.service.list_by_user(user_id=self.user.id, limit=2)
        result = list(qs)
        self.assertLessEqual(len(result), 2)

    def test_list_by_user_with_offset_only(self):
        """list_by_user with offset=1 → skips first element."""
        for _ in range(3):
            Execution.objects.create(
                action=self.action, user=self.user, environment='dev',
                status=ExecutionStatus.SUBMITTED,
            )
        qs = self.service.list_by_user(user_id=self.user.id, offset=1)
        self.assertIsNotNone(qs)

    # ----------------------------------------------------------------
    # get_recent
    # ----------------------------------------------------------------
    def test_get_recent_returns_queryset(self):
        """get_recent() → returns QuerySet of recent executions."""
        ExecutionFactory(user=self.user, action=self.action)
        qs = self.service.get_recent(limit=5)
        self.assertIsNotNone(qs)

    # ----------------------------------------------------------------
    # get_stats
    # ----------------------------------------------------------------
    def test_get_stats_no_user_returns_stats(self):
        """get_stats without user_id → overall stats dict."""
        stats = self.service.get_stats()
        self.assertIn('total', stats)
        self.assertIn('completed', stats)
        self.assertIn('failed', stats)
        self.assertIn('running', stats)
        self.assertIn('success_rate', stats)
        self.assertIn('by_status', stats)
        self.assertIn('by_environment', stats)

    def test_get_stats_with_user_id_filter(self):
        """get_stats with user_id → filtered stats dict."""
        ExecutionFactory(user=self.user, action=self.action, status=ExecutionStatus.COMPLETED)
        stats = self.service.get_stats(user_id=self.user.id)
        self.assertGreaterEqual(stats['total'], 1)
        self.assertEqual(stats['completed'], 1)

    def test_get_stats_with_completions_calculates_success_rate(self):
        """get_stats with COMPLETED + FAILED → success_rate > 0."""
        ExecutionFactory(user=self.user, action=self.action, status=ExecutionStatus.COMPLETED)
        ExecutionFactory(user=self.user, action=self.action, status=ExecutionStatus.FAILED)
        stats = self.service.get_stats(user_id=self.user.id)
        self.assertGreater(stats['total'], 0)
        self.assertGreater(stats['success_rate'], 0)

    # ----------------------------------------------------------------
    # Step CRUD methods
    # ----------------------------------------------------------------
    def test_create_step_creates_execution_step(self):
        """create_step → ExecutionStep created."""
        execution = ExecutionFactory(user=self.user, action=self.action)
        step = self.service.create_step(
            execution=execution,
            step_order=1,
            step_name='Init DB',
            step_type='manual',
        )
        self.assertIsNotNone(step.id)
        self.assertEqual(step.step_name, 'Init DB')

    def test_get_steps_by_execution_returns_ordered_steps(self):
        """get_steps_by_execution → QuerySet ordered by step_order."""
        execution = ExecutionFactory(user=self.user, action=self.action)
        self.service.create_step(execution, 2, 'Step B', 'manual')
        self.service.create_step(execution, 1, 'Step A', 'manual')
        qs = self.service.get_steps_by_execution(execution.id)
        steps = list(qs)
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].step_order, 1)
        self.assertEqual(steps[1].step_order, 2)

    def test_get_step_by_id_found(self):
        """get_step_by_id with valid id → step returned."""
        execution = ExecutionFactory(user=self.user, action=self.action)
        step = self.service.create_step(execution, 1, 'Step 1', 'manual')
        result = self.service.get_step_by_id(step.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, step.id)

    def test_get_step_by_id_not_found_returns_none(self):
        """get_step_by_id with non-existent id → None."""
        result = self.service.get_step_by_id(99999999)
        self.assertIsNone(result)

    def test_update_step_status_updates_status(self):
        """update_step_status → step status updated."""
        execution = ExecutionFactory(user=self.user, action=self.action)
        step = self.service.create_step(execution, 1, 'Step 1', 'manual')
        updated = self.service.update_step_status(step.id, 'COMPLETED')
        self.assertEqual(updated.status, 'COMPLETED')

    def test_update_step_status_with_output(self):
        """update_step_status with output → output stored."""
        execution = ExecutionFactory(user=self.user, action=self.action)
        step = self.service.create_step(execution, 1, 'Step 1', 'manual')
        output = {'result': 'success', 'rows_affected': 10}
        updated = self.service.update_step_status(step.id, 'COMPLETED', output=output)
        self.assertIsNotNone(updated)

    def test_update_step_status_not_found_returns_none(self):
        """update_step_status with non-existent step → None."""
        result = self.service.update_step_status(99999999, 'COMPLETED')
        self.assertIsNone(result)
