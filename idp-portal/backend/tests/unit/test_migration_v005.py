"""Tests for SQL migration V005 — USER_PERMISSIONS table."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # idp-portal/
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"


def test_v005_file_exists():
    """V005 migration file exists."""
    assert (MIGRATIONS_DIR / "V005_create_user_permissions.sql").is_file()


def test_v005_creates_user_permissions_table():
    """V005 contains CREATE TABLE USER_PERMISSIONS."""
    sql = (MIGRATIONS_DIR / "V005_create_user_permissions.sql").read_text()
    assert "CREATE TABLE USER_PERMISSIONS" in sql


def test_v005_primary_key():
    """V005 defines composite PK on (USER_ID, ACTION_ID, ENVIRONMENT)."""
    sql = (MIGRATIONS_DIR / "V005_create_user_permissions.sql").read_text()
    assert "PK_USER_PERMISSIONS" in sql
    assert "USER_ID" in sql
    assert "ACTION_ID" in sql
    assert "ENVIRONMENT" in sql


def test_v005_foreign_key_users():
    """V005 references USERS table via FK."""
    sql = (MIGRATIONS_DIR / "V005_create_user_permissions.sql").read_text()
    assert "FK_USER_PERM_USER" in sql
    assert "REFERENCES USERS" in sql


def test_v005_environment_check_constraint():
    """V005 constrains ENVIRONMENT to DEV, QA, PROD."""
    sql = (MIGRATIONS_DIR / "V005_create_user_permissions.sql").read_text()
    assert "CK_USER_PERM_ENV" in sql
    for env in ["DEV", "QA", "PROD"]:
        assert env in sql


def test_v005_columns():
    """V005 has all required columns."""
    sql = (MIGRATIONS_DIR / "V005_create_user_permissions.sql").read_text()
    for col in ["USER_ID", "ACTION_ID", "ENVIRONMENT", "GRANTED_BY", "GRANTED_AT"]:
        assert col in sql, f"Missing column {col}"


def test_v005_indexes():
    """V005 creates indexes for query performance."""
    sql = (MIGRATIONS_DIR / "V005_create_user_permissions.sql").read_text()
    assert "IDX_USER_PERM_USER" in sql
    assert "IDX_USER_PERM_ACTION" in sql
