"""
Django project package.
Initializes oracledb in thick mode when ORACLE_CLIENT_LIB is set.
Thick mode is required for TIMESTAMP WITH TIME ZONE (DPY-3022: named time zones
are not supported in thin mode).
Story 20.3: Loads Celery app on Django startup.
"""
import os

# Story 20.3: Import Celery app so that shared_task uses this app
from idp_backend.celery import app as celery_app

__all__ = ('celery_app',)

_oracle_client_initialized = False


def _init_oracle_client_if_needed():
    global _oracle_client_initialized
    if _oracle_client_initialized:
        return
    lib_dir = os.getenv("ORACLE_CLIENT_LIB")
    if lib_dir and os.path.isdir(lib_dir):
        try:
            import oracledb

            oracledb.init_oracle_client(lib_dir=lib_dir)
            _oracle_client_initialized = True
        except Exception as e:
            # Story 17.6: Justified broad catch - Oracle client init can fail in various ways
            import logging
            logging.getLogger(__name__).warning(
                "Oracle thick mode init failed, falling back to thin mode: %s", str(e)
            )


_init_oracle_client_if_needed()
