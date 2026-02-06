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


# =============================================================================
# Story 13.2: Target-based execution tests
# =============================================================================

@pytest.mark.django_db
class ExecutionWithTargetsTest(TestCase):
    """Tests for execution creation with target_names (Story 13.2, Task 8.3-8.4)."""

    def setUp(self):
        """Set up test data."""
        from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission

        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        # Set AD groups for RBAC
        self.user.groups = ['DBA_GROUP']

        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=True
        )

        # Create a profile with permissions
        self.profile = Profile.objects.create(
            name='Test Profile',
            ad_group='DBA_GROUP',
            is_admin=False,
            is_auditor=False
        )
        # Add action permissions with dev environment
        ProfileActionPermission.objects.create(
            profile=self.profile,
            permission_type='ALL',
            environments='["dev", "staging", "prod"]'
        )
        # Add target permissions (all targets)
        ProfileTargetPermission.objects.create(
            profile=self.profile,
            permission_type='ALL'
        )

    def test_execution_stores_targets_in_parameters(self):
        """Test that target_names are stored in parameters._targets."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='dev',
            status='SUBMITTED'
        )
        params = {'_targets': ['srv-dev-01', 'srv-dev-02'], 'other_param': 'value'}
        execution.set_parameters(params)
        execution.save()

        retrieved = execution.get_parameters()
        self.assertEqual(retrieved['_targets'], ['srv-dev-01', 'srv-dev-02'])
        self.assertEqual(retrieved['other_param'], 'value')

    def test_execution_requires_target_field(self):
        """Test that requires_target field is correctly stored on Action."""
        action_with_target = Action.objects.create(
            name='Action With Target',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            requires_target=True
        )
        self.assertTrue(action_with_target.requires_target)

        action_without_target = Action.objects.create(
            name='Action Without Target',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            requires_target=False
        )
        self.assertFalse(action_without_target.requires_target)

    def test_execution_requires_target_default_true(self):
        """Test that requires_target defaults to True."""
        action_default = Action.objects.create(
            name='Action Default Target',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )
        self.assertTrue(action_default.requires_target)


@pytest.mark.django_db
class ExecutionViewTargetsTest(TestCase):
    """Integration tests for POST /executions with target_names (Story 13.2, Task 8.3)."""

    def setUp(self):
        """Set up test data."""
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = User.objects.create(
            username='testuser',
            profile='DBA'
        )
        self.user.groups = ['DBA_GROUP']
        self.client.force_authenticate(user=self.user)

        self.action = Action.objects.create(
            name='Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=True
        )

    def test_post_execution_requires_action_id(self):
        """Test that action_id is required."""
        response = self.client.post('/api/v1/executions', {
            'environment': 'dev'
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('action_id', str(response.data))

    def test_post_execution_requires_environment_or_targets(self):
        """Test that either environment or target_names is required."""
        response = self.client.post('/api/v1/executions', {
            'action_id': self.action.id
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('environment', str(response.data).lower())

    def test_post_execution_with_environment_only(self):
        """Test creating execution with environment only (backward compatibility)."""
        response = self.client.post('/api/v1/executions', {
            'action_id': self.action.id,
            'environment': 'dev'
        }, format='json')
        # Should succeed (backward compatibility)
        self.assertEqual(response.status_code, 201)
        self.assertIn('execution_id', response.data.get('data', {}))

    def test_post_execution_target_names_must_be_list(self):
        """Test that target_names must be a non-empty list."""
        response = self.client.post('/api/v1/executions', {
            'action_id': self.action.id,
            'target_names': 'not-a-list'
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('list', str(response.data).lower())

    def test_post_execution_target_names_not_empty(self):
        """Test that target_names must not be empty."""
        response = self.client.post('/api/v1/executions', {
            'action_id': self.action.id,
            'target_names': []
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('vide', str(response.data).lower())

    def test_post_execution_with_target_names_success(self):
        """Test successful execution creation with target_names when InventoryService returns allowed targets (Story 13.2, Task 8.3)."""
        from unittest.mock import patch, MagicMock

        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-dev-02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.views.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2)
            MockInventoryService.return_value = mock_instance

            response = self.client.post('/api/v1/executions', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
                'parameters': {},
            }, format='json')

        self.assertEqual(response.status_code, 201)
        data = response.data.get('data', {})
        self.assertIn('execution_id', data)
        self.assertIn('status', data)
        self.assertIn('created_at', data)

        execution = Execution.objects.get(id=data['execution_id'])
        self.assertEqual(execution.environment, 'dev')
        params = execution.get_parameters()
        self.assertIsNotNone(params)
        self.assertEqual(params.get('_targets'), ['srv-dev-01'])
