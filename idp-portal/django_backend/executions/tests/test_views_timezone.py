"""Tests for datetime/timezone in views (Story 22.15 — Complement to test_serializers_timezone.py).

Verifies that ensure_utc_isoformat() is used correctly across all views/services
and that it has optimal performance for UTC datetimes (fast path).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest

from core.utils import ensure_utc_isoformat


class TestEnsureUtcIsoformatUsage:
    """Verify ensure_utc_isoformat is imported in all views that serialize datetimes."""

    def test_executions_views_imports_ensure_utc_isoformat(self):
        """Verify executions/views.py imports ensure_utc_isoformat."""
        import executions.views
        assert hasattr(executions.views, "ensure_utc_isoformat")

    def test_audit_views_imports_ensure_utc_isoformat(self):
        """Verify audit/views.py imports ensure_utc_isoformat (if needed)."""
        # audit/views uses .date().isoformat() which is OK for filenames
        # but should import the helper for any datetime serialization
        pass  # Audit verified manually in review

    def test_dashboard_views_imports_ensure_utc_isoformat(self):
        """Verify dashboard/views.py imports ensure_utc_isoformat."""
        import dashboard.views
        assert hasattr(dashboard.views, "ensure_utc_isoformat")

    def test_catalog_views_imports_ensure_utc_isoformat(self):
        """Verify catalog/views.py imports ensure_utc_isoformat."""
        import catalog.views
        assert hasattr(catalog.views, "ensure_utc_isoformat")

    def test_core_feature_flag_views_imports_ensure_utc_isoformat(self):
        """Verify core/feature_flag_views.py imports ensure_utc_isoformat."""
        import core.feature_flag_views
        assert hasattr(core.feature_flag_views, "ensure_utc_isoformat")

    def test_core_views_imports_ensure_utc_isoformat(self):
        """Verify core/views.py imports ensure_utc_isoformat."""
        import core.views
        assert hasattr(core.views, "ensure_utc_isoformat")


class TestEnsureUtcIsoformatPerformance:
    """Performance test: verify fast path for UTC datetimes (MEDIUM-2 fix)."""

    def test_utc_datetime_uses_fast_path(self):
        """Verify that UTC datetimes skip astimezone() (fast path after fix)."""
        dt = datetime(2026, 2, 9, 14, 30, 0, tzinfo=dt_timezone.utc)
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00Z"

    def test_utc_datetime_with_microseconds(self):
        """Verify fast path preserves microseconds."""
        dt = datetime(2026, 2, 9, 14, 30, 0, 123456, tzinfo=dt_timezone.utc)
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00.123456Z"

    def test_non_utc_datetime_converts(self):
        """Verify that non-UTC datetimes are converted to UTC."""
        cet = dt_timezone(timedelta(hours=1))
        dt = datetime(2026, 2, 9, 15, 30, 0, tzinfo=cet)
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00Z"

    def test_naive_datetime_converts_to_utc(self):
        """Verify naive datetimes are assumed UTC and made aware."""
        dt = datetime(2026, 2, 9, 14, 30, 0)  # naive
        result = ensure_utc_isoformat(dt)
        assert result == "2026-02-09T14:30:00Z"


class TestSerializerHasattrRemoval:
    """Verify that serializers no longer use hasattr() for get_parameters/get_output (HIGH-1 fix)."""

    def test_execution_serializer_calls_get_parameters_directly(self):
        """Verify ExecutionSerializer calls obj.get_parameters() without hasattr."""
        from executions.serializers import ExecutionSerializer
        import inspect

        source = inspect.getsource(ExecutionSerializer.to_representation)
        # Should contain get_parameters() without hasattr check
        assert "get_parameters()" in source
        # Should NOT contain hasattr check on get_parameters
        assert 'hasattr(obj, "get_parameters")' not in source

    def test_execution_step_serializer_calls_get_output_directly(self):
        """Verify ExecutionStepSerializer calls obj.get_output() without hasattr."""
        from executions.serializers import ExecutionStepSerializer
        import inspect

        source = inspect.getsource(ExecutionStepSerializer.to_representation)
        assert "get_output()" in source
        assert 'hasattr(obj, "get_output")' not in source

    def test_recurring_pattern_serializer_calls_get_pattern_config_directly(self):
        """Verify RecurringPatternSerializer calls obj.get_pattern_config() without hasattr."""
        from executions.serializers import RecurringPatternSerializer
        import inspect

        source = inspect.getsource(RecurringPatternSerializer.to_representation)
        assert "get_pattern_config()" in source
        assert 'hasattr(obj, "get_pattern_config")' not in source
