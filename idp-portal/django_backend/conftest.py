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


def ensure_admin_profiles():
    """Create standard Profile records needed by AdminProfilePermission.

    Uses get_or_create so it's safe to call multiple times.
    Call this from TestCase.setUp() methods that need admin profile resolution.
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
    Django TestCase classes must call ensure_admin_profiles() in their setUp() explicitly.
    """
    if _is_simple_test_case(request):
        return
    if _is_django_test_case(request):
        # Django TestCase manages its own DB — can't inject via fixture.
        # Tests that need admin profiles should call ensure_admin_profiles() in setUp().
        return
    ensure_admin_profiles()
