"""
Shared helpers for Story 78.12 tests.

Creates/drops unmanaged tables (managed=False) for SQLite test DB.
Uses raw SQL to avoid Django's SchemaEditor FK constraint check limitation.
"""
from django.db import connection


def create_unmanaged_tables():
    """Create tables for managed=False models via raw SQL (SQLite compatible)."""
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_ALLOWLIST" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "PROFILE_ID" INTEGER NOT NULL,
                "TARGET_NAME" VARCHAR(255) NOT NULL,
                UNIQUE ("PROFILE_ID", "TARGET_NAME")
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_PATTERNS" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "PROFILE_ID" INTEGER NOT NULL,
                "PATTERN" VARCHAR(255) NOT NULL,
                UNIQUE ("PROFILE_ID", "PATTERN")
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_ATTR_FILTERS" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "PROFILE_ID" INTEGER NOT NULL,
                "ATTRIBUTE_KEY" VARCHAR(255) NOT NULL,
                "ATTRIBUTE_VALUE" VARCHAR(255) NOT NULL,
                UNIQUE ("PROFILE_ID", "ATTRIBUTE_KEY", "ATTRIBUTE_VALUE")
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "PROFILE_TARGET_EXCLUSIONS" (
                "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
                "PROFILE_ID" INTEGER NOT NULL,
                "EXCLUSION_PATTERN" VARCHAR(255) NOT NULL,
                UNIQUE ("PROFILE_ID", "EXCLUSION_PATTERN")
            )
        """)


def drop_unmanaged_tables():
    """Drop tables for managed=False models via raw SQL."""
    with connection.cursor() as cursor:
        cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_ALLOWLIST"')
        cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_PATTERNS"')
        cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_ATTR_FILTERS"')
        cursor.execute('DROP TABLE IF EXISTS "PROFILE_TARGET_EXCLUSIONS"')
