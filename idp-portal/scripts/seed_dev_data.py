#!/usr/bin/env python3
"""Seed development database with test data for frontend validation.

Story 5.6 - Script de seed de données en base pour tests frontend
Epic 80 (stories 80.1–80.4) - Reset + reseed dev : purge orchestration, garde-fous, trace, validation QA

This script inserts a comprehensive test dataset covering:
- Users (3): dbops1, dba1, user1
- Profiles (3): DBOPS, DBA, BUSINESS
- Tags (8): oracle, patching, backup, dev, prod, urgente, provisioning, monitoring
- Actions (8): Various with AAP/ServiceNow connectors
- Integrations (2): AAP demo, ServiceNow demo
- Favorites: User favorites on actions
- Executions (15): Various statuses (SUBMITTED, RUNNING, COMPLETED, FAILED, CANCELLED, REJECTED)
- Execution steps: Timeline data for some executions

IMPORTANT: This script is for DEVELOPMENT ONLY.
- Requires APP_ENV=development or --env=dev argument
- Use --reset to clear existing data before seeding
- Never run on production databases

Usage:
    python scripts/seed_dev_data.py --env=dev
    python scripts/seed_dev_data.py --env=dev --reset
"""

import argparse
import getpass
import json
import os
import socket
import sys
from datetime import datetime, timedelta

import oracledb


# === Configuration ===

ALLOWED_ENVIRONMENTS = ("development", "dev")
BLOCKED_ENVIRONMENTS = ("staging", "production", "prod")


def get_connection() -> oracledb.Connection:
    """Create Oracle connection using environment variables.

    Uses ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD (same as backend app/core/config.py).
    Keep these env vars aligned with the application.
    """
    dsn = os.environ.get("ORACLE_DSN", "localhost:1521/FREEPDB1")
    user = os.environ.get("ORACLE_USER", "idp_app")
    password = os.environ.get("ORACLE_PASSWORD", "Oracle123!")
    return oracledb.connect(user=user, password=password, dsn=dsn)


def check_environment(env_arg: str | None) -> None:
    """Verify we're running in development environment.

    Rules:
    - --env, if provided, must be a recognized value (allowed or blocked)
    - APP_ENV must not be staging/prod/production
    - --env must not be staging/prod/production
    - At least one of APP_ENV or --env must be in ALLOWED_ENVIRONMENTS

    Raises:
        SystemExit: If not in development environment or staging/prod detected
    """
    app_env = os.environ.get("APP_ENV", "").lower()
    env_flag = env_arg.lower() if env_arg else ""

    # Reject unrecognized --env values (must be explicitly allowed or blocked)
    if env_flag and env_flag not in ALLOWED_ENVIRONMENTS and env_flag not in BLOCKED_ENVIRONMENTS:
        print(
            f"ERROR: Unrecognized --env value: '{env_flag}'.\n"
            f"Accepted values: {', '.join(ALLOWED_ENVIRONMENTS)}\n"
            f"Blocked values: {', '.join(BLOCKED_ENVIRONMENTS)}"
        )
        sys.exit(1)

    # Explicit block: refuse staging/prod in either indicator
    for value, source in [(app_env, "APP_ENV"), (env_flag, "--env")]:
        if value and value in BLOCKED_ENVIRONMENTS:
            print(
                f"ERROR: Refused to run on {source}={value}.\n"
                f"This script is NEVER allowed on staging or production environments.\n"
                f"Detected: APP_ENV={app_env or '(not set)'}, --env={env_arg or '(not set)'}"
            )
            sys.exit(1)

    # Require at least one dev indicator
    if app_env not in ALLOWED_ENVIRONMENTS and env_flag not in ALLOWED_ENVIRONMENTS:
        print(
            f"ERROR: This script can only run in development environment.\n"
            f"Current: APP_ENV={app_env or '(not set)'}, --env={env_arg or '(not set)'}\n"
            f"Use --env=dev or set APP_ENV=development"
        )
        sys.exit(1)

    env_check = env_flag if env_flag in ALLOWED_ENVIRONMENTS else app_env
    print(f"Environment check passed: {env_check}")


def log_reset_start(env_arg: str | None) -> None:
    """Log a structured trace at the start of a reset operation."""
    app_env = os.environ.get("APP_ENV", "(not set)")
    print(
        f"\n{'='*60}\n"
        f"RESET TRACE\n"
        f"  User      : {getpass.getuser()}@{socket.gethostname()}\n"
        f"  Timestamp : {datetime.now().isoformat(timespec='seconds')}\n"
        f"  APP_ENV   : {app_env}\n"
        f"  --env     : {env_arg or '(not set)'}\n"
        f"{'='*60}\n"
    )


# === Seed Data Definitions ===

USERS = [
    # dev-user: used when AUTH_DEV_BYPASS=true so favorites/executions FK to USERS(ID) succeed
    {"username": "dev-user", "display_name": "Dev User", "profile": "DBOPS", "saml_subject": "dev-user@local"},
    {"username": "dbops1", "display_name": "Alice DBOPS", "profile": "DBOPS", "saml_subject": "dbops1@example.com"},
    {"username": "dba1", "display_name": "Bob DBA", "profile": "DBA", "saml_subject": "dba1@example.com"},
    {"username": "user1", "display_name": "Charlie Business", "profile": "BUSINESS", "saml_subject": "user1@example.com"},
]

PROFILES = [
    {"name": "DBOPS", "description": "Database Operations - Full access", "ad_group": "GRP-IDP-DBOPS", "is_admin": 1, "is_auditor": 0, "is_approver": 1},
    {"name": "DBA", "description": "Database Administrator - Execute access", "ad_group": "GRP-IDP-DBA", "is_admin": 0, "is_auditor": 0, "is_approver": 1},
    {"name": "BUSINESS", "description": "Business User - Limited access", "ad_group": "GRP-IDP-BUSINESS", "is_admin": 0, "is_auditor": 1, "is_approver": 0},
]

TAGS = [
    "oracle", "patching", "backup", "dev", "prod", "urgente", "provisioning", "monitoring"
]

INTEGRATIONS = [
    {
        "type": "aap",
        "name": "AAP Demo",
        "base_url": "https://aap-demo.example.com",
        "credential_ref": "vault/aap-demo",
        "icon": "aap",
        "auth_flow": "token",
        "token_url": "https://aap-demo.example.com/api/v2/tokens/",
        "config": json.dumps({"verify_ssl": False}),
    },
    {
        "type": "servicenow",
        "name": "ServiceNow Demo",
        "base_url": "https://demo.service-now.com",
        "credential_ref": "vault/servicenow-demo",
        "icon": "servicenow",
        "auth_flow": "basic",
        "token_url": None,
        "config": None,
    },
]

# Actions with various connectors and configurations
# CATEGORY must match REF_CATEGORIES (provisioning, patching, administration, monitoring, backup, autres)
ACTIONS = [
    {
        "name": "Backup Oracle Database",
        "description": "Execute a full RMAN backup of an Oracle database",
        "category": "backup",
        "engine": "Oracle",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "database_name": {"type": "string", "title": "Database Name"},
                "backup_type": {"type": "string", "enum": ["full", "incremental"], "default": "full"},
            },
            "required": ["database_name"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "low"},
            "STAGING": {"level": "medium"},
            "PROD": {"level": "high"},
        }),
        "default_impact_level": "medium",
        "status": "published",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Recuperation secrets Vault", "type": "prerequisite", "connector_type": "vault", "connector_config": None, "conditional_environments": None},
            {"order": 2, "name": "Execution backup RMAN", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 42}, "conditional_environments": None},
            {"order": 3, "name": "Verification backup", "type": "verification", "connector_type": "none", "connector_config": None, "conditional_environments": None},
        ]),
        "documentation_md": "# Backup Oracle Database\n\nThis action performs a full RMAN backup.\n\n## Prerequisites\n- Database must be in ARCHIVELOG mode\n- Sufficient disk space for backup",
        "tags": ["oracle", "backup"],
    },
    {
        "name": "Apply Oracle Patch",
        "description": "Apply quarterly security patch to Oracle database",
        "category": "patching",
        "engine": "Oracle",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "database_name": {"type": "string"},
                "patch_number": {"type": "string"},
            },
            "required": ["database_name", "patch_number"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "medium"},
            "STAGING": {"level": "high"},
            "PROD": {"level": "critical"},
        }),
        "default_impact_level": "high",
        "status": "published",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Ouverture changement ServiceNow", "type": "prerequisite", "connector_type": "servicenow", "connector_config": None, "conditional_environments": ["STAGING", "PROD"]},
            {"order": 2, "name": "Arret base de donnees", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 50}, "conditional_environments": None},
            {"order": 3, "name": "Application patch OPatch", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 51}, "conditional_environments": None},
            {"order": 4, "name": "Demarrage base de donnees", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 52}, "conditional_environments": None},
            {"order": 5, "name": "Fermeture changement ServiceNow", "type": "verification", "connector_type": "servicenow", "connector_config": None, "conditional_environments": ["STAGING", "PROD"]},
        ]),
        "documentation_md": "# Apply Oracle Patch\n\nQuarterly security patching procedure.",
        "tags": ["oracle", "patching", "urgente"],
    },
    {
        "name": "Create Oracle Schema",
        "description": "Provision a new Oracle schema with standard grants",
        "category": "provisioning",
        "engine": "Oracle",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "schema_name": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]*$"},
                "tablespace": {"type": "string", "default": "USERS"},
                "quota_mb": {"type": "integer", "default": 100, "minimum": 10},
            },
            "required": ["schema_name"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "low"},
            "STAGING": {"level": "low"},
            "PROD": {"level": "medium"},
        }),
        "default_impact_level": "low",
        "status": "published",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Creation schema", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 60}, "conditional_environments": None},
            {"order": 2, "name": "Attribution grants", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 61}, "conditional_environments": None},
        ]),
        "documentation_md": "# Create Oracle Schema\n\nProvisions a new schema with standard security grants.",
        "tags": ["oracle", "provisioning", "dev"],
    },
    {
        "name": "SQL Server Backup",
        "description": "Execute SQL Server database backup",
        "category": "backup",
        "engine": "SQL Server",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "database_name": {"type": "string"},
                "compression": {"type": "boolean", "default": True},
            },
            "required": ["database_name"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "low"},
            "PROD": {"level": "medium"},
        }),
        "default_impact_level": "low",
        "status": "published",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Backup SQL Server", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 70}, "conditional_environments": None},
        ]),
        "documentation_md": "# SQL Server Backup\n\nNative SQL Server backup with compression.",
        "tags": ["backup"],
    },
    {
        "name": "Database Health Check",
        "description": "Run comprehensive health checks on database",
        "category": "monitoring",
        "engine": "Oracle",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "database_name": {"type": "string"},
                "check_level": {"type": "string", "enum": ["basic", "full"], "default": "basic"},
            },
            "required": ["database_name"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "low"},
            "STAGING": {"level": "low"},
            "PROD": {"level": "low"},
        }),
        "default_impact_level": "low",
        "status": "published",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Collecte metriques", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 80}, "conditional_environments": None},
            {"order": 2, "name": "Analyse alertes", "type": "verification", "connector_type": "none", "connector_config": None, "conditional_environments": None},
        ]),
        "documentation_md": "# Database Health Check\n\nComprehensive health monitoring for Oracle databases.",
        "tags": ["oracle", "monitoring"],
    },
    {
        "name": "Refresh Dev Database",
        "description": "Clone production data to development environment",
        "category": "provisioning",
        "engine": "Oracle",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "source_db": {"type": "string"},
                "target_db": {"type": "string"},
                "scramble_data": {"type": "boolean", "default": True},
            },
            "required": ["source_db", "target_db"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "medium"},
        }),
        "default_impact_level": "medium",
        "status": "published",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Export source", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 90}, "conditional_environments": None},
            {"order": 2, "name": "Import target", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 91}, "conditional_environments": None},
            {"order": 3, "name": "Data scrambling", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 92}, "conditional_environments": None},
        ]),
        "documentation_md": "# Refresh Dev Database\n\nClone and anonymize production data for development.",
        "tags": ["oracle", "dev", "provisioning"],
    },
    {
        "name": "Emergency Stop Database",
        "description": "Immediate shutdown of database instance",
        "category": "administration",
        "engine": "Oracle",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "database_name": {"type": "string"},
                "shutdown_mode": {"type": "string", "enum": ["immediate", "abort"], "default": "immediate"},
            },
            "required": ["database_name"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "medium"},
            "STAGING": {"level": "high"},
            "PROD": {"level": "critical"},
        }),
        "default_impact_level": "critical",
        "status": "published",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Arret immediat", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 100}, "conditional_environments": None},
        ]),
        "documentation_md": "# Emergency Stop Database\n\n**WARNING**: Use only in emergency situations.",
        "tags": ["oracle", "urgente"],
    },
    {
        "name": "Archive Log Cleanup",
        "description": "Clean up old archive logs to free disk space",
        "category": "administration",
        "engine": "Oracle",
        "platform": "AAP",
        "parameters_schema": json.dumps({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "database_name": {"type": "string"},
                "retention_days": {"type": "integer", "default": 7, "minimum": 1},
            },
            "required": ["database_name"],
        }),
        "impact_rules": json.dumps({
            "DEV": {"level": "low"},
            "STAGING": {"level": "low"},
            "PROD": {"level": "medium"},
        }),
        "default_impact_level": "low",
        "status": "draft",
        "execution_steps": json.dumps([
            {"order": 1, "name": "Identification archives", "type": "prerequisite", "connector_type": "none", "connector_config": None, "conditional_environments": None},
            {"order": 2, "name": "Suppression archives", "type": "execution", "connector_type": "aap", "connector_config": {"job_template_id": 110}, "conditional_environments": None},
        ]),
        "documentation_md": "# Archive Log Cleanup\n\nAutomated cleanup of Oracle archive logs.",
        "tags": ["oracle", "monitoring"],
    },
]

# Execution status distribution for realistic dashboard
EXECUTION_STATUSES = [
    ("COMPLETED", 6),
    ("FAILED", 3),
    ("RUNNING", 2),
    ("SUBMITTED", 2),
    ("CANCELLED", 1),
    ("REJECTED", 1),  # PENDING_APPROVAL deprecated (ADR-007, story 78.14) — removed from CHK_EXECUTION_STATUS
]


# === Database Operations ===

def has_seed_data(conn: oracledb.Connection) -> bool:
    """Return True if seed data already exists (e.g. USERS has rows)."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM USERS")
        count = cursor.fetchone()[0]
        return count > 0
    finally:
        cursor.close()


def reset_data(conn: oracledb.Connection) -> None:
    """Delete all seeded data in reverse FK order (children before parents)."""
    print("Resetting existing data...")
    cursor = conn.cursor()
    # Order: delete children first to satisfy FK constraints.
    # RECURRING_PATTERNS → SCHEDULED_EXECUTIONS;
    # Orchestration tables (FK → EXECUTIONS, RUNNABLE_STEPS also FK → EXECUTION_STEPS):
    #   WORKFLOW_EVENT_COUNTER → EXECUTIONS (OneToOne CASCADE, migration 0015);
    #   WORKFLOW_EVENTS, WORKFLOW_COMMANDS, EXECUTION_OUTBOX → EXECUTIONS;
    #   RUNNABLE_STEPS → EXECUTION_STEPS (OneToOne) + EXECUTIONS (both CASCADE);
    # EXECUTION_STEPS, EXECUTION_TARGETS → EXECUTIONS;
    # SCHEDULED_EXECUTIONS → EXECUTIONS, USERS, ACTIONS_CATALOG; EXECUTIONS → USERS, ACTIONS_CATALOG;
    # USER_FAVORITES → USERS, ACTIONS_CATALOG; ACTION_TAGS → ACTIONS_CATALOG, TAGS;
    # ACTIONS_CATALOG → INTEGRATIONS, USERS; PROFILE_* → PROFILES
    tables = [
        "RECURRING_PATTERNS",
        # Orchestration tables — all FK → EXECUTIONS; RUNNABLE_STEPS also FK → EXECUTION_STEPS
        "WORKFLOW_EVENT_COUNTER",  # OneToOne CASCADE → EXECUTIONS (migration 0015)
        "WORKFLOW_EVENTS",
        "RUNNABLE_STEPS",      # must precede both EXECUTION_STEPS and EXECUTIONS
        "WORKFLOW_COMMANDS",
        "EXECUTION_OUTBOX",
        "EXECUTION_STEPS",
        "EXECUTION_TARGETS",
        "SCHEDULED_EXECUTIONS",
        "EXECUTIONS",
        "USER_FAVORITES",
        "PROFILE_TARGET_PERMISSIONS",
        "PROFILE_ACTION_PERMISSIONS",
        "ACTION_TAGS",
        "TAGS",
        "ACTIONS_CATALOG",
        "INTEGRATIONS",
        "PROFILES",
        "USERS",
    ]
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"  Cleared {table}: {cursor.rowcount} rows")
        except oracledb.DatabaseError as e:
            print(f"  Warning: Could not clear {table}: {e}")
    conn.commit()
    cursor.close()


def seed_users(conn: oracledb.Connection) -> dict[str, int]:
    """Insert users and return username -> id mapping."""
    print("Seeding USERS...")
    cursor = conn.cursor()
    user_ids = {}

    for user in USERS:
        out_id_var = cursor.var(int)
        cursor.execute(
            """
            INSERT INTO USERS (USERNAME, DISPLAY_NAME, PROFILE, SAML_SUBJECT)
            VALUES (:username, :display_name, :profile, :saml_subject)
            RETURNING ID INTO :out_id
            """,
            {
                "username": user["username"],
                "display_name": user["display_name"],
                "profile": user["profile"],
                "saml_subject": user["saml_subject"],
                "out_id": out_id_var,
            },
        )
        user_id = out_id_var.getvalue()[0]
        user_ids[user["username"]] = user_id
        print(f"  Created user: {user['username']} (ID={user_id})")

    conn.commit()
    cursor.close()
    return user_ids


def seed_profiles(conn: oracledb.Connection) -> dict[str, int]:
    """Insert profiles and return name -> id mapping."""
    print("Seeding PROFILES...")
    cursor = conn.cursor()
    profile_ids = {}

    for profile in PROFILES:
        out_id_var = cursor.var(int)
        cursor.execute(
            """
            INSERT INTO PROFILES (NAME, DESCRIPTION, AD_GROUP, IS_ADMIN, IS_AUDITOR, IS_APPROVER)
            VALUES (:name, :description, :ad_group, :is_admin, :is_auditor, :is_approver)
            RETURNING ID INTO :out_id
            """,
            {
                "name": profile["name"],
                "description": profile["description"],
                "ad_group": profile["ad_group"],
                "is_admin": profile["is_admin"],
                "is_auditor": profile["is_auditor"],
                "is_approver": profile["is_approver"],
                "out_id": out_id_var,
            },
        )
        profile_id = out_id_var.getvalue()[0]
        profile_ids[profile["name"]] = profile_id
        print(f"  Created profile: {profile['name']} (ID={profile_id})")

    conn.commit()
    cursor.close()
    return profile_ids


def seed_tags(conn: oracledb.Connection) -> dict[str, int]:
    """Insert tags and return name -> id mapping."""
    print("Seeding TAGS...")
    cursor = conn.cursor()
    tag_ids = {}

    for tag_name in TAGS:
        out_id_var = cursor.var(int)
        cursor.execute(
            """
            INSERT INTO TAGS (NAME)
            VALUES (:name)
            RETURNING ID INTO :out_id
            """,
            {"name": tag_name, "out_id": out_id_var},
        )
        tag_id = out_id_var.getvalue()[0]
        tag_ids[tag_name] = tag_id
        print(f"  Created tag: {tag_name} (ID={tag_id})")

    conn.commit()
    cursor.close()
    return tag_ids


def seed_integrations(conn: oracledb.Connection) -> dict[str, int]:
    """Insert integrations and return name -> id mapping."""
    print("Seeding INTEGRATIONS...")
    cursor = conn.cursor()
    integration_ids = {}

    for integ in INTEGRATIONS:
        out_id_var = cursor.var(int)
        cursor.execute(
            """
            INSERT INTO INTEGRATIONS (TYPE, NAME, BASE_URL, CREDENTIAL_REF, ICON, AUTH_FLOW, TOKEN_URL, CONFIG)
            VALUES (:type, :name, :base_url, :credential_ref, :icon, :auth_flow, :token_url, :config)
            RETURNING ID INTO :out_id
            """,
            {
                "type": integ["type"],
                "name": integ["name"],
                "base_url": integ["base_url"],
                "credential_ref": integ["credential_ref"],
                "icon": integ["icon"],
                "auth_flow": integ["auth_flow"],
                "token_url": integ["token_url"],
                "config": integ["config"],
                "out_id": out_id_var,
            },
        )
        integ_id = out_id_var.getvalue()[0]
        integration_ids[integ["name"]] = integ_id
        print(f"  Created integration: {integ['name']} ({integ['type']}) (ID={integ_id})")

    conn.commit()
    cursor.close()
    return integration_ids


def seed_actions(conn: oracledb.Connection, user_ids: dict[str, int], tag_ids: dict[str, int]) -> dict[str, int]:
    """Insert actions and action_tags, return name -> id mapping."""
    print("Seeding ACTIONS_CATALOG...")
    cursor = conn.cursor()
    action_ids = {}

    # Use dbops1 as creator
    creator_id = user_ids["dbops1"]

    for action in ACTIONS:
        out_id_var = cursor.var(int)
        cursor.execute(
            """
            INSERT INTO ACTIONS_CATALOG
            (NAME, DESCRIPTION, CATEGORY, ENGINE, PLATFORM, PARAMETERS_SCHEMA, IMPACT_RULES,
             DEFAULT_IMPACT_LEVEL, STATUS, EXECUTION_STEPS,
             DOCUMENTATION_MD, CREATED_BY)
            VALUES
            (:name, :description, :category, :engine, :platform, :parameters_schema, :impact_rules,
             :default_impact_level, :status, :execution_steps,
             :documentation_md, :created_by)
            RETURNING ID INTO :out_id
            """,
            {
                "name": action["name"],
                "description": action["description"],
                "category": action["category"],
                "engine": action["engine"],
                "platform": action["platform"],
                "parameters_schema": action["parameters_schema"],
                "impact_rules": action["impact_rules"],
                "default_impact_level": action["default_impact_level"],
                "status": action["status"],
                "execution_steps": action["execution_steps"],
                "documentation_md": action["documentation_md"],
                "created_by": creator_id,
                "out_id": out_id_var,
            },
        )
        action_id = out_id_var.getvalue()[0]
        action_ids[action["name"]] = action_id
        print(f"  Created action: {action['name']} ({action['status']}) (ID={action_id})")

        # Insert action_tags
        for tag_name in action["tags"]:
            if tag_name in tag_ids:
                cursor.execute(
                    "INSERT INTO ACTION_TAGS (ACTION_ID, TAG_ID) VALUES (:action_id, :tag_id)",
                    {"action_id": action_id, "tag_id": tag_ids[tag_name]},
                )

    conn.commit()
    cursor.close()
    return action_ids


def seed_profile_permissions(conn: oracledb.Connection, profile_ids: dict[str, int], action_ids: dict[str, int]) -> None:
    """Insert profile action and target permissions."""
    print("Seeding PROFILE_ACTION_PERMISSIONS and PROFILE_TARGET_PERMISSIONS...")
    cursor = conn.cursor()

    # DBOPS: ALL actions, ALL targets, ALL environments
    cursor.execute(
        """
        INSERT INTO PROFILE_ACTION_PERMISSIONS (PROFILE_ID, PERMISSION_TYPE, ENVIRONMENTS_JSON)
        VALUES (:profile_id, 'ALL', :environments)
        """,
        {
            "profile_id": profile_ids["DBOPS"],
            "environments": json.dumps(["dev", "staging", "prod"]),
        },
    )
    cursor.execute(
        """
        INSERT INTO PROFILE_TARGET_PERMISSIONS (PROFILE_ID, PERMISSION_TYPE)
        VALUES (:profile_id, 'ALL')
        """,
        {"profile_id": profile_ids["DBOPS"]},
    )
    print("  DBOPS: ALL actions, ALL targets")

    # DBA: PATTERN by tags (oracle, backup), dev/staging only
    cursor.execute(
        """
        INSERT INTO PROFILE_ACTION_PERMISSIONS (PROFILE_ID, PERMISSION_TYPE, TAG_PATTERNS_JSON, ENVIRONMENTS_JSON)
        VALUES (:profile_id, 'PATTERN', :tags, :environments)
        """,
        {
            "profile_id": profile_ids["DBA"],
            "tags": json.dumps(["oracle", "backup"]),
            "environments": json.dumps(["dev", "staging"]),
        },
    )
    cursor.execute(
        """
        INSERT INTO PROFILE_TARGET_PERMISSIONS (PROFILE_ID, PERMISSION_TYPE, TARGET_PATTERNS_JSON)
        VALUES (:profile_id, 'PATTERN', :patterns)
        """,
        {
            "profile_id": profile_ids["DBA"],
            "patterns": json.dumps(["dba-*", "oracle-*"]),
        },
    )
    print("  DBA: PATTERN (oracle, backup tags), dev/staging envs")

    # BUSINESS: LIST specific actions, dev only
    business_action_ids = [
        action_ids["Database Health Check"],
        action_ids["Backup Oracle Database"],
    ]
    cursor.execute(
        """
        INSERT INTO PROFILE_ACTION_PERMISSIONS (PROFILE_ID, PERMISSION_TYPE, ACTION_IDS_JSON, ENVIRONMENTS_JSON)
        VALUES (:profile_id, 'LIST', :action_ids, :environments)
        """,
        {
            "profile_id": profile_ids["BUSINESS"],
            "action_ids": json.dumps(business_action_ids),
            "environments": json.dumps(["dev"]),
        },
    )
    cursor.execute(
        """
        INSERT INTO PROFILE_TARGET_PERMISSIONS (PROFILE_ID, PERMISSION_TYPE, TARGET_NAMES_JSON)
        VALUES (:profile_id, 'LIST', :targets)
        """,
        {
            "profile_id": profile_ids["BUSINESS"],
            "targets": json.dumps(["business-db01", "business-db02"]),
        },
    )
    print("  BUSINESS: LIST (2 actions), dev env only")

    conn.commit()
    cursor.close()


def seed_favorites(conn: oracledb.Connection, user_ids: dict[str, int], action_ids: dict[str, int]) -> None:
    """Insert user favorites."""
    print("Seeding USER_FAVORITES...")
    cursor = conn.cursor()

    # dbops1 favorites: Backup, Patching, Health Check
    favorites = [
        (user_ids["dbops1"], action_ids["Backup Oracle Database"]),
        (user_ids["dbops1"], action_ids["Apply Oracle Patch"]),
        (user_ids["dbops1"], action_ids["Database Health Check"]),
        (user_ids["dba1"], action_ids["Backup Oracle Database"]),
        (user_ids["dba1"], action_ids["Create Oracle Schema"]),
    ]

    for user_id, action_id in favorites:
        cursor.execute(
            "INSERT INTO USER_FAVORITES (USER_ID, ACTION_ID) VALUES (:user_id, :action_id)",
            {"user_id": user_id, "action_id": action_id},
        )

    print(f"  Created {len(favorites)} favorites")
    conn.commit()
    cursor.close()


def seed_executions(conn: oracledb.Connection, user_ids: dict[str, int], action_ids: dict[str, int]) -> list[int]:
    """Insert executions with various statuses, return list of execution IDs."""
    print("Seeding EXECUTIONS...")
    cursor = conn.cursor()
    execution_ids = []

    # Get list of published actions for executions
    published_actions = [
        (name, aid) for name, aid in action_ids.items()
        if any(a["name"] == name and a["status"] == "published" for a in ACTIONS)
    ]

    users = list(user_ids.values())
    environments = ["dev", "staging", "prod"]
    now = datetime.now()
    exec_count = 0

    for status, count in EXECUTION_STATUSES:
        for i in range(count):
            action_name, action_id = published_actions[exec_count % len(published_actions)]
            user_id = users[exec_count % len(users)]
            env = environments[exec_count % len(environments)]

            # All executions in last 24h so dashboard stats match the "Activité récente" table
            # (executions_jour, taux_succes 24h, en cours, en erreur 24h align with visible rows)
            hours_ago = (exec_count * 2) % 24  # 0, 2, 4, ... 22 hours ago
            created_at = now - timedelta(hours=hours_ago)

            # Set started_at and completed_at based on status
            started_at = None
            completed_at = None
            if status in ("RUNNING", "COMPLETED", "FAILED", "CANCELLED"):
                started_at = created_at + timedelta(seconds=30)
            if status in ("COMPLETED", "FAILED", "CANCELLED"):
                completed_at = started_at + timedelta(minutes=2)

            parameters = json.dumps({"database_name": f"db_{exec_count:02d}", "test_param": f"value_{i}"})
            servicenow_id = f"CHG00{exec_count:05d}" if status in ("COMPLETED", "RUNNING") and env != "dev" else None

            out_id_var = cursor.var(int)
            cursor.execute(
                """
                INSERT INTO EXECUTIONS
                (ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, STATUS,
                 SERVICENOW_CHANGE_ID, STARTED_AT, COMPLETED_AT, CREATED_AT)
                VALUES
                (:action_id, :user_id, :environment, :parameters, :status,
                 :servicenow_change_id, :started_at, :completed_at, :created_at)
                RETURNING ID INTO :out_id
                """,
                {
                    "action_id": action_id,
                    "user_id": user_id,
                    "environment": env,
                    "parameters": parameters,
                    "status": status,
                    "servicenow_change_id": servicenow_id,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "created_at": created_at,
                    "out_id": out_id_var,
                },
            )
            exec_id = out_id_var.getvalue()[0]
            execution_ids.append(exec_id)
            print(f"  Created execution: {action_name[:30]} ({status}) (ID={exec_id})")
            exec_count += 1

    conn.commit()
    cursor.close()
    return execution_ids


def seed_execution_steps(conn: oracledb.Connection, execution_ids: list[int]) -> None:
    """Insert execution steps for some executions (for timeline testing)."""
    print("Seeding EXECUTION_STEPS...")
    cursor = conn.cursor()
    step_count = 0

    # Add steps to first 5 executions for detailed timeline testing
    step_templates = [
        ("Recuperation secrets Vault", "vault", "COMPLETED"),
        ("Ouverture changement ServiceNow", "servicenow", "COMPLETED"),
        ("Execution action principale", "platform", "RUNNING"),
        ("Verification post-execution", "verification", "PENDING"),
    ]

    for i, exec_id in enumerate(execution_ids[:5]):
        # Get execution status to determine step statuses
        cursor.execute("SELECT STATUS FROM EXECUTIONS WHERE ID = :id", {"id": exec_id})
        row = cursor.fetchone()
        exec_status = row[0] if row else "SUBMITTED"

        for step_order, (step_name, step_type, default_status) in enumerate(step_templates, start=1):
            # Adjust step status based on execution status
            if exec_status == "COMPLETED":
                step_status = "COMPLETED"
            elif exec_status == "FAILED":
                step_status = "FAILED" if step_order == 3 else ("COMPLETED" if step_order < 3 else "SKIPPED")
            elif exec_status == "RUNNING":
                step_status = "COMPLETED" if step_order < 3 else ("RUNNING" if step_order == 3 else "PENDING")
            elif exec_status == "REJECTED":
                # Rejected before execution: submission steps done, execution step and beyond skipped
                step_status = "COMPLETED" if step_order < 3 else "SKIPPED"
            else:
                step_status = default_status

            started_at = datetime.now() - timedelta(minutes=10 - step_order) if step_status != "PENDING" else None
            completed_at = datetime.now() - timedelta(minutes=9 - step_order) if step_status in ("COMPLETED", "FAILED", "SKIPPED") else None

            output = json.dumps({"result": "success", "duration_ms": 1500 + step_order * 100}) if step_status == "COMPLETED" else None
            error_msg = "Connection timeout to platform" if step_status == "FAILED" else None
            platform_job_id = f"JOB-{exec_id}-{step_order}" if step_type == "platform" and step_status != "PENDING" else None

            cursor.execute(
                """
                INSERT INTO EXECUTION_STEPS
                (EXECUTION_ID, STEP_ORDER, STEP_NAME, STEP_TYPE, STATUS,
                 STARTED_AT, COMPLETED_AT, OUTPUT, PLATFORM_JOB_ID, ERROR_MESSAGE)
                VALUES
                (:execution_id, :step_order, :step_name, :step_type, :status,
                 :started_at, :completed_at, :output, :platform_job_id, :error_message)
                """,
                {
                    "execution_id": exec_id,
                    "step_order": step_order,
                    "step_name": step_name,
                    "step_type": step_type,
                    "status": step_status,
                    "started_at": started_at,
                    "completed_at": completed_at,
                    "output": output,
                    "platform_job_id": platform_job_id,
                    "error_message": error_msg,
                },
            )
            step_count += 1

    print(f"  Created {step_count} execution steps for {min(5, len(execution_ids))} executions")
    conn.commit()
    cursor.close()


def print_summary(
    conn: oracledb.Connection,
    user_ids: dict,
    profile_ids: dict,
    tag_ids: dict,
    integration_ids: dict,
    action_ids: dict,
    execution_ids: list,
) -> None:
    """Print summary of seeded data (counts from actual DB for executions)."""
    print("\n" + "=" * 60)
    print("SEED SUMMARY")
    print("=" * 60)
    print(f"Users:        {len(user_ids)}")
    print(f"Profiles:     {len(profile_ids)}")
    print(f"Tags:         {len(tag_ids)}")
    print(f"Integrations: {len(integration_ids)}")
    print(f"Actions:      {len(action_ids)}")
    print(f"Executions:   {len(execution_ids)}")
    # Actual counts by status from DB
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT STATUS, COUNT(*) FROM EXECUTIONS GROUP BY STATUS ORDER BY STATUS"
        )
        for status, count in cur.fetchall():
            print(f"  - {status}: {count}")
    finally:
        cur.close()
    print("=" * 60)
    print("\nFrontend test coverage:")
    print("  - Catalogue: liste, filtres tags, favoris, fiche detail")
    print("  - Admin: actions (draft/published), profils, integrations")
    print("  - Executions: liste avec tous statuts, detail timeline/logs")
    print("  - Dashboard: stats et activite recente avec donnees")
    print("=" * 60)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed development database with test data",
        epilog="IMPORTANT: For development environment only!",
    )
    parser.add_argument(
        "--env",
        type=str,
        help="Environment (must be 'dev' or 'development')",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing data before seeding",
    )
    args = parser.parse_args()

    # Check environment
    check_environment(args.env)

    # --reset requires BOTH APP_ENV and --env to be explicitly set (user story 80.2)
    if args.reset:
        app_env_valid = os.environ.get("APP_ENV", "").lower() in ALLOWED_ENVIRONMENTS
        env_arg_valid = bool(args.env) and args.env.lower() in ALLOWED_ENVIRONMENTS
        if not app_env_valid or not env_arg_valid:
            print(
                "ERROR: --reset requires BOTH APP_ENV and --env to be explicitly set to a dev value.\n"
                f"Current: APP_ENV={os.environ.get('APP_ENV') or '(not set)'}, --env={args.env or '(not set)'}\n"
                "Example: APP_ENV=development python3 seed_dev_data.py --env=dev --reset"
            )
            sys.exit(1)

    print("\nConnecting to Oracle database...")
    try:
        conn = get_connection()
        print(f"Connected: {conn.dsn}")
    except oracledb.DatabaseError as e:
        err_msg = str(e).lower()
        print(f"ERROR: Failed to connect to database: {e}")
        if "ora-01017" in err_msg or "invalid credential" in err_msg or "logon denied" in err_msg:
            print(
                "\nHint: ORA-01017 usually means wrong password. "
                "Ensure ORACLE_PASSWORD matches idp_app in the database.\n"
                "  - Init script (database/init/01-create-idp-app-user.sql) uses Oracle123!\n"
                "  - If you ran an older init with 'changeme', try: ORACLE_PASSWORD=changeme python3 seed_dev_data.py --env=dev\n"
                "  - To change password: sqlplus sys/Oracle123!@//localhost:1521/FREEPDB1 as sysdba\n"
                "    Then: ALTER USER idp_app IDENTIFIED BY \"Oracle123!\";"
            )
        sys.exit(1)

    try:
        # Reset if requested
        if args.reset:
            log_reset_start(args.env)
            reset_data(conn)
        else:
            if has_seed_data(conn):
                print(
                    "ERROR: Database already contains seed data. Refusing to insert to avoid duplicate key errors.\n"
                    "Use --reset to clear existing data before seeding, or run this script only once on an empty database."
                )
                sys.exit(1)

        # Seed in FK order
        user_ids = seed_users(conn)
        profile_ids = seed_profiles(conn)
        tag_ids = seed_tags(conn)
        integration_ids = seed_integrations(conn)
        action_ids = seed_actions(conn, user_ids, tag_ids)
        seed_profile_permissions(conn, profile_ids, action_ids)
        seed_favorites(conn, user_ids, action_ids)
        execution_ids = seed_executions(conn, user_ids, action_ids)
        seed_execution_steps(conn, execution_ids)

        # Summary
        print_summary(
            conn, user_ids, profile_ids, tag_ids, integration_ids, action_ids, execution_ids
        )
        print("\nSeed completed successfully!")

    except oracledb.DatabaseError as e:
        print(f"\nERROR: Database operation failed: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
