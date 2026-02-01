"""Minimal integration test: Oracle connection + CRUD against Docker Oracle (AC2).

Run with Oracle up: docker compose up -d oracle, wait ~1–2 min, then:
  cd idp-portal/backend && ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=idp_app ORACLE_PASSWORD=changeme pytest tests/integration/ -v
Skipped when ORACLE_DSN / ORACLE_USER / ORACLE_PASSWORD are not set.
Uses skip_if_no_oracle fixture from conftest.py.
"""

import os

import oracledb
import pytest


def test_oracle_connection_and_select_dual(skip_if_no_oracle):
    """Connection + SELECT 1 FROM DUAL (validates Oracle is reachable)."""
    conn = oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        dsn=os.environ["ORACLE_DSN"],
    )
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM DUAL")
        row = cursor.fetchone()
        assert row == (1,)
    finally:
        conn.close()


def test_oracle_flyway_schema_history(skip_if_no_oracle):
    """SELECT from flyway_schema_history (Story 2.20: Flyway native, migrations applied)."""
    conn = oracledb.connect(
        user=os.environ["ORACLE_USER"],
        password=os.environ["ORACLE_PASSWORD"],
        dsn=os.environ["ORACLE_DSN"],
    )
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT installed_rank, version, description FROM flyway_schema_history ORDER BY installed_rank")
        rows = cursor.fetchall()
        assert isinstance(rows, list)
        assert len(rows) >= 1, "At least one Flyway migration should be recorded"
    finally:
        conn.close()


def test_oracle_insert_update_select_delete_users(skip_if_no_oracle):
    """INSERT / UPDATE / SELECT / DELETE on USERS (CRUD validation including modify)."""
    conn = None
    cursor = None
    username = "_integration_test_user_"
    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO USERS (USERNAME, PROFILE) VALUES (:1, :2)",
            [username, "dev"],
        )
        conn.commit()
        cursor.execute(
            "UPDATE USERS SET PROFILE = :1 WHERE USERNAME = :2",
            ["admin", username],
        )
        conn.commit()
        cursor.execute(
            "SELECT ID, USERNAME, PROFILE FROM USERS WHERE USERNAME = :1",
            [username],
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == username
        assert row[2] == "admin"
    finally:
        if cursor is not None and conn is not None:
            cursor.execute("DELETE FROM USERS WHERE USERNAME = :1", [username])
            conn.commit()
        if conn is not None:
            conn.close()


def test_oracle_insert_update_select_delete_profiles(skip_if_no_oracle):
    """INSERT / UPDATE / SELECT / DELETE on PROFILES (second table CRUD validation)."""
    conn = None
    cursor = None
    name = "_integration_test_profile_"
    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO PROFILES (NAME, DESCRIPTION, AD_GROUP, IS_ADMIN, IS_AUDITOR)
               VALUES (:1, :2, :3, :4, :5)""",
            [name, "Test profile", "GRP-TEST", 0, 0],
        )
        conn.commit()
        cursor.execute(
            "UPDATE PROFILES SET DESCRIPTION = :1, IS_ADMIN = 1 WHERE NAME = :2",
            ["Updated description", name],
        )
        conn.commit()
        cursor.execute(
            "SELECT ID, NAME, DESCRIPTION, IS_ADMIN FROM PROFILES WHERE NAME = :1",
            [name],
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == name
        assert row[2] == "Updated description"
        assert row[3] == 1
    finally:
        if cursor is not None and conn is not None:
            cursor.execute("DELETE FROM PROFILES WHERE NAME = :1", [name])
            conn.commit()
        if conn is not None:
            conn.close()
