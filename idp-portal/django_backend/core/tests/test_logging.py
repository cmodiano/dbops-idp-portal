"""
Tests for core/logging.py — configure_structlog, _configure_splunk_handler, get_logger.
Story 39.2 — Tâche 2
"""
from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

import pytest
import structlog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_root_handlers():
    """Remove all handlers from the root logger to avoid test bleed."""
    root = logging.getLogger()
    root.handlers.clear()


# ---------------------------------------------------------------------------
# 2.1  configure_structlog() sans LOG_LEVEL → INFO par défaut, pas d'erreur
# ---------------------------------------------------------------------------
def test_configure_structlog_default_info_level():
    """configure_structlog() without LOG_LEVEL env → log level INFO, no error."""
    _clear_root_handlers()

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop('LOG_LEVEL', None)
        with patch('core.logging._configure_splunk_handler'):
            from core import logging as core_logging
            # Should not raise
            core_logging.configure_structlog()

    assert logging.getLogger().level == logging.INFO

    # Nettoyage structlog
    structlog.reset_defaults()


# ---------------------------------------------------------------------------
# 2.2  configure_structlog() avec LOG_LEVEL=DEBUG → DEBUG appliqué
# ---------------------------------------------------------------------------
def test_configure_structlog_debug_level():
    """configure_structlog() with LOG_LEVEL=DEBUG → root logger level DEBUG."""
    _clear_root_handlers()

    with patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'}):
        with patch('core.logging._configure_splunk_handler'):
            from core import logging as core_logging
            core_logging.configure_structlog()

    assert logging.getLogger().level == logging.DEBUG

    structlog.reset_defaults()


# ---------------------------------------------------------------------------
# 2.3  _configure_splunk_handler() avec handler.enabled=False → non ajouté
# ---------------------------------------------------------------------------
def test_configure_splunk_handler_disabled():
    """_configure_splunk_handler() with enabled=False → handler NOT added."""
    _clear_root_handlers()

    # SplunkLoggingHandler est importé localement dans _configure_splunk_handler
    with patch('core.splunk_logging_handler.SplunkLoggingHandler') as MockHandler:
        mock_handler = MagicMock()
        mock_handler.enabled = False
        MockHandler.return_value = mock_handler

        from core.logging import _configure_splunk_handler

        handlers_before = len(logging.getLogger().handlers)
        _configure_splunk_handler(logging.INFO)
        handlers_after = len(logging.getLogger().handlers)

    assert handlers_after == handlers_before


# ---------------------------------------------------------------------------
# 2.4  _configure_splunk_handler() avec handler.enabled=True → ajouté
# ---------------------------------------------------------------------------
def test_configure_splunk_handler_enabled():
    """_configure_splunk_handler() with enabled=True → handler added to root logger."""
    _clear_root_handlers()
    root = logging.getLogger()

    try:
        with patch('core.splunk_logging_handler.SplunkLoggingHandler') as MockHandler:
            mock_handler = MagicMock()
            mock_handler.enabled = True
            MockHandler.return_value = mock_handler

            from core.logging import _configure_splunk_handler

            handlers_before = len(root.handlers)
            _configure_splunk_handler(logging.INFO)
            handlers_after = len(root.handlers)

        assert handlers_after == handlers_before + 1
    finally:
        # Nettoyage garanti même si l'assertion échoue
        _clear_root_handlers()


# ---------------------------------------------------------------------------
# 2.5  get_logger(name) → retourne un BoundLogger structlog
# ---------------------------------------------------------------------------
def test_get_logger_returns_bound_logger():
    """get_logger(name) → returns a structlog BoundLogger instance."""
    from core.logging import get_logger

    lg = get_logger('test.module')
    assert lg is not None
    # Vérifie que c'est bien un BoundLogger structlog (ou proxy BoundLoggerBase)
    assert isinstance(lg, (structlog.stdlib.BoundLogger, structlog.BoundLoggerBase))
    assert hasattr(lg, 'info')
    assert hasattr(lg, 'warning')
    assert hasattr(lg, 'error')
