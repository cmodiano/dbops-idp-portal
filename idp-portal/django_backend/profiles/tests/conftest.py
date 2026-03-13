"""
Story 78.11: Auto-create unmanaged tables for all profile tests.

Django's CASCADE collector follows reverse FK relations even for managed=False models.
If PROFILE_ACTION_ALLOWLIST etc. don't exist in SQLite, deleting a
ProfileActionPermission raises OperationalError. This conftest ensures the tables
exist for all profile test modules.
"""
import pytest
from profiles.tests._action_permission_test_helpers import (
    create_unmanaged_tables,
    drop_unmanaged_tables,
)


@pytest.fixture(autouse=True, scope="session")
def _ensure_action_permission_tables(django_db_setup, django_db_blocker):
    """Create unmanaged normalized tables once per test session."""
    with django_db_blocker.unblock():
        create_unmanaged_tables()
    yield
    with django_db_blocker.unblock():
        drop_unmanaged_tables()
