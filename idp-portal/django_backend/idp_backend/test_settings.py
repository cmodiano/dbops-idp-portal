"""
Test settings for Django backend.
Uses SQLite for fast, Oracle-independent test execution.

Story 15.2: Security functional tests require reliable test DB.
Story 30.1: Set secrets BEFORE importing settings.py to avoid ImproperlyConfigured.
"""

import os

# Story 30.1: Provide test-safe secrets BEFORE importing settings.py (fail-fast)
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-tests-only')
os.environ.setdefault('JWT_SECRET_KEY', 'test-jwt-secret-key-for-tests-only')
os.environ.setdefault('DEBUG', 'True')
os.environ.setdefault('ORACLE_PASSWORD', 'test-oracle-password')

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

# Story 27.4: GitHub webhook secret for tests
GITHUB_WEBHOOK_SECRET = 'test-github-webhook-secret'

# Story 22.2: Superuser fallback disabled by default in tests (fail-secure)
# Enable per-test with @override_settings(ALLOW_SUPERUSER_FALLBACK=True) for dev-mode tests
ALLOW_SUPERUSER_FALLBACK = False

# Story 56.4: Admin profile names for SAML string resolution (configurable, explicit in tests)
# Déprécié (Story 56.7) — conservé pour référence, non utilisé par core/permissions.py (chemin SAML string → DB lookup désormais)
# NE PAS supprimer — peut être utilisé par des tests tiers
ADMIN_PROFILE_NAMES = {'dbops', 'dba', 'dba_applicatif', 'dba_infrastructure'}
# DBOPS_PROFILE_NAMES: admin endpoints only — DBA excluded (Story 15.2 AC2)
# Déprécié (Story 56.7) — conservé pour référence, non utilisé par core/permissions.py
DBOPS_PROFILE_NAMES = {'dbops'}

# Story 19.0: Disable simulation by default in tests (enable per-test with @override_settings)
SIMULATE_EXECUTION_DEV = False
SIMULATE_EXECUTION_FAILURE_RATE = 0.0
SIMULATE_EXECUTION_STEP_DURATION = 0

# Story 20.3: Celery eager mode for tests (synchronous execution, no broker needed)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Story 20.3: Disable cancellation cache in tests by default
WORKFLOW_RETRY_USE_CANCELLATION_CACHE = False

# Story 78.8: Legacy runtime disabled by default in tests
WORKFLOW_LEGACY_RUNTIME_ENABLED = False

# Story 78.10: Normalized definitions disabled by default in tests
WORKFLOW_NORMALIZED_DEFINITIONS_ENABLED = False

# Story 78.11: Normalized profile action permissions disabled by default in tests
PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED = False

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

# Story 65.2 — 1 worker en tests pour éviter les "database table is locked" SQLite
# (SQLite ne supporte pas les écritures simultanées multi-threads)
# Le code path ThreadPoolExecutor est toujours exercé, mais séquentiellement.
PARALLEL_GROUP_MAX_WORKERS = 1
