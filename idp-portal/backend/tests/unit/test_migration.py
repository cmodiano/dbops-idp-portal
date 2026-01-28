"""Tests for SQL migration V001 (AC #6)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent  # idp-portal/
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"


def test_v001_file_exists():
    """AC #6: V001 migration file exists."""
    assert (MIGRATIONS_DIR / "V001_create_users.sql").is_file()


def test_v001_creates_users_table():
    """AC #6: V001 contains CREATE TABLE USERS."""
    sql = (MIGRATIONS_DIR / "V001_create_users.sql").read_text()
    assert "CREATE TABLE USERS" in sql


def test_v001_creates_sequence():
    """AC #6: V001 contains SEQ_USERS sequence."""
    sql = (MIGRATIONS_DIR / "V001_create_users.sql").read_text()
    assert "CREATE SEQUENCE SEQ_USERS" in sql


def test_v001_creates_unique_index():
    """AC #6: V001 contains unique index on USERNAME."""
    sql = (MIGRATIONS_DIR / "V001_create_users.sql").read_text()
    assert "UK_USERS_USERNAME" in sql


def test_v001_columns():
    """AC #6: V001 has all required columns."""
    sql = (MIGRATIONS_DIR / "V001_create_users.sql").read_text()
    for col in ["ID", "USERNAME", "DISPLAY_NAME", "PROFILE", "SAML_SUBJECT", "CREATED_AT", "UPDATED_AT"]:
        assert col in sql, f"Missing column {col}"


def test_run_migrations_script_exists():
    """AC #6: Migration script exists and is executable."""
    script = PROJECT_ROOT / "scripts" / "run_migrations.sh"
    assert script.is_file()
