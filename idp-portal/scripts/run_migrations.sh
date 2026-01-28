#!/usr/bin/env bash
# Run database migrations sequentially via python-oracledb.
# Usage: ./scripts/run_migrations.sh
#
# Environment variables required:
#   ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD
#
set -euo pipefail

MIGRATIONS_DIR="$(dirname "$0")/../database/migrations"

echo "Running migrations from $MIGRATIONS_DIR ..."

for sql_file in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
  echo "  Applying: $(basename "$sql_file")"
  python3 -c "
import oracledb, os, sys
conn = oracledb.connect(
    user=os.environ['ORACLE_USER'],
    password=os.environ['ORACLE_PASSWORD'],
    dsn=os.environ['ORACLE_DSN'],
)
cursor = conn.cursor()
with open('$sql_file') as f:
    stmts = [s.strip() for s in f.read().split(';') if s.strip() and not s.strip().startswith('--')]
for stmt in stmts:
    try:
        cursor.execute(stmt)
        print(f'    OK: {stmt[:60]}...')
    except oracledb.DatabaseError as e:
        print(f'    WARN: {e}', file=sys.stderr)
conn.commit()
conn.close()
"
done

echo "Migrations complete."
