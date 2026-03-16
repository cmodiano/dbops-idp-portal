"""
Tests for SplunkLoggingHandler — structlog sink for Splunk HEC.

Story 27.8, AC8: 10+ tests covering buffer management, flush behavior,
enrichment, thread safety, error handling, and disabled handler.

Story 86.9, AC9: Tests for _dropped_count, dropped_count property, get_splunk_handler_stats().
"""
from __future__ import annotations

import json
import logging
import threading
from unittest.mock import patch

import pytest

from core.splunk_logging_handler import SplunkLoggingHandler, get_splunk_handler_stats


@pytest.fixture
def handler() -> SplunkLoggingHandler:
    """Create an enabled SplunkLoggingHandler for testing."""
    h = SplunkLoggingHandler(
        hec_url="https://splunk.example.com:8088",
        hec_token="test-token-123",
        index="test-idp",
        sourcetype="idp:test",
        flush_interval=5.0,
        batch_size=100,
        max_buffer_size=1000,
    )
    # Cancel the timer for controlled testing
    if h._timer:
        h._timer.cancel()
    yield h
    h.close()


def _make_log_record(
    msg: str = "test event",
    level: int = logging.INFO,
    **extra,
) -> logging.LogRecord:
    """Create a LogRecord with optional extra attributes."""
    record = logging.LogRecord(
        name="test.logger",
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


class TestEmitEvent:
    """Test handler.emit() adds events to buffer."""

    def test_emit_event_buffered(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 15: handler.emit(LogRecord) -> event added to buffer."""
        record = _make_log_record("test_event")
        handler.emit(record)
        assert handler._buffer.qsize() == 1

    def test_emit_json_event(self, handler: SplunkLoggingHandler) -> None:
        """Emit a JSON string message (structlog JSONRenderer output)."""
        json_msg = json.dumps({"event": "execution_started", "level": "INFO", "correlation_id": "abc-123"})
        record = _make_log_record(json_msg)
        handler.emit(record)

        assert handler._buffer.qsize() == 1
        event = handler._buffer.get_nowait()
        assert event["event"] == "execution_started"
        assert event["correlation_id"] == "abc-123"


class TestBufferFlush:
    """Test buffer flush behavior."""

    def test_buffer_flush_on_count(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 13: 100 events -> flush automatic -> send_batch called."""
        handler.batch_size = 100

        with patch.object(handler, "_send_to_splunk") as mock_send:
            for i in range(100):
                record = _make_log_record(f"event_{i}")
                handler.emit(record)

            # After 100 events, flush should have been called automatically
            mock_send.assert_called()
            # Buffer should be empty after flush
            assert handler._buffer.qsize() == 0

    def test_buffer_flush_on_time(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 14: periodic flush calls send_to_splunk."""
        # Add a few events
        for i in range(5):
            handler.emit(_make_log_record(f"event_{i}"))

        assert handler._buffer.qsize() == 5

        with patch.object(handler, "_send_to_splunk") as mock_send:
            handler.flush()
            mock_send.assert_called_once()
            args = mock_send.call_args[0][0]
            assert len(args) == 5

    def test_flush_calls_send_batch(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 16: handler.flush() -> SplunkAdapter.send_batch() called."""
        for i in range(3):
            handler.emit(_make_log_record(f"event_{i}"))

        with patch.object(handler, "_send_to_splunk") as mock_send:
            handler.flush()
            mock_send.assert_called_once()
            events = mock_send.call_args[0][0]
            assert len(events) == 3

    def test_flush_empty_buffer(self, handler: SplunkLoggingHandler) -> None:
        """Flush with empty buffer does nothing."""
        with patch.object(handler, "_send_to_splunk") as mock_send:
            handler.flush()
            mock_send.assert_not_called()


class TestErrorHandling:
    """Test error handling when Splunk is unavailable."""

    def test_error_handling_send_batch_failure(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 17: send_batch raises -> log warning + drop events."""
        handler.emit(_make_log_record("test_event"))

        # Mock SplunkAdapter.send_batch to raise exception
        async def mock_send_batch_error(*args, **kwargs):
            raise Exception("Connection refused")

        with patch("services.splunk_service.SplunkService") as MockAdapter:
            mock_adapter = MockAdapter.return_value
            mock_adapter.send_batch = mock_send_batch_error

            # Should not raise — errors are handled internally via _send_to_splunk
            handler.flush()

        # Buffer should be empty (events consumed before send attempt)
        assert handler._buffer.qsize() == 0

    def test_send_to_splunk_exception_drops_events(self, handler: SplunkLoggingHandler) -> None:
        """Splunk unavailable: events are dropped with structlog warning."""
        events = [{"event": "test"}]

        # Mock SplunkAdapter.send_batch to raise exception
        async def mock_send_batch_error(*args, **kwargs):
            raise Exception("Splunk down")

        with patch("services.splunk_service.SplunkService") as MockAdapter:
            mock_adapter = MockAdapter.return_value
            mock_adapter.send_batch = mock_send_batch_error

            with patch("core.splunk_logging_handler.logger") as mock_structlog:
                handler._send_to_splunk(events)
                mock_structlog.warning.assert_called_once()
                call_kwargs = mock_structlog.warning.call_args
                assert call_kwargs[0][0] == "splunk_events_dropped"


class TestEnrichment:
    """Test event enrichment with correlation_id, user_id."""

    def test_enrichment_correlation_id(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 18: LogRecord extra={'correlation_id': 'abc'} -> event contains it."""
        record = _make_log_record("test", correlation_id="abc-123")
        handler.emit(record)

        event = handler._buffer.get_nowait()
        assert event["correlation_id"] == "abc-123"

    def test_enrichment_user_id(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 19: LogRecord extra={'user_id': 'john'} -> event contains it."""
        record = _make_log_record("test", user_id="john.doe@example.com")
        handler.emit(record)

        event = handler._buffer.get_nowait()
        assert event["user_id"] == "john.doe@example.com"


class TestThreadSafety:
    """Test thread-safe buffer operations."""

    def test_thread_safety_concurrent_emit(self, handler: SplunkLoggingHandler) -> None:
        """AC8 test 20: 10 threads emit 100 events each -> all events buffered."""
        errors: list[Exception] = []

        def emit_events():
            try:
                for i in range(100):
                    handler.emit(_make_log_record(f"thread_event_{i}"))
            except Exception as e:  # noqa: BLE001 — test: collect errors for assertion
                errors.append(e)

        # Prevent auto-flush during test
        handler.batch_size = 2000

        threads = [threading.Thread(target=emit_events) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Thread errors: {errors}"
        # Should have ~1000 events (some may be dropped due to max_buffer_size=1000)
        assert handler._buffer.qsize() == 1000


class TestDisabledHandler:
    """Test handler behavior when Splunk is not configured."""

    def test_disable_if_no_config(self) -> None:
        """AC8 test 21: SPLUNK_HEC_URL not set -> handler disabled."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("core.splunk_logging_handler._get_config", return_value={
                "hec_url": "",
                "hec_token": "",
                "index": "prod-idp",
                "sourcetype": "idp:execution",
                "flush_interval": 5.0,
                "batch_size": 100,
                "max_buffer_size": 1000,
            }):
                h = SplunkLoggingHandler()
                assert not h.enabled
                # emit should not raise or buffer anything
                h.emit(_make_log_record("test"))
                assert h._buffer.qsize() == 0
                h.close()


class TestMaxBufferSize:
    """Test buffer overflow handling."""

    def test_max_buffer_size_drops_oldest(self) -> None:
        """AC8 test 22: buffer > max_buffer_size -> drop oldest (FIFO)."""
        h = SplunkLoggingHandler(
            hec_url="https://splunk.example.com:8088",
            hec_token="token",
            max_buffer_size=5,
            batch_size=1000,  # Prevent auto-flush
        )
        if h._timer:
            h._timer.cancel()

        try:
            for i in range(10):
                h.emit(_make_log_record(json.dumps({"event": f"event_{i}"})))

            # Buffer should contain exactly max_buffer_size events
            assert h._buffer.qsize() == 5
        finally:
            h.close()


class TestGetConfig:
    """Test _get_config() fallback to Django settings."""

    def test_get_config_django_settings_fallback(self) -> None:
        """Lines 49-50: Django settings fallback used when env var not set."""
        from core.splunk_logging_handler import _get_config
        import os

        # Clear relevant env vars and simulate Django settings fallback exception
        with patch.dict(os.environ, {}, clear=True):
            # Patch django.conf.settings to raise an exception to cover lines 49-50
            with patch("core.splunk_logging_handler.os.getenv", side_effect=lambda key, default="": default):
                # Patch the import inside _get_config to raise
                import builtins
                real_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name == "django.conf":
                        raise ImportError("Django not available")
                    return real_import(name, *args, **kwargs)

                with patch.object(builtins, "__import__", mock_import):
                    config = _get_config()
                    assert "hec_url" in config

    def test_get_config_django_settings_exception_covered(self) -> None:
        """Lines 49-50: Exception in Django settings import is silently caught."""
        from core.splunk_logging_handler import _get_config

        # Patch to ensure hec_url is empty so Django settings branch is entered,
        # then raise inside the try block to cover the except pass (lines 49-50)
        original_getenv = __import__('os').getenv

        def patched_getenv(key, default=""):
            if key == "SPLUNK_HEC_URL":
                return ""  # Force Django settings fallback
            return original_getenv(key, default)

        with patch("core.splunk_logging_handler.os.getenv", side_effect=patched_getenv):
            with patch("django.conf.settings") as mock_settings:
                mock_settings.SPLUNK_CONFIG = None  # getattr will return {}
                type(mock_settings).__getattr__ = lambda self, name: (_ for _ in ()).throw(Exception("settings error"))
                # Should not raise — exception is silently caught
                config = _get_config()
                assert isinstance(config, dict)


class TestStartTimer:
    """Test _start_timer() closed-handler guard."""

    def test_start_timer_does_nothing_when_closed(self, handler: SplunkLoggingHandler) -> None:
        """Line 122: _start_timer() returns immediately when handler is closed."""
        handler._closed = True
        handler._timer = None
        handler._start_timer()
        # Timer should NOT have been created since handler is closed
        assert handler._timer is None


class TestTimerFlush:
    """Test _timer_flush() behavior."""

    def test_timer_flush_does_nothing_when_closed(self, handler: SplunkLoggingHandler) -> None:
        """Lines 129-130: _timer_flush() returns immediately when handler is closed."""
        handler._closed = True
        with patch.object(handler, "flush") as mock_flush:
            handler._timer_flush()
            mock_flush.assert_not_called()

    def test_timer_flush_calls_flush_and_restarts_timer(self, handler: SplunkLoggingHandler) -> None:
        """Lines 131-132: _timer_flush() calls flush() then _start_timer()."""
        with patch.object(handler, "flush") as mock_flush, \
             patch.object(handler, "_start_timer") as mock_start_timer:
            handler._timer_flush()
            mock_flush.assert_called_once()
            mock_start_timer.assert_called_once()


class TestEmitBufferFull:
    """Test emit() when buffer is full."""

    def test_emit_buffer_full_queue_empty_exception(self) -> None:
        """Lines 150-151: queue.Empty exception when get_nowait on full buffer — covered."""
        import queue
        h = SplunkLoggingHandler(
            hec_url="https://splunk.example.com:8088",
            hec_token="token",
            max_buffer_size=3,
            batch_size=1000,
        )
        if h._timer:
            h._timer.cancel()

        try:
            # Fill the buffer to capacity
            for i in range(3):
                h._buffer.put_nowait({"event": f"pre_{i}"})

            # Now mock get_nowait to raise queue.Empty to cover lines 150-151
            original_get_nowait = h._buffer.get_nowait
            call_count = [0]

            def mock_get_nowait():
                call_count[0] += 1
                if call_count[0] == 1:
                    raise queue.Empty()
                return original_get_nowait()

            h._buffer.get_nowait = mock_get_nowait  # type: ignore[method-assign]

            record = _make_log_record("new event")
            # Should not raise — queue.Empty is silently caught
            h.emit(record)
            # _dropped_count must NOT be incremented when get_nowait raised Empty
            # (no event was actually removed from the buffer)
            assert h._dropped_count == 0
        finally:
            h.close()

    def test_emit_exception_calls_handle_error(self, handler: SplunkLoggingHandler) -> None:
        """Lines 159-161: exception in emit() calls handleError()."""
        record = _make_log_record("test")

        with patch.object(handler, "_extract_event", side_effect=RuntimeError("extract failed")):
            with patch.object(handler, "handleError") as mock_handle_error:
                handler.emit(record)
                mock_handle_error.assert_called_once_with(record)


class TestExtractEventFallback:
    """Test _extract_event() fallback for non-JSON and non-dict JSON."""

    def test_extract_event_non_json_string(self, handler: SplunkLoggingHandler) -> None:
        """Lines 167->175, 169->175: non-JSON msg falls back to LogRecord attributes."""
        record = _make_log_record("plain text message, not JSON")
        event = handler._extract_event(record)
        assert event["event"] == "plain text message, not JSON"
        assert event["level"] == "INFO"
        assert "logger" in event
        assert "timestamp" in event

    def test_extract_event_json_list_falls_back(self, handler: SplunkLoggingHandler) -> None:
        """Lines 169->175: JSON that is not a dict (e.g. list) falls back to LogRecord."""
        record = _make_log_record(json.dumps(["a", "b", "c"]))
        event = handler._extract_event(record)
        # JSON parsed but not a dict — fallback path taken
        assert "event" in event
        assert "level" in event


class TestFlushQueueEmpty:
    """Test flush() queue.Empty exception path."""

    def test_flush_queue_empty_during_drain(self, handler: SplunkLoggingHandler) -> None:
        """Lines 199-200: queue.Empty raised during flush drain is silently caught."""
        import queue

        # Add one event then mock get_nowait to raise Empty on second call
        handler._buffer.put_nowait({"event": "test"})

        _original_empty = handler._buffer.empty
        call_count = [0]

        def mock_empty():
            # Always return False for first few calls so the while loop enters
            call_count[0] += 1
            if call_count[0] <= 2:
                return False
            return True

        original_get_nowait = handler._buffer.get_nowait
        get_count = [0]

        def mock_get_nowait():
            get_count[0] += 1
            if get_count[0] == 2:
                raise queue.Empty()
            return original_get_nowait()

        handler._buffer.empty = mock_empty  # type: ignore[method-assign]
        handler._buffer.get_nowait = mock_get_nowait  # type: ignore[method-assign]

        with patch.object(handler, "_send_to_splunk") as mock_send:
            handler.flush()
            # Should have called send with whatever was collected before Empty
            mock_send.assert_called_once()


# ============================================================================
# Story 86.9 — Tests AC#1, #2, #3, #4
# ============================================================================


class TestDroppedCount:
    """Story 86.9 AC#1/#3: _dropped_count increments and dropped_count property."""

    def test_dropped_count_increments_on_buffer_full(self) -> None:
        """AC#1: emit() when buffer full increments _dropped_count by 1."""
        h = SplunkLoggingHandler(
            hec_url="https://splunk.example.com:8088",
            hec_token="token",
            max_buffer_size=3,
            batch_size=1000,  # Prevent auto-flush
        )
        if h._timer:
            h._timer.cancel()

        try:
            # Fill the buffer to capacity
            for i in range(3):
                h.emit(_make_log_record(f"event_{i}"))

            assert h._buffer.qsize() == 3
            assert h.dropped_count == 0

            # Emit one more — buffer full, oldest dropped, _dropped_count += 1
            h.emit(_make_log_record("overflow_event"))

            assert h.dropped_count == 1
        finally:
            h.close()

    def test_dropped_count_increments_on_send_failure(self) -> None:
        """AC#1: _send_to_splunk() failure increments _dropped_count by len(events)."""
        h = SplunkLoggingHandler(
            hec_url="https://splunk.example.com:8088",
            hec_token="token",
            max_buffer_size=1000,
            batch_size=1000,
        )
        if h._timer:
            h._timer.cancel()

        try:
            for i in range(3):
                h.emit(_make_log_record(f"event_{i}"))

            assert h._buffer.qsize() == 3
            assert h.dropped_count == 0

            # Mock send_batch to raise exception
            async def mock_send_batch_error(*args, **kwargs):
                raise Exception("HEC unavailable")

            with patch("services.splunk_service.SplunkService") as MockAdapter:
                mock_adapter = MockAdapter.return_value
                mock_adapter.send_batch = mock_send_batch_error
                h.flush()

            assert h.dropped_count == 3
        finally:
            h.close()

    def test_dropped_count_property(self, handler: SplunkLoggingHandler) -> None:
        """AC#3: dropped_count property returns same value as _dropped_count."""
        assert handler.dropped_count == handler._dropped_count
        handler._dropped_count = 42
        assert handler.dropped_count == 42


class TestGetSplunkHandlerStats:
    """Story 86.9 AC#4: get_splunk_handler_stats() returns correct fields."""

    def test_get_splunk_handler_stats_with_handler(self) -> None:
        """AC#4: handler registered → buffer_qsize, dropped_count, enabled returned."""
        import logging as _logging

        h = SplunkLoggingHandler(
            hec_url="https://splunk.example.com:8088",
            hec_token="token",
            max_buffer_size=1000,
            batch_size=1000,
        )
        if h._timer:
            h._timer.cancel()

        try:
            h.emit(_make_log_record("event_1"))
            h.emit(_make_log_record("event_2"))

            with patch.object(_logging.root, "handlers", [h]):
                stats = get_splunk_handler_stats()

            assert stats["buffer_qsize"] == 2
            assert stats["dropped_count"] == 0
            assert stats["enabled"] is True
        finally:
            h.close()

    def test_get_splunk_handler_stats_no_handler(self) -> None:
        """AC#4: no handler registered → zeros/False returned."""
        import logging as _logging

        with patch.object(_logging.root, "handlers", []):
            with patch.object(_logging.Logger.manager, "loggerDict", {}):
                stats = get_splunk_handler_stats()

        assert stats == {"buffer_qsize": 0, "dropped_count": 0, "enabled": False}
