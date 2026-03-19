"""
ScheduleExecutionHandler — Handler pour les steps de type schedule_execution.

Crée une ScheduledExecution à partir des resolved_params (issus de input_mapping
et du StepTemplateResolver). Permet de planifier une exécution différée dont les
paramètres proviennent de steps précédents (ex: numéro de changement ServiceNow).

schedule_config (dans step_config) détermine la source de la date de planification :
  - 'parameter' : la date vient de resolved_params[schedule_parameter_name]
  - 'fixed_offset' : décalage relatif depuis now (+2d, +4h, etc.)
  - 'input_mapping' : la date et l'heure viennent directement des resolved_params
    (clés : scheduled_date, scheduled_time, duration_minutes, schedule_name)

Les paramètres résolus (via {{ steps.<step_id>.<field> }}) sont transmis tels quels
à la ScheduledExecution créée, ce qui permet au variable picker du frontend de
référencer les outputs de steps précédents.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

import structlog
from django.utils import timezone

from executions.models import Execution, ScheduledExecution, ScheduledExecutionStatus

logger = structlog.get_logger(__name__)

# Regex pour parser fixed_offset (+2d, +4h, +1w, +3m)
_OFFSET_RE = re.compile(r'^\+(\d+)([dhwm])$')
_OFFSET_UNITS = {'d': 'days', 'h': 'hours', 'w': 'weeks'}


def _parse_offset(offset_str: str) -> timedelta:
    """Parse a fixed_offset string like '+2d' into a timedelta."""
    match = _OFFSET_RE.match(offset_str)
    if not match:
        raise ValueError(f"Invalid fixed_offset format: {offset_str!r}. Expected +Nd, +Nh, +Nw, +Nm")
    amount = int(match.group(1))
    unit = match.group(2)
    if unit == 'm':
        # months → approximate as 30 days
        return timedelta(days=amount * 30)
    return timedelta(**{_OFFSET_UNITS[unit]: amount})


def _parse_scheduled_datetime(date_str: str, time_str: str | None = None) -> datetime:
    """Parse date and optional time strings into a timezone-aware datetime.

    Supports ISO 8601 full datetime, or date + optional time separately.
    """
    if not date_str:
        raise ValueError("scheduled_date is required")

    # Try full ISO datetime first (e.g. from a previous step output)
    try:
        dt = datetime.fromisoformat(str(date_str))
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt
    except (ValueError, TypeError):
        pass

    # Parse date-only + optional time
    try:
        base_date = datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"Invalid scheduled_date format: {date_str!r}. Expected YYYY-MM-DD or ISO 8601.")

    if time_str:
        try:
            t = datetime.strptime(str(time_str), "%H:%M").time()
        except ValueError:
            try:
                t = datetime.strptime(str(time_str), "%H:%M:%S").time()
            except ValueError:
                raise ValueError(f"Invalid scheduled_time format: {time_str!r}. Expected HH:MM or HH:MM:SS.")
        dt = datetime.combine(base_date, t)
    else:
        dt = datetime.combine(base_date, datetime.min.time())

    if dt.tzinfo is None:
        dt = timezone.make_aware(dt)
    return dt


class ScheduleExecutionHandler:
    """Handler pour les steps de type schedule_execution.

    Crée une ScheduledExecution en base avec les paramètres résolus depuis
    l'input_mapping (qui peut référencer des outputs de steps précédents
    via {{ steps.<step_id>.<field> }}).

    Paramètres attendus dans resolved_params (via input_mapping) :
        - schedule_name (str, optionnel) : nom/description de la planification
        - scheduled_date (str) : date de planification (YYYY-MM-DD ou ISO 8601)
        - scheduled_time (str, optionnel) : heure (HH:MM ou HH:MM:SS)
        - duration_minutes (int, optionnel) : durée estimée en minutes
        - Tout autre paramètre : transmis comme parameters de la ScheduledExecution

    Paramètres dans step_config :
        - action_id (int) : ID de l'action cible à planifier
        - schedule_config (dict) : configuration de la source de planification
    """

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        """
        Crée une ScheduledExecution à partir de la configuration du step et des
        paramètres résolus (potentiellement issus de steps précédents).

        Returns:
            dict avec scheduled_execution_id, scheduled_at, schedule_name, action_id,
            et parameters_injected (bool indiquant si des params de steps précédents
            ont été injectés).
        """
        from catalog.models import Action  # noqa: PLC0415

        # --- Validate action_id ---
        action_id = step_config.get('action_id')
        if not action_id:
            raise ValueError("schedule_execution step requires 'action_id' in step_config")

        try:
            target_action = Action.objects.get(id=action_id)
        except Action.DoesNotExist:
            raise ValueError(f"Action with id={action_id} not found")

        schedule_config = step_config.get('schedule_config', {}) or {}

        # --- Determine scheduled_at datetime ---
        scheduled_at = self._resolve_scheduled_at(schedule_config, resolved_params)

        # --- Extract scheduling metadata from resolved_params ---
        schedule_name = resolved_params.pop('schedule_name', None)
        # Remove scheduling-specific keys from params before forwarding
        scheduled_date = resolved_params.pop('scheduled_date', None)
        scheduled_time = resolved_params.pop('scheduled_time', None)
        duration_minutes = resolved_params.pop('duration_minutes', None)

        # Remaining resolved_params become the execution parameters
        execution_parameters = dict(resolved_params) if resolved_params else {}

        # Add duration as metadata if provided
        if duration_minutes is not None:
            execution_parameters['_schedule_duration_minutes'] = duration_minutes
        if schedule_name:
            execution_parameters['_schedule_name'] = schedule_name

        parameters_injected = bool(execution_parameters)

        logger.info(
            "schedule_execution_handler_start",
            action_id=action_id,
            scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
            schedule_name=schedule_name,
            parameters_injected=parameters_injected,
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        # --- Create ScheduledExecution ---
        scheduled_execution = ScheduledExecution.objects.create(
            action=target_action,
            user=execution.user,
            environment=execution.environment,
            scheduled_at=scheduled_at,
            status=ScheduledExecutionStatus.PENDING,
            correlation_id=correlation_id,
            source_execution_id=execution.id,
        )

        if execution_parameters:
            scheduled_execution.set_parameters(execution_parameters)
            scheduled_execution.save(update_fields=['parameters'])

        logger.info(
            "schedule_execution_handler_created",
            scheduled_execution_id=scheduled_execution.id,
            action_id=action_id,
            action_name=target_action.name,
            scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
            schedule_name=schedule_name,
            parameters_injected=parameters_injected,
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        return {
            'scheduled_execution_id': scheduled_execution.id,
            'scheduled_at': scheduled_at.isoformat() if scheduled_at else None,
            'schedule_name': schedule_name or '',
            'action_id': action_id,
            'action_name': target_action.name,
            'parameters_injected': parameters_injected,
            'status': 'pending',
        }

    def _resolve_scheduled_at(
        self,
        schedule_config: dict,
        resolved_params: dict,
    ) -> datetime | None:
        """Resolve the scheduled_at datetime from schedule_config and resolved_params."""
        source = schedule_config.get('schedule_source', 'input_mapping')

        if source == 'fixed_offset':
            offset_str = schedule_config.get('fixed_offset', '+1d')
            delta = _parse_offset(offset_str)
            return timezone.now() + delta

        if source == 'parameter':
            param_name = schedule_config.get('schedule_parameter_name', 'scheduled_at')
            raw_value = resolved_params.get(param_name)
            if not raw_value:
                raise ValueError(
                    f"schedule_source='parameter' but '{param_name}' not found in resolved_params"
                )
            return _parse_scheduled_datetime(str(raw_value))

        # Default: 'input_mapping' — date/time come from resolved_params directly
        scheduled_date = resolved_params.get('scheduled_date')
        if scheduled_date:
            scheduled_time = resolved_params.get('scheduled_time')
            return _parse_scheduled_datetime(str(scheduled_date), str(scheduled_time) if scheduled_time else None)

        # No date specified — will be pending without a scheduled_at (manual trigger)
        return None
