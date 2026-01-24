#!/bin/bash
# Docker Verification Script for Code Eval Problems
# Usage: ./verify_docker.sh <problem-dir> <repo-url> <commit-hash>

set -e

PROBLEM_DIR="${1:-.}"
REPO_URL="$2"
COMMIT_HASH="$3"
WORK_DIR="/tmp/code_eval_verify_$$"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_pass() { echo -e "${GREEN}✅ PASS:${NC} $1"; }
log_fail() { echo -e "${RED}❌ FAIL:${NC} $1"; }
log_info() { echo -e "${YELLOW}ℹ️  INFO:${NC} $1"; }

cleanup() {
    if [ -d "$WORK_DIR" ]; then
        rm -rf "$WORK_DIR"
    fi
    docker rmi -f problem-verify-test 2>/dev/null || true
}
trap cleanup EXIT

# Validate inputs
if [ -z "$REPO_URL" ] || [ -z "$COMMIT_HASH" ]; then
    echo "Usage: $0 <problem-dir> <repo-url> <commit-hash>"
    exit 1
fi

log_info "Problem directory: $PROBLEM_DIR"
log_info "Repository: $REPO_URL"
log_info "Commit: $COMMIT_HASH"

# Create work directory
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Clone repository
log_info "Cloning repository..."
git clone --quiet "$REPO_URL" repo
cd repo
git checkout --quiet "$COMMIT_HASH"

# Copy files from problem directory
PROBLEM_DIR_ABS=$(cd "$PROBLEM_DIR" && pwd)

# Copy Dockerfile
if [ -f "$PROBLEM_DIR_ABS/dockerfile" ]; then
    cp "$PROBLEM_DIR_ABS/dockerfile" ./Dockerfile
elif [ -f "$PROBLEM_DIR_ABS/Dockerfile" ]; then
    cp "$PROBLEM_DIR_ABS/Dockerfile" ./Dockerfile
else
    log_fail "Dockerfile not found"
    exit 1
fi

# Verify base image
if grep -q "public.ecr.aws/x8v8d7g8/mars-base:latest" Dockerfile; then
    log_pass "Correct base image"
else
    log_fail "Wrong base image - must use public.ecr.aws/x8v8d7g8/mars-base:latest"
fi

# Build Docker image
log_info "Building Docker image..."
if docker build -t problem-verify-test . > /dev/null 2>&1; then
    log_pass "Docker build successful"
else
    log_fail "Docker build failed"
    exit 1
fi

# Test 1: Base tests without patches
log_info "Running base tests (no patches)..."
if docker run --rm --network=none problem-verify-test ./test.sh base > /dev/null 2>&1; then
    log_pass "Base tests pass (no patches)"
    BASE_PASS=true
else
    log_fail "Base tests fail (no patches)"
    BASE_PASS=false
fi

# Apply test.patch
if [ -f "$PROBLEM_DIR_ABS/test.patch" ]; then
    log_info "Applying test.patch..."
    git apply "$PROBLEM_DIR_ABS/test.patch"
    
    # Rebuild
    docker build -t problem-verify-test . > /dev/null 2>&1
    
    # Test 2: New tests should fail without solution
    log_info "Running new tests (without solution - should fail)..."
    if docker run --rm --network=none problem-verify-test ./test.sh new > /dev/null 2>&1; then
        log_fail "New tests PASS without solution (unexpected!)"
        NEW_FAIL=false
    else
        log_pass "New tests FAIL without solution (expected)"
        NEW_FAIL=true
    fi
else
    log_fail "test.patch not found"
fi

# Apply solution.patch
if [ -f "$PROBLEM_DIR_ABS/solution.patch" ]; then
    log_info "Applying solution.patch..."
    git apply "$PROBLEM_DIR_ABS/solution.patch"
    
    # Rebuild
    docker build -t problem-verify-test . > /dev/null 2>&1
    
    # Test 3: Base tests with solution
    log_info "Running base tests (with solution)..."
    if docker run --rm --network=none problem-verify-test ./test.sh base > /dev/null 2>&1; then
        log_pass "Base tests pass with solution"
        SOL_BASE=true
    else
        log_fail "Base tests fail with solution (regression!)"
        SOL_BASE=false
    fi
    
    # Test 4: New tests with solution
    log_info "Running new tests (with solution)..."
    if docker run --rm --network=none problem-verify-test ./test.sh new > /dev/null 2>&1; then
        log_pass "New tests pass with solution"
        SOL_NEW=true
    else
        log_fail "New tests fail with solution"
        SOL_NEW=false
    fi
else
    log_fail "solution.patch not found"
fi

# Summary
echo ""
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo "Base tests (no patches):     $([ "$BASE_PASS" = true ] && echo 'PASS' || echo 'FAIL')"
echo "New tests (no solution):     $([ "$NEW_FAIL" = true ] && echo 'FAIL (expected)' || echo 'PASS (bad!)')"
echo "Base tests (with solution):  $([ "$SOL_BASE" = true ] && echo 'PASS' || echo 'FAIL')"
echo "New tests (with solution):   $([ "$SOL_NEW" = true ] && echo 'PASS' || echo 'FAIL')"
echo "=========================================="

# Exit with appropriate code
if [ "$BASE_PASS" = true ] && [ "$NEW_FAIL" = true ] && [ "$SOL_BASE" = true ] && [ "$SOL_NEW" = true ]; then
    echo -e "${GREEN}All verification checks passed!${NC}"
    exit 0
else
    echo -e "${RED}Some verification checks failed!${NC}"
    exit 1
fi
