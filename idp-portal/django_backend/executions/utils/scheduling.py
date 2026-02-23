"""
Module executions.utils.scheduling — Calcul de la prochaine date d'exécution planifiée.

Responsabilité unique : calculer `calculate_next_execution_date` pour les patterns
daily, weekly et cron (via croniter).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from django.utils import timezone
from croniter import croniter

from core.exceptions import BadRequestError

# Fixed-offset UTC — Oracle Thin Mode ne supporte pas les named timezones (DPY-3022)
UTC = dt_timezone(timedelta(0))


def calculate_next_execution_date(pattern_type: str, pattern_config: dict, reference: datetime) -> datetime:
    """
    Compute next execution datetime in UTC for daily/weekly/cron patterns.
    Story 26.10: Renamed from _calculate_next_execution_date to respect Python convention (PEP 8).
    """
    if timezone.is_naive(reference):
        reference = timezone.make_aware(reference, timezone=UTC)
    else:
        reference = reference.astimezone(UTC)

    pattern_type = (pattern_type or "").lower()

    if pattern_type == "daily":
        try:
            hour = int(pattern_config.get("hour", 0))
            minute = int(pattern_config.get("minute", 0))
        except (TypeError, ValueError) as exc:
            raise BadRequestError(
                code="INVALID_PATTERN_CONFIG",
                message="pattern_config.hour et pattern_config.minute doivent être des entiers",
                details={"pattern_type": pattern_type, "error": str(exc)},
            ) from exc
        candidate = reference.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= reference:
            candidate = candidate + timedelta(days=1)
        return candidate

    if pattern_type == "weekly":
        try:
            day_of_week = int(pattern_config.get("day_of_week", 1))  # 1=Mon .. 7=Sun
            hour = int(pattern_config.get("hour", 0))
            minute = int(pattern_config.get("minute", 0))
        except (TypeError, ValueError) as exc:
            raise BadRequestError(
                code="INVALID_PATTERN_CONFIG",
                message="pattern_config.day_of_week, hour et minute doivent être des entiers",
                details={"pattern_type": pattern_type, "error": str(exc)},
            ) from exc
        # ISO weekday: Monday=1..Sunday=7
        current_dow = reference.isoweekday()
        days_ahead = (day_of_week - current_dow) % 7
        candidate = (reference + timedelta(days=days_ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= reference:
            candidate = candidate + timedelta(days=7)
        return candidate

    if pattern_type == "cron":
        expr = str(pattern_config.get("cron_expression", "")).strip()
        if not expr or not croniter.is_valid(expr):
            raise BadRequestError(
                code="INVALID_CRON_EXPRESSION",
                message="Expression cron invalide. Format attendu : minute hour day month day_of_week",
                details={"expression": expr},
            )
        it = croniter(expr, reference)
        nxt: datetime = it.get_next(datetime)
        if timezone.is_naive(nxt):
            nxt = timezone.make_aware(nxt, timezone=UTC)
        else:
            nxt = nxt.astimezone(UTC)
        return nxt

    raise BadRequestError(
        code="BAD_REQUEST",
        message="pattern_type invalide",
        details={"pattern_type": pattern_type},
    )
