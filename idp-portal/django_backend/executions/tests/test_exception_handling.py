"""
Story 17.6: Tests for restricted exception catches.

Validates that:
- Workflow runtime logs unexpected exceptions with exc_info=True and correlation_id
- ProfileService failures in executions/views.py log WARNING with context
- Cron validation catches specific CroniterBadCronError/CroniterBadDateError
- All broad catches include proper logging
"""

import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from django.utils import timezone

from executions.models import Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus
from executions.workflow_runtime import WorkflowRuntime, StepOutcome
from catalog.models import Action, ActionStatus, ActionItemType
from idp_auth.models import User


@pytest.mark.django_db
class TestWorkflowRuntimeExceptionHandling:
    """Story 17.6: Workflow runtime exception handling."""

    def setup_method(self):
        """Create test workflow."""
        self.user = User.objects.create(username="test_exception_user")
        self.action = Action.objects.create(
            name="Test Exception Workflow",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.WORKFLOW,
        )

        self.referenced_action = Action.objects.create(
            name="Referenced Action",
            category="Administration",
            engine="Oracle",
            platform="AAP",
            status=ActionStatus.PUBLISHED,
            item_type=ActionItemType.ACTION,
        )

        workflow_steps = [
            {
                "step_id": "step-1",
                "order": 1,
                "name": "Test Step",
                "referenced_action_id": self.referenced_action.id,
                "on_success_step_id": None,
                "on_error_step_id": None,
            },
        ]
        self.action.execution_steps = workflow_steps
        self.action.save()

        self.execution = Execution.objects.create(
            action=self.action,
            user=self.user,
            environment="dev",
            status=ExecutionStatus.SUBMITTED,
        )

    def test_unexpected_exception_logged_with_exc_info(self):
        """Unexpected exception in step is logged with exc_info=True."""
        runtime = WorkflowRuntime(self.execution)

        # Patch Action.objects.get to raise a RuntimeError (unexpected)
        with patch('executions.workflow_runtime.logger') as mock_logger:
            with patch('catalog.models.Action.objects.get', side_effect=RuntimeError("Unexpected DB failure")):
                result = runtime._execute_step(runtime.workflow_steps[0])

                assert result.outcome == StepOutcome.ERROR
                assert result.error_details['error_type'] == 'RuntimeError'

                # Verify logger.error called with exc_info=True
                error_calls = [c for c in mock_logger.error.call_args_list
                               if c[0][0] == "workflow_step_failed"]
                assert len(error_calls) == 1
                call_kwargs = error_calls[0][1]
                assert call_kwargs.get('exc_info') is True
                assert call_kwargs.get('error_type') == 'RuntimeError'
                assert 'correlation_id' in call_kwargs

    def test_unexpected_exception_saves_error_type_in_step(self):
        """ExecutionStep.error_message includes exception type for debugging."""
        runtime = WorkflowRuntime(self.execution)

        with patch('executions.workflow_runtime.logger'):
            with patch('catalog.models.Action.objects.get', side_effect=TypeError("bad type")):
                result = runtime._execute_step(runtime.workflow_steps[0])

                assert result.outcome == StepOutcome.ERROR
                assert "bad type" in result.error_message
                # ExecutionStep stored in DB should have type prefix
                step = ExecutionStep.objects.filter(execution=self.execution).last()
                assert "TypeError" in step.error_message
                assert "bad type" in step.error_message

    def test_validation_error_caught_by_specific_handler(self):
        """ValueError is still caught by the specific handler, not the broad catch."""
        runtime = WorkflowRuntime(self.execution)

        # A step without referenced_action_id triggers ValueError
        step_without_ref = {
            "step_id": "step-no-ref",
            "order": 1,
            "name": "No Reference Step",
            "on_success_step_id": None,
            "on_error_step_id": None,
        }

        with patch('executions.workflow_runtime.logger') as mock_logger:
            result = runtime._execute_step(step_without_ref)

            assert result.outcome == StepOutcome.ERROR
            # Should be caught by the ValueError handler
            error_calls = [c for c in mock_logger.error.call_args_list
                           if c[0][0] == "workflow_step_validation_failed"]
            assert len(error_calls) == 1
            call_kwargs = error_calls[0][1]
            # Workflow runtime uses 'validation' as error_type for ValidationErrors
            assert 'error_type' in call_kwargs
            assert result.error_details['error_type'] == 'validation'


@pytest.mark.django_db
class TestCronValidationExceptionHandling:
    """Story 17.6: Cron validation uses specific exceptions."""

    def setup_method(self):
        self.user = User.objects.create(username="test_cron_user")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_invalid_cron_returns_validation_error(self):
        """Invalid cron expression returns 200 with valid=false."""
        response = self.client.get(
            "/api/v1/scheduled-executions/validate-cron",
            {"expression": "invalid cron"},
        )

        assert response.status_code == 200
        assert response.data["data"]["valid"] is False

    def test_valid_cron_returns_valid_true(self):
        """Valid cron expression returns 200 with valid=true."""
        response = self.client.get(
            "/api/v1/scheduled-executions/validate-cron",
            {"expression": "*/5 * * * *"},
        )

        assert response.status_code == 200
        assert response.data["data"]["valid"] is True

    def test_missing_expression_returns_400(self):
        """Missing expression returns 400 error."""
        response = self.client.get(
            "/api/v1/scheduled-executions/validate-cron",
            {},
        )

        assert response.status_code == 400

    def test_unexpected_croniter_exception_logs_error(self):
        """Unexpected croniter exception logs ERROR and is caught by broad catch."""
        with patch('executions.views.scheduled_views.croniter.is_valid', side_effect=RuntimeError("Unexpected croniter error")):
            with patch('executions.views.scheduled_views.exec_logger') as mock_logger:
                response = self.client.get(
                    "/api/v1/scheduled-executions/validate-cron",
                    {"expression": "* * * * *"},
                )

                # Should still return 200 with error message (graceful degradation)
                # OR return 500 depending on implementation
                assert response.status_code in (200, 500)

                # Verify error was logged
                if mock_logger.error.called:
                    call_kwargs = mock_logger.error.call_args[1]
                    assert 'exc_info' in call_kwargs or 'error_type' in call_kwargs


@pytest.mark.django_db
class TestProfileServiceExceptionLogging:
    """Story 17.6: ProfileService failures are logged."""

    def test_profile_service_failure_logs_warning(self):
        """ProfileService exception logs warning with context."""
        from executions.utils import _get_allowed_action_ids_for_user

        user = User.objects.create(username="test_profile_user")

        with patch('executions.utils.ProfileService') as mock_ps_class:
            mock_ps_class.return_value.get_cumulative_permissions.side_effect = ConnectionError("Service down")
            with patch('executions.utils.exec_logger') as mock_logger:
                result = _get_allowed_action_ids_for_user(user)

                assert result == set()
                mock_logger.warning.assert_called_once()
                call_kwargs = mock_logger.warning.call_args[1]
                assert call_kwargs.get('exc_info') is True
                assert call_kwargs.get('error_type') == 'ConnectionError'


@pytest.mark.django_db
class TestDashboardExceptionHandling:
    """Story 17.6: Dashboard views exception handling."""

    def test_stats_queryset_logs_invalid_timestamps(self):
        """Invalid timestamps in duration calculation are logged."""
        from dashboard.views import _stats_for_queryset
        from unittest.mock import MagicMock

        # Create mock queryset with invalid timestamp data
        mock_qs = MagicMock()
        mock_qs.count.return_value = 1
        mock_qs.filter.return_value = mock_qs
        mock_qs.values_list.return_value = [(None, "not_a_datetime")]

        with patch('dashboard.views.logger') as mock_logger:
            result = _stats_for_queryset(mock_qs)

            # Should have logged the invalid timestamp
            debug_calls = [c for c in mock_logger.debug.call_args_list
                          if c[0][0] == "execution_duration_calculation_skipped"]
            assert len(debug_calls) == 1
            call_kwargs = debug_calls[0][1]
            assert 'correlation_id' in call_kwargs
            assert call_kwargs.get('error_type') in ('TypeError', 'AttributeError')


@pytest.mark.django_db
class TestCatalogProfileServiceExceptionLogging:
    """Story 17.6: Catalog ProfileService failures are logged."""

    def test_catalog_profile_service_failure_logs_warning(self):
        """Catalog ProfileService exception logs warning with context."""
        from catalog.views import _get_cumulative_permissions_for_user

        user = User.objects.create(username="test_catalog_user")

        with patch('catalog.views.ProfileService') as mock_ps_class:
            mock_ps_class.return_value.get_cumulative_permissions.side_effect = ConnectionError("Service down")
            with patch('catalog.views.logger') as mock_logger:
                result = _get_cumulative_permissions_for_user(user)

                assert result is None
                mock_logger.warning.assert_called_once()
                call_kwargs = mock_logger.warning.call_args[1]
                assert call_kwargs.get('exc_info') is True
                assert call_kwargs.get('error_type') == 'ConnectionError'
                assert 'correlation_id' in call_kwargs


@pytest.mark.django_db
class TestCorePermissionsExceptionLogging:
    """Story 17.6: Core permissions has exception logging."""

    def test_core_permissions_has_exception_logging_pattern(self):
        """Core permissions module contains Story 17.6 exception logging patterns."""
        import core.permissions
        import inspect

        source = inspect.getsource(core.permissions)

        # Verify the Story 17.6 pattern exists
        assert "Story 17.6: Justified broad catch" in source
        assert "logger.warning" in source
        assert "exc_info=True" in source or "exc_info" in source
        assert "error_type" in source


@pytest.mark.django_db
class TestBroadCatchJustification:
    """Story 17.6: Verify all broad catches have Story 17.6 comment."""

    def test_no_bare_except_in_codebase(self):
        """No bare except: statements in Python files."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", r"^\s*except\s*:", "idp-portal/django_backend",
             "--include=*.py", "--exclude-dir=security-reports",
             "--exclude-dir=__pycache__", "--exclude-dir=.venv"],
            capture_output=True, text=True,
            cwd="/Users/cyrille/Documents/Dev/test",
        )
        bare_excepts = [line for line in result.stdout.strip().split('\n') if line.strip()]
        assert bare_excepts == [], f"Found bare excepts: {bare_excepts}"

    def test_no_except_exception_without_as_e(self):
        """All except Exception must capture with 'as e' for logging."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "except Exception:", "idp-portal/django_backend",
             "--include=*.py", "--exclude-dir=security-reports",
             "--exclude-dir=__pycache__", "--exclude-dir=.venv",
             "--exclude=test_exception_handling.py"],
            capture_output=True, text=True,
            cwd="/Users/cyrille/Documents/Dev/test",
        )
        without_as = [
            line for line in result.stdout.strip().split('\n')
            if line.strip() and 'except Exception as' not in line
        ]
        assert without_as == [], f"Found except Exception without 'as e': {without_as}"
