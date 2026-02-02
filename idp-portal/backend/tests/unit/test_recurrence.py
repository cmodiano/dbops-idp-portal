"""Tests for recurrence calculation utilities (Story 11.7, Task 12).

Tests calculate_next_execution_date for daily and weekly patterns:
- Daily pattern: calculates next execution based on current time
- Weekly pattern: calculates next execution for specific day of week
- Validation: raises ValueError for invalid patterns
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.utils.recurrence import (
    calculate_next_execution_date,
    increment_next_execution_date,
)


class TestCalculateDailyNextExecution:
    """Tests for daily pattern next execution calculation (Story 11.7, AC4)."""

    def test_daily_before_time_returns_today(self):
        """Daily pattern created before target time returns today (AC4)."""
        # Reference: 2026-02-02 at 01:00 UTC
        # Pattern: 02:30 every day
        # Expected: 2026-02-02 at 02:30 UTC (today, not passed yet)
        reference_datetime = datetime(2026, 2, 2, 1, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"hour": 2, "minute": 30}

        result = calculate_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 2, 2, 30, 0, tzinfo=timezone.utc)

    def test_daily_after_time_returns_tomorrow(self):
        """Daily pattern created after target time returns tomorrow (AC4)."""
        # Reference: 2026-02-02 at 15:00 UTC
        # Pattern: 02:30 every day
        # Expected: 2026-02-03 at 02:30 UTC (tomorrow)
        reference_datetime = datetime(2026, 2, 2, 15, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"hour": 2, "minute": 30}

        result = calculate_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 3, 2, 30, 0, tzinfo=timezone.utc)

    def test_daily_exact_time_returns_tomorrow(self):
        """Daily pattern created at exact target time returns tomorrow."""
        # Reference: 2026-02-02 at 02:30 UTC (exact match)
        # Pattern: 02:30 every day
        # Expected: 2026-02-03 at 02:30 UTC (tomorrow, since current time is not "in future")
        reference_datetime = datetime(2026, 2, 2, 2, 30, 0, tzinfo=timezone.utc)
        pattern_config = {"hour": 2, "minute": 30}

        result = calculate_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 3, 2, 30, 0, tzinfo=timezone.utc)

    def test_daily_midnight_pattern(self):
        """Daily pattern with midnight (00:00) works correctly."""
        # Reference: 2026-02-02 at 01:00 UTC
        # Pattern: 00:00 every day
        # Expected: 2026-02-03 at 00:00 UTC (tomorrow, since 00:00 already passed today)
        reference_datetime = datetime(2026, 2, 2, 1, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"hour": 0, "minute": 0}

        result = calculate_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 3, 0, 0, 0, tzinfo=timezone.utc)

    def test_daily_end_of_month(self):
        """Daily pattern works correctly at end of month."""
        # Reference: 2026-02-28 at 15:00 UTC
        # Pattern: 02:30 every day
        # Expected: 2026-03-01 at 02:30 UTC (next month)
        reference_datetime = datetime(2026, 2, 28, 15, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"hour": 2, "minute": 30}

        result = calculate_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 3, 1, 2, 30, 0, tzinfo=timezone.utc)


class TestCalculateWeeklyNextExecution:
    """Tests for weekly pattern next execution calculation (Story 11.7, AC5)."""

    def test_weekly_same_day_before_time_returns_today(self):
        """Weekly pattern on same day before time returns today (AC5)."""
        # Reference: Monday 2026-02-02 at 10:00 UTC
        # Pattern: Monday (day_of_week=1) at 14:00
        # Expected: 2026-02-02 at 14:00 UTC (today, same Monday)
        reference_datetime = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        # Verify it's a Monday: 2026-02-02 is Monday (weekday() = 0)
        assert reference_datetime.weekday() == 0  # Monday

        pattern_config = {"day_of_week": 1, "hour": 14, "minute": 0}

        result = calculate_next_execution_date(
            pattern_type="weekly",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 2, 14, 0, 0, tzinfo=timezone.utc)

    def test_weekly_same_day_after_time_returns_next_week(self):
        """Weekly pattern on same day after time returns next week (AC5)."""
        # Reference: Monday 2026-02-02 at 16:00 UTC
        # Pattern: Monday (day_of_week=1) at 14:00
        # Expected: 2026-02-09 at 14:00 UTC (next Monday)
        reference_datetime = datetime(2026, 2, 2, 16, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"day_of_week": 1, "hour": 14, "minute": 0}

        result = calculate_next_execution_date(
            pattern_type="weekly",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc)

    def test_weekly_different_day_returns_next_occurrence(self):
        """Weekly pattern on different day returns next occurrence (AC5)."""
        # Reference: Tuesday 2026-02-03 at 10:00 UTC
        # Pattern: Monday (day_of_week=1) at 14:00
        # Expected: 2026-02-09 at 14:00 UTC (next Monday)
        reference_datetime = datetime(2026, 2, 3, 10, 0, 0, tzinfo=timezone.utc)
        # Verify it's a Tuesday: 2026-02-03 is Tuesday (weekday() = 1)
        assert reference_datetime.weekday() == 1  # Tuesday

        pattern_config = {"day_of_week": 1, "hour": 14, "minute": 0}

        result = calculate_next_execution_date(
            pattern_type="weekly",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc)

    def test_weekly_friday_from_monday(self):
        """Weekly pattern for Friday calculated from Monday."""
        # Reference: Monday 2026-02-02 at 10:00 UTC
        # Pattern: Friday (day_of_week=5) at 09:00
        # Expected: 2026-02-06 at 09:00 UTC (this Friday)
        reference_datetime = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"day_of_week": 5, "hour": 9, "minute": 0}

        result = calculate_next_execution_date(
            pattern_type="weekly",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        assert result == datetime(2026, 2, 6, 9, 0, 0, tzinfo=timezone.utc)

    def test_weekly_sunday_pattern(self):
        """Weekly pattern for Sunday (day_of_week=7) works correctly."""
        # Reference: Monday 2026-02-02 at 10:00 UTC
        # Pattern: Sunday (day_of_week=7) at 20:00
        # Expected: 2026-02-08 at 20:00 UTC (this Sunday)
        reference_datetime = datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"day_of_week": 7, "hour": 20, "minute": 0}

        result = calculate_next_execution_date(
            pattern_type="weekly",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        # 2026-02-08 is Sunday
        expected = datetime(2026, 2, 8, 20, 0, 0, tzinfo=timezone.utc)
        assert expected.weekday() == 6  # Sunday in Python
        assert result == expected


class TestValidation:
    """Tests for pattern validation errors (Story 11.7, AC6)."""

    def test_invalid_pattern_type_raises_error(self):
        """Invalid pattern_type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date(
                pattern_type="monthly",  # Invalid
                pattern_config={"hour": 2, "minute": 30},
            )

        assert "non supporté" in str(exc_info.value)

    def test_daily_missing_hour_raises_error(self):
        """Daily pattern missing hour raises ValueError (AC6)."""
        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date(
                pattern_type="daily",
                pattern_config={"minute": 30},  # Missing hour
            )

        assert "hour" in str(exc_info.value)
        assert "minute" in str(exc_info.value)

    def test_daily_missing_minute_raises_error(self):
        """Daily pattern missing minute raises ValueError (AC6)."""
        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date(
                pattern_type="daily",
                pattern_config={"hour": 2},  # Missing minute
            )

        assert "hour" in str(exc_info.value)
        assert "minute" in str(exc_info.value)

    def test_daily_invalid_hour_raises_error(self):
        """Daily pattern with hour > 23 raises ValueError (AC6)."""
        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date(
                pattern_type="daily",
                pattern_config={"hour": 25, "minute": 0},  # Invalid hour
            )

        assert "hour" in str(exc_info.value)
        assert "0" in str(exc_info.value) and "23" in str(exc_info.value)

    def test_weekly_missing_day_of_week_raises_error(self):
        """Weekly pattern missing day_of_week raises ValueError (AC6)."""
        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date(
                pattern_type="weekly",
                pattern_config={"hour": 14, "minute": 0},  # Missing day_of_week
            )

        assert "day_of_week" in str(exc_info.value)

    def test_weekly_invalid_day_of_week_raises_error(self):
        """Weekly pattern with day_of_week > 7 raises ValueError (AC6)."""
        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date(
                pattern_type="weekly",
                pattern_config={"day_of_week": 8, "hour": 14, "minute": 0},
            )

        assert "day_of_week" in str(exc_info.value)
        assert "1" in str(exc_info.value)
        assert "7" in str(exc_info.value)

    def test_weekly_invalid_day_of_week_zero_raises_error(self):
        """Weekly pattern with day_of_week = 0 raises ValueError (AC6)."""
        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date(
                pattern_type="weekly",
                pattern_config={"day_of_week": 0, "hour": 14, "minute": 0},
            )

        assert "day_of_week" in str(exc_info.value)


class TestIncrementNextExecutionDate:
    """Tests for incrementing next_execution_date after execution."""

    def test_increment_daily_adds_one_day(self):
        """Incrementing daily pattern adds 1 day."""
        current = datetime(2026, 2, 2, 2, 30, 0, tzinfo=timezone.utc)
        pattern_config = {"hour": 2, "minute": 30}

        result = increment_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            current_next_execution_date=current,
        )

        assert result == datetime(2026, 2, 3, 2, 30, 0, tzinfo=timezone.utc)

    def test_increment_weekly_adds_seven_days(self):
        """Incrementing weekly pattern adds 7 days."""
        current = datetime(2026, 2, 2, 14, 0, 0, tzinfo=timezone.utc)
        pattern_config = {"day_of_week": 1, "hour": 14, "minute": 0}

        result = increment_next_execution_date(
            pattern_type="weekly",
            pattern_config=pattern_config,
            current_next_execution_date=current,
        )

        assert result == datetime(2026, 2, 9, 14, 0, 0, tzinfo=timezone.utc)

    def test_increment_invalid_pattern_type_raises_error(self):
        """Incrementing with invalid pattern_type raises ValueError."""
        current = datetime(2026, 2, 2, 2, 30, 0, tzinfo=timezone.utc)

        with pytest.raises(ValueError):
            increment_next_execution_date(
                pattern_type="monthly",
                pattern_config={},
                current_next_execution_date=current,
            )


class TestTimezoneHandling:
    """Tests for timezone handling in calculations."""

    def test_naive_datetime_converted_to_utc(self):
        """Naive datetime is converted to UTC for calculation."""
        # Reference without timezone
        reference_datetime = datetime(2026, 2, 2, 1, 0, 0)  # Naive
        pattern_config = {"hour": 2, "minute": 30}

        result = calculate_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            reference_datetime=reference_datetime,
        )

        # Result should be timezone-aware UTC
        assert result.tzinfo == timezone.utc
        assert result == datetime(2026, 2, 2, 2, 30, 0, tzinfo=timezone.utc)

    def test_uses_now_utc_when_no_reference(self):
        """Uses current UTC time when reference_datetime is None."""
        pattern_config = {"hour": 23, "minute": 59}

        result = calculate_next_execution_date(
            pattern_type="daily",
            pattern_config=pattern_config,
            reference_datetime=None,  # Should use now()
        )

        # Result should be in the future
        assert result.tzinfo == timezone.utc
        assert result > datetime.now(timezone.utc) - timedelta(minutes=1)
