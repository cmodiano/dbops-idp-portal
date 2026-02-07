#!/bin/bash
# Story 17.9: Check mypy errors against baseline
# Usage: scripts/check_mypy_baseline.sh
# Exit 0: No new errors (PASS)
# Exit 1: New errors introduced (FAIL)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BASELINE_FILE="$PROJECT_DIR/.mypy-baseline-count"
REPORT_FILE="$PROJECT_DIR/mypy-report.txt"

cd "$PROJECT_DIR"

# Validate baseline file exists and is valid
if [ ! -f "$BASELINE_FILE" ]; then
    echo "❌ Baseline file not found: .mypy-baseline-count"
    echo "Run: scripts/generate_mypy_baseline.sh"
    exit 1
fi

BASELINE_COUNT=$(cat "$BASELINE_FILE" | tr -d '[:space:]')

# Validate baseline count is a non-negative integer
if ! [[ "$BASELINE_COUNT" =~ ^[0-9]+$ ]]; then
    echo "❌ Invalid baseline count in .mypy-baseline-count: '$BASELINE_COUNT'"
    echo "Expected a non-negative integer. Run: scripts/generate_mypy_baseline.sh"
    exit 1
fi

# Validate environment: Check if django-stubs is installed
echo "Validating environment..."
if ! python3 -c "import mypy_django_plugin" 2>/dev/null; then
    echo "❌ django-stubs not installed! Mypy Django plugin missing."
    echo "Install dependencies: uv pip install -r requirements-dev.lock --system"
    exit 1
fi
if ! python3 -c "import mypy_drf_plugin" 2>/dev/null; then
    echo "❌ djangorestframework-stubs not installed! Mypy DRF plugin missing."
    echo "Install dependencies: uv pip install -r requirements-dev.lock --system"
    exit 1
fi
echo "✓ Environment validated (django-stubs and djangorestframework-stubs installed)"

echo "Running mypy..."
export DJANGO_SETTINGS_MODULE=idp_backend.settings
mypy . --no-error-summary 2>&1 | grep ": error:" > "$REPORT_FILE" || true

CURRENT_COUNT=$(wc -l < "$REPORT_FILE" | tr -d ' ')

echo "================================================="
echo "Mypy Type Checking Report"
echo "================================================="
echo "Baseline errors: $BASELINE_COUNT"
echo "Current errors:  $CURRENT_COUNT"

if [ "$CURRENT_COUNT" -gt "$BASELINE_COUNT" ]; then
    echo "================================================="
    echo "❌ FAILURE: New type errors introduced!"
    echo "================================================="
    echo "New errors: $(($CURRENT_COUNT - $BASELINE_COUNT))"
    echo ""
    echo "Please fix the new type errors or update baseline if intentional:"
    echo "  scripts/generate_mypy_baseline.sh"
    echo ""
    echo "Recent errors:"
    tail -n 20 "$REPORT_FILE"
    exit 1
elif [ "$CURRENT_COUNT" -lt "$BASELINE_COUNT" ]; then
    echo "================================================="
    echo "🎉 SUCCESS: Type errors reduced!"
    echo "================================================="
    echo "Fixed errors: $(($BASELINE_COUNT - $CURRENT_COUNT))"
    echo ""
    echo "Please update baseline to lock in improvement:"
    echo "  scripts/generate_mypy_baseline.sh"
    echo "  git add .mypy-baseline-count"
    echo "  git commit -m 'chore: update mypy baseline'"
else
    echo "================================================="
    echo "✅ PASS: No new type errors"
    echo "================================================="
fi

echo ""
echo "Full mypy report available in mypy-report.txt"
