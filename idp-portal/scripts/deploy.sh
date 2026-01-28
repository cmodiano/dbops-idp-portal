#!/usr/bin/env bash
# IDP Portal Deployment Script
# Usage: ./deploy.sh <host> <user> <deploy_path>
# Example: ./deploy.sh idp-portal.example.com deploy /opt/idp-portal

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Verify arguments
if [[ $# -lt 3 ]]; then
    log_error "Usage: $0 <host> <user> <deploy_path>"
    log_error "Example: $0 idp-portal.example.com deploy /opt/idp-portal"
    exit 1
fi

HOST="$1"
USER="$2"
DEPLOY_PATH="$3"

# Validate inputs
if [[ -z "$HOST" ]] || [[ -z "$USER" ]] || [[ -z "$DEPLOY_PATH" ]]; then
    log_error "All arguments (host, user, deploy_path) are required"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log_info "Starting deployment to $USER@$HOST:$DEPLOY_PATH"

# Build frontend
log_info "Building frontend..."
cd "$PROJECT_ROOT/frontend"
npm ci --silent
npm run build

# Verify build output exists
if [ ! -f "$PROJECT_ROOT/frontend/dist/index.html" ]; then
    log_error "Build failed: frontend/dist/index.html not found"
    exit 1
fi
log_info "Frontend build verified"

# Deploy frontend
log_info "Deploying frontend..."
rsync -avz --delete \
    -e "ssh" \
    "$PROJECT_ROOT/frontend/dist/" \
    "$USER@$HOST:$DEPLOY_PATH/frontend/dist/"

# Deploy backend
log_info "Deploying backend..."
rsync -avz --delete \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    --exclude 'tests/' \
    --exclude '.env' \
    -e "ssh" \
    "$PROJECT_ROOT/backend/" \
    "$USER@$HOST:$DEPLOY_PATH/backend/"

# Restart service
log_info "Restarting idp-portal service..."
if ! ssh "$USER@$HOST" "sudo systemctl restart idp-portal"; then
    log_error "Failed to restart idp-portal service"
    log_warn "Service may not exist yet. Checking systemd status..."
    ssh "$USER@$HOST" "sudo systemctl status idp-portal || true"
    exit 1
fi
log_info "Service restarted successfully"

# Health check
log_info "Running health check..."
sleep 3
if ssh "$USER@$HOST" "curl -sf http://localhost:8000/api/v1/health > /dev/null"; then
    log_info "Health check passed!"
else
    log_error "Health check failed!"
    exit 1
fi

log_info "Deployment completed successfully!"
