"""Tests for datetime/timezone serialization (Story 22.15 — MED-1 fix).

Verifies that all serialized datetimes include explicit UTC timezone
(``Z`` suffix) and that the ``ensure_utc_isoformat`` helper correctly
handles aware, naive, and ``None`` datetimes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from core.utils import ensure_utc_isoformat
from executions.serializers import (
    ExecutionSerializer,
    ExecutionStepSerializer,
    RecurringPatternSerializer,
    ScheduledExecutionSerializer,
    ScheduledExecutionListItemSerializer,
)


# ---------------------------------------------------------------------------
# Tests for ensure_utc_isoformat helper
# ---------------------------------------------------------------------------

class TestEnsureUtcIsoformat:
    """Unit tests for ``core.utils.ensure_utc_isoformat``."""

    def test_none_returns_none(self):
        assert ensure_utc_isoformat(None) is None

    def test_aware_utc_datetime(self):
        dt = datetime(2026, 2, 9, 14, 30, 0, tzinfo=dt_timezone.utc)
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00Z"

    def test_naive_datetime_assumed_utc(self):
        dt = datetime(2026, 2, 9, 14, 30, 0)
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00Z"

    def test_aware_non_utc_datetime_converted(self):
        # CET = UTC+1
        cet = dt_timezone(timedelta(hours=1))
        dt = datetime(2026, 2, 9, 15, 30, 0, tzinfo=cet)
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00Z"

    def test_result_ends_with_z(self):
        dt = timezone.now()
        result = ensure_utc_isoformat(dt)
        assert result.endswith("Z"), f"Expected Z suffix, got: {result}"

    def test_no_plus_zero_offset(self):
        dt = timezone.now()
        result = ensure_utc_isoformat(dt)
        assert "+00:00" not in result, f"Should use Z, not +00:00: {result}"

    def test_microseconds_preserved(self):
        dt = datetime(2026, 2, 9, 14, 30, 0, 123456, tzinfo=dt_timezone.utc)
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00.123456Z"


# ---------------------------------------------------------------------------
# Tests for ExecutionSerializer timezone handling
# ---------------------------------------------------------------------------

def _make_execution_mock(**overrides):
    """Create a mock Execution with default datetime fields."""
    now = timezone.now()
    obj = MagicMock()
    obj.id = 1
    obj.action_id = 10
    obj.user_id = 5
    obj.environment = "production"
    obj.status = "COMPLETED"
    obj.servicenow_change_id = None
    obj.started_at = overrides.get("started_at", now)
    obj.completed_at = overrides.get("completed_at", now + timedelta(minutes=5))
    obj.created_at = overrides.get("created_at", now - timedelta(minutes=1))
    obj.approved_by_id = None
    obj.approved_at = overrides.get("approved_at", None)
    obj.approval_comment = None
    obj.parent_execution_id = None
    obj.error_message = None

    action = MagicMock()
    action.name = "Test Action"
    action.engine = "oracle"
    action.platform = "aap"
    action.item_type = "action"
    integration = MagicMock()
    integration.id = 1
    integration.name = "Test Integration"
    integration.icon = None
    action.integration = integration
    obj.action = action

    user = MagicMock()
    user.display_name = "Test User"
    obj.user = user

    return obj


class TestExecutionSerializerTimezone:
    """Verify that ExecutionSerializer datetime fields include timezone."""

    def test_execution_serializer_includes_timezone(self):
        obj = _make_execution_mock()
        serializer = ExecutionSerializer()
        data = serializer.to_representation(obj)

        for field in ("started_at", "completed_at", "created_at"):
            value = data[field]
            assert value is not None, f"{field} should not be None"
            assert value.endswith("Z"), f"{field} should end with Z: {value}"

    def test_execution_serializer_approved_at_timezone(self):
        obj = _make_execution_mock(approved_at=timezone.now())
        serializer = ExecutionSerializer()
        data = serializer.to_representation(obj)

        assert data["approved_at"].endswith("Z"), f"approved_at should end with Z: {data['approved_at']}"

    def test_execution_serializer_none_dates(self):
        obj = _make_execution_mock(started_at=None, completed_at=None, approved_at=None)
        serializer = ExecutionSerializer()
        data = serializer.to_representation(obj)

        assert data["started_at"] is None
        assert data["completed_at"] is None
        assert data["approved_at"] is None


# ---------------------------------------------------------------------------
# Tests for ExecutionStepSerializer timezone handling
# ---------------------------------------------------------------------------

def _make_step_mock(**overrides):
    """Create a mock ExecutionStep."""
    now = timezone.now()
    obj = MagicMock()
    obj.id = 100
    obj.execution_id = 1
    obj.step_order = 1
    obj.step_name = "Step 1"
    obj.step_type = "script"
    obj.status = "COMPLETED"
    obj.started_at = overrides.get("started_at", now)
    obj.completed_at = overrides.get("completed_at", now + timedelta(seconds=30))
    obj.platform_job_id = "job-123"
    obj.error_message = None
    return obj


class TestExecutionStepSerializerTimezone:
    """Verify ExecutionStepSerializer datetime fields."""

    def test_step_serializer_includes_timezone(self):
        obj = _make_step_mock()
        serializer = ExecutionStepSerializer()
        data = serializer.to_representation(obj)

        for field in ("started_at", "completed_at"):
            value = data[field]
            assert value is not None
            assert value.endswith("Z"), f"{field} should end with Z: {value}"


# ---------------------------------------------------------------------------
# Tests for ScheduledExecutionSerializer timezone handling
# ---------------------------------------------------------------------------

def _make_scheduled_mock(**overrides):
    """Create a mock ScheduledExecution."""
    now = timezone.now()
    obj = MagicMock()
    obj.id = 200
    obj.action_id = 10
    obj.environment = "staging"
    obj.status = "PENDING"
    obj.scheduled_at = overrides.get("scheduled_at", now + timedelta(hours=1))
    obj.created_at = overrides.get("created_at", now)
    obj.correlation_id = "corr-123"
    obj.recurringpattern = None

    action = MagicMock()
    action.name = "Scheduled Action"
    obj.action = action

    return obj


class TestScheduledExecutionSerializerTimezone:
    """Verify ScheduledExecutionSerializer datetime fields."""

    def test_scheduled_serializer_includes_timezone(self):
        obj = _make_scheduled_mock()
        serializer = ScheduledExecutionSerializer()
        data = serializer.to_representation(obj)

        for field in ("scheduled_at", "created_at"):
            value = data[field]
            assert value is not None
            assert value.endswith("Z"), f"{field} should end with Z: {value}"


# ---------------------------------------------------------------------------
# Tests for RecurringPatternSerializer timezone handling
# ---------------------------------------------------------------------------

def _make_recurring_mock(**overrides):
    """Create a mock RecurringPattern."""
    now = timezone.now()
    obj = MagicMock()
    obj.pattern_type = "daily"
    obj.next_execution_date = overrides.get("next_execution_date", now + timedelta(days=1))
    obj.is_active = 1
    return obj


class TestRecurringPatternSerializerTimezone:
    """Verify RecurringPatternSerializer datetime fields."""

    def test_recurring_serializer_includes_timezone(self):
        obj = _make_recurring_mock()
        serializer = RecurringPatternSerializer()
        data = serializer.to_representation(obj)

        assert data["next_execution_date"].endswith("Z"), (
            f"next_execution_date should end with Z: {data['next_execution_date']}"
        )


# ---------------------------------------------------------------------------
# Tests for ScheduledExecutionListItemSerializer timezone handling
# ---------------------------------------------------------------------------

def _make_scheduled_list_mock(**overrides):
    """Create a mock for ScheduledExecutionListItemSerializer."""
    now = timezone.now()
    obj = MagicMock()
    obj.id = 300
    obj.action_id = 10
    obj.user_id = 5
    obj.environment = "production"
    obj.scheduled_at = overrides.get("scheduled_at", now + timedelta(hours=2))
    obj.status = "PENDING"
    obj.created_at = overrides.get("created_at", now)
    obj.correlation_id = "corr-456"
    obj.execution_id = None
    obj.recurringpattern = None

    action = MagicMock()
    action.name = "List Action"
    action.engine = "oracle"
    action.platform = "aap"
    obj.action = action

    user = MagicMock()
    user.display_name = "Test User"
    user.username = "testuser"
    obj.user = user

    return obj


class TestScheduledExecutionListItemSerializerTimezone:
    """Verify ScheduledExecutionListItemSerializer datetime fields."""

    def test_list_item_serializer_includes_timezone(self):
        obj = _make_scheduled_list_mock()
        serializer = ScheduledExecutionListItemSerializer()
        data = serializer.to_representation(obj)

        for field in ("scheduled_at", "created_at"):
            value = data[field]
            assert value is not None
            assert value.endswith("Z"), f"{field} should end with Z: {value}"


# ---------------------------------------------------------------------------
# Edge case: naive datetime from stdlib datetime.now() (without tz)
# ---------------------------------------------------------------------------

class TestNaiveDatetimeSafetyNet:
    """Verify that naive datetimes are safely converted to UTC by the helper."""

    def test_naive_datetime_gets_z_suffix(self):
        naive_dt = datetime(2026, 6, 15, 10, 0, 0)
        result = ensure_utc_isoformat(naive_dt)
        assert result.endswith("Z")
        assert "2026-06-15T10:00:00Z" == result

    def test_serializer_handles_naive_datetime_via_helper(self):
        naive_dt = datetime(2026, 6, 15, 10, 0, 0)
        obj = _make_execution_mock(started_at=naive_dt)
        serializer = ExecutionSerializer()
        data = serializer.to_representation(obj)
        assert data["started_at"] == "2026-06-15T10:00:00Z"
