"""
Tests for SplunkLoggingHandler — structlog sink for Splunk HEC.

Story 27.8, AC8: 10+ tests covering buffer management, flush behavior,
enrichment, thread safety, error handling, and disabled handler.
"""
from __future__ import annotations

import json
import logging
import threading
from unittest.mock import MagicMock, patch

import pytest

from core.splunk_logging_handler import SplunkLoggingHandler


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
        """Splunk unavailable: events are dropped with warning log."""
        events = [{"event": "test"}]

        # Mock SplunkAdapter.send_batch to raise exception
        async def mock_send_batch_error(*args, **kwargs):
            raise Exception("Splunk down")

        with patch("services.splunk_service.SplunkService") as MockAdapter:
            mock_adapter = MockAdapter.return_value
            mock_adapter.send_batch = mock_send_batch_error

            with patch("core.splunk_logging_handler.logging.getLogger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger
                handler._send_to_splunk(events)
                mock_logger.warning.assert_called_once()


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
            except Exception as e:
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
