import os
import threading

from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integrations'

    def ready(self):
        import integrations.signals  # noqa: F401

        # Vault cache warmup at Gunicorn/Django server startup.
        # Runs in a background thread so it doesn't block app startup.
        # Guarded by VAULT_CACHE_WARMUP env var (default: true).
        # Skipped during manage.py commands (migrate, test, etc.) by
        # checking RUN_MAIN (autoreloader) and SERVER_SOFTWARE (gunicorn).
        if self._should_warmup():
            thread = threading.Thread(
                target=self._run_warmup,
                name="vault-cache-warmup",
                daemon=True,
            )
            thread.start()

    @staticmethod
    def _should_warmup() -> bool:
        """Determine whether to run vault cache warmup at startup."""
        enabled = os.getenv("VAULT_CACHE_WARMUP", "true").lower() in ("true", "1")
        if not enabled:
            return False

        # Only run under Gunicorn or Django dev server (autoreloader child process).
        # Avoids running during migrate, test, shell, etc.
        is_gunicorn = "gunicorn" in os.getenv("SERVER_SOFTWARE", "")
        is_dev_server = os.getenv("RUN_MAIN") == "true"
        return is_gunicorn or is_dev_server

    @staticmethod
    def _run_warmup() -> None:
        """Execute vault cache warmup in background thread."""
        import structlog
        logger = structlog.get_logger(__name__)

        try:
            # Small delay to let DB connections settle after fork
            import time
            time.sleep(2)

            from services.vault_service import warmup_vault_cache
            stats = warmup_vault_cache()
            logger.info("vault_cache_warmup_startup_done", **stats)
        except Exception:  # noqa: BLE001 — best-effort warmup must never crash worker
            logger.warning("vault_cache_warmup_startup_error", exc_info=True)
