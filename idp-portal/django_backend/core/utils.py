"""Core utility functions shared across apps."""

from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

from django.utils import timezone


def ensure_utc_isoformat(dt: datetime | None) -> str | None:
    """Convert datetime to UTC-aware ISO 8601 string with explicit timezone.

    If the datetime is naive (no timezone info), it is assumed to be UTC and
    made timezone-aware before serialization.

    Args:
        dt: datetime object (aware or naive) or None.

    Returns:
        ISO 8601 string ending with ``Z`` (e.g. ``"2026-02-09T14:30:00Z"``)
        or ``None`` if ``dt`` is ``None``.
    """
    if dt is None:
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone=dt_timezone.utc)

    # Fast path: if already UTC, skip astimezone()
    if dt.tzinfo == dt_timezone.utc:
        return dt.isoformat().replace("+00:00", "Z")

    dt_utc = dt.astimezone(dt_timezone.utc)
    return dt_utc.isoformat().replace("+00:00", "Z")
