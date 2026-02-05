"""
Tests for executions managers (ExecutionManager, ScheduledExecutionManager).
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from idp_auth.models import User
from catalog.models import Action
from executions.models import Execution, ExecutionStatus, ScheduledExecution, ScheduledExecutionStatus


@pytest.mark.django_db
class TestExecutionManager(TestCase):
    """Tests for ExecutionManager."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action',
            engine='Oracle',
            platform='AAP',
            status='published'
        )
    
    def test_list_by_user(self):
        """Test list_by_user() returns executions for specific user."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        
        results = Execution.objects.list_by_user(self.user.id)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].id, execution.id)
    
    def test_list_by_status(self):
        """Test list_by_status() filters by status."""
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )
        
        submitted = Execution.objects.list_by_status(ExecutionStatus.SUBMITTED)
        self.assertEqual(submitted.count(), 1)
        
        completed = Execution.objects.list_by_status(ExecutionStatus.COMPLETED)
        self.assertEqual(completed.count(), 1)
    
    def test_get_recent(self):
        """Test get_recent() returns recent executions."""
        for i in range(5):
            Execution.objects.create(
                action=self.action,
                user=self.user,
                environment='dev',
                status=ExecutionStatus.COMPLETED
            )
        
        recent = Execution.objects.get_recent(limit=3)
        self.assertEqual(len(list(recent)), 3)

    def test_with_action(self):
        """Test with_action() uses select_related to avoid N+1 queries."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )

        exec_with_action = Execution.objects.with_action().get(id=execution.id)
        # Access action without additional query
        self.assertEqual(exec_with_action.action.name, 'Test Action')

    def test_with_user(self):
        """Test with_user() uses select_related to avoid N+1 queries."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )

        exec_with_user = Execution.objects.with_user().get(id=execution.id)
        # Access user without additional query
        self.assertEqual(exec_with_user.user.username, 'testuser')


@pytest.mark.django_db
class TestExecutionManagerAdvanced(TestCase):
    """Story M.9: Advanced tests for ExecutionManager."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='testuser_adv', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action Adv',
            engine='Oracle',
            platform='AAP',
            status='published'
        )

    def test_filter_by_environment(self):
        """Test filtering executions by environment."""
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='staging',
            status=ExecutionStatus.COMPLETED
        )
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='prod',
            status=ExecutionStatus.COMPLETED
        )

        dev_execs = Execution.objects.filter(environment='dev')
        self.assertEqual(dev_execs.count(), 1)

        staging_execs = Execution.objects.filter(environment='staging')
        self.assertEqual(staging_execs.count(), 1)

        prod_execs = Execution.objects.filter(environment='prod')
        self.assertEqual(prod_execs.count(), 1)

    def test_filter_by_date_range(self):
        """Test filtering executions by date range."""
        from datetime import timedelta

        now = timezone.now()
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )
        recent_execs = Execution.objects.filter(created_at__gte=now - timedelta(days=1))
        self.assertGreaterEqual(recent_execs.count(), 1)

    def test_list_by_status_multiple(self):
        """Test listing executions by multiple statuses."""
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.RUNNING
        )
        Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.COMPLETED
        )

        active_statuses = [ExecutionStatus.SUBMITTED, ExecutionStatus.RUNNING]
        active_execs = Execution.objects.filter(status__in=active_statuses)
        self.assertEqual(active_execs.count(), 2)

    def test_parameters_json_serialization(self):
        """Test execution parameters JSON field serialization."""
        params = {'target_host': 'db-01.example.com', 'database_name': 'ORCL'}
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ExecutionStatus.SUBMITTED
        )
        execution.set_parameters(params)
        execution.save()

        # Reload from DB
        execution.refresh_from_db()
        loaded_params = execution.get_parameters()

        self.assertEqual(loaded_params['target_host'], 'db-01.example.com')
        self.assertEqual(loaded_params['database_name'], 'ORCL')


@pytest.mark.django_db
class TestScheduledExecutionManager(TestCase):
    """Story M.9: Tests for ScheduledExecutionManager."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(username='testuser_sched', profile='DBA')
        self.action = Action.objects.create(
            name='Test Action Sched',
            engine='Oracle',
            platform='AAP',
            status='published'
        )

    def test_list_by_user(self):
        """Test list_by_user() returns scheduled executions for user."""
        scheduled = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ScheduledExecutionStatus.PENDING,
            scheduled_at=timezone.now() + timezone.timedelta(hours=1)
        )

        results = ScheduledExecution.objects.list_by_user(self.user.id)
        self.assertEqual(results.count(), 1)
        self.assertEqual(results[0].id, scheduled.id)

    def test_list_by_status(self):
        """Test list_by_status() filters by status."""
        ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ScheduledExecutionStatus.PENDING,
            scheduled_at=timezone.now() + timezone.timedelta(hours=1)
        )
        ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ScheduledExecutionStatus.EXECUTED,
            scheduled_at=timezone.now() - timezone.timedelta(hours=1)
        )

        pending = ScheduledExecution.objects.list_by_status(ScheduledExecutionStatus.PENDING)
        self.assertEqual(pending.count(), 1)

        executed = ScheduledExecution.objects.list_by_status(ScheduledExecutionStatus.EXECUTED)
        self.assertEqual(executed.count(), 1)

    def test_list_pending_one_time(self):
        """Test list_pending() returns one-time scheduled executions due."""
        past_scheduled = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ScheduledExecutionStatus.PENDING,
            scheduled_at=timezone.now() - timezone.timedelta(hours=1)  # In the past
        )
        future_scheduled = ScheduledExecution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status=ScheduledExecutionStatus.PENDING,
            scheduled_at=timezone.now() + timezone.timedelta(hours=24)  # Far future
        )

        now = timezone.now()
        pending = ScheduledExecution.objects.list_pending(now)
        # Should include past_scheduled but not future_scheduled
        pending_ids = [p.id for p in pending]
        self.assertIn(past_scheduled.id, pending_ids)
        self.assertNotIn(future_scheduled.id, pending_ids)
