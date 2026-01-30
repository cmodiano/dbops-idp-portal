#!/usr/bin/env bash
# Run database migrations via Flyway (replaces legacy python-oracledb runner).
# Usage: ./scripts/run_migrations.sh
#
# Environment variables required (same as backend):
#   ORACLE_DSN (e.g. localhost:1521/XEPDB1)
#   ORACLE_USER, ORACLE_PASSWORD
#
# Flyway uses flyway_schema_history; migrations in database/migrations/ (V001__desc.sql).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATIONS_DIR="$ROOT_DIR/database/migrations"

if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "❌ Error: Migrations directory not found: $MIGRATIONS_DIR"
    exit 1
fi

if [ -z "${ORACLE_DSN:-}" ] || [ -z "${ORACLE_USER:-}" ] || [ -z "${ORACLE_PASSWORD:-}" ]; then
    echo "❌ Error: Required environment variables not set: ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD"
    exit 1
fi

# JDBC URL: ORACLE_DSN is host:port/service -> jdbc:oracle:thin:@//host:port/service
FLYWAY_URL="jdbc:oracle:thin:@//${ORACLE_DSN}"
export FLYWAY_URL
export FLYWAY_USER="$ORACLE_USER"
export FLYWAY_PASSWORD="$ORACLE_PASSWORD"
export FLYWAY_LOCATIONS="filesystem:database/migrations"

echo "Running Flyway migrations from $MIGRATIONS_DIR ..."
echo "  URL: $FLYWAY_URL"

cd "$ROOT_DIR"

if command -v flyway >/dev/null 2>&1; then
    flyway -configFiles=flyway.conf migrate
else
    # Use Flyway Docker image (no local Java/CLI required)
    docker run --rm \
        -v "$ROOT_DIR:/work" \
        -w /work \
        -e FLYWAY_URL \
        -e FLYWAY_USER \
        -e FLYWAY_PASSWORD \
        -e FLYWAY_LOCATIONS \
        flyway/flyway:10-alpine \
        -configFiles=flyway.conf \
        migrate
fi

echo "✅ Migrations completed successfully."
