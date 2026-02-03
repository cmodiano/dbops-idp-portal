import pytest
import json
from django.test import TestCase
from idp_auth.models import User
from catalog.models import Action
from executions.models import (
    Execution, ExecutionStep, ScheduledExecution, RecurringPattern,
    ExecutionStatus, ExecutionStepStatus, ScheduledExecutionStatus
)


@pytest.mark.django_db
class ExecutionModelTest(TestCase):
    """Tests for Execution model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )

    def test_create_execution(self):
        """Test creating an execution."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status='SUBMITTED'
        )
        self.assertEqual(execution.action, self.action)
        self.assertEqual(execution.user, self.user)
        self.assertEqual(execution.environment, 'dev')
        self.assertEqual(execution.status, 'SUBMITTED')
        self.assertIsNotNone(execution.id)
        self.assertIsNotNone(execution.created_at)

    def test_execution_json_parameters(self):
        """Test JSON parameters field helper."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev'
        )
        params = {'database_name': 'testdb', 'schema': 'test'}
        execution.set_parameters(params)
        execution.save()
        self.assertEqual(execution.get_parameters(), params)

    def test_execution_approval_fields(self):
        """Test approval workflow fields."""
        approver = User.objects.create(
            username='approver',
            profile='DBA'
        )
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='prod',
            status='PENDING_APPROVAL',
            approved_by=approver,
            approval_comment='Approved for production'
        )
        self.assertEqual(execution.approved_by, approver)
        self.assertEqual(execution.approval_comment, 'Approved for production')


@pytest.mark.django_db
class ExecutionStepModelTest(TestCase):
    """Tests for ExecutionStep model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )
        self.execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev'
        )

    def test_create_execution_step(self):
        """Test creating an execution step."""
        step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=1,
            step_name='Retrieve Secrets',
            step_type='vault',
            status='PENDING'
        )
        self.assertEqual(step.execution, self.execution)
        self.assertEqual(step.step_order, 1)
        self.assertEqual(step.step_name, 'Retrieve Secrets')
        self.assertEqual(step.step_type, 'vault')
        self.assertIsNotNone(step.id)

    def test_execution_step_json_output(self):
        """Test JSON output field helper."""
        step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=1,
            step_name='Test Step',
            step_type='platform'
        )
        output = {'job_id': '12345', 'status': 'completed'}
        step.set_output(output)
        step.save()
        self.assertEqual(step.get_output(), output)

    def test_execution_step_unique_order(self):
        """Test that step_order must be unique per execution."""
        ExecutionStep.objects.create(
            execution=self.execution,
            step_order=1,
            step_name='Step 1',
            step_type='vault'
        )
        with self.assertRaises(Exception):  # IntegrityError
            ExecutionStep.objects.create(
                execution=self.execution,
                step_order=1,
                step_name='Step 1 Duplicate',
                step_type='vault'
            )


@pytest.mark.django_db
class ScheduledExecutionModelTest(TestCase):
    """Tests for ScheduledExecution model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )

    def test_create_scheduled_execution(self):
        """Test creating a scheduled execution."""
        from django.utils import timezone
        scheduled = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=timezone.now(),
            status='pending'
        )
        self.assertEqual(scheduled.action, self.action)
        self.assertEqual(scheduled.user, self.user)
        self.assertEqual(scheduled.environment, 'dev')
        self.assertEqual(scheduled.status, 'pending')
        self.assertIsNotNone(scheduled.id)


@pytest.mark.django_db
class RecurringPatternModelTest(TestCase):
    """Tests for RecurringPattern model."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )
        from django.utils import timezone
        self.scheduled = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            scheduled_at=timezone.now()
        )

    def test_create_recurring_pattern(self):
        """Test creating a recurring pattern."""
        from django.utils import timezone
        pattern = RecurringPattern.objects.create(
            scheduled_execution=self.scheduled,
            pattern_type='daily',
            pattern_config='{"hour": 2, "minute": 30}',
            next_execution_date=timezone.now(),
            is_active=1
        )
        self.assertEqual(pattern.scheduled_execution, self.scheduled)
        self.assertEqual(pattern.pattern_type, 'daily')
        self.assertEqual(pattern.is_active, 1)
        self.assertIsNotNone(pattern.id)

    def test_recurring_pattern_json_config(self):
        """Test JSON pattern_config field helper."""
        from django.utils import timezone
        pattern = RecurringPattern.objects.create(
            scheduled_execution=self.scheduled,
            pattern_type='weekly',
            next_execution_date=timezone.now()
        )
        config = {'day_of_week': 1, 'hour': 2, 'minute': 30}
        pattern.set_pattern_config(config)
        pattern.save()
        self.assertEqual(pattern.get_pattern_config(), config)
