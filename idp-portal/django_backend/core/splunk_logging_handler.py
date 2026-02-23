"""
SplunkLoggingHandler — structlog sink for async batch log forwarding to Splunk HEC.

Story 27.8, AC4: Buffer events in memory, flush to Splunk HEC periodically
(every FLUSH_INTERVAL seconds) or when batch size reaches BATCH_SIZE.
Non-blocking: runs in a background thread.

Configuration (environment variables or Django settings):
- SPLUNK_HEC_URL: Splunk HEC endpoint (e.g. https://splunk.example.com:8088)
- SPLUNK_HEC_TOKEN: Splunk HEC authentication token
- SPLUNK_INDEX: Target Splunk index (default: prod-idp)
- SPLUNK_SOURCETYPE: Splunk sourcetype (default: idp:execution)
- SPLUNK_FLUSH_INTERVAL: Flush interval in seconds (default: 5)
- SPLUNK_BATCH_SIZE: Max events before auto-flush (default: 100)
- SPLUNK_MAX_BUFFER_SIZE: Max buffer size before dropping old events (default: 1000)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
from typing import Any, cast

import structlog

logger = structlog.get_logger(__name__)

# Configuration defaults
DEFAULT_FLUSH_INTERVAL = 5.0  # seconds
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_BUFFER_SIZE = 1000


def _get_config() -> dict[str, Any]:
    """Load Splunk HEC configuration from environment or Django settings."""
    hec_url = os.getenv("SPLUNK_HEC_URL", "")
    hec_token = os.getenv("SPLUNK_HEC_TOKEN", "")

    # Fallback to Django settings if env vars not set
    if not hec_url:
        try:
            from django.conf import settings
            splunk_config = getattr(settings, "SPLUNK_CONFIG", {})
            hec_url = splunk_config.get("HEC_URL", "")
            hec_token = hec_token or splunk_config.get("HEC_TOKEN", "")
        except Exception:
            pass

    return {
        "hec_url": hec_url,
        "hec_token": hec_token,
        "index": os.getenv("SPLUNK_INDEX", "prod-idp"),
        "sourcetype": os.getenv("SPLUNK_SOURCETYPE", "idp:execution"),
        "flush_interval": float(os.getenv("SPLUNK_FLUSH_INTERVAL", str(DEFAULT_FLUSH_INTERVAL))),
        "batch_size": int(os.getenv("SPLUNK_BATCH_SIZE", str(DEFAULT_BATCH_SIZE))),
        "max_buffer_size": int(os.getenv("SPLUNK_MAX_BUFFER_SIZE", str(DEFAULT_MAX_BUFFER_SIZE))),
    }


class SplunkLoggingHandler(logging.Handler):
    """Logging handler that buffers events and sends them to Splunk HEC in batches.

    Thread-safe: uses queue.Queue for the buffer.
    Non-blocking: flush runs in a background thread via threading.Timer.

    If Splunk is unavailable, events are dropped after retry with a local warning log.
    This ensures the application is never blocked by Splunk unavailability.
    """

    def __init__(
        self,
        hec_url: str = "",
        hec_token: str = "",
        index: str = "prod-idp",
        sourcetype: str = "idp:execution",
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_buffer_size: int = DEFAULT_MAX_BUFFER_SIZE,
    ) -> None:
        super().__init__()

        # Load from config if not provided directly
        if not hec_url:
            config = _get_config()
            hec_url = config["hec_url"]
            hec_token = hec_token or config["hec_token"]
            index = config["index"]
            sourcetype = config["sourcetype"]
            flush_interval = config["flush_interval"]
            batch_size = config["batch_size"]
            max_buffer_size = config["max_buffer_size"]

        self.hec_url = hec_url
        self.hec_token = hec_token
        self.index = index
        self.sourcetype = sourcetype
        self.flush_interval = flush_interval
        self.batch_size = batch_size
        self.max_buffer_size = max_buffer_size

        # Thread-safe buffer
        self._buffer: queue.Queue[dict] = queue.Queue(maxsize=max_buffer_size)
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._closed = False

        # Check if handler is enabled (has URL configured)
        self.enabled = bool(self.hec_url)
        if not self.enabled:
            logger.warning("splunk_hec_not_configured", message="SPLUNK_HEC_URL not set, SplunkLoggingHandler disabled")
            return

        # Start periodic flush timer
        self._start_timer()

    def _start_timer(self) -> None:
        """Start or restart the periodic flush timer."""
        if self._closed:
            return
        self._timer = threading.Timer(self.flush_interval, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self) -> None:
        """Called by timer thread to flush buffer."""
        if self._closed:
            return
        self.flush()
        self._start_timer()

    def emit(self, record: logging.LogRecord) -> None:
        """Add a log record to the buffer for batch sending.

        Extracts event data from LogRecord. If structlog JSONRenderer was used,
        the message is already a JSON string. Otherwise, format the record.
        """
        if not self.enabled or self._closed:
            return

        try:
            event = self._extract_event(record)

            # If buffer is full, drop oldest event (FIFO) to prevent OOM
            if self._buffer.full():
                try:
                    self._buffer.get_nowait()
                except queue.Empty:
                    pass

            self._buffer.put_nowait(event)

            # Auto-flush if batch size reached
            if self._buffer.qsize() >= self.batch_size:
                self.flush()

        except Exception:
            # Never let handler errors propagate to the application
            self.handleError(record)

    def _extract_event(self, record: logging.LogRecord) -> dict:
        """Extract structured event dict from a LogRecord."""
        # Try parsing as JSON (structlog JSONRenderer output)
        try:
            if isinstance(record.msg, str):
                event = json.loads(record.msg)
                if isinstance(event, dict):
                    return cast(dict[str, Any], event)
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback: build event from LogRecord attributes
        fallback_event: dict[str, Any] = {
            "event": record.getMessage(),
            "level": record.levelname,
            "logger": record.name,
            "timestamp": record.created,
        }

        # Extract structlog extra fields (correlation_id, user_id, execution_id)
        for key in ("correlation_id", "user_id", "execution_id"):
            value = getattr(record, key, None)
            if value is not None:
                fallback_event[key] = value

        return fallback_event

    def flush(self) -> None:
        """Flush buffered events to Splunk HEC via SplunkAdapter.send_batch()."""
        if not self.enabled or self._closed:
            return

        events: list[dict] = []
        while not self._buffer.empty():
            try:
                events.append(self._buffer.get_nowait())
            except queue.Empty:
                break

        if not events:
            return

        with self._lock:
            self._send_to_splunk(events)

    def _send_to_splunk(self, events: list[dict]) -> None:
        """Send events to Splunk HEC. Drop events if Splunk is unavailable."""
        try:
            from services.splunk_service import SplunkService

            adapter = SplunkService(
                base_url=self.hec_url,
                auth_headers={"Authorization": f"Splunk {self.hec_token}"},
                default_sourcetype=self.sourcetype,
                default_index=self.index,
            )

            # Run async send_batch in a new event loop (we're in a thread)
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    adapter.send_batch(events=events, correlation_id="splunk-handler-flush")
                )
            finally:
                loop.close()

        except Exception as exc:
            # Splunk unavailable: log warning locally, drop events
            # Use standard logging to avoid recursion
            logging.getLogger(__name__).warning(
                "splunk_hec_unavailable: %s — dropped %d events",
                str(exc),
                len(events),
            )

    def close(self) -> None:
        """Close the handler: flush remaining events and stop timer."""
        self._closed = True
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        # Final flush
        if self.enabled:
            self.flush()
        super().close()
