#!/bin/bash
# Story 17.8: Reproducible dependency installation
# Usage: ./scripts/install_deps.sh [prod|dev]

set -e

# Check virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "WARNING: No virtual environment detected (\$VIRTUAL_ENV not set)"
    echo "It's recommended to run this script inside a Python virtual environment."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check Python version
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3,12) else 1)"; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "ERROR: Python 3.12+ required, found $PYTHON_VERSION"
    exit 1
fi

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    pip install uv
fi

# Install dependencies based on environment
if [ "$1" == "prod" ]; then
    echo "Installing production dependencies..."
    uv pip install -r requirements.lock
else
    echo "Installing development dependencies..."
    uv pip install -r requirements-dev.lock
fi

echo "Dependencies installed successfully ✅"
