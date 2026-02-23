"""
Tests for BUG-BE-4: calculate next_execution_date uses pattern_type and pattern_config.
Story 30.3 — AC3.

Verifies that update_scheduled_execution() uses calculate_next_execution_date()
instead of a hardcoded timedelta(days=1).
"""

import json
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from executions.models import (
    ScheduledExecution, ScheduledExecutionStatus, RecurringPattern
)
from catalog.models import Action
from tests.factories import UserFactory


@pytest.mark.django_db
class TestRecurrenceCalculationOnExecuted(TestCase):
    """Tests that next_execution_date is properly calculated when status → EXECUTED."""

    def setUp(self):
        self.user = UserFactory(profile='dba')
        self.action = Action.objects.create(
            name='Recurrence Action',
            category='Maintenance',
            engine='Oracle',
            platform='AAP',
        )
        self.now = timezone.now()

    def _create_scheduled_with_pattern(self, pattern_type, pattern_config):
        """Helper to create ScheduledExecution with a RecurringPattern."""
        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=self.now,
            status=ScheduledExecutionStatus.PENDING,
        )
        pattern = RecurringPattern.objects.create(
            scheduled_execution=se,
            pattern_type=pattern_type,
            pattern_config=json.dumps(pattern_config),
            next_execution_date=self.now,
            is_active=1,
        )
        return se, pattern

    def test_daily_pattern_next_execution_date(self):
        """Daily pattern → next_execution_date should be ~1 day ahead (via calculate function)."""
        from executions.services import SchedulingService
        service = SchedulingService()

        se, pattern = self._create_scheduled_with_pattern('daily', {'hour': 9, 'minute': 0})

        service.update_status(
            se.id, ScheduledExecutionStatus.EXECUTED, user_id=str(self.user.id)
        )

        pattern.refresh_from_db()
        # Should be at 09:00 tomorrow or later, NOT just now + 1 day
        delta = pattern.next_execution_date - self.now
        assert delta.total_seconds() > 0, "next_execution_date should be in the future"
        assert delta.days <= 1, "next_execution_date should be within ~1 day for daily"

    def test_weekly_pattern_next_execution_date(self):
        """Weekly pattern → next_execution_date should be ~7 days ahead."""
        from executions.services import SchedulingService
        service = SchedulingService()

        # Use the current day of the week so it schedules 7 days from now
        current_dow = self.now.isoweekday()
        se, pattern = self._create_scheduled_with_pattern(
            'weekly', {'day_of_week': current_dow, 'hour': 9, 'minute': 0}
        )

        service.update_status(
            se.id, ScheduledExecutionStatus.EXECUTED, user_id=str(self.user.id)
        )

        pattern.refresh_from_db()
        delta = pattern.next_execution_date - self.now
        # Should be close to 7 days (between 6 and 8 days to account for hour differences)
        assert 5 <= delta.days <= 8, f"Weekly pattern should be ~7 days ahead, got {delta.days} days"

    def test_cron_pattern_next_execution_date(self):
        """Cron pattern '0 9 * * MON' → next_execution_date should be next Monday 9h."""
        from executions.services import SchedulingService
        service = SchedulingService()

        se, pattern = self._create_scheduled_with_pattern(
            'cron', {'cron_expression': '0 9 * * MON'}
        )

        service.update_status(
            se.id, ScheduledExecutionStatus.EXECUTED, user_id=str(self.user.id)
        )

        pattern.refresh_from_db()
        # next_execution_date should be on a Monday at 09:00
        assert pattern.next_execution_date.weekday() == 0, "Should be a Monday"
        assert pattern.next_execution_date.hour == 9, "Should be at 9h"
        assert pattern.next_execution_date > self.now, "Should be in the future"

    def test_inactive_pattern_not_updated(self):
        """Inactive pattern should not have its next_execution_date updated."""
        from executions.services import SchedulingService
        service = SchedulingService()

        se = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=self.now,
            status=ScheduledExecutionStatus.PENDING,
        )
        original_date = self.now - timedelta(days=1)
        pattern = RecurringPattern.objects.create(
            scheduled_execution=se,
            pattern_type='daily',
            pattern_config=json.dumps({'hour': 9, 'minute': 0}),
            next_execution_date=original_date,
            is_active=0,  # Inactive
        )

        service.update_status(
            se.id, ScheduledExecutionStatus.EXECUTED, user_id=str(self.user.id)
        )

        pattern.refresh_from_db()
        assert pattern.next_execution_date == original_date, "Inactive pattern should not be updated"
