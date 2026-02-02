"""Unit tests for cron recurrence calculation (Story 11.8).

Tests for _calculate_cron_next_execution and cron pattern validation.
All datetime calculations are performed in UTC.
"""

from datetime import datetime, timezone

import pytest

from app.utils.recurrence import (
    calculate_next_execution_date,
    increment_next_execution_date,
)


class TestCalculateCronNextExecution:
    """Tests for cron pattern next_execution_date calculation (Story 11.8, AC6)."""

    def test_cron_weekdays_2am(self):
        """Test "0 2 * * 1-5" - weekdays at 2am (AC6 example 1)."""
        # Monday 2026-02-02 at 15:00 UTC -> Tuesday 2026-02-03 at 02:00 UTC
        reference = datetime(2026, 2, 2, 15, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 2 * * 1-5"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 3, 2, 0, tzinfo=timezone.utc)

    def test_cron_first_of_month(self):
        """Test "0 0 1 * *" - first of each month at midnight (AC6 example 2)."""
        # 2026-02-15 at 10:00 UTC -> 2026-03-01 at 00:00 UTC
        reference = datetime(2026, 2, 15, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 0 1 * *"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)

    def test_cron_every_15_minutes(self):
        """Test "*/15 * * * *" - every 15 minutes (AC6 example 3)."""
        # 2026-02-02 at 14:08 UTC -> 2026-02-02 at 14:15 UTC
        reference = datetime(2026, 2, 2, 14, 8, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "*/15 * * * *"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 2, 14, 15, tzinfo=timezone.utc)

    def test_cron_complex_expression_twice_daily_weekdays(self):
        """Test "0 9,17 * * 1-5" - weekdays at 9h and 17h."""
        # Monday 2026-02-02 at 10:00 UTC -> Monday 2026-02-02 at 17:00 UTC (same day)
        reference = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 9,17 * * 1-5"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 2, 17, 0, tzinfo=timezone.utc)

    def test_cron_mondays_at_14h(self):
        """Test "0 14 * * 1" - every Monday at 14:00."""
        # Wednesday 2026-02-04 at 10:00 UTC -> Monday 2026-02-09 at 14:00 UTC
        reference = datetime(2026, 2, 4, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 14 * * 1"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 9, 14, 0, tzinfo=timezone.utc)

    def test_cron_fridays_at_18h(self):
        """Test "0 18 * * 5" - every Friday at 18:00."""
        # Monday 2026-02-02 at 10:00 UTC -> Friday 2026-02-06 at 18:00 UTC
        reference = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 18 * * 5"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 6, 18, 0, tzinfo=timezone.utc)

    def test_cron_every_day_at_2am(self):
        """Test "0 2 * * *" - every day at 2:00."""
        # 2026-02-02 at 03:00 UTC -> 2026-02-03 at 02:00 UTC (tomorrow)
        reference = datetime(2026, 2, 2, 3, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 2 * * *"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 3, 2, 0, tzinfo=timezone.utc)

    def test_cron_before_time_same_day(self):
        """Test cron when reference time is before today's scheduled time."""
        # 2026-02-02 at 01:00 UTC -> 2026-02-02 at 02:00 UTC (same day)
        reference = datetime(2026, 2, 2, 1, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 2 * * *"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 2, 2, 0, tzinfo=timezone.utc)

    def test_cron_saturday_skips_to_monday_for_weekdays(self):
        """Test weekday cron on Saturday skips to Monday."""
        # Saturday 2026-02-07 at 10:00 UTC -> Monday 2026-02-09 at 02:00 UTC
        reference = datetime(2026, 2, 7, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 2 * * 1-5"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 9, 2, 0, tzinfo=timezone.utc)

    def test_cron_end_of_month_rolls_to_next(self):
        """Test cron at end of month rolls to next month's first day."""
        # 2026-01-31 at 23:00 UTC with "0 0 1 * *" -> 2026-02-01 at 00:00 UTC
        reference = datetime(2026, 1, 31, 23, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "0 0 1 * *"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        assert result == datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)


class TestCronValidation:
    """Tests for cron expression validation (Story 11.8, AC5)."""

    def test_invalid_cron_raises_error(self):
        """Test "99 99 * * *" raises ValueError (AC5 example)."""
        reference = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "99 99 * * *"}

        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date("cron", pattern_config, reference)

        assert "Expression cron invalide" in str(exc_info.value)

    def test_invalid_cron_format_raises_error(self):
        """Test invalid format "invalid cron" raises ValueError."""
        reference = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "invalid cron"}

        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date("cron", pattern_config, reference)

        assert "Expression cron invalide" in str(exc_info.value)

    def test_cron_missing_expression_raises_error(self):
        """Test missing cron_expression raises ValueError."""
        reference = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)
        pattern_config = {}  # Missing cron_expression

        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date("cron", pattern_config, reference)

        assert "cron_expression requis" in str(exc_info.value)

    def test_cron_empty_expression_raises_error(self):
        """Test empty cron_expression raises ValueError."""
        reference = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": ""}

        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date("cron", pattern_config, reference)

        # Empty string is treated as missing
        assert "cron_expression requis" in str(exc_info.value)

    def test_cron_whitespace_only_raises_error(self):
        """Test whitespace-only cron_expression raises ValueError."""
        reference = datetime(2026, 2, 2, 10, 0, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "   "}

        with pytest.raises(ValueError) as exc_info:
            calculate_next_execution_date("cron", pattern_config, reference)

        assert "Expression cron invalide" in str(exc_info.value)


class TestCronIncrement:
    """Tests for increment_next_execution_date with cron patterns."""

    def test_increment_cron_calculates_next_from_current(self):
        """Test increment for cron uses croniter to get next occurrence."""
        current = datetime(2026, 2, 2, 2, 0, tzinfo=timezone.utc)  # Monday at 2am
        pattern_config = {"cron_expression": "0 2 * * 1-5"}  # Weekdays at 2am

        result = increment_next_execution_date("cron", pattern_config, current)

        # Next weekday at 2am after Monday is Tuesday
        assert result == datetime(2026, 2, 3, 2, 0, tzinfo=timezone.utc)

    def test_increment_cron_every_15_minutes(self):
        """Test increment for */15 minutes pattern."""
        current = datetime(2026, 2, 2, 14, 15, tzinfo=timezone.utc)
        pattern_config = {"cron_expression": "*/15 * * * *"}

        result = increment_next_execution_date("cron", pattern_config, current)

        assert result == datetime(2026, 2, 2, 14, 30, tzinfo=timezone.utc)

    def test_increment_cron_friday_to_monday(self):
        """Test increment from Friday skips weekend for weekday pattern."""
        current = datetime(2026, 2, 6, 2, 0, tzinfo=timezone.utc)  # Friday at 2am
        pattern_config = {"cron_expression": "0 2 * * 1-5"}  # Weekdays at 2am

        result = increment_next_execution_date("cron", pattern_config, current)

        # Next weekday at 2am after Friday is Monday
        assert result == datetime(2026, 2, 9, 2, 0, tzinfo=timezone.utc)


class TestCronTimezoneHandling:
    """Tests for timezone handling in cron calculations."""

    def test_cron_naive_datetime_converted_to_utc(self):
        """Test naive reference datetime is converted to UTC."""
        # Naive datetime should be treated as UTC
        reference = datetime(2026, 2, 2, 1, 0)  # No timezone
        pattern_config = {"cron_expression": "0 2 * * *"}

        result = calculate_next_execution_date("cron", pattern_config, reference)

        # Result should have UTC timezone
        assert result.tzinfo == timezone.utc
        assert result == datetime(2026, 2, 2, 2, 0, tzinfo=timezone.utc)

    def test_cron_uses_now_utc_when_no_reference(self):
        """Test cron uses current UTC time when no reference provided."""
        pattern_config = {"cron_expression": "0 2 * * *"}

        result = calculate_next_execution_date("cron", pattern_config)

        # Result should be in the future and have UTC timezone
        assert result > datetime.now(timezone.utc)
        assert result.tzinfo == timezone.utc
