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

parameter_mapping (dans step_config) permet de mapper les valeurs résolues depuis
des steps précédents vers les paramètres attendus par l'action cible :

    "parameter_mapping": {
        "change_number": "{{ steps.create_change.number }}",
        "target_server": "{{ steps.discovery.server_name }}"
    }

Ces valeurs sont résolues via le StepTemplateResolver (comme input_mapping) et
transmises comme paramètres de la ScheduledExecution. Quand le Celery Beat
déclenche la planification, ces paramètres sont injectés dans l'Execution créée
via ExecutionRequest.parameters.
"""
from __future__ import annotations

import re
import zoneinfo
from datetime import datetime, timedelta
from typing import Any

import structlog
from django.utils import timezone

from executions.models import Execution, ExecutionStatus, ScheduledExecution, ScheduledExecutionStatus

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


def _parse_scheduled_datetime(
    date_str: str,
    time_str: str | None = None,
    tz_name: str | None = None,
) -> datetime:
    """Parse date and optional time strings into a UTC-aware datetime.

    Args:
        date_str: Date string (YYYY-MM-DD or full ISO 8601).
        time_str: Optional time string (HH:MM or HH:MM:SS).
        tz_name: IANA timezone name for the input (e.g. 'America/Montreal').
                 If None, falls back to Django settings.TIME_ZONE (UTC).

    The user enters date/time in their local timezone. This function interprets
    the naive datetime in that timezone, then converts to UTC for DB storage.
    """
    if not date_str:
        raise ValueError("scheduled_date is required")

    # Resolve the user's timezone (or fall back to Django default = UTC)
    user_tz: zoneinfo.ZoneInfo | None = None
    if tz_name:
        try:
            user_tz = zoneinfo.ZoneInfo(tz_name)
        except (KeyError, zoneinfo.ZoneInfoNotFoundError):
            logger.warning(
                "schedule_execution_invalid_timezone",
                timezone=tz_name,
            )
            # Fall through to Django default

    # Try full ISO datetime first (e.g. "2025-07-15T22:00:00-04:00" from a
    # previous step output).  Only use this fast path when:
    #   1. No separate time_str was provided (otherwise the caller expects
    #      date_str to be date-only and time_str to carry the time component).
    #   2. date_str contains a time component ('T' separator) so we don't
    #      accidentally match a bare "YYYY-MM-DD" — which fromisoformat()
    #      accepts on Python 3.11+ and silently returns midnight, discarding
    #      any time_str the caller intended us to combine.
    if time_str is None and 'T' in str(date_str):
        try:
            dt = datetime.fromisoformat(str(date_str))
            if dt.tzinfo is not None:
                # Already tz-aware → convert to UTC
                return dt.astimezone(zoneinfo.ZoneInfo('UTC'))
            # Naive ISO datetime → interpret in user's timezone
            if user_tz:
                dt = dt.replace(tzinfo=user_tz)
                return dt.astimezone(zoneinfo.ZoneInfo('UTC'))
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

    # Interpret in user's local timezone, then convert to UTC for storage
    if user_tz:
        dt = dt.replace(tzinfo=user_tz)
        return dt.astimezone(zoneinfo.ZoneInfo('UTC'))

    # No user timezone provided → interpret in Django default (UTC)
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

    Paramètres dans step_config :
        - action_id (int) : ID de l'action cible à planifier
        - schedule_config (dict) : configuration de la source de planification
        - parameter_mapping (dict) : mapping des paramètres de l'action cible.
          Les clés sont les noms de paramètres attendus par l'action, les valeurs
          sont des templates Jinja2 résolus via input_mapping.
          Exemple : {"change_number": "{{ steps.create_change.number }}"}
          Ces valeurs arrivent déjà résolues dans resolved_params car le
          StepTemplateResolver traite input_mapping avant l'appel au handler.
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
        # schedule_timezone allows the user to specify their local timezone
        # (e.g. 'America/Montreal') so that date/time inputs are correctly
        # converted to UTC before DB storage.
        user_timezone = resolved_params.get('schedule_timezone')
        scheduled_at = self._resolve_scheduled_at(schedule_config, resolved_params, user_timezone)

        # --- Extract scheduling metadata from resolved_params ---
        schedule_name = resolved_params.pop('schedule_name', None)
        # Remove scheduling-specific keys from params before forwarding
        scheduled_date = resolved_params.pop('scheduled_date', None)
        scheduled_time = resolved_params.pop('scheduled_time', None)
        duration_minutes = resolved_params.pop('duration_minutes', None)
        # Pop timezone so it doesn't leak into action parameters
        resolved_params.pop('schedule_timezone', None)

        # --- Build execution parameters for the target action ---
        # parameter_mapping keys in step_config define which resolved_params
        # map to the target action's parameters. The values are already resolved
        # by StepTemplateResolver before reaching this handler.
        #
        # Example step_config:
        #   "input_mapping": {
        #       "schedule_name": "Deploy CHG {{ steps.create_change.number }}",
        #       "scheduled_date": "2025-06-20",
        #       "change_number": "{{ steps.create_change.number }}",
        #       "target_host": "{{ steps.discovery.hostname }}"
        #   },
        #   "parameter_mapping": {
        #       "change_number": "change_number",
        #       "target_host": "target_host"
        #   }
        #
        # parameter_mapping tells us which resolved_params keys are action
        # parameters (vs scheduling metadata). If parameter_mapping is absent,
        # all non-scheduling keys in resolved_params are forwarded as-is.
        parameter_mapping = step_config.get('parameter_mapping')

        if parameter_mapping and isinstance(parameter_mapping, dict):
            # Explicit mapping: only forward mapped keys, renaming if needed
            # Keys = target action param name, Values = source key in resolved_params
            execution_parameters: dict = {}
            for target_key, source_key in parameter_mapping.items():
                if source_key in resolved_params:
                    execution_parameters[target_key] = resolved_params[source_key]
                else:
                    logger.warning(
                        "schedule_execution_parameter_mapping_missing_source",
                        target_key=target_key,
                        source_key=source_key,
                        execution_id=execution.id,
                        correlation_id=correlation_id,
                    )
        else:
            # No explicit mapping: forward all remaining resolved_params as-is
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
            'status': ExecutionStatus.COMPLETED,
        }

    def _resolve_scheduled_at(
        self,
        schedule_config: dict,
        resolved_params: dict,
        user_timezone: str | None = None,
    ) -> datetime | None:
        """Resolve the scheduled_at datetime from schedule_config and resolved_params.

        All returned datetimes are UTC-aware for consistent DB storage.
        user_timezone (IANA name, e.g. 'America/Montreal') is used to
        interpret naive date/time inputs from the user's local timezone.
        """
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
            return _parse_scheduled_datetime(str(raw_value), tz_name=user_timezone)

        # Default: 'input_mapping' — date/time come from resolved_params directly
        scheduled_date = resolved_params.get('scheduled_date')
        if scheduled_date:
            scheduled_time = resolved_params.get('scheduled_time')
            return _parse_scheduled_datetime(
                str(scheduled_date),
                str(scheduled_time) if scheduled_time else None,
                tz_name=user_timezone,
            )

        # No date specified — will be pending without a scheduled_at (manual trigger)
        return None
