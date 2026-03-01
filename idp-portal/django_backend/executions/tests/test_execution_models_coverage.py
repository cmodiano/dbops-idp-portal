"""
Coverage tests for executions/models.py.

Targets missing lines:
  91, 170, 178-180, 188, 236-238, 311, 319-321, 329,
  412, 420-423, 430, 470, 473, 481-484, 491
plus additional manager/str/JSON helpers for full ≥90% coverage.
"""

import json
import pytest
from django.test import TestCase
from django.utils import timezone

from tests.factories import (
    UserFactory,
    ActionFactory,
    ExecutionFactory,
    ExecutionStepFactory,
    ScheduledExecutionFactory,
    RecurringPatternFactory,
    ExecutionTargetFactory,
)
from executions.models import (
    Execution,
    ScheduledExecution,
    ScheduledExecutionStatus,
)


# ---------------------------------------------------------------------------
# ExecutionManager — missing branches (lines 54, 66, 79, 83, 87, 91)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionManagerCoverage(TestCase):
    """Ensure all ExecutionManager methods are exercised."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()

    def test_list_by_user_returns_queryset(self):
        """Line 54: list_by_user return value is evaluated."""
        exec1 = ExecutionFactory(user=self.user, action=self.action)
        other_user = UserFactory()
        ExecutionFactory(user=other_user, action=self.action)

        qs = Execution.objects.list_by_user(self.user.id)
        ids = list(qs.values_list('id', flat=True))
        self.assertIn(exec1.id, ids)
        self.assertEqual(len(ids), 1)

    def test_list_by_status_returns_queryset(self):
        """Line 66: list_by_status return value is evaluated."""
        ExecutionFactory(user=self.user, action=self.action, status='RUNNING')
        ExecutionFactory(user=self.user, action=self.action, status='COMPLETED')

        running = list(Execution.objects.list_by_status('RUNNING'))
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0].status, 'RUNNING')

    def test_get_recent_returns_queryset(self):
        """Line 79: get_recent return value is evaluated (select_related + slice)."""
        for _ in range(3):
            ExecutionFactory(user=self.user, action=self.action)

        recent = list(Execution.objects.get_recent(limit=2))
        self.assertEqual(len(recent), 2)

    def test_with_action_returns_queryset(self):
        """Line 83: with_action return value is evaluated."""
        exec1 = ExecutionFactory(user=self.user, action=self.action)
        result = Execution.objects.with_action().get(id=exec1.id)
        self.assertEqual(result.action.id, self.action.id)

    def test_with_user_returns_queryset(self):
        """Line 87: with_user return value is evaluated."""
        exec1 = ExecutionFactory(user=self.user, action=self.action)
        result = Execution.objects.with_user().get(id=exec1.id)
        self.assertEqual(result.user.id, self.user.id)

    def test_with_steps_returns_queryset(self):
        """Line 91: with_steps return value is evaluated (prefetch_related)."""
        exec1 = ExecutionFactory(user=self.user, action=self.action)
        ExecutionStepFactory(execution=exec1, step_order=1)
        ExecutionStepFactory(execution=exec1, step_order=2)

        qs = Execution.objects.with_steps().filter(id=exec1.id)
        result = list(qs)
        self.assertEqual(len(result), 1)
        # prefetch_related: _prefetched_objects_cache should exist after evaluation
        steps = list(result[0].executionstep_set.all())
        self.assertEqual(len(steps), 2)


# ---------------------------------------------------------------------------
# Execution.__str__ and JSON helpers (lines 170, 178-181, 188)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionStrAndJSON(TestCase):
    """Cover Execution.__str__ and get/set_parameters edge cases."""

    def setUp(self):
        self.execution = ExecutionFactory()

    def test_str_representation(self):
        """Line 170: __str__ returns expected string."""
        s = str(self.execution)
        self.assertIn(str(self.execution.id), s)
        self.assertIn(self.execution.action.name, s)
        self.assertIn(self.execution.status, s)

    def test_get_parameters_invalid_json_returns_none(self):
        """Lines 178-180: get_parameters handles JSONDecodeError gracefully."""
        self.execution.parameters = "not-valid-json{{{"
        result = self.execution.get_parameters()
        self.assertIsNone(result)

    def test_set_parameters_none_sets_null(self):
        """Line 188: set_parameters(None) sets parameters to None."""
        self.execution.set_parameters({'key': 'value'})
        self.assertIsNotNone(self.execution.parameters)
        self.execution.set_parameters(None)
        self.assertIsNone(self.execution.parameters)

    def test_get_parameters_none_when_empty(self):
        """get_parameters returns None when parameters field is empty."""
        self.execution.parameters = None
        self.assertIsNone(self.execution.get_parameters())

        self.execution.parameters = ''
        self.assertIsNone(self.execution.get_parameters())


# ---------------------------------------------------------------------------
# ExecutionTarget.__str__ and JSON helpers (lines 229, 233-239, 246)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionTargetCoverage(TestCase):
    """Cover ExecutionTarget.__str__ and get/set_target_metadata."""

    def setUp(self):
        self.target = ExecutionTargetFactory()

    def test_str_representation(self):
        """Line 229: __str__ returns expected string."""
        s = str(self.target)
        self.assertIn(self.target.target_type, s)
        self.assertIn(self.target.target_name, s)

    def test_get_target_metadata_valid_json(self):
        """Lines 233-235: get_target_metadata returns dict for valid JSON."""
        self.target.set_target_metadata({'env': 'dev', 'rack': 'A1'})
        result = self.target.get_target_metadata()
        self.assertEqual(result, {'env': 'dev', 'rack': 'A1'})

    def test_get_target_metadata_invalid_json_returns_none(self):
        """Lines 236-238: get_target_metadata handles invalid JSON gracefully."""
        self.target.target_metadata = "{{invalid-json"
        result = self.target.get_target_metadata()
        self.assertIsNone(result)

    def test_get_target_metadata_none_when_empty(self):
        """Line 239 branch: returns None when target_metadata is falsy."""
        self.target.target_metadata = None
        self.assertIsNone(self.target.get_target_metadata())

    def test_set_target_metadata_none_sets_null(self):
        """Line 246: set_target_metadata(None) sets field to None."""
        self.target.set_target_metadata({'key': 'val'})
        self.assertIsNotNone(self.target.target_metadata)
        self.target.set_target_metadata(None)
        self.assertIsNone(self.target.target_metadata)


# ---------------------------------------------------------------------------
# ExecutionStep.__str__ and JSON helpers (lines 311, 319-322, 329)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionStepCoverage(TestCase):
    """Cover ExecutionStep.__str__ and get/set_output edge cases."""

    def setUp(self):
        execution = ExecutionFactory()
        self.step = ExecutionStepFactory(execution=execution, step_order=1)

    def test_str_representation(self):
        """Line 311: __str__ returns expected string."""
        s = str(self.step)
        self.assertIn(str(self.step.step_order), s)
        self.assertIn(self.step.step_name, s)
        self.assertIn(self.step.status, s)

    def test_get_output_invalid_json_returns_none(self):
        """Lines 319-321: get_output handles JSONDecodeError gracefully."""
        self.step.output = "<<not-json>>"
        result = self.step.get_output()
        self.assertIsNone(result)

    def test_set_output_none_sets_null(self):
        """Line 329: set_output(None) sets output to None."""
        self.step.set_output({'job_id': '999'})
        self.assertIsNotNone(self.step.output)
        self.step.set_output(None)
        self.assertIsNone(self.step.output)

    def test_get_output_none_when_empty(self):
        """get_output returns None when output field is empty."""
        self.step.output = None
        self.assertIsNone(self.step.get_output())

        self.step.output = ''
        self.assertIsNone(self.step.get_output())


# ---------------------------------------------------------------------------
# ScheduledExecutionManager (lines 347, 351, 358-359)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScheduledExecutionManagerCoverage(TestCase):
    """Cover ScheduledExecutionManager methods."""

    def setUp(self):
        self.user = UserFactory()
        self.action = ActionFactory()

    def test_list_by_user_returns_queryset(self):
        """Line 347: list_by_user return value is evaluated."""
        sched = ScheduledExecutionFactory(user=self.user, action=self.action)
        other_user = UserFactory()
        ScheduledExecutionFactory(user=other_user, action=self.action)

        qs = ScheduledExecution.objects.list_by_user(self.user.id)
        ids = list(qs.values_list('id', flat=True))
        self.assertIn(sched.id, ids)
        self.assertEqual(len(ids), 1)

    def test_list_by_status_returns_queryset(self):
        """Line 351: list_by_status return value is evaluated."""
        ScheduledExecutionFactory(
            user=self.user, action=self.action,
            status=ScheduledExecutionStatus.PENDING
        )
        ScheduledExecutionFactory(
            user=self.user, action=self.action,
            status=ScheduledExecutionStatus.EXECUTED
        )

        pending = list(ScheduledExecution.objects.list_by_status(ScheduledExecutionStatus.PENDING))
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].status, ScheduledExecutionStatus.PENDING)

    def test_list_pending_returns_due_executions(self):
        """Lines 358-359: list_pending return value is evaluated."""
        past = ScheduledExecutionFactory(
            user=self.user, action=self.action,
            status=ScheduledExecutionStatus.PENDING,
            scheduled_at=timezone.now() - timezone.timedelta(hours=2),
        )
        future = ScheduledExecutionFactory(
            user=self.user, action=self.action,
            status=ScheduledExecutionStatus.PENDING,
            scheduled_at=timezone.now() + timezone.timedelta(hours=24),
        )

        due = list(ScheduledExecution.objects.list_pending(timezone.now()))
        due_ids = [s.id for s in due]
        self.assertIn(past.id, due_ids)
        self.assertNotIn(future.id, due_ids)


# ---------------------------------------------------------------------------
# ScheduledExecution.__str__ and JSON helpers (lines 412, 420-423, 430)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScheduledExecutionCoverage(TestCase):
    """Cover ScheduledExecution.__str__ and get/set_parameters edge cases."""

    def setUp(self):
        self.scheduled = ScheduledExecutionFactory()

    def test_str_representation(self):
        """Line 412: __str__ returns expected string."""
        s = str(self.scheduled)
        self.assertIn(str(self.scheduled.id), s)
        self.assertIn(self.scheduled.action.name, s)
        self.assertIn(self.scheduled.status, s)

    def test_get_parameters_valid_json(self):
        """Lines 417-419: get_parameters returns dict for valid JSON."""
        self.scheduled.set_parameters({'host': 'db-01'})
        result = self.scheduled.get_parameters()
        self.assertEqual(result, {'host': 'db-01'})

    def test_get_parameters_invalid_json_returns_none(self):
        """Lines 420-422: get_parameters handles JSONDecodeError gracefully."""
        self.scheduled.parameters = "{{bad-json"
        result = self.scheduled.get_parameters()
        self.assertIsNone(result)

    def test_get_parameters_none_when_empty(self):
        """Line 423 branch: returns None when parameters is falsy."""
        self.scheduled.parameters = None
        self.assertIsNone(self.scheduled.get_parameters())

        self.scheduled.parameters = ''
        self.assertIsNone(self.scheduled.get_parameters())

    def test_set_parameters_serializes_dict(self):
        """Lines 427-428: set_parameters serializes a dict to JSON string."""
        self.scheduled.set_parameters({'key': 'value'})
        self.assertEqual(json.loads(self.scheduled.parameters), {'key': 'value'})

    def test_set_parameters_none_sets_null(self):
        """Line 430: set_parameters(None) sets parameters to None."""
        self.scheduled.set_parameters({'key': 'value'})
        self.assertIsNotNone(self.scheduled.parameters)
        self.scheduled.set_parameters(None)
        self.assertIsNone(self.scheduled.parameters)


# ---------------------------------------------------------------------------
# RecurringPattern.is_active_bool, __str__, get/set_pattern_config
# (lines 470, 473, 481-484, 491)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRecurringPatternCoverage(TestCase):
    """Cover RecurringPattern properties, __str__ and get/set_pattern_config."""

    def setUp(self):
        self.pattern = RecurringPatternFactory()

    def test_is_active_bool_true(self):
        """Line 470: is_active_bool returns True when is_active == 1."""
        self.pattern.is_active = 1
        self.assertTrue(self.pattern.is_active_bool)

    def test_is_active_bool_false(self):
        """Line 470 branch: is_active_bool returns False when is_active != 1."""
        self.pattern.is_active = 0
        self.assertFalse(self.pattern.is_active_bool)

    def test_str_representation(self):
        """Line 473: __str__ returns expected string."""
        s = str(self.pattern)
        self.assertIn(str(self.pattern.id), s)
        self.assertIn(self.pattern.pattern_type, s)

    def test_get_pattern_config_valid_json(self):
        """Lines 479-480: get_pattern_config returns dict for valid JSON."""
        self.pattern.set_pattern_config({'hour': 3, 'minute': 0})
        result = self.pattern.get_pattern_config()
        self.assertEqual(result, {'hour': 3, 'minute': 0})

    def test_get_pattern_config_invalid_json_returns_none(self):
        """Lines 481-483: get_pattern_config handles invalid JSON gracefully."""
        self.pattern.pattern_config = "{{invalid"
        result = self.pattern.get_pattern_config()
        self.assertIsNone(result)

    def test_get_pattern_config_none_when_empty(self):
        """Line 484 branch: returns None when pattern_config is falsy."""
        self.pattern.pattern_config = None
        self.assertIsNone(self.pattern.get_pattern_config())

        self.pattern.pattern_config = ''
        self.assertIsNone(self.pattern.get_pattern_config())

    def test_set_pattern_config_serializes_dict(self):
        """Lines 488-489: set_pattern_config serializes a dict to JSON string."""
        self.pattern.set_pattern_config({'day': 'monday'})
        self.assertEqual(json.loads(self.pattern.pattern_config), {'day': 'monday'})

    def test_set_pattern_config_none_sets_null(self):
        """Line 491: set_pattern_config(None) sets pattern_config to None."""
        self.pattern.set_pattern_config({'day': 'monday'})
        self.assertIsNotNone(self.pattern.pattern_config)
        self.pattern.set_pattern_config(None)
        self.assertIsNone(self.pattern.pattern_config)
