"""
Tests for catalog validation against reference tables.
Story 13.7 - Tests for engine/platform validation against REF_ENGINES/REF_PLATFORMS.
"""

from django.test import TestCase
from idp_auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import Action
from reference.models import RefEngine, RefPlatform

class CatalogValidationTests(TestCase):
    """Tests for catalog validation against reference tables."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create(
            username='testuser',
            profile='DBOPS'
        )
        self.client.force_authenticate(user=self.user)

        # Create reference data
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        RefEngine.objects.create(code='SQL Server', label='SQL Server', display_order=2, is_active=1)
        RefPlatform.objects.create(code='AAP', label='AAP', display_order=1, is_active=1)
        RefPlatform.objects.create(code='GitHub Actions', label='GitHub Actions', display_order=2, is_active=1)

    def test_create_action_with_valid_engine(self):
        """Test creating action with valid engine."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'item_type': 'action'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_action_with_invalid_engine(self):
        """Test creating action with invalid engine returns 400."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action',
            'engine': 'InvalidEngine',
            'platform': 'AAP',
            'item_type': 'action'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('engine', str(response.data).lower())

    def test_create_action_with_inactive_engine(self):
        """Test creating action with inactive engine returns 400."""
        # Create inactive engine
        RefEngine.objects.create(code='InactiveEngine', label='Inactive', display_order=99, is_active=0)
        
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action',
            'engine': 'InactiveEngine',
            'platform': 'AAP',
            'item_type': 'action'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_action_with_valid_platform(self):
        """Test creating action with valid platform."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action',
            'engine': 'Oracle',
            'platform': 'GitHub Actions',
            'item_type': 'action'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_action_with_invalid_platform(self):
        """Test creating action with invalid platform returns 400."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action',
            'engine': 'Oracle',
            'platform': 'InvalidPlatform',
            'item_type': 'action'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('platform', str(response.data).lower())

    def test_create_action_with_inactive_platform(self):
        """Test creating action with inactive platform returns 400."""
        # Create inactive platform
        RefPlatform.objects.create(code='InactivePlatform', label='Inactive', display_order=99, is_active=0)
        
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action',
            'engine': 'Oracle',
            'platform': 'InactivePlatform',
            'item_type': 'action'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# Story 16.2: Workflow steps validation (branches, retry, cycles)
# ============================================================================

import pytest
from rest_framework import serializers as drf_serializers
from catalog.validation import (
    validate_workflow_steps,
    validate_retry_constraints,
    _detect_workflow_cycles
)


class TestValidateWorkflowSteps:
    """Test workflow steps validation with branches and retry."""

    def test_empty_steps_valid(self):
        """Empty steps list is valid."""
        result = validate_workflow_steps([])
        assert result == []

    def test_simple_linear_workflow_valid(self):
        """Linear workflow without branches is valid."""
        steps = [
            {'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1'},
            {'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 's2'},
        ]
        result = validate_workflow_steps(steps)
        assert result == steps

    def test_workflow_with_branches_valid(self):
        """Workflow with valid branches is valid."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_success_step_id': 's2', 'on_error_step_id': 's3'
            },
            {
                'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 's2',
                'on_success_step_id': None  # Exit on success
            },
            {
                'order': 3, 'name': 'Error Step', 'referenced_action_id': 30, 'step_id': 's3',
                'on_error_step_id': None  # Exit on error
            },
        ]
        result = validate_workflow_steps(steps)
        assert result == steps

    def test_invalid_on_success_reference(self):
        """Invalid on_success_step_id reference raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_success_step_id': 'invalid_step_id'
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "does not reference a valid step_id" in str(exc_info.value)

    def test_invalid_on_error_reference(self):
        """Invalid on_error_step_id reference raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_error_step_id': 'nonexistent_step'
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "does not reference a valid step_id" in str(exc_info.value)

    def test_no_exit_point_invalid(self):
        """Workflow without exit point raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_success_step_id': 's2', 'on_error_step_id': 's2'
            },
            {
                'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 's2',
                'on_success_step_id': 's1', 'on_error_step_id': 's1'
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "at least one exit point" in str(exc_info.value)

    def test_retry_enabled_without_max_attempts_invalid(self):
        """retry_enabled=true without retry_max_attempts applies default (3)."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'retry_enabled': True,
                'on_success_step_id': None
            },
        ]
        result = validate_workflow_steps(steps)
        assert result[0]['retry_max_attempts'] == 3
        assert result[0]['retry_interval_seconds'] == 60
        assert result[0]['retry_backoff_multiplier'] == 2.0

    def test_retry_enabled_with_zero_max_attempts_invalid(self):
        """retry_enabled=true with retry_max_attempts=0 raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'retry_enabled': True,
                'retry_max_attempts': 0,
                'retry_interval_seconds': 60,
                'on_success_step_id': None
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "retry_max_attempts must be >= 1" in str(exc_info.value)

    def test_retry_enabled_without_interval_seconds_invalid(self):
        """retry_enabled=true without retry_interval_seconds applies default (60)."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'retry_enabled': True,
                'retry_max_attempts': 3,
                'on_success_step_id': None
            },
        ]
        result = validate_workflow_steps(steps)
        assert result[0]['retry_interval_seconds'] == 60
        assert result[0]['retry_backoff_multiplier'] == 2.0

    def test_retry_enabled_with_zero_interval_seconds_invalid(self):
        """retry_enabled=true with retry_interval_seconds=0 raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'retry_enabled': True,
                'retry_max_attempts': 3,
                'retry_interval_seconds': 0,
                'on_success_step_id': None
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "retry_interval_seconds must be >= 1" in str(exc_info.value)

    def test_retry_enabled_with_valid_config(self):
        """retry_enabled=true with valid config is valid."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'retry_enabled': True,
                'retry_max_attempts': 5,
                'retry_interval_seconds': 30,
                'retry_backoff_multiplier': 1.5,
                'on_success_step_id': None
            },
        ]
        result = validate_workflow_steps(steps)
        assert result == steps

    def test_branches_require_step_id(self):
        """Branch fields require step_id on all steps."""
        steps = [
            {'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'on_success_step_id': None},
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "step_id is required" in str(exc_info.value)

    def test_duplicate_step_id_invalid(self):
        """Duplicate step_id values are rejected."""
        steps = [
            {'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 'dup', 'on_success_step_id': None},
            {'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 'dup', 'on_success_step_id': None},
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "Duplicate step_id" in str(exc_info.value)

    def test_cycle_detection_simple_loop(self):
        """Simple cycle (s1 -> s2 -> s1) raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_success_step_id': 's2',
                'on_error_step_id': None,  # Explicit exit point
            },
            {
                'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 's2',
                'on_success_step_id': 's1'  # Loop back to s1
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "Infinite loop detected" in str(exc_info.value)

    def test_cycle_detection_three_node_loop(self):
        """Three-node cycle (s1 -> s2 -> s3 -> s1) raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_success_step_id': 's2',
                'on_error_step_id': None,  # Explicit exit point
            },
            {
                'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 's2',
                'on_success_step_id': 's3'
            },
            {
                'order': 3, 'name': 'Step 3', 'referenced_action_id': 30, 'step_id': 's3',
                'on_success_step_id': 's1'  # Loop back to s1
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "Infinite loop detected" in str(exc_info.value)

    def test_cycle_detection_error_path_loop(self):
        """Cycle in error path raises error."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_success_step_id': None,
                'on_error_step_id': 's2'
            },
            {
                'order': 2, 'name': 'Error Handler', 'referenced_action_id': 20, 'step_id': 's2',
                'on_error_step_id': 's2'  # Loop back to itself
            },
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_workflow_steps(steps)
        assert "Infinite loop detected" in str(exc_info.value)

    def test_no_cycle_with_convergence(self):
        """Converging paths (s1, s2 -> s3) is valid (not a cycle)."""
        steps = [
            {
                'order': 1, 'name': 'Step 1', 'referenced_action_id': 10, 'step_id': 's1',
                'on_success_step_id': 's3', 'on_error_step_id': 's2'
            },
            {
                'order': 2, 'name': 'Step 2', 'referenced_action_id': 20, 'step_id': 's2',
                'on_success_step_id': 's3'
            },
            {
                'order': 3, 'name': 'Step 3', 'referenced_action_id': 30, 'step_id': 's3',
                'on_success_step_id': None  # Exit
            },
        ]
        result = validate_workflow_steps(steps)
        assert result == steps


class TestValidateRetryConstraints:
    """Test retry constraints validation for individual steps."""

    def test_retry_disabled_no_validation(self):
        """Retry disabled (or not set) does not trigger validation."""
        step = {'retry_enabled': False}
        validate_retry_constraints(step)  # Should not raise

        step = {}
        validate_retry_constraints(step)  # Should not raise

    def test_retry_enabled_without_max_attempts_invalid(self):
        """retry_enabled=true without retry_max_attempts raises error."""
        step = {'retry_enabled': True}
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_retry_constraints(step)
        assert "retry_max_attempts must be >= 1" in str(exc_info.value)

    def test_retry_enabled_without_interval_seconds_invalid(self):
        """retry_enabled=true without retry_interval_seconds raises error."""
        step = {'retry_enabled': True, 'retry_max_attempts': 3}
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            validate_retry_constraints(step)
        assert "retry_interval_seconds must be >= 1" in str(exc_info.value)

    def test_retry_enabled_with_valid_config(self):
        """retry_enabled=true with valid config is valid."""
        step = {
            'retry_enabled': True,
            'retry_max_attempts': 5,
            'retry_interval_seconds': 30,
        }
        validate_retry_constraints(step)  # Should not raise


class TestDetectWorkflowCycles:
    """Test cycle detection in workflow branch paths."""

    def test_no_cycle_linear_workflow(self):
        """Linear workflow (s1 -> s2 -> s3) has no cycle."""
        steps = [
            {'step_id': 's1', 'on_success_step_id': 's2'},
            {'step_id': 's2', 'on_success_step_id': 's3'},
            {'step_id': 's3', 'on_success_step_id': None},
        ]
        _detect_workflow_cycles(steps)  # Should not raise

    def test_no_cycle_diamond_workflow(self):
        """Diamond workflow (s1 -> s2, s3; s2, s3 -> s4) has no cycle."""
        steps = [
            {'step_id': 's1', 'on_success_step_id': 's2', 'on_error_step_id': 's3'},
            {'step_id': 's2', 'on_success_step_id': 's4'},
            {'step_id': 's3', 'on_success_step_id': 's4'},
            {'step_id': 's4', 'on_success_step_id': None},
        ]
        _detect_workflow_cycles(steps)  # Should not raise

    def test_cycle_self_loop(self):
        """Self-loop (s1 -> s1) is detected."""
        steps = [
            {'step_id': 's1', 'on_success_step_id': 's1'},
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            _detect_workflow_cycles(steps)
        assert "Infinite loop detected" in str(exc_info.value)

    def test_cycle_two_node_loop(self):
        """Two-node cycle (s1 -> s2 -> s1) is detected."""
        steps = [
            {'step_id': 's1', 'on_success_step_id': 's2'},
            {'step_id': 's2', 'on_success_step_id': 's1'},
        ]
        with pytest.raises(drf_serializers.ValidationError) as exc_info:
            _detect_workflow_cycles(steps)
        assert "Infinite loop detected" in str(exc_info.value)
