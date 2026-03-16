"""
Tests for core.tasks.flush_splunk_logging_handler — Story 86.9, AC#9.
"""
from __future__ import annotations

import logging as _logging
from unittest.mock import MagicMock, patch


from core.tasks import flush_splunk_logging_handler


class TestFlushSplunkLoggingHandlerTask:
    """Story 86.9 AC#5/#9: Celery task flush_splunk_logging_handler."""

    def test_flush_task_calls_flush_on_handlers(self) -> None:
        """AC#9: task finds handler in root.handlers and calls flush()."""
        from core.splunk_logging_handler import SplunkLoggingHandler

        mock_handler = MagicMock(spec=SplunkLoggingHandler)
        mock_handler.enabled = True
        mock_handler._closed = False
        mock_handler.level = _logging.NOTSET  # needed by Python logging callHandlers
        mock_buffer = MagicMock()
        mock_buffer.qsize.return_value = 0
        mock_handler._buffer = mock_buffer
        mock_handler.dropped_count = 0

        with patch.object(_logging.root, "handlers", [mock_handler]):
            with patch.object(_logging.Logger.manager, "loggerDict", {}):
                result = flush_splunk_logging_handler()

        mock_handler.flush.assert_called_once()
        assert result["handlers_flushed"] == 1

    def test_flush_task_no_handlers_returns_zeros(self) -> None:
        """AC#9: no handlers → returns dict with all zeros."""
        with patch.object(_logging.root, "handlers", []):
            with patch.object(_logging.Logger.manager, "loggerDict", {}):
                result = flush_splunk_logging_handler()

        assert result == {"handlers_flushed": 0, "buffer_qsize": 0, "dropped_count": 0}

    def test_flush_task_does_not_raise_on_handler_error(self) -> None:
        """AC#9: handler.flush() raises → task does not raise, returns gracefully."""
        from core.splunk_logging_handler import SplunkLoggingHandler

        mock_handler = MagicMock(spec=SplunkLoggingHandler)
        mock_handler.enabled = True
        mock_handler._closed = False
        mock_handler.level = _logging.NOTSET  # needed by Python logging callHandlers
        mock_handler.flush.side_effect = RuntimeError("flush failed")

        with patch.object(_logging.root, "handlers", [mock_handler]):
            with patch.object(_logging.Logger.manager, "loggerDict", {}):
                # Must not raise
                result = flush_splunk_logging_handler()

        assert result["handlers_flushed"] == 0

    def test_flush_task_skips_disabled_handler(self) -> None:
        """Task skips handlers where enabled=False."""
        from core.splunk_logging_handler import SplunkLoggingHandler

        mock_handler = MagicMock(spec=SplunkLoggingHandler)
        mock_handler.enabled = False
        mock_handler._closed = False
        mock_handler.level = _logging.NOTSET  # needed by Python logging callHandlers

        with patch.object(_logging.root, "handlers", [mock_handler]):
            with patch.object(_logging.Logger.manager, "loggerDict", {}):
                result = flush_splunk_logging_handler()

        mock_handler.flush.assert_not_called()
        assert result["handlers_flushed"] == 0
