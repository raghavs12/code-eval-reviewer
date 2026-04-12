#!/usr/bin/env bash
# Docker Verification Script for Code Eval Problems
# Usage: ./verify_docker.sh <problem-dir> <repo-url> <commit-hash>

set -euo pipefail

PROBLEM_DIR="${1:-.}"
REPO_URL="${2:-}"
COMMIT_HASH="${3:-}"
WORK_DIR="/tmp/code_eval_verify_$$"
IMAGE_NAME="problem-verify-test"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}PASS:${NC} $1"; }
log_fail() { echo -e "${RED}FAIL:${NC} $1"; }
log_info() { echo -e "${YELLOW}INFO:${NC} $1"; }

cleanup() {
    if [ -d "$WORK_DIR" ]; then
        rm -rf "$WORK_DIR"
    fi
    docker rmi -f "$IMAGE_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [ -z "$REPO_URL" ] || [ -z "$COMMIT_HASH" ]; then
    echo "Usage: $0 <problem-dir> <repo-url> <commit-hash>"
    exit 1
fi

log_info "Problem directory: $PROBLEM_DIR"
log_info "Repository: $REPO_URL"
log_info "Commit: $COMMIT_HASH"

mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

log_info "Cloning repository..."
git clone --quiet "$REPO_URL" repo
cd repo
git checkout --quiet "$COMMIT_HASH"

PROBLEM_DIR_ABS=$(cd "$PROBLEM_DIR" && pwd)

if [ -f "$PROBLEM_DIR_ABS/dockerfile" ]; then
    cp "$PROBLEM_DIR_ABS/dockerfile" ./Dockerfile
elif [ -f "$PROBLEM_DIR_ABS/Dockerfile" ]; then
    cp "$PROBLEM_DIR_ABS/Dockerfile" ./Dockerfile
else
    log_fail "Dockerfile not found"
    exit 1
fi

if grep -q "public.ecr.aws/x8v8d7g8/mars-base:latest" Dockerfile; then
    log_pass "Correct base image"
else
    log_fail "Wrong base image - must use public.ecr.aws/x8v8d7g8/mars-base:latest"
fi

log_info "Building Docker image..."
if docker build -t "$IMAGE_NAME" . >/dev/null 2>&1; then
    log_pass "Docker build successful"
else
    log_fail "Docker build failed"
    exit 1
fi

run_mode() {
    local mode="$1"
    local xml_name="$2"
    local expected_exit="$3"
    local xml_mode_expectation="$4"
    local output_file="$WORK_DIR/${xml_name}.log"

    set +e
    docker run --rm --network=none "$IMAGE_NAME" bash -lc "
        sed -i 's/\r$//' ./test.sh
        xml='/tmp/${xml_name}'
        rm -f \"\$xml\"
        ./test.sh --output_path \"\$xml\" ${mode}
        status=\$?
        echo '__XML_STATUS__='\$status
        if [ -f \"\$xml\" ]; then
            echo '__XML_BEGIN__'
            cat \"\$xml\"
            echo '__XML_END__'
        else
            echo '__XML_MISSING__'
        fi
        exit \$status
    " >"$output_file" 2>&1
    local status=$?
    set -e

    if [ "$expected_exit" = "pass" ] && [ "$status" -eq 0 ]; then
        log_pass "${mode} exit code matches expected pass"
    elif [ "$expected_exit" = "fail" ] && [ "$status" -ne 0 ]; then
        log_pass "${mode} exit code matches expected failure"
    else
        log_fail "${mode} exit code did not match expectation"
        cat "$output_file"
        return 1
    fi

    if ! grep -q "__XML_BEGIN__" "$output_file"; then
        log_fail "${mode} did not produce JUnit XML"
        cat "$output_file"
        return 1
    fi

    awk '/__XML_BEGIN__/{flag=1;next}/__XML_END__/{flag=0}flag' "$output_file" > "$WORK_DIR/${xml_name}"
    if [ ! -s "$WORK_DIR/${xml_name}" ]; then
        log_fail "${mode} XML file is empty"
        cat "$output_file"
        return 1
    fi

    if ! python - "$WORK_DIR/${xml_name}" "$mode" "$xml_mode_expectation" >/dev/null <<'PY'
import sys
import xml.etree.ElementTree as ET
path = sys.argv[1]
mode = sys.argv[2]
expectation = sys.argv[3]
root = ET.parse(path).getroot()
failures = int(root.attrib.get("failures", "0") or 0)
errors = int(root.attrib.get("errors", "0") or 0)
tests = int(root.attrib.get("tests", "0") or 0)
if tests == 0:
    raise SystemExit(f"{mode} XML reports zero tests")
if expectation == "must_fail" and failures + errors <= 0:
    raise SystemExit(f"{mode} XML does not record a failure")
if expectation == "must_pass" and failures + errors != 0:
    raise SystemExit(f"{mode} XML records failures unexpectedly")
print(f"{mode} xml ok: tests={tests} failures={failures} errors={errors}")
PY
    then
        log_fail "${mode} XML validation failed"
        cat "$output_file"
        return 1
    fi

    log_pass "${mode} wrote valid JUnit XML"
    return 0
}

BASE_PASS=false
NEW_FAIL=false
SOL_BASE=false
SOL_NEW=false

log_info "Running base mode without patches..."
if run_mode "base" "base-pre.xml" "pass" "must_pass"; then
    BASE_PASS=true
fi

if [ -f "$PROBLEM_DIR_ABS/test.patch" ]; then
    log_info "Applying test.patch..."
    git apply "$PROBLEM_DIR_ABS/test.patch"
    docker build -t "$IMAGE_NAME" . >/dev/null 2>&1
    log_info "Running new mode without solution..."
    if run_mode "new" "new-pre.xml" "fail" "must_fail"; then
        NEW_FAIL=true
    fi
else
    log_fail "test.patch not found"
fi

if [ -f "$PROBLEM_DIR_ABS/solution.patch" ]; then
    log_info "Applying solution.patch..."
    git apply "$PROBLEM_DIR_ABS/solution.patch"
    docker build -t "$IMAGE_NAME" . >/dev/null 2>&1

    log_info "Running base mode with solution..."
    if run_mode "base" "base-post.xml" "pass" "must_pass"; then
        SOL_BASE=true
    fi

    log_info "Running new mode with solution..."
    if run_mode "new" "new-post.xml" "pass" "must_pass"; then
        SOL_NEW=true
    fi
else
    log_fail "solution.patch not found"
fi

echo ""
echo "=========================================="
echo "VERIFICATION SUMMARY"
echo "=========================================="
echo "Base tests (no patches):     $([ "$BASE_PASS" = true ] && echo 'PASS' || echo 'FAIL')"
echo "New tests (no solution):     $([ "$NEW_FAIL" = true ] && echo 'FAIL (expected)' || echo 'PASS (bad!)')"
echo "Base tests (with solution):  $([ "$SOL_BASE" = true ] && echo 'PASS' || echo 'FAIL')"
echo "New tests (with solution):   $([ "$SOL_NEW" = true ] && echo 'PASS' || echo 'FAIL')"
echo "=========================================="

if [ "$BASE_PASS" = true ] && [ "$NEW_FAIL" = true ] && [ "$SOL_BASE" = true ] && [ "$SOL_NEW" = true ]; then
    echo -e "${GREEN}All verification checks passed!${NC}"
    exit 0
fi

echo -e "${RED}Some verification checks failed!${NC}"
exit 1
