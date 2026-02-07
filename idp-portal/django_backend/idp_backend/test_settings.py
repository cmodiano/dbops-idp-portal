"""
Test settings for Django backend.
Uses SQLite for fast, Oracle-independent test execution.

Story 15.2: Security functional tests require reliable test DB.
"""

from idp_backend.settings import *  # noqa: F401,F403

# Override database to SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Ensure auth dev bypass is disabled by default in tests
AUTH_DEV_BYPASS = False

# Story 17.5: Provide test-safe secret values (settings.py no longer has hardcoded defaults)
if not SECRET_KEY or SECRET_KEY == 'django-insecure-dev-fallback-will-be-validated':  # noqa: F405
    SECRET_KEY = 'test-secret-key-for-tests-only'  # noqa: F811
if not JWT_SECRET_KEY:  # noqa: F405
    JWT_SECRET_KEY = 'test-jwt-secret-key-for-tests-only'  # noqa: F811
if not ORACLE_PASSWORD:  # noqa: F405
    ORACLE_PASSWORD = 'test-oracle-password'  # noqa: F811
