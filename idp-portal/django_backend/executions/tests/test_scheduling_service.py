"""
Tests for executions/scheduling_service.py — SchedulingService.
Story 39.4 — Tâche 2.
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone

from executions.models import (
    ScheduledExecutionStatus, RecurringPattern,
)
from executions.scheduling_service import SchedulingService
from core.models import AuditLog
from tests.factories import (
    UserFactory, ActionFactory,
    ScheduledExecutionFactory, RecurringPatternFactory,
)


class TestSchedulingService(TestCase):
    """Tests for SchedulingService — all branches of create/list/update/cancel/pending."""

    def setUp(self):
        self.user = UserFactory(username='scheduler_tester')
        self.action = ActionFactory(status='published')
        self.service = SchedulingService()

    # ----------------------------------------------------------------
    # Tâche 2.1 — create_scheduled_execution sans recurring_pattern_data
    # ----------------------------------------------------------------
    def test_create_without_recurring_pattern_creates_pending_with_audit(self):
        """2.1: No recurring_pattern_data → PENDING status, SCHEDULED_EXECUTION_CREATED audit."""
        scheduled_at = timezone.now() + timedelta(hours=2)
        se = self.service.create_scheduled_execution(
            user=self.user,
            action=self.action,
            environment='dev',
            scheduled_at=scheduled_at,
        )
        self.assertIsNotNone(se.id)
        self.assertEqual(se.status, ScheduledExecutionStatus.PENDING)

        audit = AuditLog.objects.filter(
            action_type='SCHEDULED_EXECUTION_CREATED',
            entity_id=se.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 2.2 — create_scheduled_execution avec recurring_pattern_data
    # ----------------------------------------------------------------
    def test_create_with_recurring_pattern_creates_pattern_and_audit(self):
        """2.2: With recurring_pattern_data → RecurringPattern created, RECURRING_CREATED audit."""
        next_exec = timezone.now() + timedelta(days=1)
        pattern_data = {
            'pattern_type': 'weekly',
            'pattern_config': {'day_of_week': 1, 'hour': 9, 'minute': 0},
            'next_execution_date': next_exec,
            'is_active': 1,
        }
        se = self.service.create_scheduled_execution(
            user=self.user,
            action=self.action,
            environment='dev',
            recurring_pattern_data=pattern_data,
        )
        self.assertEqual(se.status, ScheduledExecutionStatus.PENDING)

        # RecurringPattern should be created
        self.assertTrue(RecurringPattern.objects.filter(scheduled_execution=se).exists())
        pattern = RecurringPattern.objects.get(scheduled_execution=se)
        self.assertEqual(pattern.pattern_type, 'weekly')

        # Audit RECURRING_CREATED
        audit = AuditLog.objects.filter(
            action_type='SCHEDULED_EXECUTION_RECURRING_CREATED',
            entity_id=se.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 2.3 — create_scheduled_execution avec parameters
    # ----------------------------------------------------------------
    def test_create_with_parameters_saves_parameters(self):
        """2.3: With parameters → set_parameters called and saved."""
        params = {'db_name': 'DEVDB', 'target_host': 'db-dev-01'}
        se = self.service.create_scheduled_execution(
            user=self.user,
            action=self.action,
            environment='dev',
            parameters=params,
        )
        # Parameters should be stored
        stored = se.get_parameters()
        self.assertEqual(stored.get('db_name'), 'DEVDB')

    # ----------------------------------------------------------------
    # Tâche 2.4 — list_all sans filtres → pagination
    # ----------------------------------------------------------------
    def test_list_all_without_filters_returns_all_with_pagination(self):
        """2.4: No filters → all scheduled executions with pagination."""
        ScheduledExecutionFactory.create_batch(3, user=self.user, action=self.action)
        results, total = self.service.list_all()
        self.assertGreaterEqual(total, 3)
        self.assertIsInstance(results, list)

    # ----------------------------------------------------------------
    # Tâche 2.5 — list_all avec filtres status, user_id, action_id, scheduled_from/to
    # ----------------------------------------------------------------
    def test_list_all_with_status_filter(self):
        """2.5a: Filter by status."""
        ScheduledExecutionFactory(user=self.user, action=self.action, status='pending')
        results, total = self.service.list_all(status='pending')
        self.assertGreaterEqual(total, 1)
        for r in results:
            self.assertEqual(r.status, 'pending')

    def test_list_all_with_user_id_filter(self):
        """2.5b: Filter by user_id."""
        other_user = UserFactory(username='other_sched_user')
        ScheduledExecutionFactory(user=other_user, action=self.action)
        results, total = self.service.list_all(user_id=other_user.id)
        self.assertGreaterEqual(total, 1)
        for r in results:
            self.assertEqual(r.user_id, other_user.id)

    def test_list_all_with_action_id_filter(self):
        """2.5c: Filter by action_id."""
        other_action = ActionFactory(status='published')
        ScheduledExecutionFactory(user=self.user, action=other_action)
        results, total = self.service.list_all(action_id=other_action.id)
        self.assertGreaterEqual(total, 1)
        for r in results:
            self.assertEqual(r.action_id, other_action.id)

    def test_list_all_with_scheduled_from_filter(self):
        """2.5d: Filter by scheduled_from."""
        scheduled_from = timezone.now() + timedelta(hours=3)
        scheduled_at = timezone.now() + timedelta(hours=5)
        ScheduledExecutionFactory(user=self.user, action=self.action, scheduled_at=scheduled_at)
        results, total = self.service.list_all(scheduled_from=scheduled_from)
        self.assertGreaterEqual(total, 1)
        for r in results:
            self.assertGreaterEqual(
                r.scheduled_at, scheduled_from,
                f"scheduled_at {r.scheduled_at} should be >= scheduled_from {scheduled_from}",
            )

    def test_list_all_with_scheduled_to_filter(self):
        """2.5e: Filter by scheduled_to."""
        scheduled_to = timezone.now() - timedelta(hours=1)
        scheduled_at = timezone.now() - timedelta(hours=5)
        ScheduledExecutionFactory(user=self.user, action=self.action, scheduled_at=scheduled_at)
        results, total = self.service.list_all(scheduled_to=scheduled_to)
        self.assertGreaterEqual(total, 1)
        for r in results:
            self.assertLessEqual(
                r.scheduled_at, scheduled_to,
                f"scheduled_at {r.scheduled_at} should be <= scheduled_to {scheduled_to}",
            )

    # ----------------------------------------------------------------
    # Tâche 2.6 — get_by_id: trouvé → instance retournée
    # ----------------------------------------------------------------
    def test_get_by_id_found_returns_instance(self):
        """2.6: Found → instance returned."""
        se = ScheduledExecutionFactory(user=self.user, action=self.action)
        result = self.service.get_by_id(se.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.id, se.id)

    # ----------------------------------------------------------------
    # Tâche 2.7 — get_by_id: introuvable → None
    # ----------------------------------------------------------------
    def test_get_by_id_not_found_returns_none(self):
        """2.7: Not found → None."""
        result = self.service.get_by_id(99999999)
        self.assertIsNone(result)

    # ----------------------------------------------------------------
    # Tâche 2.8 — update_status: introuvable → None
    # ----------------------------------------------------------------
    def test_update_status_not_found_returns_none(self):
        """2.8: Scheduled execution not found → None."""
        result = self.service.update_status(99999999, ScheduledExecutionStatus.EXECUTED, str(self.user.id))
        self.assertIsNone(result)

    # ----------------------------------------------------------------
    # Tâche 2.9 — update_status: EXECUTED sur recurring active → next_execution_date recalculé
    # ----------------------------------------------------------------
    def test_update_status_executed_recalculates_next_date_for_active_recurring(self):
        """2.9: EXECUTED on active recurring → next_execution_date recalculated."""
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status='pending')
        old_next_date = timezone.now() + timedelta(days=1)
        pattern = RecurringPatternFactory(
            scheduled_execution=se,
            pattern_type='daily',
            pattern_config='{"hour": 10, "minute": 0}',
            next_execution_date=old_next_date,
            is_active=1,
        )

        updated = self.service.update_status(
            se.id, ScheduledExecutionStatus.EXECUTED, str(self.user.id)
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, ScheduledExecutionStatus.EXECUTED)

        pattern.refresh_from_db()
        # next_execution_date should have been recalculated
        self.assertNotEqual(pattern.next_execution_date, old_next_date)

    # ----------------------------------------------------------------
    # Tâche 2.9b — update_status: EXECUTED sur recurring INACTIF → pas de recalcul
    # ----------------------------------------------------------------
    def test_update_status_executed_inactive_recurring_no_recalculation(self):
        """2.9b: EXECUTED on INACTIVE recurring → next_execution_date NOT recalculated."""
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status='pending')
        original_date = timezone.now() + timedelta(days=7)
        pattern = RecurringPatternFactory(
            scheduled_execution=se,
            pattern_type='daily',
            pattern_config='{"hour": 10, "minute": 0}',
            next_execution_date=original_date,
            is_active=0,  # INACTIVE
        )

        updated = self.service.update_status(
            se.id, ScheduledExecutionStatus.EXECUTED, str(self.user.id)
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, ScheduledExecutionStatus.EXECUTED)

        pattern.refresh_from_db()
        # next_execution_date should NOT have changed (is_active=0)
        self.assertEqual(pattern.next_execution_date, original_date)

    # ----------------------------------------------------------------
    # Tâche 2.10 — update_status: CANCELLED → audit SCHEDULED_EXECUTION_CANCELLED
    # ----------------------------------------------------------------
    def test_update_status_cancelled_creates_audit(self):
        """2.10: CANCELLED → SCHEDULED_EXECUTION_CANCELLED audit created."""
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status='pending')
        updated = self.service.update_status(
            se.id, ScheduledExecutionStatus.CANCELLED, str(self.user.id)
        )
        self.assertEqual(updated.status, ScheduledExecutionStatus.CANCELLED)

        audit = AuditLog.objects.filter(
            action_type='SCHEDULED_EXECUTION_CANCELLED',
            entity_id=se.id,
        ).first()
        self.assertIsNotNone(audit)
        # Story 72.2: format standard changes: { status: { old, new } }
        details = audit.get_details() or {}
        self.assertIn('changes', details)
        self.assertIn('status', details['changes'])
        self.assertEqual(details['changes']['status']['old'], ScheduledExecutionStatus.PENDING)
        self.assertEqual(details['changes']['status']['new'], ScheduledExecutionStatus.CANCELLED)

    # ----------------------------------------------------------------
    # Tâche 2.11 — update_status: PENDING → pas d'audit, pas d'exception
    # ----------------------------------------------------------------
    def test_update_status_pending_no_audit_no_exception(self):
        """2.11: Status without audit mapping (PENDING) → no audit, no exception."""
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status='executed')
        count_before = AuditLog.objects.filter(entity_id=se.id).count()

        # PENDING is not in status_to_audit_type map for SchedulingService
        updated = self.service.update_status(
            se.id, ScheduledExecutionStatus.PENDING, str(self.user.id)
        )
        self.assertIsNotNone(updated)
        count_after = AuditLog.objects.filter(entity_id=se.id).count()
        self.assertEqual(count_before, count_after)

    # ----------------------------------------------------------------
    # Tâche 2.12 — cancel_scheduled_execution: introuvable → None
    # ----------------------------------------------------------------
    def test_cancel_not_found_returns_none(self):
        """2.12: Scheduled execution not found → None."""
        result = self.service.cancel_scheduled_execution(99999999, str(self.user.id))
        self.assertIsNone(result)

    # ----------------------------------------------------------------
    # Tâche 2.13 — cancel_scheduled_execution: sans recurring → CANCELLED + audit
    # ----------------------------------------------------------------
    def test_cancel_without_recurring_pattern_cancelled_with_audit(self):
        """2.13: Without recurring pattern → CANCELLED, SCHEDULED_EXECUTION_CANCELLED audit."""
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status='pending')
        # Ensure no recurring pattern
        self.assertFalse(RecurringPattern.objects.filter(scheduled_execution=se).exists())

        result = self.service.cancel_scheduled_execution(se.id, str(self.user.id))
        self.assertEqual(result.status, ScheduledExecutionStatus.CANCELLED)

        audit = AuditLog.objects.filter(
            action_type='SCHEDULED_EXECUTION_CANCELLED',
            entity_id=se.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 2.14 — cancel_scheduled_execution: avec recurring → is_active=0 + RECURRING_DISABLED audit
    # ----------------------------------------------------------------
    def test_cancel_with_recurring_pattern_deactivates_and_creates_audit(self):
        """2.14: With recurring pattern → is_active=0, SCHEDULED_EXECUTION_RECURRING_DISABLED audit."""
        se = ScheduledExecutionFactory(user=self.user, action=self.action, status='pending')
        pattern = RecurringPatternFactory(
            scheduled_execution=se,
            is_active=1,
        )

        result = self.service.cancel_scheduled_execution(se.id, str(self.user.id))
        self.assertEqual(result.status, ScheduledExecutionStatus.CANCELLED)

        pattern.refresh_from_db()
        self.assertEqual(pattern.is_active, 0)

        audit = AuditLog.objects.filter(
            action_type='SCHEDULED_EXECUTION_RECURRING_DISABLED',
            entity_id=se.id,
        ).first()
        self.assertIsNotNone(audit)

    # ----------------------------------------------------------------
    # Tâche 2.15 — list_pending: sans before_datetime → utilise timezone.now()
    # ----------------------------------------------------------------
    def test_list_pending_without_before_datetime_uses_now(self):
        """2.15: No before_datetime → uses timezone.now() as threshold."""
        # Create a pending execution scheduled in the past
        past = timezone.now() - timedelta(hours=1)
        se = ScheduledExecutionFactory(
            user=self.user, action=self.action,
            status='pending', scheduled_at=past,
        )
        qs = self.service.list_pending()
        # Should return a queryset without error
        self.assertIsNotNone(qs)
        result_ids = list(qs.values_list('id', flat=True))
        self.assertIn(se.id, result_ids)

    # ----------------------------------------------------------------
    # Tâche 2.16 — list_pending: avec before_datetime → délègue à objects.list_pending
    # ----------------------------------------------------------------
    def test_list_pending_with_explicit_before_datetime(self):
        """2.16: With explicit before_datetime → delegates to ScheduledExecution.objects.list_pending."""
        explicit_dt = timezone.now() + timedelta(hours=24)
        before_dt = timezone.now() - timedelta(hours=1)
        after_dt = timezone.now() + timedelta(hours=48)
        se_before = ScheduledExecutionFactory(
            user=self.user, action=self.action,
            status='pending', scheduled_at=before_dt,
        )
        se_after = ScheduledExecutionFactory(
            user=self.user, action=self.action,
            status='pending', scheduled_at=after_dt,
        )
        qs = self.service.list_pending(before_datetime=explicit_dt)
        self.assertIsNotNone(qs)
        result_ids = list(qs.values_list('id', flat=True))
        self.assertIn(se_before.id, result_ids)
        self.assertNotIn(se_after.id, result_ids)
