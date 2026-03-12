"""
Root conftest for django_backend — applies to all tests (catalog, reference, integrations, etc.).

Story 56.7: Ensures Profile records exist for AdminProfilePermission so tests using
users with profile='dbops' or 'DBOPS' can access admin endpoints.
Story 71.9: Reusable throttle_rates fixture for DRF throttle testing.
"""

import pytest
from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle


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
