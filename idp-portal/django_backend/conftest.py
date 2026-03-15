"""
Root conftest for django_backend — applies to all tests (catalog, reference, integrations, etc.).

Story 56.7: Ensures Profile records exist for AdminProfilePermission so tests using
users with profile='dbops' or 'DBOPS' can access admin endpoints.
Story 71.9: Reusable throttle_rates fixture for DRF throttle testing.
Story 78.10/78.11/78.12: Ensures unmanaged Flyway tables exist for SQLite tests
(WORKFLOW_DEFINITIONS, PROFILE_ACTION_ALLOWLIST, etc.) — required by inventory,
executions, catalog, profiles tests.
"""

import pytest
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle


# ---------------------------------------------------------------------------
# Unmanaged tables for SQLite tests (Story 78.10, 78.11, 78.12)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_unmanaged_tables_for_sqlite(django_db_setup, django_db_blocker):
    """Create Flyway-managed unmanaged tables for all tests using SQLite.

    These tables (WORKFLOW_DEFINITIONS, PROFILE_ACTION_ALLOWLIST, etc.) are created
    by Flyway in Oracle but don't exist in Django migrations. Tests in inventory,
    executions, catalog, profiles need them. Uses raw SQL compatible with SQLite.
    """
    def _create_tables():
        from django.db import connection

        with connection.cursor() as cursor:
            # Profile action permission tables (Story 78.11)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PROFILE_ACTION_ALLOWLIST" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "PROFILE_ID" INTEGER NOT NULL,
                    "ACTION_ID" INTEGER NOT NULL,
                    UNIQUE ("PROFILE_ID", "ACTION_ID")
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PROFILE_ACTION_TAG_PATTERNS" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "PROFILE_ID" INTEGER NOT NULL,
                    "TAG_PATTERN" VARCHAR(255) NOT NULL,
                    UNIQUE ("PROFILE_ID", "TAG_PATTERN")
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PROFILE_ACTION_ENVS" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "PROFILE_ID" INTEGER NOT NULL,
                    "ENVIRONMENT" VARCHAR(255) NOT NULL,
                    UNIQUE ("PROFILE_ID", "ENVIRONMENT")
                )
            """)
            # Profile target permission tables (Story 78.12)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_ALLOWLIST" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "PROFILE_ID" INTEGER NOT NULL,
                    "TARGET_NAME" VARCHAR(255) NOT NULL,
                    UNIQUE ("PROFILE_ID", "TARGET_NAME")
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_PATTERNS" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "PROFILE_ID" INTEGER NOT NULL,
                    "PATTERN" VARCHAR(255) NOT NULL,
                    UNIQUE ("PROFILE_ID", "PATTERN")
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_ATTR_FILTERS" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "PROFILE_ID" INTEGER NOT NULL,
                    "ATTRIBUTE_KEY" VARCHAR(255) NOT NULL,
                    "ATTRIBUTE_VALUE" VARCHAR(255) NOT NULL,
                    UNIQUE ("PROFILE_ID", "ATTRIBUTE_KEY", "ATTRIBUTE_VALUE")
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_EXCLUSIONS" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "PROFILE_ID" INTEGER NOT NULL,
                    "EXCLUSION_PATTERN" VARCHAR(255) NOT NULL,
                    UNIQUE ("PROFILE_ID", "EXCLUSION_PATTERN")
                )
            """)
            # Workflow definition tables (Story 78.10) — FK to ACTIONS_CATALOG
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "WORKFLOW_DEFINITIONS" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "ACTION_ID" INTEGER REFERENCES "ACTIONS_CATALOG" ("ID") ON DELETE CASCADE,
                    "VERSION" INTEGER NOT NULL DEFAULT 1,
                    "CREATED_AT" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    "UPDATED_AT" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "WORKFLOW_STEPS" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "WORKFLOW_DEFINITION_ID" INTEGER NOT NULL REFERENCES "WORKFLOW_DEFINITIONS" ("ID") ON DELETE CASCADE,
                    "STEP_ID" VARCHAR(255) NOT NULL,
                    "STEP_ORDER" INTEGER NOT NULL,
                    "STEP_NAME" VARCHAR(255) NOT NULL,
                    "STEP_TYPE" VARCHAR(50) NOT NULL,
                    "REFERENCED_ACTION_ID" INTEGER REFERENCES "ACTIONS_CATALOG" ("ID") ON DELETE SET NULL,
                    "INTEGRATION_TYPE" VARCHAR(100),
                    "OPERATION" VARCHAR(255),
                    "INPUT_MAPPING" TEXT,
                    "OUTPUT_MAPPING" TEXT,
                    "CONDITION" TEXT,
                    "RETRY_ENABLED" INTEGER NOT NULL DEFAULT 0,
                    "RETRY_MAX_ATTEMPTS" INTEGER,
                    "RETRY_INTERVAL_SECONDS" INTEGER,
                    "RETRY_BACKOFF_MULTIPLIER" REAL,
                    "JOIN_POLICY" VARCHAR(50),
                    UNIQUE ("WORKFLOW_DEFINITION_ID", "STEP_ID")
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "WORKFLOW_STEP_EDGES" (
                    "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "FROM_STEP_ID" INTEGER NOT NULL REFERENCES "WORKFLOW_STEPS" ("ID") ON DELETE CASCADE,
                    "TO_STEP_ID" INTEGER NOT NULL REFERENCES "WORKFLOW_STEPS" ("ID") ON DELETE CASCADE,
                    "EDGE_TYPE" VARCHAR(20) NOT NULL,
                    UNIQUE ("FROM_STEP_ID", "TO_STEP_ID", "EDGE_TYPE")
                )
            """)

    def _drop_tables():
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS "WORKFLOW_STEP_EDGES"')
            cursor.execute('DROP TABLE IF EXISTS "WORKFLOW_STEPS"')
            cursor.execute('DROP TABLE IF EXISTS "WORKFLOW_DEFINITIONS"')
            cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_EXCLUSIONS"')
            cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_ATTR_FILTERS"')
            cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_PATTERNS"')
            cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_ALLOWLIST"')
            cursor.execute('DROP TABLE IF EXISTS "PROFILE_ACTION_ENVS"')
            cursor.execute('DROP TABLE IF EXISTS "PROFILE_ACTION_TAG_PATTERNS"')
            cursor.execute('DROP TABLE IF EXISTS "PROFILE_ACTION_ALLOWLIST"')

    with django_db_blocker.unblock():
        _create_tables()
    yield
    with django_db_blocker.unblock():
        _drop_tables()


def _is_simple_test_case(request) -> bool:
    """Skip fixture for SimpleTestCase — they forbid database queries."""
    cls = getattr(request.node, "cls", None)
    if cls is None:
        return False
    for base in cls.__mro__:
        if base.__name__ == "SimpleTestCase":
            return True
    return False


def _is_django_test_case(request) -> bool:
    """Check if the test is a Django TestCase (or subclass like TransactionTestCase)."""
    cls = getattr(request.node, "cls", None)
    if cls is None:
        return False
    for base in cls.__mro__:
        if base.__name__ in ("TestCase", "TransactionTestCase", "LiveServerTestCase"):
            if base.__module__.startswith("django.test"):
                return True
    return False


def ensure_admin_profiles():
    """Create standard Profile records needed by AdminProfilePermission.

    Uses get_or_create so it's safe to call multiple times or after
    tests have already created profiles with the same names.
    """
    from profiles.models import Profile

    Profile.objects.get_or_create(
        name='DBOPS',
        defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
    )
    Profile.objects.get_or_create(
        name='DBA',
        defaults={'ad_group': 'CN=DBA,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
    )
    Profile.objects.get_or_create(
        name='client_business',
        defaults={'ad_group': 'CN=Business,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
    )
    Profile.objects.get_or_create(
        name='dba_infrastructure',
        defaults={'ad_group': 'CN=DBA-Infra,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
    )
    Profile.objects.get_or_create(
        name='AUDITOR',
        defaults={'ad_group': 'CN=Auditors,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 1},
    )
    Profile.objects.get_or_create(
        name='BUSINESS_USER',
        defaults={'ad_group': 'CN=Business,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
    )
    Profile.objects.get_or_create(
        name='dba_applicatif',
        defaults={'ad_group': 'CN=DBA-App,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
    )


@pytest.fixture(autouse=True)
def _ensure_admin_profiles(request, db):
    """Ensure Profile records exist for pure-pytest tests (not Django TestCase).

    Story 56.7: AdminProfilePermission resolves user.profile string via Profile lookup.
    Django TestCase classes are handled by pytest_runtest_setup hook below.
    """
    if _is_simple_test_case(request):
        return
    if _is_django_test_case(request):
        return
    ensure_admin_profiles()


def pytest_runtest_setup(item):
    """Hook: inject Profile records for Django TestCase classes.

    Django TestCase classes don't receive pytest fixtures with 'db' dependency.
    This hook patches setUp to call ensure_admin_profiles() AFTER the test's
    own setUp, so tests that create their own profiles (via .create()) run first,
    and our get_or_create() calls become no-ops for those names.
    """
    cls = getattr(item, "cls", None)
    if cls is None:
        return

    is_django_tc = False
    for base in cls.__mro__:
        if base.__name__ in ("TestCase", "TransactionTestCase", "LiveServerTestCase"):
            if base.__module__.startswith("django.test"):
                is_django_tc = True
                break
    if not is_django_tc:
        return

    _original_key = "_original_setUp_for_profiles"
    if hasattr(cls, _original_key):
        return  # Already patched

    original_setUp = cls.setUp if hasattr(cls, "setUp") else lambda self: None

    def patched_setUp(self):
        original_setUp(self)
        ensure_admin_profiles()

    setattr(cls, _original_key, original_setUp)
    cls.setUp = patched_setUp


# ============================================================================
# Throttle Rate Override Fixture (Story 71.9 — AC#1)
# ============================================================================

@pytest.fixture
def throttle_rates():
    """Fixture to override DRF throttle rates reliably.

    DRF's SimpleRateThrottle.THROTTLE_RATES is a class attribute set at
    import time. override_settings does NOT update it because the class
    attribute holds a stale reference. This fixture patches THROTTLE_RATES
    directly and clears the Django cache to avoid cross-test artifacts.

    Usage::

        def test_rate_limit(throttle_rates):
            throttle_rates({'auth': '2/minute', 'execution': '3/minute'})
            # ... test rate limiting ...
    """
    original = SimpleRateThrottle.THROTTLE_RATES.copy()
    cache.clear()

    def _set(rates: dict):
        SimpleRateThrottle.THROTTLE_RATES.update(rates)
        cache.clear()

    yield _set

    SimpleRateThrottle.THROTTLE_RATES.clear()
    SimpleRateThrottle.THROTTLE_RATES.update(original)
    cache.clear()
