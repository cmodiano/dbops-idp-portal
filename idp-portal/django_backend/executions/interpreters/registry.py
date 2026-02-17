"""
Registry for output interpreters.

Singleton registry that maps step_type strings to OutputInterpreter instances.
New interpreters can be registered without modifying existing code.
"""
from __future__ import annotations

import threading

import structlog

from executions.interpreters.base import OutputInterpreter

logger = structlog.get_logger(__name__)


class OutputInterpreterRegistry:
    """
    Singleton registry mapping step_type → OutputInterpreter.

    Thread-safe via threading.Lock.
    """

    _instance: OutputInterpreterRegistry | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._interpreters: dict[str, OutputInterpreter] = {}

    @classmethod
    def get_instance(cls) -> OutputInterpreterRegistry:
        """Return the singleton registry instance.

        Thread-safe: All checks performed inside lock to prevent race conditions.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing only)."""
        with cls._lock:
            cls._instance = None

    def register(self, step_type: str, interpreter: OutputInterpreter) -> None:
        """Register an interpreter for a step_type."""
        with self._lock:
            self._interpreters[step_type] = interpreter
            logger.debug(
                "interpreter_registered",
                step_type=step_type,
                interpreter_class=type(interpreter).__name__,
            )

    def get(self, step_type: str) -> OutputInterpreter | None:
        """Get the interpreter for a step_type, or None if not registered."""
        interpreter = self._interpreters.get(step_type)
        if interpreter is None:
            logger.debug(
                "interpreter_not_found",
                step_type=step_type,
                registered_types=list(self._interpreters.keys()),
            )
        return interpreter

    def list_registered(self) -> dict[str, type]:
        """Return a dict of step_type → interpreter class."""
        return {k: type(v) for k, v in self._interpreters.items()}
