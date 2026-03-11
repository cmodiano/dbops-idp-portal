import os
import threading

from django.apps import AppConfig


class ExecutionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'executions'

    def ready(self) -> None:
        # Crash recovery: reconcile stale RUNNING executions at startup.
        # Dispatches reconcile_stale_executions to the Celery worker so it runs
        # with proper time limits and doesn't block Gunicorn worker startup.
        # Guarded by RECONCILE_ON_STARTUP env var (default: true).
        # Skipped during manage.py commands (migrate, test, shell, etc.) by
        # checking RUN_MAIN (autoreloader) and SERVER_SOFTWARE (gunicorn).
        if self._should_reconcile():
            thread = threading.Thread(
                target=self._run_reconcile_on_startup,
                name="executions-startup-reconcile",
                daemon=True,
            )
            thread.start()

    @staticmethod
    def _should_reconcile() -> bool:
        """Determine whether to run startup reconciliation."""
        enabled = os.getenv("RECONCILE_ON_STARTUP", "true").lower() in ("true", "1")
        if not enabled:
            return False

        # Only run under Gunicorn or Django dev server (autoreloader child process).
        # Avoids running during migrate, test, shell, collectstatic, etc.
        is_gunicorn = "gunicorn" in os.getenv("SERVER_SOFTWARE", "")
        is_dev_server = os.getenv("RUN_MAIN") == "true"
        return is_gunicorn or is_dev_server

    @staticmethod
    def _run_reconcile_on_startup() -> None:
        """Dispatch reconcile_stale_executions to the Celery worker at startup."""
        import structlog
        logger = structlog.get_logger(__name__)

        try:
            # Small delay to let DB connections and Celery broker settle after fork
            import time
            time.sleep(3)

            from executions.tasks.reconcile import reconcile_stale_executions
            reconcile_stale_executions.delay()
            logger.info("executions_startup_reconcile_dispatched")
        except Exception:  # noqa: BLE001 — best-effort: must never crash the worker
            logger.warning("executions_startup_reconcile_dispatch_error", exc_info=True)
