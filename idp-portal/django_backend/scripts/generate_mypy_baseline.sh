#!/bin/bash
# Story 17.9: Generate mypy baseline error count
# Usage: scripts/generate_mypy_baseline.sh
# Output: .mypy-baseline-count file (commit this file)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BASELINE_FILE="$PROJECT_DIR/.mypy-baseline-count"
REPORT_FILE="$PROJECT_DIR/mypy-report.txt"

cd "$PROJECT_DIR"

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

echo "Running mypy to generate baseline..."
export DJANGO_SETTINGS_MODULE=idp_backend.settings
mypy . --no-error-summary 2>&1 | grep ": error:" > "$REPORT_FILE" || true

ERROR_COUNT=$(wc -l < "$REPORT_FILE" | tr -d ' ')

echo "================================================="
echo "Mypy Baseline Generated"
echo "================================================="
echo "Total mypy errors found: $ERROR_COUNT"
echo "$ERROR_COUNT" > "$BASELINE_FILE"

echo ""
echo "Baseline file: .mypy-baseline-count"
echo "Full report:   mypy-report.txt"
echo ""
echo "Next steps:"
echo "  git add .mypy-baseline-count"
echo "  git commit -m 'chore: update mypy baseline ($ERROR_COUNT errors)'"
