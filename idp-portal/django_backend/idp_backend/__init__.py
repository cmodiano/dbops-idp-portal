"""
Django project package.
Initializes oracledb in thick mode when ORACLE_CLIENT_LIB is set.
Thick mode is required for TIMESTAMP WITH TIME ZONE (DPY-3022: named time zones
are not supported in thin mode).
"""
import os

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
        except Exception:
            pass  # Fall back to thin mode


_init_oracle_client_if_needed()
