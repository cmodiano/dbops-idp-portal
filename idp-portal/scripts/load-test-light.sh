#!/bin/bash
# ============================================================================
# Light Load Test Script
# IDP Portal - Django Backend Load Testing
# ============================================================================
#
# This script performs a light load test (10 req/s for 1 minute) to validate
# Django backend performance.
#
# Requirements:
#   - curl
#   - bc (for floating point math)
#
# Usage:
#   ./load-test-light.sh [--api-url URL] [--duration SECONDS] [--rate RPS]
#
# ============================================================================

set -euo pipefail

# Configuration
API_URL="${API_URL:-https://api.idp.internal}"
DURATION="${DURATION:-60}"       # Duration in seconds
RATE="${RATE:-10}"               # Requests per second
ENDPOINT="/api/v1/health"        # Endpoint to test
TIMEOUT=5                        # Timeout per request

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Metrics
TOTAL_REQUESTS=0
SUCCESS_COUNT=0
ERROR_COUNT=0
RESPONSE_TIMES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --rate)
            RATE="$2"
            shift 2
            ;;
        --endpoint)
            ENDPOINT="$2"
            shift 2
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

# Calculate percentile from array
percentile() {
    local -n arr=$1
    local p=$2
    local n=${#arr[@]}

    if [[ $n -eq 0 ]]; then
        echo "0"
        return
    fi

    # Sort array
    IFS=$'\n' sorted=($(sort -n <<<"${arr[*]}"))
    unset IFS

    local idx=$(echo "($p / 100) * $n" | bc)
    idx=${idx%.*}  # Round down

    if [[ $idx -ge $n ]]; then
        idx=$((n - 1))
    fi

    echo "${sorted[$idx]}"
}

# Single request with timing
do_request() {
    local start_time
    local end_time
    local http_code
    local response_time

    start_time=$(date +%s%N)

    http_code=$(curl -sf -o /dev/null -w "%{http_code}" \
        --max-time "$TIMEOUT" \
        "${API_URL}${ENDPOINT}" 2>/dev/null) || http_code="000"

    end_time=$(date +%s%N)
    response_time=$(( (end_time - start_time) / 1000000 ))  # Convert to ms

    ((TOTAL_REQUESTS++))

    if [[ "$http_code" == "200" ]]; then
        ((SUCCESS_COUNT++))
        RESPONSE_TIMES+=("$response_time")
    else
        ((ERROR_COUNT++))
    fi
}

# ============================================================================
# Main Execution
# ============================================================================

main() {
    echo "============================================================================"
    echo "  IDP Portal - Light Load Test"
    echo "============================================================================"
    echo ""
    echo "  Target URL: ${API_URL}${ENDPOINT}"
    echo "  Duration: ${DURATION}s"
    echo "  Target Rate: ${RATE} req/s"
    echo "  Expected Requests: $((DURATION * RATE))"
    echo ""
    echo "============================================================================"
    echo ""

    local interval
    interval=$(echo "scale=6; 1 / $RATE" | bc)

    log_info "Starting load test..."
    log_info "Press Ctrl+C to stop early"
    echo ""

    local start_time
    local current_time
    local elapsed

    start_time=$(date +%s)

    # Progress tracking
    local progress_interval=10
    local last_progress=0

    while true; do
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))

        if [[ $elapsed -ge $DURATION ]]; then
            break
        fi

        # Progress update
        if [[ $((elapsed - last_progress)) -ge $progress_interval ]]; then
            local current_rate
            if [[ $elapsed -gt 0 ]]; then
                current_rate=$(echo "scale=1; $TOTAL_REQUESTS / $elapsed" | bc)
            else
                current_rate=0
            fi
            echo "  Progress: ${elapsed}s / ${DURATION}s | Requests: $TOTAL_REQUESTS | Rate: ${current_rate} req/s | Errors: $ERROR_COUNT"
            last_progress=$elapsed
        fi

        # Send request
        do_request &

        # Wait for rate limiting
        sleep "$interval"
    done

    # Wait for remaining requests
    wait

    echo ""
    log_info "Load test completed!"
    echo ""

    # Calculate statistics
    local success_rate
    local error_rate
    local avg_response_time
    local p50
    local p95
    local p99

    if [[ $TOTAL_REQUESTS -gt 0 ]]; then
        success_rate=$(echo "scale=2; $SUCCESS_COUNT * 100 / $TOTAL_REQUESTS" | bc)
        error_rate=$(echo "scale=2; $ERROR_COUNT * 100 / $TOTAL_REQUESTS" | bc)
    else
        success_rate=0
        error_rate=0
    fi

    if [[ ${#RESPONSE_TIMES[@]} -gt 0 ]]; then
        local sum=0
        for t in "${RESPONSE_TIMES[@]}"; do
            sum=$((sum + t))
        done
        avg_response_time=$((sum / ${#RESPONSE_TIMES[@]}))

        p50=$(percentile RESPONSE_TIMES 50)
        p95=$(percentile RESPONSE_TIMES 95)
        p99=$(percentile RESPONSE_TIMES 99)
    else
        avg_response_time=0
        p50=0
        p95=0
        p99=0
    fi

    local actual_rate
    actual_rate=$(echo "scale=1; $TOTAL_REQUESTS / $DURATION" | bc)

    # Results
    echo "============================================================================"
    echo "  Load Test Results"
    echo "============================================================================"
    echo ""
    echo "  Total Requests: $TOTAL_REQUESTS"
    echo "  Successful: $SUCCESS_COUNT (${success_rate}%)"
    echo "  Failed: $ERROR_COUNT (${error_rate}%)"
    echo "  Actual Rate: ${actual_rate} req/s"
    echo ""
    echo "  Response Times:"
    echo "    Average: ${avg_response_time}ms"
    echo "    p50: ${p50}ms"
    echo "    p95: ${p95}ms"
    echo "    p99: ${p99}ms"
    echo ""

    # Evaluation
    echo "============================================================================"
    echo "  Evaluation"
    echo "============================================================================"
    echo ""

    local pass=true

    # Check error rate
    if (( $(echo "$error_rate > 1" | bc -l) )); then
        log_error "Error rate too high: ${error_rate}% (threshold: 1%)"
        pass=false
    else
        log_info "Error rate acceptable: ${error_rate}%"
    fi

    # Check p95 latency
    if [[ $p95 -gt 500 ]]; then
        log_warn "p95 latency high: ${p95}ms (threshold: 500ms)"
    else
        log_info "p95 latency acceptable: ${p95}ms"
    fi

    # Check p99 latency
    if [[ $p99 -gt 1000 ]]; then
        log_warn "p99 latency high: ${p99}ms (threshold: 1000ms)"
    else
        log_info "p99 latency acceptable: ${p99}ms"
    fi

    echo ""

    if [[ "$pass" == "true" ]]; then
        echo -e "${GREEN}✓ LOAD TEST PASSED${NC}"
        exit 0
    else
        echo -e "${RED}✗ LOAD TEST FAILED${NC}"
        exit 1
    fi
}

main "$@"
