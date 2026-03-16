"""
Shared helpers for Story 78.11 tests.

Creates/drops unmanaged tables (managed=False) for SQLite test DB.
Uses raw SQL to avoid Django's SchemaEditor FK constraint check limitation.
"""
from django.db import connection


def create_unmanaged_tables():
    """Create tables for managed=False models via raw SQL (SQLite compatible)."""
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PROFILE_ACTION_ALLOWLIST" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "PROFILE_ID" INTEGER NOT NULL,
                "ACTION_ID" INTEGER NOT NULL,
                UNIQUE ("PROFILE_ID", "ACTION_ID")
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PROFILE_ACTION_TAG_PATTERNS" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "PROFILE_ID" INTEGER NOT NULL,
                "TAG_PATTERN" VARCHAR(255) NOT NULL,
                UNIQUE ("PROFILE_ID", "TAG_PATTERN")
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PROFILE_ACTION_ENVS" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "PROFILE_ID" INTEGER NOT NULL,
                "ENVIRONMENT" VARCHAR(255) NOT NULL,
                UNIQUE ("PROFILE_ID", "ENVIRONMENT")
            )
        """)


def drop_unmanaged_tables():
    """Drop tables for managed=False models via raw SQL."""
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS "PROFILE_ACTION_ALLOWLIST"')
        cursor.execute('DROP TABLE IF EXISTS "PROFILE_ACTION_TAG_PATTERNS"')
        cursor.execute('DROP TABLE IF EXISTS "PROFILE_ACTION_ENVS"')
