import pytest
from django.test import TestCase
from idp_auth.models import User
from catalog.models import Action
from executions.models import (
    Execution, ExecutionStep, ExecutionStepStatus, ExecutionStepType,
    ExecutionStatus, ScheduledExecution, RecurringPattern
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
            environment='developpement',
            status='SUBMITTED'
        )
        self.assertEqual(execution.action, self.action)
        self.assertEqual(execution.user, self.user)
        self.assertEqual(execution.environment, 'developpement')
        self.assertEqual(execution.status, 'SUBMITTED')
        self.assertIsNotNone(execution.id)
        self.assertIsNotNone(execution.created_at)

    def test_execution_json_parameters(self):
        """Test JSON parameters field helper."""
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='developpement'
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
            environment='production',
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
            environment='developpement'
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

    # --- Story 57.1 : Tests nouveaux types et champs d'approbation ---

    def test_execution_step_type_all_nine_values(self):
        """AC#2 : ExecutionStepType doit avoir exactement 9 valeurs."""
        expected_values = {
            'vault', 'servicenow', 'platform', 'prerequisite', 'verification',
            'service_call', 'http_request', 'evaluation', 'gate',
        }
        actual_values = {choice[0] for choice in ExecutionStepType.choices}
        self.assertEqual(actual_values, expected_values)

    def test_execution_step_type_new_values(self):
        """AC#2 : Les 4 nouvelles valeurs ADR-007 sont présentes dans l'enum."""
        self.assertEqual(ExecutionStepType.SERVICE_CALL, 'service_call')
        self.assertEqual(ExecutionStepType.HTTP_REQUEST, 'http_request')
        self.assertEqual(ExecutionStepType.EVALUATION, 'evaluation')
        self.assertEqual(ExecutionStepType.GATE, 'gate')

    def test_execution_step_type_existing_values_preserved(self):
        """AC#2 : Les 5 valeurs existantes sont conservées."""
        self.assertEqual(ExecutionStepType.VAULT, 'vault')
        self.assertEqual(ExecutionStepType.SERVICENOW, 'servicenow')
        self.assertEqual(ExecutionStepType.PLATFORM, 'platform')
        self.assertEqual(ExecutionStepType.PREREQUISITE, 'prerequisite')
        self.assertEqual(ExecutionStepType.VERIFICATION, 'verification')

    def test_create_execution_step_with_new_types(self):
        """AC#2 : Création d'un step avec chaque nouveau type ADR-007."""
        new_types = [
            ('service_call', 2),
            ('http_request', 3),
            ('evaluation', 4),
            ('gate', 5),
        ]
        for step_type, order in new_types:
            step = ExecutionStep.objects.create(
                execution=self.execution,
                step_order=order,
                step_name=f'Step {step_type}',
                step_type=step_type,
            )
            self.assertEqual(step.step_type, step_type)

    def test_create_execution_step_with_approval_fields(self):
        """AC#1 : Création d'un step avec les champs d'approbation renseignés."""
        from django.utils import timezone
        approver = User.objects.create(username='approver57', profile='DBA')
        now = timezone.now()
        step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=10,
            step_name='Gate Step',
            step_type='gate',
            approved_by=approver,
            approved_at=now,
            approval_comment='Approuvé pour production',
        )
        self.assertEqual(step.approved_by, approver)
        self.assertEqual(step.approved_at, now)
        self.assertEqual(step.approval_comment, 'Approuvé pour production')

    def test_execution_step_approval_fields_nullable(self):
        """AC#1 : Les champs d'approbation sont null=True / blank=True."""
        step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=11,
            step_name='Step sans approbation',
            step_type='vault',
        )
        self.assertIsNone(step.approved_by)
        self.assertIsNone(step.approved_at)
        self.assertIsNone(step.approval_comment)

    def test_execution_step_approval_comment_max_length(self):
        """AC#1 : Le champ approval_comment supporte jusqu'à 1000 caractères mais pas 1001."""
        from django.core.exceptions import ValidationError
        long_comment = 'x' * 1000
        step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=12,
            step_name='Step long comment',
            step_type='evaluation',
            approval_comment=long_comment,
        )
        self.assertEqual(len(step.approval_comment), 1000)
        # Vérifier que 1001 chars échoue la validation Django (full_clean enforce max_length)
        step.approval_comment = 'x' * 1001
        with self.assertRaises(ValidationError):
            step.full_clean()

    def test_execution_step_approved_by_related_name(self):
        """AC#1 : Le related_name 'approved_steps' est distinct de 'approved_executions'."""
        approver = User.objects.create(username='approver_steps', profile='DBA')
        step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=13,
            step_name='Step avec approver',
            step_type='gate',
            approved_by=approver,
        )
        # Le reverse relation via related_name='approved_steps' doit fonctionner
        self.assertIn(step, approver.approved_steps.all())

    def test_execution_step_approved_by_set_null_on_user_delete(self):
        """AC#1 : La suppression d'un approbateur met approved_by à NULL (on_delete=SET_NULL)."""
        approver = User.objects.create(username='approver_to_delete', profile='DBA')
        step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=14,
            step_name='Step with deletable approver',
            step_type='gate',
            approved_by=approver,
        )
        self.assertEqual(step.approved_by, approver)
        approver.delete()
        step.refresh_from_db()
        self.assertIsNone(step.approved_by)


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
            environment='developpement',
            scheduled_at=timezone.now(),
            status='pending'
        )
        self.assertEqual(scheduled.action, self.action)
        self.assertEqual(scheduled.user, self.user)
        self.assertEqual(scheduled.environment, 'developpement')
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
            environment='developpement',
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
            environments_json='["developpement", "certification", "production"]'
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
            environment='developpement',
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
        response = self.client.post('/api/v1/executions/', {
            'environment': 'dev'
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('action_id', str(response.data))

    def test_post_execution_requires_environment_or_targets(self):
        """Test that environment is required for actions with requires_target=False."""
        # Create action that doesn't require targets
        action_no_target = Action.objects.create(
            name='No Target Action',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=False
        )
        response = self.client.post('/api/v1/executions/', {
            'action_id': action_no_target.id
        }, format='json')
        self.assertEqual(response.status_code, 400)
        # Error should mention environment or target_names
        error_msg = str(response.data).lower()
        self.assertTrue('environment' in error_msg or 'target' in error_msg)

    def test_post_execution_with_environment_only(self):
        """Test creating execution with environment only for actions with requires_target=False."""
        # Create action that doesn't require targets
        action_no_target = Action.objects.create(
            name='No Target Action',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=False
        )
        response = self.client.post('/api/v1/executions/', {
            'action_id': action_no_target.id,
            'environment': 'dev'
        }, format='json')
        # Should succeed for actions that don't require targets
        self.assertEqual(response.status_code, 201)
        self.assertIn('execution_id', response.data.get('data', {}))

    def test_post_execution_target_names_must_be_list(self):
        """Test that target_names must be a non-empty list."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'target_names': 'not-a-list'
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('list', str(response.data).lower())

    def test_post_execution_target_names_not_empty(self):
        """Test that target_names must not be empty for actions with requires_target=True."""
        response = self.client.post('/api/v1/executions/', {
            'action_id': self.action.id,
            'target_names': []
        }, format='json')
        self.assertEqual(response.status_code, 400)
        # Error should mention that targets are required
        error_msg = str(response.data).lower()
        self.assertTrue('requis' in error_msg or 'required' in error_msg or 'vide' in error_msg or 'empty' in error_msg)

    def test_post_execution_with_target_names_success(self):
        """Test successful execution creation with target_names when InventoryService returns allowed targets (Story 13.2, Task 8.3)."""
        from unittest.mock import patch, MagicMock

        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-dev-02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventoryService.return_value = mock_instance

            response = self.client.post('/api/v1/executions/', {
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


# =============================================================================
# Story 13.3: RBAC validation tests for POST /executions with targets
# =============================================================================

@pytest.mark.django_db
class ExecutionRBACValidationTests(TestCase):
    """
    Story 13.3, AC4: Tests for RBAC validation in POST /executions.
    Tests that unauthorized targets are rejected with 403.
    """

    def setUp(self):
        """Set up test data."""
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = User.objects.create(
            username='rbac_testuser',
            profile='DEV'  # Non-admin profile
        )
        self.user.groups = ['DEV_GROUP']
        self.client.force_authenticate(user=self.user)

        self.action = Action.objects.create(
            name='RBAC Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=True
        )

    def test_post_execution_forbidden_target(self):
        """
        AC4/Task 3.5: Target not in allowed list should return 403.
        """
        from unittest.mock import patch, MagicMock

        # User only has access to dev targets
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventoryService.return_value = mock_instance

            # Try to execute on a target not in the allowed list
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-prod-01'],  # Not in allowed list
            }, format='json')

        self.assertEqual(response.status_code, 403)
        self.assertIn('srv-prod-01', str(response.data))

    def test_post_execution_pattern_mismatch(self):
        """
        AC4/Task 3.6: Target not matching pattern should return 403.
        User has pattern web-* but tries to access db-* target.
        """
        from unittest.mock import patch, MagicMock

        # User only has access to web-* pattern (filtered by InventoryService)
        allowed_targets = [
            {'name': 'web-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'web-dev-02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventoryService.return_value = mock_instance

            # Try to execute on a db-* target (not matching web-* pattern)
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['db-dev-01'],  # Doesn't match web-* pattern
            }, format='json')

        self.assertEqual(response.status_code, 403)
        self.assertIn('db-dev-01', str(response.data))

    def test_post_execution_allowed_target(self):
        """
        AC4/Task 3.7: Target in allowed list should return 201.
        """
        from unittest.mock import patch, MagicMock

        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-dev-02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventoryService.return_value = mock_instance

            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],  # In allowed list
            }, format='json')

        self.assertEqual(response.status_code, 201)
        data = response.data.get('data', {})
        self.assertIn('execution_id', data)

    def test_post_execution_multiple_targets_one_forbidden(self):
        """
        AC4: If any target in the list is forbidden, reject the whole request.
        """
        from unittest.mock import patch, MagicMock

        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 1, False)
            MockInventoryService.return_value = mock_instance

            # One allowed, one forbidden
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01', 'srv-prod-01'],  # srv-prod-01 not allowed
            }, format='json')

        self.assertEqual(response.status_code, 403)
        self.assertIn('srv-prod-01', str(response.data))

    def test_post_execution_mixed_environments_rejected(self):
        """
        AC4/Subtask 2.3: Targets from different environments should be rejected.
        """
        from unittest.mock import patch, MagicMock

        # User has access to both DEV and STAGING
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-stg-01', 'environment': 'staging', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventoryService.return_value = mock_instance

            # Try to mix DEV and STAGING targets in same execution
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01', 'srv-stg-01'],  # Different environments
            }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('environnement', str(response.data).lower())

    def test_post_execution_audit_log_on_forbidden(self):
        """
        AC4/Subtask 2.2: Forbidden target should create audit log entry.
        """
        from unittest.mock import patch, MagicMock

        allowed_targets = []  # User has no access
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 0, False)
            MockInventoryService.return_value = mock_instance

            with patch('executions.validators.target_validator.AuditService.create_entry') as mock_audit:
                response = self.client.post('/api/v1/executions/', {
                    'action_id': self.action.id,
                    'target_names': ['forbidden-target'],
                }, format='json')

        self.assertEqual(response.status_code, 403)
        # Verify audit was called with correct entity type (no execution created)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args[1]
        self.assertEqual(call_kwargs['action_type'].value, 'EXECUTION_TARGET_FORBIDDEN')
        self.assertEqual(call_kwargs['entity_type'].value, 'execution')
        self.assertEqual(call_kwargs['entity_id'], 0)
        self.assertIn('forbidden-target', str(call_kwargs['details']))


@pytest.mark.django_db
class ExecutionRBACMultiProfileTests(TestCase):
    """
    Story 13.3, AC5: Tests for multi-profile RBAC validation.
    """

    def setUp(self):
        """Set up test data with multiple profiles."""
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = User.objects.create(
            username='multi_profile_user',
            profile='MULTI'
        )
        self.client.force_authenticate(user=self.user)

        self.action = Action.objects.create(
            name='Multi Profile Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=True
        )

    def test_post_execution_with_union_permissions(self):
        """
        AC5: User with multiple profiles should have union of permissions.
        Profile A grants DEV, Profile B grants STAGING.
        User should be able to execute on both DEV and STAGING targets.
        """
        from unittest.mock import patch, MagicMock

        # InventoryService already applies union of permissions
        # So allowed_targets will include both DEV and STAGING
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-stg-01', 'environment': 'staging', 'target_type': 'server', 'metadata': None},
        ]
        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventoryService.return_value = mock_instance

            # Execute on DEV target
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
            }, format='json')

        self.assertEqual(response.status_code, 201)

        with patch('executions.validators.target_validator.InventoryService') as MockInventoryService:
            mock_instance = MagicMock()
            mock_instance.list_targets_for_user.return_value = (allowed_targets, 2, False)
            MockInventoryService.return_value = mock_instance

            # Execute on STAGING target
            response = self.client.post('/api/v1/executions/', {
                'action_id': self.action.id,
                'target_names': ['srv-stg-01'],
            }, format='json')

        self.assertEqual(response.status_code, 201)


# =============================================================================
# Story 57.12: Tests is_pending_approval (ADR-007 Phase 4.2)
# =============================================================================

@pytest.mark.django_db
class TestExecutionIsPendingApproval(TestCase):
    """
    AC#6 : Tests unitaires pour Execution.is_pending_approval.
    Vérifie la logique backward-compat (status PENDING_APPROVAL) et
    le nouveau mécanisme step-based (ExecutionStep WAITING).
    """

    def setUp(self):
        """Fixtures de base."""
        self.user = User.objects.create(
            username='approval_testuser',
            profile='DBA'
        )
        self.action = Action.objects.create(
            name='Approval Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP'
        )

    def test_is_pending_approval_true_when_status_pending_approval(self):
        """
        AC#6 / backward compat : is_pending_approval == True si status == PENDING_APPROVAL
        même sans aucun ExecutionStep WAITING.
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='production',
            status=ExecutionStatus.PENDING_APPROVAL,
        )
        self.assertTrue(execution.is_pending_approval)

    def test_is_pending_approval_true_when_step_waiting(self):
        """
        AC#6 / step-based : is_pending_approval == True si un ExecutionStep
        avec status=WAITING existe, même si Execution.status != PENDING_APPROVAL.
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='production',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Gate — Approval',
            step_type='gate',
            status=ExecutionStepStatus.WAITING,
        )
        self.assertTrue(execution.is_pending_approval)

    def test_is_pending_approval_false_when_no_waiting_steps(self):
        """
        AC#6 : is_pending_approval == False si aucun step WAITING et
        status != PENDING_APPROVAL.
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='developpement',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Platform Step',
            step_type='platform',
            status=ExecutionStepStatus.COMPLETED,
        )
        self.assertFalse(execution.is_pending_approval)

    def test_is_pending_approval_false_when_no_steps_and_running(self):
        """
        AC#6 : is_pending_approval == False si aucun step du tout et
        status == RUNNING.
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='developpement',
            status=ExecutionStatus.RUNNING,
        )
        self.assertFalse(execution.is_pending_approval)

    def test_is_pending_approval_true_when_maintenance_window_waiting(self):
        """
        ADR-007 Dev Notes (Story 57.12) : comportement documenté intentionnel —
        un step WAITING de type maintenance_window déclenche aussi is_pending_approval=True.
        Les deux types de gate (approval et maintenance_window) représentent
        un blocage opérationnel légitime. Voir docstring de is_pending_approval.
        """
        execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment='production',
            status=ExecutionStatus.RUNNING,
        )
        ExecutionStep.objects.create(
            execution=execution,
            step_order=1,
            step_name='Gate — Maintenance Window',
            step_type='gate',
            status=ExecutionStepStatus.WAITING,
        )
        # Comportement intentionnel : maintenance_window WAITING → is_pending_approval True
        self.assertTrue(execution.is_pending_approval)


# Story 13.4 tests: see executions/tests/test_story_13_4.py (single source of truth)
