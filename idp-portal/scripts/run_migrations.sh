#!/usr/bin/env bash
# Run database migrations sequentially via python-oracledb.
# Usage: ./scripts/run_migrations.sh
#
# Environment variables required:
#   ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD
#
# AC #6: Executes SQL migration files in order (V001, V002, ...)
# Stops on first error to prevent inconsistent database state.
#
set -euo pipefail

MIGRATIONS_DIR="$(dirname "$0")/../database/migrations"

if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "❌ Error: Migrations directory not found: $MIGRATIONS_DIR"
    exit 1
fi

echo "Running migrations from $MIGRATIONS_DIR ..."

# Check required environment variables
if [ -z "${ORACLE_DSN:-}" ] || [ -z "${ORACLE_USER:-}" ] || [ -z "${ORACLE_PASSWORD:-}" ]; then
    echo "❌ Error: Required environment variables not set: ORACLE_DSN, ORACLE_USER, ORACLE_PASSWORD"
    exit 1
fi

# Process each SQL file in sorted order
for sql_file in $(ls "$MIGRATIONS_DIR"/*.sql 2>/dev/null | sort); do
    echo "  Applying: $(basename "$sql_file")"
    
    # Use python-oracledb to execute the entire SQL file.
    # Pass path via env to avoid heredoc variable-expansion issues (single quotes).
    export CURRENT_MIGRATION="$sql_file"
    python3 <<'PYEOF'
import oracledb
import os
import sys

try:
    conn = oracledb.connect(
        user=os.environ['ORACLE_USER'],
        password=os.environ['ORACLE_PASSWORD'],
        dsn=os.environ['ORACLE_DSN'],
    )
    cursor = conn.cursor()
    
    fpath = os.environ['CURRENT_MIGRATION']
    with open(fpath, 'r') as f:
        sql_content = f.read()
    
    # Execute the entire script (Oracle handles multiple statements)
    try:
        # For Oracle, we can execute the entire script
        # Split by semicolon but preserve statements that span multiple lines
        statements = []
        current_stmt = []
        for line in sql_content.split('\n'):
            line = line.strip()
            if not line or line.startswith('--'):
                continue
            current_stmt.append(line)
            if line.endswith(';'):
                stmt = ' '.join(current_stmt).rstrip(';').strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []
        
        # Execute each statement
        for stmt in statements:
            try:
                cursor.execute(stmt)
                print(f'    ✓ Executed: {stmt[:50]}...')
            except oracledb.DatabaseError as e:
                error_msg = str(e)
                # Check if it's a "name is already used" error (object exists)
                if 'ORA-00955' in error_msg or 'ORA-00942' in error_msg:
                    print(f'    ⚠ Skipped (already exists): {stmt[:50]}...')
                else:
                    print(f'    ❌ Error: {error_msg}', file=sys.stderr)
                    print(f'    Statement: {stmt[:100]}', file=sys.stderr)
                    conn.rollback()
                    conn.close()
                    sys.exit(1)
        
        conn.commit()
        print(f'  ✓ Migration {os.path.basename(fpath)} completed successfully')
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
        
except oracledb.DatabaseError as e:
    print(f'❌ Database error: {e}', file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'❌ Unexpected error: {e}', file=sys.stderr)
    sys.exit(1)
PYEOF
    
    if [ $? -ne 0 ]; then
        echo "❌ Migration failed: $(basename "$sql_file")"
        echo "Stopping migrations to prevent inconsistent database state."
        exit 1
    fi
done

echo "✅ All migrations completed successfully."
