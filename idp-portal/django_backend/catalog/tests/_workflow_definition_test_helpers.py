"""
Shared helpers for Story 78.10 tests.

Creates/drops unmanaged tables (managed=False) for SQLite test DB.
Uses raw SQL to avoid Django's SchemaEditor FK constraint check limitation.
"""
from django.db import connection


def create_unmanaged_tables():
    """Create tables for managed=False models via raw SQL (SQLite compatible)."""
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "WORKFLOW_DEFINITIONS" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "ACTION_ID" INTEGER REFERENCES "ACTIONS_CATALOG" ("ID") ON DELETE CASCADE,
                "VERSION" INTEGER NOT NULL DEFAULT 1,
                "CREATED_AT" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                "UPDATED_AT" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "WORKFLOW_STEPS" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "WORKFLOW_DEFINITION_ID" INTEGER NOT NULL REFERENCES "WORKFLOW_DEFINITIONS" ("ID") ON DELETE CASCADE,
                "STEP_ID" VARCHAR(255) NOT NULL,
                "STEP_ORDER" INTEGER NOT NULL,
                "STEP_NAME" VARCHAR(255) NOT NULL,
                "STEP_TYPE" VARCHAR(50) NOT NULL,
                "REFERENCED_ACTION_ID" INTEGER REFERENCES "ACTIONS_CATALOG" ("ID") ON DELETE SET NULL,
                "INTEGRATION_TYPE" VARCHAR(100),
                "OPERATION" VARCHAR(255),
                "INPUT_MAPPING" TEXT,
                "OUTPUT_MAPPING" TEXT,
                "CONDITION" TEXT,
                "RETRY_ENABLED" INTEGER NOT NULL DEFAULT 0,
                "RETRY_MAX_ATTEMPTS" INTEGER,
                "RETRY_INTERVAL_SECONDS" INTEGER,
                "RETRY_BACKOFF_MULTIPLIER" REAL,
                "JOIN_POLICY" VARCHAR(50),
                UNIQUE ("WORKFLOW_DEFINITION_ID", "STEP_ID")
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "WORKFLOW_STEP_EDGES" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "FROM_STEP_ID" INTEGER NOT NULL REFERENCES "WORKFLOW_STEPS" ("ID") ON DELETE CASCADE,
                "TO_STEP_ID" INTEGER NOT NULL REFERENCES "WORKFLOW_STEPS" ("ID") ON DELETE CASCADE,
                "EDGE_TYPE" VARCHAR(20) NOT NULL,
                UNIQUE ("FROM_STEP_ID", "TO_STEP_ID", "EDGE_TYPE")
            )
        """)


def drop_unmanaged_tables():
    """Drop tables for managed=False models via raw SQL."""
    with connection.cursor() as cursor:
        cursor.execute("DROP TABLE IF EXISTS \"WORKFLOW_STEP_EDGES\"")
        cursor.execute("DROP TABLE IF EXISTS \"WORKFLOW_STEPS\"")
        cursor.execute("DROP TABLE IF EXISTS \"WORKFLOW_DEFINITIONS\"")
