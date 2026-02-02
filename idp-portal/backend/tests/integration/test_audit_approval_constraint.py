"""Integration tests for audit log approval action types constraint (Story 9.8).

Verify Oracle CHECK constraint CK_AUDIT_LOG_ACTION_TYPE allows approval workflow
action types introduced in V032: EXECUTION_PENDING_APPROVAL, EXECUTION_APPROVED,
EXECUTION_REJECTED.

Run with Oracle up:
    docker compose up -d oracle
    # Wait ~1-2 min for Oracle to start
    cd idp-portal/backend
    ORACLE_DSN=localhost:1521/FREEPDB1 ORACLE_USER=idp_app ORACLE_PASSWORD=changeme \
        pytest tests/integration/test_audit_approval_constraint.py -v

Skipped when ORACLE_DSN / ORACLE_USER / ORACLE_PASSWORD are not set.
"""

import os
from datetime import datetime

import oracledb
import pytest


def test_audit_log_constraint_allows_execution_pending_approval(skip_if_no_oracle):
    """Verify constraint allows EXECUTION_PENDING_APPROVAL action type (Story 9.8, AC3).

    Performs real INSERT into Oracle - will fail with ORA-02290 if constraint missing.
    """
    conn = None
    cursor = None
    test_user_id = "_test-story-9-8-pending_"
    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()

        # Insert with EXECUTION_PENDING_APPROVAL - will raise ORA-02290 if not in constraint
        cursor.execute(
            """INSERT INTO AUDIT_LOG (
                USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
                ACTION_TIMESTAMP, CLIENT_IP, ACTION_DETAILS
            ) VALUES (
                :user_id, 'EXECUTION_PENDING_APPROVAL', 'execution', 999999,
                SYSTIMESTAMP, '127.0.0.1', :details
            )""",
            {
                "user_id": test_user_id,
                "details": '{"test": true, "story": "9-8", "type": "PENDING_APPROVAL"}',
            },
        )
        conn.commit()

        # Verify insert succeeded by reading back
        cursor.execute(
            "SELECT ACTION_TYPE FROM AUDIT_LOG WHERE USER_ID = :user_id",
            {"user_id": test_user_id},
        )
        row = cursor.fetchone()
        assert row is not None, "INSERT should have succeeded"
        assert row[0] == "EXECUTION_PENDING_APPROVAL"
    finally:
        # Cleanup test data
        if cursor is not None and conn is not None:
            cursor.execute("DELETE FROM AUDIT_LOG WHERE USER_ID = :1", [test_user_id])
            conn.commit()
        if conn is not None:
            conn.close()


def test_audit_log_constraint_allows_execution_approved(skip_if_no_oracle):
    """Verify constraint allows EXECUTION_APPROVED action type (Story 9.8, AC3).

    Performs real INSERT into Oracle - will fail with ORA-02290 if constraint missing.
    """
    conn = None
    cursor = None
    test_user_id = "_test-story-9-8-approved_"
    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO AUDIT_LOG (
                USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
                ACTION_TIMESTAMP, CLIENT_IP, ACTION_DETAILS
            ) VALUES (
                :user_id, 'EXECUTION_APPROVED', 'execution', 999999,
                SYSTIMESTAMP, '127.0.0.1', :details
            )""",
            {
                "user_id": test_user_id,
                "details": '{"test": true, "story": "9-8", "type": "APPROVED", "approver_id": 42}',
            },
        )
        conn.commit()

        cursor.execute(
            "SELECT ACTION_TYPE FROM AUDIT_LOG WHERE USER_ID = :user_id",
            {"user_id": test_user_id},
        )
        row = cursor.fetchone()
        assert row is not None, "INSERT should have succeeded"
        assert row[0] == "EXECUTION_APPROVED"
    finally:
        if cursor is not None and conn is not None:
            cursor.execute("DELETE FROM AUDIT_LOG WHERE USER_ID = :1", [test_user_id])
            conn.commit()
        if conn is not None:
            conn.close()


def test_audit_log_constraint_allows_execution_rejected(skip_if_no_oracle):
    """Verify constraint allows EXECUTION_REJECTED action type (Story 9.8, AC3).

    Performs real INSERT into Oracle - will fail with ORA-02290 if constraint missing.
    """
    conn = None
    cursor = None
    test_user_id = "_test-story-9-8-rejected_"
    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO AUDIT_LOG (
                USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
                ACTION_TIMESTAMP, CLIENT_IP, ACTION_DETAILS
            ) VALUES (
                :user_id, 'EXECUTION_REJECTED', 'execution', 999999,
                SYSTIMESTAMP, '127.0.0.1', :details
            )""",
            {
                "user_id": test_user_id,
                "details": '{"test": true, "story": "9-8", "type": "REJECTED", "rejector_id": 43, "reason": "Test rejection"}',
            },
        )
        conn.commit()

        cursor.execute(
            "SELECT ACTION_TYPE FROM AUDIT_LOG WHERE USER_ID = :user_id",
            {"user_id": test_user_id},
        )
        row = cursor.fetchone()
        assert row is not None, "INSERT should have succeeded"
        assert row[0] == "EXECUTION_REJECTED"
    finally:
        if cursor is not None and conn is not None:
            cursor.execute("DELETE FROM AUDIT_LOG WHERE USER_ID = :1", [test_user_id])
            conn.commit()
        if conn is not None:
            conn.close()


def test_all_approval_action_types_insertable(skip_if_no_oracle):
    """Comprehensive test: all three approval types can be inserted (Story 9.8, AC3-4).

    This is the critical regression test that will fail if any migration after V032
    accidentally drops the approval types from the CHECK constraint.
    """
    conn = None
    cursor = None
    test_user_prefix = "_test-story-9-8-all_"
    approval_types = [
        "EXECUTION_PENDING_APPROVAL",
        "EXECUTION_APPROVED",
        "EXECUTION_REJECTED",
    ]

    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()

        for i, action_type in enumerate(approval_types):
            test_user_id = f"{test_user_prefix}{i}"
            cursor.execute(
                """INSERT INTO AUDIT_LOG (
                    USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
                    ACTION_TIMESTAMP, CLIENT_IP, ACTION_DETAILS
                ) VALUES (
                    :user_id, :action_type, 'execution', :entity_id,
                    SYSTIMESTAMP, '127.0.0.1', :details
                )""",
                {
                    "user_id": test_user_id,
                    "action_type": action_type,
                    "entity_id": 999990 + i,
                    "details": f'{{"test": true, "story": "9-8", "index": {i}}}',
                },
            )

        conn.commit()

        # Verify all three inserts
        cursor.execute(
            "SELECT COUNT(*) FROM AUDIT_LOG WHERE USER_ID LIKE :pattern",
            {"pattern": f"{test_user_prefix}%"},
        )
        count = cursor.fetchone()[0]
        assert count == 3, f"Expected 3 inserts, got {count}"

    finally:
        if cursor is not None and conn is not None:
            cursor.execute(
                "DELETE FROM AUDIT_LOG WHERE USER_ID LIKE :1", [f"{test_user_prefix}%"]
            )
            conn.commit()
        if conn is not None:
            conn.close()


def test_audit_log_constraint_content_includes_approval_types(skip_if_no_oracle):
    """Verify constraint definition includes approval types (Story 9.8, AC2).

    Query USER_CONSTRAINTS to verify the CHECK constraint text includes all three
    approval action types. This is a direct validation of AC2.
    """
    conn = None
    cursor = None
    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()

        cursor.execute(
            """SELECT SEARCH_CONDITION
               FROM USER_CONSTRAINTS
               WHERE CONSTRAINT_NAME = 'CK_AUDIT_LOG_ACTION_TYPE'"""
        )
        row = cursor.fetchone()
        assert row is not None, "Constraint CK_AUDIT_LOG_ACTION_TYPE should exist"

        constraint_text = str(row[0])

        # Verify all approval types are in constraint (AC2)
        assert (
            "EXECUTION_PENDING_APPROVAL" in constraint_text
        ), "Constraint must include EXECUTION_PENDING_APPROVAL"
        assert (
            "EXECUTION_APPROVED" in constraint_text
        ), "Constraint must include EXECUTION_APPROVED"
        assert (
            "EXECUTION_REJECTED" in constraint_text
        ), "Constraint must include EXECUTION_REJECTED"

    finally:
        if conn is not None:
            conn.close()


def test_flyway_migrations_v032_v034_v035_applied(skip_if_no_oracle):
    """Verify migrations V032, V034, V035 are applied in correct order (Story 9.8, AC1).

    Query flyway_schema_history to confirm migration sequence.
    """
    conn = None
    cursor = None
    try:
        conn = oracledb.connect(
            user=os.environ["ORACLE_USER"],
            password=os.environ["ORACLE_PASSWORD"],
            dsn=os.environ["ORACLE_DSN"],
        )
        cursor = conn.cursor()

        cursor.execute(
            """SELECT version, description, success
               FROM flyway_schema_history
               WHERE version IN ('032', '034', '035')
               ORDER BY installed_rank"""
        )
        rows = cursor.fetchall()

        # Extract versions that were applied
        applied_versions = [row[0] for row in rows if row[2] == 1]

        # V032 must be applied (approval types)
        assert "032" in applied_versions, (
            "V032 (approval audit types) must be applied - "
            "run: flyway migrate"
        )

        # If V034 and V035 exist, they should also be applied
        # (these add remediation and auto-remediation types but preserve approval types)
        if "034" in applied_versions:
            assert applied_versions.index("032") < applied_versions.index("034"), (
                "V032 must be applied before V034"
            )
        if "035" in applied_versions:
            assert applied_versions.index("032") < applied_versions.index("035"), (
                "V032 must be applied before V035"
            )
            if "034" in applied_versions:
                assert applied_versions.index("034") < applied_versions.index("035"), (
                    "V034 must be applied before V035"
                )

    finally:
        if conn is not None:
            conn.close()
