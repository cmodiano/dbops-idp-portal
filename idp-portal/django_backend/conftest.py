"""
Root conftest for django_backend — applies to all tests (catalog, reference, integrations, etc.).

Story 56.7: Ensures Profile records exist for AdminProfilePermission so tests using
users with profile='dbops' or 'DBOPS' can access admin endpoints.
"""

import pytest


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


def _create_admin_profiles():
    """Create standard Profile records needed by AdminProfilePermission."""
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
    For Django TestCase classes, see pytest_runtest_setup hook below.
    """
    if _is_simple_test_case(request):
        return
    if _is_django_test_case(request):
        # Django TestCase manages its own DB — handled by pytest_runtest_setup
        return
    _create_admin_profiles()


def pytest_runtest_setup(item):
    """Hook: inject Profile records for Django TestCase classes.

    Django TestCase classes don't receive pytest fixtures with 'db' dependency.
    This hook patches setUp to create Profile records inside the test transaction.
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

    # Patch setUp to create profiles inside the test's transaction
    _original_key = "_original_setUp_for_profiles"
    if hasattr(cls, _original_key):
        return  # Already patched

    original_setUp = cls.setUp if hasattr(cls, "setUp") else lambda self: None

    def patched_setUp(self):
        _create_admin_profiles()
        original_setUp(self)

    setattr(cls, _original_key, original_setUp)
    cls.setUp = patched_setUp
