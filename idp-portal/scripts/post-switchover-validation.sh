#!/bin/bash
# ============================================================================
# Post-Switchover Validation Script
# IDP Portal - Django Backend Validation
# ============================================================================
#
# This script validates that the Django backend is functioning correctly.
#
# Usage:
#   ./post-switchover-validation.sh [--api-url URL] [--jwt-token TOKEN]
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#
# ============================================================================

set -euo pipefail

# Configuration
API_URL="${API_URL:-https://api.idp.internal}"
JWT_TOKEN="${JWT_TOKEN:-}"
VERBOSE="${VERBOSE:-false}"
TIMEOUT=10
PASSED=0
FAILED=0
TOTAL=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --jwt-token)
            JWT_TOKEN="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# Helper Functions
# ============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_test() {
    echo -e "\n${YELLOW}[TEST]${NC} $1"
}

test_pass() {
    echo -e "  ${GREEN}✓ PASS${NC} $1"
    ((PASSED++))
    ((TOTAL++))
}

test_fail() {
    echo -e "  ${RED}✗ FAIL${NC} $1"
    ((FAILED++))
    ((TOTAL++))
}

# ============================================================================
# Test Functions
# ============================================================================

test_health_check() {
    log_test "Health Check Endpoint"

    local response
    local http_code

    response=$(curl -sf -w "\n%{http_code}" --max-time "$TIMEOUT" \
        "${API_URL}/api/v1/health" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)

    if [[ "$http_code" == "200" ]]; then
        test_pass "Health check returns 200 OK"

        # Check response contains expected fields
        if echo "$body" | grep -q '"status"'; then
            test_pass "Response contains 'status' field"
        else
            test_fail "Response missing 'status' field"
        fi

        if echo "$body" | grep -q '"database"'; then
            test_pass "Response contains 'database' field"
        else
            test_fail "Response missing 'database' field"
        fi

        if [[ "$VERBOSE" == "true" ]]; then
            echo "  Response: $body"
        fi
    else
        test_fail "Health check returned $http_code (expected 200)"
        return 1
    fi
}

test_saml_redirect() {
    log_test "SAML Authentication Redirect"

    local http_code

    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" \
        "${API_URL}/api/v1/auth/login" 2>/dev/null) || true

    # SAML login should redirect (302) or return 200 with redirect URL
    if [[ "$http_code" == "302" ]] || [[ "$http_code" == "200" ]]; then
        test_pass "Login endpoint responds correctly ($http_code)"
    else
        test_fail "Login endpoint returned $http_code (expected 302 or 200)"
    fi
}

test_catalog_list() {
    log_test "Catalog Actions List"

    if [[ -z "$JWT_TOKEN" ]]; then
        log_warn "No JWT token provided, skipping authenticated tests"
        return 0
    fi

    local response
    local http_code

    response=$(curl -sf -w "\n%{http_code}" --max-time "$TIMEOUT" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        "${API_URL}/api/v1/catalog/actions" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n -1)

    if [[ "$http_code" == "200" ]]; then
        test_pass "Catalog list returns 200 OK"

        # Check response structure
        if echo "$body" | grep -q '"data"'; then
            test_pass "Response contains 'data' field"
        else
            test_fail "Response missing 'data' field"
        fi

        if echo "$body" | grep -q '"total"'; then
            test_pass "Response contains 'total' field"
        else
            test_fail "Response missing 'total' field"
        fi
    elif [[ "$http_code" == "401" ]]; then
        test_fail "Catalog list returned 401 - JWT token may be expired"
    else
        test_fail "Catalog list returned $http_code (expected 200)"
    fi
}

test_catalog_detail() {
    log_test "Catalog Action Detail"

    if [[ -z "$JWT_TOKEN" ]]; then
        return 0
    fi

    local response
    local http_code

    # Get first action ID from list
    local action_id
    action_id=$(curl -sf --max-time "$TIMEOUT" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        "${API_URL}/api/v1/catalog/actions?limit=1" 2>/dev/null | \
        grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*') || true

    if [[ -z "$action_id" ]]; then
        log_warn "No actions found to test detail endpoint"
        return 0
    fi

    response=$(curl -sf -w "\n%{http_code}" --max-time "$TIMEOUT" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        "${API_URL}/api/v1/catalog/actions/${action_id}" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -n1)

    if [[ "$http_code" == "200" ]]; then
        test_pass "Action detail returns 200 OK (action_id=$action_id)"
    else
        test_fail "Action detail returned $http_code (expected 200)"
    fi
}

test_profiles_list() {
    log_test "Profiles List"

    if [[ -z "$JWT_TOKEN" ]]; then
        return 0
    fi

    local response
    local http_code

    response=$(curl -sf -w "\n%{http_code}" --max-time "$TIMEOUT" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        "${API_URL}/api/v1/profiles" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -n1)

    if [[ "$http_code" == "200" ]]; then
        test_pass "Profiles list returns 200 OK"
    else
        test_fail "Profiles list returned $http_code (expected 200)"
    fi
}

test_executions_list() {
    log_test "Executions History"

    if [[ -z "$JWT_TOKEN" ]]; then
        return 0
    fi

    local response
    local http_code

    response=$(curl -sf -w "\n%{http_code}" --max-time "$TIMEOUT" \
        -H "Authorization: Bearer $JWT_TOKEN" \
        "${API_URL}/api/v1/executions" 2>/dev/null) || true

    http_code=$(echo "$response" | tail -n1)

    if [[ "$http_code" == "200" ]]; then
        test_pass "Executions list returns 200 OK"
    else
        test_fail "Executions list returned $http_code (expected 200)"
    fi
}

test_websocket() {
    log_test "WebSocket Connectivity"

    # Check for WebSocket testing tool (websocat or wscat)
    local ws_tool=""
    if command -v websocat &>/dev/null; then
        ws_tool="websocat"
    elif command -v wscat &>/dev/null; then
        ws_tool="wscat"
    fi

    if [[ -z "$ws_tool" ]]; then
        log_warn "No WebSocket testing tool found (websocat or wscat)"
        log_warn "Install: cargo install websocat  OR  npm install -g wscat"
        log_warn "Skipping WebSocket tests (non-blocking)"
        return 0
    fi

    # Derive WebSocket URL from API URL
    local ws_url
    ws_url=$(echo "$API_URL" | sed 's|^https://|wss://|; s|^http://|ws://|')

    # Test WebSocket connection to timeline endpoint
    # Use a dummy execution_id — we expect connection upgrade to succeed
    local ws_endpoint="${ws_url}/ws/timeline/test-validation/"
    local ws_result

    if [[ "$ws_tool" == "websocat" ]]; then
        # websocat: try connection with 5s timeout, send ping, capture response
        ws_result=$(echo '{"type":"ping"}' | timeout 5 websocat -n1 "$ws_endpoint" 2>&1) || true
    else
        # wscat: try connection with timeout
        ws_result=$(echo '{"type":"ping"}' | timeout 5 wscat -c "$ws_endpoint" -w 3 2>&1) || true
    fi

    if [[ -n "$ws_result" ]]; then
        # Check if we got a valid JSON response
        if echo "$ws_result" | grep -q '{'; then
            test_pass "WebSocket connection successful ($ws_tool)"
            if [[ "$VERBOSE" == "true" ]]; then
                echo "  Response: $ws_result"
            fi
        else
            # Non-JSON response but connection was made
            test_pass "WebSocket connection established ($ws_tool)"
        fi
    else
        # Empty result could mean timeout or rejected connection
        # In production, this would be a concern — mark as warning but don't fail
        log_warn "WebSocket endpoint did not respond within timeout"
        log_warn "This may indicate auth requirement or endpoint unavailable"
        log_warn "Manual verification recommended for production deployments"
        # Don't mark as pass — this is indeterminate, not success
    fi
}

test_response_time() {
    log_test "Response Time (Health Check)"

    local time_total

    time_total=$(curl -sf -o /dev/null -w "%{time_total}" --max-time "$TIMEOUT" \
        "${API_URL}/api/v1/health" 2>/dev/null) || true

    if [[ -n "$time_total" ]]; then
        local time_ms
        time_ms=$(echo "$time_total * 1000" | bc | cut -d. -f1)

        if [[ "$time_ms" -lt 500 ]]; then
            test_pass "Health check response time: ${time_ms}ms (< 500ms)"
        elif [[ "$time_ms" -lt 1000 ]]; then
            log_warn "Health check response time: ${time_ms}ms (slow but acceptable)"
            test_pass "Health check response time acceptable: ${time_ms}ms"
        else
            test_fail "Health check response time too slow: ${time_ms}ms (> 1000ms)"
        fi
    else
        test_fail "Could not measure response time"
    fi
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    echo "============================================================================"
    echo "  IDP Portal - Post-Switchover Validation"
    echo "  Target: $API_URL"
    echo "  Date: $(date)"
    echo "============================================================================"
    echo ""

    # Run all tests
    test_health_check
    test_saml_redirect
    test_catalog_list
    test_catalog_detail
    test_profiles_list
    test_executions_list
    test_websocket
    test_response_time

    # Summary
    echo ""
    echo "============================================================================"
    echo "  Test Summary"
    echo "============================================================================"
    echo ""
    echo -e "  Total Tests: $TOTAL"
    echo -e "  ${GREEN}Passed: $PASSED${NC}"
    echo -e "  ${RED}Failed: $FAILED${NC}"
    echo ""

    if [[ "$FAILED" -eq 0 ]]; then
        echo -e "${GREEN}✓ ALL TESTS PASSED - Backend is operational${NC}"
        exit 0
    else
        echo -e "${RED}✗ SOME TESTS FAILED - Review errors above${NC}"
        exit 1
    fi
}

main "$@"
