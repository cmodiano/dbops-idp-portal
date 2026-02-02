"""Recurrence calculation utilities for Story 11.7, 11.8 - Recurring executions.

Provides functions to calculate next_execution_date for daily, weekly, and cron patterns.
All datetime calculations are performed in UTC.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from croniter import croniter
import structlog

logger = structlog.get_logger(__name__)


def calculate_next_execution_date(
    pattern_type: str,
    pattern_config: dict[str, Any],
    reference_datetime: datetime | None = None,
) -> datetime:
    """Calculate next execution date for recurring pattern (Story 11.7 AC4-AC5, Story 11.8 AC6).

    Args:
        pattern_type: Type of pattern ("daily", "weekly", or "cron")
        pattern_config: Pattern configuration dict
            - daily: {"hour": int, "minute": int}
            - weekly: {"day_of_week": int, "hour": int, "minute": int}
            - cron: {"cron_expression": str} (Story 11.8)
        reference_datetime: Reference time (defaults to now in UTC)

    Returns:
        Next execution datetime in UTC

    Raises:
        ValueError: If pattern_type or pattern_config is invalid
    """
    if reference_datetime is None:
        reference_datetime = datetime.now(timezone.utc)

    # Ensure reference_datetime is in UTC
    if reference_datetime.tzinfo is None:
        reference_datetime = reference_datetime.replace(tzinfo=timezone.utc)

    if pattern_type == "daily":
        return _calculate_daily_next_execution(pattern_config, reference_datetime)
    elif pattern_type == "weekly":
        return _calculate_weekly_next_execution(pattern_config, reference_datetime)
    elif pattern_type == "cron":
        return _calculate_cron_next_execution(pattern_config, reference_datetime)
    else:
        raise ValueError(f"Type de pattern non supporté : {pattern_type}")


def _calculate_daily_next_execution(
    pattern_config: dict[str, Any],
    reference_datetime: datetime,
) -> datetime:
    """Calculate next execution for daily pattern (Story 11.7, AC4).

    Args:
        pattern_config: {"hour": int, "minute": int}
        reference_datetime: Reference datetime in UTC

    Returns:
        Next execution datetime in UTC

    Logic:
        - If today's target time is still in the future, use today
        - Otherwise, use tomorrow at the target time
    """
    hour = pattern_config.get("hour")
    minute = pattern_config.get("minute")

    if hour is None or minute is None:
        raise ValueError(
            "Pattern config incomplet : hour et minute requis pour pattern daily"
        )

    if not isinstance(hour, int) or hour < 0 or hour > 23:
        raise ValueError("Valeur invalide pour hour : doit être entre 0 et 23")

    if not isinstance(minute, int) or minute < 0 or minute > 59:
        raise ValueError("Valeur invalide pour minute : doit être entre 0 et 59")

    # Build target time for today
    target_time = reference_datetime.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    # If target time is in the future today, use today; otherwise tomorrow
    if target_time > reference_datetime:
        next_execution = target_time
    else:
        next_execution = target_time + timedelta(days=1)

    logger.info(
        "calculated_daily_next_execution",
        pattern_config=pattern_config,
        reference_datetime=reference_datetime.isoformat(),
        next_execution=next_execution.isoformat(),
    )

    return next_execution


def _calculate_weekly_next_execution(
    pattern_config: dict[str, Any],
    reference_datetime: datetime,
) -> datetime:
    """Calculate next execution for weekly pattern (Story 11.7, AC5).

    Args:
        pattern_config: {"day_of_week": int, "hour": int, "minute": int}
            day_of_week: 1=Monday, 2=Tuesday, ..., 7=Sunday
        reference_datetime: Reference datetime in UTC

    Returns:
        Next execution datetime in UTC

    Logic:
        - If today is the target day and target time is still in the future, use today
        - Otherwise, calculate days until next occurrence of target day
    """
    day_of_week = pattern_config.get("day_of_week")  # 1=Monday, 7=Sunday
    hour = pattern_config.get("hour")
    minute = pattern_config.get("minute")

    if day_of_week is None or hour is None or minute is None:
        raise ValueError(
            "Pattern config incomplet : day_of_week, hour et minute requis pour pattern weekly"
        )

    if not isinstance(day_of_week, int) or day_of_week < 1 or day_of_week > 7:
        raise ValueError(
            "Valeur invalide pour day_of_week : doit être entre 1 (lundi) et 7 (dimanche)"
        )

    if not isinstance(hour, int) or hour < 0 or hour > 23:
        raise ValueError("Valeur invalide pour hour : doit être entre 0 et 23")

    if not isinstance(minute, int) or minute < 0 or minute > 59:
        raise ValueError("Valeur invalide pour minute : doit être entre 0 et 59")

    # Python weekday: 0=Monday, 6=Sunday
    # Our convention: 1=Monday, 7=Sunday
    # Convert from our convention to Python weekday
    target_weekday = day_of_week - 1  # 1->0, 2->1, ..., 7->6

    current_weekday = reference_datetime.weekday()

    # Calculate days until target weekday
    days_until_target = (target_weekday - current_weekday) % 7

    # Build target datetime
    target_datetime = reference_datetime + timedelta(days=days_until_target)
    target_datetime = target_datetime.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    # If target is in the past or equal (same day but earlier/same time), move to next week
    if target_datetime <= reference_datetime:
        target_datetime += timedelta(weeks=1)

    logger.info(
        "calculated_weekly_next_execution",
        pattern_config=pattern_config,
        reference_datetime=reference_datetime.isoformat(),
        next_execution=target_datetime.isoformat(),
    )

    return target_datetime


def _calculate_cron_next_execution(
    pattern_config: dict[str, Any],
    reference_datetime: datetime,
) -> datetime:
    """Calculate next execution for cron pattern (Story 11.8, AC6).

    Args:
        pattern_config: {"cron_expression": str}
            cron_expression: Standard 5-field cron format (minute hour day month day_of_week)
        reference_datetime: Reference datetime in UTC

    Returns:
        Next execution datetime in UTC

    Raises:
        ValueError: If cron expression is missing or invalid

    Examples:
        - "0 2 * * 1-5" (weekdays at 2am): Next weekday at 02:00 UTC
        - "0 0 1 * *" (first of month): Next 1st of month at midnight UTC
        - "*/15 * * * *" (every 15 min): Next 15-minute mark
    """
    cron_expression = pattern_config.get("cron_expression")

    if not cron_expression:
        raise ValueError(
            "Pattern config incomplet : cron_expression requis pour pattern cron"
        )

    # Validate cron expression
    if not croniter.is_valid(cron_expression):
        raise ValueError(
            f"Expression cron invalide : {cron_expression}. "
            f"Format attendu : minute hour day month day_of_week"
        )

    try:
        # Create croniter instance with reference datetime
        cron = croniter(cron_expression, reference_datetime)

        # Get next execution datetime
        next_execution = cron.get_next(datetime)

        # Ensure result has UTC timezone
        if next_execution.tzinfo is None:
            next_execution = next_execution.replace(tzinfo=timezone.utc)

        logger.info(
            "calculated_cron_next_execution",
            cron_expression=cron_expression,
            reference_datetime=reference_datetime.isoformat(),
            next_execution=next_execution.isoformat(),
        )

        return next_execution

    except (ValueError, KeyError) as e:
        raise ValueError(
            f"Erreur lors du calcul de la prochaine exécution cron : {str(e)}"
        ) from e


def increment_next_execution_date(
    pattern_type: str,
    pattern_config: dict[str, Any],
    current_next_execution_date: datetime,
) -> datetime:
    """Increment next_execution_date after execution completes (for scheduler external).

    Args:
        pattern_type: Type of pattern ("daily", "weekly", or "cron")
        pattern_config: Pattern configuration dict
        current_next_execution_date: Current next_execution_date

    Returns:
        New next_execution_date (incremented by 1 day for daily, 7 days for weekly,
        calculated via croniter for cron)
    """
    if pattern_type == "daily":
        return current_next_execution_date + timedelta(days=1)
    elif pattern_type == "weekly":
        return current_next_execution_date + timedelta(weeks=1)
    elif pattern_type == "cron":
        # For cron, recalculate from current_next_execution_date using croniter
        return _calculate_cron_next_execution(pattern_config, current_next_execution_date)
    else:
        raise ValueError(f"Type de pattern non supporté : {pattern_type}")
