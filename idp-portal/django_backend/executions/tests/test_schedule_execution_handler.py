"""
Tests unitaires pour ScheduleExecutionHandler.

Teste la création de ScheduledExecution avec des paramètres issus de
l'input_mapping (potentiellement résolus depuis des steps précédents).
"""
import pytest
import zoneinfo
from datetime import timedelta
from unittest.mock import patch, MagicMock

from catalog.models import Action as RealAction
from executions.models import ExecutionStatus
from executions.app.handlers.schedule_execution_handler import (
    ScheduleExecutionHandler,
    _parse_offset,
    _parse_scheduled_datetime,
)


class TestParseOffset:
    """Tests pour _parse_offset."""

    def test_days(self):
        assert _parse_offset('+2d') == timedelta(days=2)

    def test_hours(self):
        assert _parse_offset('+4h') == timedelta(hours=4)

    def test_weeks(self):
        assert _parse_offset('+1w') == timedelta(weeks=1)

    def test_months_approximation(self):
        assert _parse_offset('+3m') == timedelta(days=90)

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid fixed_offset"):
            _parse_offset('2d')

    def test_invalid_unit(self):
        with pytest.raises(ValueError, match="Invalid fixed_offset"):
            _parse_offset('+2x')


class TestParseScheduledDatetime:
    """Tests pour _parse_scheduled_datetime."""

    def test_iso_datetime(self):
        result = _parse_scheduled_datetime('2025-06-15T14:30:00')
        assert result.year == 2025
        assert result.month == 6
        assert result.hour == 14

    def test_date_only(self):
        result = _parse_scheduled_datetime('2025-06-15')
        assert result.year == 2025
        assert result.hour == 0

    def test_date_with_time(self):
        result = _parse_scheduled_datetime('2025-06-15', '14:30')
        assert result.hour == 14
        assert result.minute == 30

    def test_date_with_time_not_silently_dropped(self):
        """Regression: time_str must NOT be silently ignored when date_str is YYYY-MM-DD.

        On Python 3.11+, datetime.fromisoformat('2025-06-15') succeeds and
        returns midnight.  The old code early-returned from the fromisoformat
        try-block, discarding time_str entirely.
        """
        result = _parse_scheduled_datetime('2025-06-15', '22:00')
        assert result.hour == 22, (
            f"Expected hour=22 but got {result.hour} — time_str was silently dropped"
        )
        assert result.minute == 0

    def test_date_with_time_seconds(self):
        result = _parse_scheduled_datetime('2025-06-15', '14:30:45')
        assert result.second == 45

    def test_empty_date_raises(self):
        with pytest.raises(ValueError, match="scheduled_date is required"):
            _parse_scheduled_datetime('')

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError, match="Invalid scheduled_date"):
            _parse_scheduled_datetime('not-a-date')

    def test_invalid_time_raises(self):
        with pytest.raises(ValueError, match="Invalid scheduled_time"):
            _parse_scheduled_datetime('2025-06-15', 'not-a-time')

    def test_local_timezone_converts_to_utc(self):
        """Date/time in America/Montreal (UTC-4 in summer) should be converted to UTC."""
        result = _parse_scheduled_datetime('2025-06-15', '22:00', tz_name='America/Montreal')
        assert result.tzinfo == zoneinfo.ZoneInfo('UTC')
        # 22:00 EDT (UTC-4) = 02:00 UTC next day
        assert result.hour == 2
        assert result.day == 16

    def test_local_timezone_winter(self):
        """America/Montreal in winter (UTC-5) should convert correctly."""
        result = _parse_scheduled_datetime('2025-01-15', '20:00', tz_name='America/Montreal')
        assert result.tzinfo == zoneinfo.ZoneInfo('UTC')
        # 20:00 EST (UTC-5) = 01:00 UTC next day
        assert result.hour == 1
        assert result.day == 16

    def test_no_timezone_uses_utc_default(self):
        """Without timezone, naive datetime is interpreted as UTC (Django default)."""
        result = _parse_scheduled_datetime('2025-06-15', '22:00')
        # Should stay 22:00 UTC
        assert result.hour == 22
        assert result.day == 15

    def test_iso_with_offset_converts_to_utc(self):
        """ISO datetime with explicit offset should be converted to UTC."""
        result = _parse_scheduled_datetime('2025-06-15T22:00:00-04:00')
        assert result.tzinfo == zoneinfo.ZoneInfo('UTC')
        assert result.hour == 2
        assert result.day == 16

    def test_invalid_timezone_falls_back_to_utc(self):
        """Invalid timezone name should fall back to Django default (UTC)."""
        result = _parse_scheduled_datetime('2025-06-15', '22:00', tz_name='Invalid/Zone')
        # Falls back to UTC — hour stays 22
        assert result.hour == 22

    def test_europe_paris_timezone(self):
        """Europe/Paris (UTC+2 in summer) should convert correctly."""
        result = _parse_scheduled_datetime('2025-06-15', '14:00', tz_name='Europe/Paris')
        assert result.tzinfo == zoneinfo.ZoneInfo('UTC')
        # 14:00 CEST (UTC+2) = 12:00 UTC
        assert result.hour == 12
        assert result.day == 15


class TestScheduleExecutionHandler:
    """Tests de ScheduleExecutionHandler.execute()."""

    def setup_method(self):
        self.handler = ScheduleExecutionHandler()

    def _make_execution(self, exec_id=1, user_id=10, environment='production'):
        m = MagicMock()
        m.id = exec_id
        m.user = MagicMock()
        m.user.id = user_id
        m.environment = environment
        return m

    def _make_action(self, action_id=42, name='Deploy App'):
        m = MagicMock()
        m.id = action_id
        m.name = name
        return m

    @patch('executions.app.handlers.schedule_execution_handler.ScheduledExecution')
    @patch('catalog.models.Action')
    def test_basic_input_mapping_schedule(self, mock_action_class, mock_se_class):
        """Schedule with date/time from input_mapping (e.g. from variable picker)."""
        target_action = self._make_action()
        mock_action_class.objects.get.return_value = target_action

        created_se = MagicMock()
        created_se.id = 99
        mock_se_class.objects.create.return_value = created_se

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'schedule-deploy',
            'action_id': 42,
            'schedule_config': {'schedule_source': 'input_mapping'},
        }

        # Simulates resolved_params from input_mapping referencing previous steps
        resolved_params = {
            'schedule_name': 'Deploy for CHG0012345',
            'scheduled_date': '2025-06-20',
            'scheduled_time': '22:00',
            'duration_minutes': 60,
            'change_number': 'CHG0012345',  # from previous service_call step
        }

        result = self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-456',
        )

        assert result['scheduled_execution_id'] == 99
        assert result['action_id'] == 42
        assert result['schedule_name'] == 'Deploy for CHG0012345'
        assert result['parameters_injected'] is True
        assert result['status'] == ExecutionStatus.COMPLETED

        # Verify ScheduledExecution was created with correct args
        mock_se_class.objects.create.assert_called_once()
        create_kwargs = mock_se_class.objects.create.call_args[1]
        assert create_kwargs['action'] == target_action
        assert create_kwargs['source_execution_id'] == 1
        assert create_kwargs['correlation_id'] == 'corr-456'

        # Verify parameters were set (change_number forwarded)
        created_se.set_parameters.assert_called_once()
        params = created_se.set_parameters.call_args[0][0]
        assert params['change_number'] == 'CHG0012345'

    @patch('executions.app.handlers.schedule_execution_handler.ScheduledExecution')
    @patch('catalog.models.Action')
    def test_fixed_offset_schedule(self, mock_action_class, mock_se_class):
        """Schedule with fixed_offset calculates scheduled_at from now()."""
        mock_action_class.objects.get.return_value = self._make_action()
        created_se = MagicMock()
        created_se.id = 100
        mock_se_class.objects.create.return_value = created_se

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'schedule-later',
            'action_id': 42,
            'schedule_config': {
                'schedule_source': 'fixed_offset',
                'fixed_offset': '+2d',
            },
        }

        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-789',
        )

        assert result['scheduled_execution_id'] == 100
        # scheduled_at should be approximately now + 2 days
        assert result['scheduled_at'] is not None

    @patch('executions.app.handlers.schedule_execution_handler.ScheduledExecution')
    @patch('catalog.models.Action')
    def test_parameter_source_schedule(self, mock_action_class, mock_se_class):
        """Schedule with parameter source reads date from resolved_params."""
        mock_action_class.objects.get.return_value = self._make_action()
        created_se = MagicMock()
        created_se.id = 101
        mock_se_class.objects.create.return_value = created_se

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'schedule-from-param',
            'action_id': 42,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'planned_start_date',
            },
        }

        resolved_params = {
            'planned_start_date': '2025-07-01T10:00:00',
        }

        result = self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-101',
        )

        assert result['scheduled_execution_id'] == 101
        assert '2025-07-01' in result['scheduled_at']

    @patch('catalog.models.Action')
    def test_missing_action_id_raises(self, mock_action_class):
        """Missing action_id in step_config should raise ValueError."""
        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'bad-step',
        }

        with pytest.raises(ValueError, match="requires 'action_id'"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id='corr-err',
            )

    @patch('catalog.models.Action')
    def test_action_not_found_raises(self, mock_action_class):
        """Non-existent action_id should raise ValueError."""
        mock_action_class.DoesNotExist = RealAction.DoesNotExist
        mock_action_class.objects.get.side_effect = RealAction.DoesNotExist

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'bad-action',
            'action_id': 999,
        }

        with pytest.raises(ValueError, match="not found"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id='corr-err2',
            )

    @patch('executions.app.handlers.schedule_execution_handler.ScheduledExecution')
    @patch('catalog.models.Action')
    def test_no_date_creates_pending_without_scheduled_at(self, mock_action_class, mock_se_class):
        """No date info → scheduled_at is None (manual trigger later)."""
        mock_action_class.objects.get.return_value = self._make_action()
        created_se = MagicMock()
        created_se.id = 102
        mock_se_class.objects.create.return_value = created_se

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'schedule-manual',
            'action_id': 42,
        }

        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-manual',
        )

        assert result['scheduled_at'] is None
        assert result['parameters_injected'] is False

    @patch('catalog.models.Action')
    def test_parameter_source_missing_param_raises(self, mock_action_class):
        """parameter source with missing param should raise ValueError."""
        mock_action_class.objects.get.return_value = self._make_action()

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'schedule-bad-param',
            'action_id': 42,
            'schedule_config': {
                'schedule_source': 'parameter',
                'schedule_parameter_name': 'missing_date',
            },
        }

        with pytest.raises(ValueError, match="not found in resolved_params"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id='corr-bad',
            )


    @patch('executions.app.handlers.schedule_execution_handler.ScheduledExecution')
    @patch('catalog.models.Action')
    def test_parameter_mapping_forwards_only_mapped_keys(self, mock_action_class, mock_se_class):
        """parameter_mapping selectively forwards resolved_params to action parameters."""
        mock_action_class.objects.get.return_value = self._make_action()
        created_se = MagicMock()
        created_se.id = 200
        mock_se_class.objects.create.return_value = created_se

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'schedule-with-mapping',
            'action_id': 42,
            'schedule_config': {'schedule_source': 'input_mapping'},
            'parameter_mapping': {
                'change_number': 'chg_num',       # rename: chg_num → change_number
                'target_host': 'target_host',     # pass-through
            },
        }

        # These come from input_mapping already resolved by StepTemplateResolver
        resolved_params = {
            'schedule_name': 'Deploy for CHG001',
            'scheduled_date': '2025-07-15',
            'scheduled_time': '22:00',
            'chg_num': 'CHG0012345',          # from {{ steps.create_change.number }}
            'target_host': 'db-prod-01',       # from {{ steps.discovery.hostname }}
            'extra_data': 'should_not_pass',   # NOT in parameter_mapping → excluded
        }

        result = self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-mapping',
        )

        assert result['scheduled_execution_id'] == 200
        assert result['parameters_injected'] is True

        # Verify only mapped keys were forwarded
        created_se.set_parameters.assert_called_once()
        params = created_se.set_parameters.call_args[0][0]
        assert params['change_number'] == 'CHG0012345'
        assert params['target_host'] == 'db-prod-01'
        assert 'extra_data' not in params
        assert 'chg_num' not in params  # source key renamed to target key

    @patch('executions.app.handlers.schedule_execution_handler.ScheduledExecution')
    @patch('catalog.models.Action')
    def test_no_parameter_mapping_forwards_all_remaining(self, mock_action_class, mock_se_class):
        """Without parameter_mapping, all non-scheduling keys are forwarded."""
        mock_action_class.objects.get.return_value = self._make_action()
        created_se = MagicMock()
        created_se.id = 201
        mock_se_class.objects.create.return_value = created_se

        step_config = {
            'step_type': 'schedule_execution',
            'step_id': 'schedule-no-mapping',
            'action_id': 42,
            # No parameter_mapping — all remaining params forwarded
        }

        resolved_params = {
            'scheduled_date': '2025-07-15',
            'change_number': 'CHG001',
            'target_host': 'db-prod-01',
        }

        result = self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-no-mapping',
        )

        assert result['parameters_injected'] is True
        params = created_se.set_parameters.call_args[0][0]
        assert params['change_number'] == 'CHG001'
        assert params['target_host'] == 'db-prod-01'
        # scheduling keys should have been popped
        assert 'scheduled_date' not in params


class TestScheduleExecutionHandlerRegistry:
    """Verify the handler is registered in the StepHandlerRegistry."""

    def test_schedule_execution_registered(self):
        from executions.app.handlers.registry import step_handler_registry
        assert step_handler_registry.is_registered('schedule_execution')

    def test_schedule_execution_handler_class(self):
        from executions.app.handlers.registry import step_handler_registry
        handler_class = step_handler_registry.get('schedule_execution')
        assert handler_class is ScheduleExecutionHandler
