#!/bin/bash
# Run Django backend tests with coverage
# Story M.9: Tests unitaires et d'intégration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Django Backend Test Runner ===${NC}"
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: No virtual environment detected.${NC}"
    echo "Consider activating your virtual environment first."
    echo ""
fi

# Parse arguments
COVERAGE=false
INTEGRATION=false
BENCHMARK=false
VERBOSE=false
MODULE=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --cov|--coverage) COVERAGE=true ;;
        --integration) INTEGRATION=true ;;
        --benchmark) BENCHMARK=true ;;
        -v|--verbose) VERBOSE=true ;;
        --module) MODULE="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Build pytest command
CMD="pytest"

# Add verbosity
if [ "$VERBOSE" = true ]; then
    CMD="$CMD -v"
fi

# Add coverage if requested
if [ "$COVERAGE" = true ]; then
    CMD="$CMD --cov=catalog --cov=profiles --cov=integrations --cov=executions --cov=idp_auth --cov=core --cov-report=html --cov-report=xml --cov-report=term-missing"
fi

# Filter by marker
if [ "$INTEGRATION" = true ]; then
    CMD="$CMD -m integration"
elif [ "$BENCHMARK" = true ]; then
    CMD="$CMD -m benchmark --benchmark-only"
else
    # Default: run all tests except slow/benchmark
    CMD="$CMD -m 'not slow and not benchmark'"
fi

# Add specific module if provided
if [ -n "$MODULE" ]; then
    CMD="$CMD $MODULE"
fi

echo -e "${GREEN}Running: ${CMD}${NC}"
echo ""

# Execute tests
$CMD

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=== Tests Passed ===${NC}"

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo -e "${GREEN}Coverage report generated:${NC}"
        echo "  - HTML: htmlcov/index.html"
        echo "  - XML: coverage.xml"
    fi
else
    echo ""
    echo -e "${RED}=== Tests Failed ===${NC}"
    exit 1
fi
