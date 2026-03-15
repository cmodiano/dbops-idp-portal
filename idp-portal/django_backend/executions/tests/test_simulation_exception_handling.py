"""
Story 22.11: Tests for exception handling improvements.

Tests that:
- simulation_service.py catches specific DB exceptions + justified broad catch with 'as e'
- tasks.py logs with correlation_id and error_type
- views.py logs with exc_info=True
- feature_flags.py catches specific DB exceptions
- feature_flag_views.py logs audit errors with correlation_id
"""
import pytest
from unittest.mock import MagicMock

from django.db import DatabaseError, IntegrityError, OperationalError
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.mark.django_db
class TestSimulationServiceExceptionHandling:
    """Story 22.11: Tests for simulation_service.py exception handling."""

    def test_database_error_logged_with_context(self, mocker):
        """DatabaseError is logged with error, error_type, exc_info=True, correlation_id and re-raised."""
        mock_logger = mocker.patch('executions.simulation_service.logger')
        mocker.patch('executions.simulation_service.close_old_connections')
        mocker.patch('executions.simulation_service.get_correlation_id', return_value='corr-sim-123')
        mocker.patch(
            'executions.simulation_service.Execution.objects.get',
            side_effect=DatabaseError("Connection lost"),
        )

        from executions.simulation_service import SimulationService

        # Verify exception is re-raised for Celery retry (AC#6)
        with pytest.raises(DatabaseError, match="Connection lost"):
            SimulationService._run_simulation(execution_id=99999)

        error_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "simulation_db_error"
        ]
        assert len(error_calls) == 1
        call_kwargs = error_calls[0][1]
        assert call_kwargs['execution_id'] == 99999
        assert call_kwargs['error_type'] == 'DatabaseError'
        assert call_kwargs['exc_info'] is True
        assert call_kwargs['correlation_id'] == 'corr-sim-123'  # Story 22.11 AC#3,#5
        assert 'Connection lost' in call_kwargs['error']

    def test_integrity_error_caught_by_specific_handler(self, mocker):
        """IntegrityError is caught by the specific handler and re-raised."""
        mock_logger = mocker.patch('executions.simulation_service.logger')
        mocker.patch('executions.simulation_service.close_old_connections')
        mocker.patch('executions.simulation_service.get_correlation_id', return_value='corr-sim-456')
        mocker.patch(
            'executions.simulation_service.Execution.objects.get',
            side_effect=IntegrityError("Unique constraint violated"),
        )

        from executions.simulation_service import SimulationService

        # Verify exception is re-raised for Celery retry
        with pytest.raises(IntegrityError):
            SimulationService._run_simulation(execution_id=99999)

        error_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "simulation_db_error"
        ]
        assert len(error_calls) == 1
        assert error_calls[0][1]['error_type'] == 'IntegrityError'
        assert error_calls[0][1]['correlation_id'] == 'corr-sim-456'

    def test_unexpected_exception_logged_with_as_e(self, mocker):
        """Unexpected exception is captured with 'as e', logged with full context including correlation_id, and re-raised."""
        mock_logger = mocker.patch('executions.simulation_service.logger')
        mocker.patch('executions.simulation_service.close_old_connections')
        mocker.patch('executions.simulation_service.get_correlation_id', return_value='corr-sim-789')
        mocker.patch(
            'executions.simulation_service.Execution.objects.get',
            side_effect=RuntimeError("Unexpected error"),
        )

        from executions.simulation_service import SimulationService

        # Verify exception is re-raised to signal failure to caller
        with pytest.raises(RuntimeError, match="Unexpected error"):
            SimulationService._run_simulation(execution_id=99999)

        error_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "simulation_unexpected_error"
        ]
        assert len(error_calls) == 1
        call_kwargs = error_calls[0][1]
        assert call_kwargs['error_type'] == 'RuntimeError'
        assert call_kwargs['error'] == 'Unexpected error'
        assert call_kwargs['exc_info'] is True
        assert call_kwargs['correlation_id'] == 'corr-sim-789'  # Story 22.11 AC#3,#5


@pytest.mark.django_db
class TestTasksExceptionHandling:
    """Story 22.11: Tests for tasks.py exception handling."""

    def test_celery_task_logs_with_correlation_id_and_error_type(self, mocker):
        """Exception in resume_container_workflow_from_gate logs with correlation_id and error.

        Story 81: retry_workflow_step removed — test now targets resume_container_workflow_from_gate.
        """
        mock_logger = mocker.patch('executions.tasks.gates.logger')
        mocker.patch('executions.tasks.get_correlation_id', return_value='test-corr-id-123')
        mocker.patch(
            'executions.cancellation_cache.is_cancelled',
            side_effect=RuntimeError("Redis down"),
        )

        from executions.tasks.gates import resume_container_workflow_from_gate

        result = resume_container_workflow_from_gate.run(
            execution_id=99999, on_success_step_ids=['step-1']
        )

        assert result['outcome'] == 'error'

        error_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "resume_container_workflow_gate_error"
        ]
        assert len(error_calls) == 1
        call_kwargs = error_calls[0][1]
        assert 'Redis down' in call_kwargs['error']
        assert call_kwargs['correlation_id'] == 'test-corr-id-123'
        assert call_kwargs['execution_id'] == 99999


class TestFeatureFlagsExceptionHandling:
    """Story 22.11: Tests for feature_flags.py exception handling."""

    def test_database_error_returns_empty_dict_via_mock(self, mocker):
        """DatabaseError in _load_flags_from_database returns {} with specific log including correlation_id."""
        mock_logger = mocker.patch('core.feature_flags.logger')
        mocker.patch('core.feature_flags.get_correlation_id', return_value='corr-ff-123')

        # Patch FeatureFlag at the core.models module level (where it's imported from)
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(side_effect=DatabaseError("DB connection lost"))
        mock_ff_class = MagicMock()
        mock_ff_class.objects.all.return_value = mock_qs
        mocker.patch('core.models.FeatureFlag', mock_ff_class)

        from core.feature_flags import _load_flags_from_database
        result = _load_flags_from_database()

        assert result == {}
        error_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "feature_flags_db_error"
        ]
        assert len(error_calls) == 1
        call_kwargs = error_calls[0][1]
        assert call_kwargs['error_type'] == 'DatabaseError'
        assert call_kwargs['exc_info'] is True
        assert call_kwargs['correlation_id'] == 'corr-ff-123'  # Story 22.11 AC#3,#5

    def test_operational_error_caught_by_specific_handler(self, mocker):
        """OperationalError is caught by the specific handler and logs with correlation_id."""
        mock_logger = mocker.patch('core.feature_flags.logger')
        mocker.patch('core.feature_flags.get_correlation_id', return_value='corr-ff-456')

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(side_effect=OperationalError("Table not found"))
        mock_ff_class = MagicMock()
        mock_ff_class.objects.all.return_value = mock_qs
        mocker.patch('core.models.FeatureFlag', mock_ff_class)

        from core.feature_flags import _load_flags_from_database
        result = _load_flags_from_database()

        assert result == {}
        error_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "feature_flags_db_error"
        ]
        assert len(error_calls) == 1
        assert error_calls[0][1]['error_type'] == 'OperationalError'
        assert error_calls[0][1]['correlation_id'] == 'corr-ff-456'

    def test_unexpected_error_returns_empty_dict_with_justified_log(self, mocker):
        """Unexpected exception is caught with justified broad catch, logs with correlation_id, and returns empty dict."""
        mock_logger = mocker.patch('core.feature_flags.logger')
        mocker.patch('core.feature_flags.get_correlation_id', return_value='corr-ff-789')

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(side_effect=RuntimeError("Something unexpected"))
        mock_ff_class = MagicMock()
        mock_ff_class.objects.all.return_value = mock_qs
        mocker.patch('core.models.FeatureFlag', mock_ff_class)

        from core.feature_flags import _load_flags_from_database
        result = _load_flags_from_database()

        assert result == {}
        error_calls = [
            c for c in mock_logger.error.call_args_list
            if c[0][0] == "feature_flags_unexpected_error"
        ]
        assert len(error_calls) == 1
        call_kwargs = error_calls[0][1]
        assert call_kwargs['error_type'] == 'RuntimeError'
        assert call_kwargs['exc_info'] is True
        assert call_kwargs['correlation_id'] == 'corr-ff-789'  # Story 22.11 AC#3,#5


@pytest.mark.django_db
class TestFeatureFlagViewsExceptionHandling:
    """Story 22.11: Tests for feature_flag_views.py audit error handling."""

    def test_audit_error_logs_with_correlation_id_and_returns_500(self, mocker):
        """Audit failure logs with correlation_id and error_type, returns 500."""
        mock_logger = mocker.patch('core.feature_flag_views.logger')
        mocker.patch('core.feature_flag_views.get_correlation_id', return_value='corr-456')
        mocker.patch('core.feature_flag_views.feature_flags._get_flags_source', return_value='database')

        mock_flag = MagicMock()
        mock_flag.id = 1
        mock_flag.flag_key = 'test_flag'
        mock_flag.enabled = True
        mock_flag.rollout_percent = 100
        mock_flag.updated_at = None
        mock_flag.updated_by = 'user-1'

        mocker.patch(
            'core.feature_flag_views.FeatureFlag.objects.get_or_create',
            return_value=(mock_flag, False),
        )

        mocker.patch(
            'core.feature_flag_views.AuditLog.objects.create_entry',
            side_effect=RuntimeError("Audit DB error"),
        )

        user = UserFactory.create(profile='DBOPS')
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.patch(
            '/api/v1/feature-flags/test_flag/',
            {'enabled': True},
            format='json',
        )

        assert response.status_code == 500

        warning_calls = [
            c for c in mock_logger.warning.call_args_list
            if c[0][0] == "feature_flag_audit_error"
        ]
        assert len(warning_calls) == 1
        call_kwargs = warning_calls[0][1]
        assert call_kwargs['error_type'] == 'RuntimeError'
        assert call_kwargs['correlation_id'] == 'corr-456'
        assert call_kwargs['flag_key'] == 'test_flag'
