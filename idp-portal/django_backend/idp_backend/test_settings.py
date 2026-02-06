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
