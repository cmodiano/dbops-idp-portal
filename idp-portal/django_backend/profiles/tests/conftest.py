"""
Story 78.11 + 78.12: Auto-create unmanaged tables for all profile tests.

Django's CASCADE collector follows reverse FK relations even for managed=False models.
If PROFILE_ACTION_ALLOWLIST / PROFILE_TARGET_ALLOWLIST etc. don't exist in SQLite,
deleting a ProfileActionPermission / ProfileTargetPermission raises OperationalError.
This conftest ensures the tables exist for all profile test modules.
"""
import pytest
from profiles.tests._action_permission_test_helpers import (
    create_unmanaged_tables as create_action_tables,
    drop_unmanaged_tables as drop_action_tables,
)
from profiles.tests._target_permission_test_helpers import (
    create_unmanaged_tables as create_target_tables,
    drop_unmanaged_tables as drop_target_tables,
)


@pytest.fixture(autouse=True, scope="session")
def _ensure_normalized_permission_tables(django_db_setup, django_db_blocker):
    """Create unmanaged normalized tables once per test session."""
    with django_db_blocker.unblock():
        create_action_tables()
        create_target_tables()
    yield
    with django_db_blocker.unblock():
        drop_action_tables()
        drop_target_tables()
