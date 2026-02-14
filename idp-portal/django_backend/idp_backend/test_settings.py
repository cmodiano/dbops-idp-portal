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

# Story 27.4: GitHub webhook secret for tests
GITHUB_WEBHOOK_SECRET = 'test-github-webhook-secret'

# Story 22.2: Superuser fallback disabled by default in tests (fail-secure)
# Enable per-test with @override_settings(ALLOW_SUPERUSER_FALLBACK=True) for dev-mode tests
ALLOW_SUPERUSER_FALLBACK = False

# Story 19.0: Disable simulation by default in tests (enable per-test with @override_settings)
SIMULATE_EXECUTION_DEV = False
SIMULATE_EXECUTION_FAILURE_RATE = 0.0
SIMULATE_EXECUTION_STEP_DURATION = 0

# Story 20.3: Celery eager mode for tests (synchronous execution, no broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Story 20.3: Disable cancellation cache in tests by default
WORKFLOW_RETRY_USE_CANCELLATION_CACHE = False

# Story 20.5: Use in-memory cache for tests (avoids Redis dependency)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}

# Story 26.14: Disable rate limiting in tests to prevent 429 errors
RATELIMIT_ENABLED = False

# Story 22.13: In-memory channel layer for WebSocket tests
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
