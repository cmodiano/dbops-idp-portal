"""
Rollback test DB changes applied manually (not via Flyway).

This script restores the DB schema to the state prior to:
- adding surrogate ID PKs to ACTION_TAGS / USER_FAVORITES
- extending CK_AUDIT_LOG_ACTION_TYPE to include USER_* / FAVORITE_* / etc.

It is intended for local/dev environments only.
"""

from __future__ import annotations

import os
import sys


def _setup_django() -> None:
    # Ensure project root (django_backend/) is on sys.path when executed as a script
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "idp_backend.settings")
    import django  # noqa: WPS433

    django.setup()


def _constraint_exists(cur, name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM user_constraints WHERE constraint_name = :name",
        {"name": name.upper()},
    )
    return int(cur.fetchone()[0]) > 0


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) FROM user_tab_columns WHERE table_name = :t AND column_name = :c",
        {"t": table.upper(), "c": column.upper()},
    )
    return int(cur.fetchone()[0]) > 0


def main() -> None:
    _setup_django()
    from django.db import connection  # noqa: WPS433

    old_allowed = [
        # Action lifecycle
        "ACTION_CREATED",
        "ACTION_UPDATED",
        "ACTION_PUBLISHED",
        "ACTION_DISABLED",
        "ACTION_ENABLED",
        # Execution lifecycle (legacy naming in constraint)
        "EXECUTION_SUBMITTED",
        "EXECUTION_STARTED",
        "EXECUTION_COMPLETED",
        "EXECUTION_FAILED",
        # ServiceNow
        "SERVICENOW_CHANGE_CREATED",
        # Approval workflow
        "EXECUTION_PENDING_APPROVAL",
        "EXECUTION_APPROVED",
        "EXECUTION_REJECTED",
        # Remediation / auto-remediation
        "REMEDIATION_EXECUTION_CREATED",
        "AUTO_REMEDIATION_TRIGGERED",
        "AUTO_REMEDIATION_SUCCESS",
        "AUTO_REMEDIATION_FAILED",
        # Scheduling
        "SCHEDULED_EXECUTION_CREATED",
        "SCHEDULED_EXECUTION_CANCELLED",
    ]
    allowed_sql = ", ".join(f"'{v}'" for v in old_allowed)

    with connection.cursor() as cur:
        # ---------------------------------------------------------------------
        # AUDIT_LOG: delete rows with "new" action types then restore constraint
        # ---------------------------------------------------------------------
        cur.execute(
            f"DELETE FROM AUDIT_LOG WHERE ACTION_TYPE NOT IN ({allowed_sql})"  # nosec B608 - built from hardcoded list, no user input
        )
        deleted = cur.rowcount
        print(f"AUDIT_LOG: deleted {deleted} rows with out-of-scope ACTION_TYPE")

        if _constraint_exists(cur, "CK_AUDIT_LOG_ACTION_TYPE"):
            cur.execute("ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE")
        cur.execute(
            f"ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE CHECK (ACTION_TYPE IN ({allowed_sql}))"
        )
        print("AUDIT_LOG: CK_AUDIT_LOG_ACTION_TYPE restored")

        # ---------------------------------------------------------------------
        # ACTION_TAGS: drop ID column + restore composite PK
        # ---------------------------------------------------------------------
        if _constraint_exists(cur, "UK_ACTION_TAGS_ACTION_TAG"):
            cur.execute("ALTER TABLE ACTION_TAGS DROP CONSTRAINT UK_ACTION_TAGS_ACTION_TAG")
        # If there is any primary key (name may vary), drop it
        cur.execute(
            "SELECT constraint_name FROM user_constraints "
            "WHERE table_name='ACTION_TAGS' AND constraint_type='P'"
        )
        for (pk_name,) in cur.fetchall():
            cur.execute(f"ALTER TABLE ACTION_TAGS DROP CONSTRAINT {pk_name}")

        if _column_exists(cur, "ACTION_TAGS", "ID"):
            cur.execute("ALTER TABLE ACTION_TAGS DROP COLUMN ID")

        cur.execute(
            "ALTER TABLE ACTION_TAGS ADD CONSTRAINT PK_ACTION_TAGS PRIMARY KEY (ACTION_ID, TAG_ID)"
        )
        print("ACTION_TAGS: composite PK restored, surrogate ID removed")

        # ---------------------------------------------------------------------
        # USER_FAVORITES: drop ID column + restore composite PK
        # ---------------------------------------------------------------------
        if _constraint_exists(cur, "UK_USER_FAVORITES_USER_ACTION"):
            cur.execute("ALTER TABLE USER_FAVORITES DROP CONSTRAINT UK_USER_FAVORITES_USER_ACTION")
        if _constraint_exists(cur, "PK_USER_FAVORITES"):
            cur.execute("ALTER TABLE USER_FAVORITES DROP CONSTRAINT PK_USER_FAVORITES")

        if _column_exists(cur, "USER_FAVORITES", "ID"):
            cur.execute("ALTER TABLE USER_FAVORITES DROP COLUMN ID")

        cur.execute(
            "ALTER TABLE USER_FAVORITES ADD CONSTRAINT PK_USER_FAVORITES PRIMARY KEY (USER_ID, ACTION_ID)"
        )
        print("USER_FAVORITES: composite PK restored, surrogate ID removed")

        connection.commit()

        # Quick verification
        for table in ("ACTION_TAGS", "USER_FAVORITES"):
            cur.execute(
                "SELECT column_name FROM user_tab_columns WHERE table_name=:t ORDER BY column_id",
                {"t": table},
            )
            cols = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT constraint_name,constraint_type FROM user_constraints WHERE table_name=:t ORDER BY constraint_name",
                {"t": table},
            )
            cons = cur.fetchall()
            print(f"{table}: columns={cols} constraints={cons}")

        cur.execute(
            "SELECT search_condition FROM user_constraints WHERE constraint_name='CK_AUDIT_LOG_ACTION_TYPE'"
        )
        print("AUDIT_LOG CK:", cur.fetchone()[0])

    print("ROLLBACK_OK")


if __name__ == "__main__":
    main()

