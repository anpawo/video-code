#!/usr/bin/env bash

# Runs every assertion-based test/*_test.py (see test/shapes_test.py,
# test/group_test.py, ... for the convention: print "All checks passed." and
# exit 0, or print "N FAILURE(S):" and exit 1). Used locally and by CI
# (.github/workflows/ci-build.yaml).

set -u
cd "$(dirname "$0")/.."

_R="\033[0m"
_BOLD="\033[1m"
_CYAN="\033[36m"
_GREEN="\033[32m"
_RED="\033[31m"
_DIM="\033[2m"

failed=0
passed=0
failed_files=()

# test/mutants.py needs to know which lines of videocode/ each file runs:
# VC_LINECOV is the folder test/linecov/sitecustomize.py writes that into.
if [ -n "${VC_LINECOV:-}" ]; then
    mkdir -p "$VC_LINECOV"
    export VC_LINECOV_ROOT="$(pwd -P)"
    export PYTHONPATH="$VC_LINECOV_ROOT/test/linecov${PYTHONPATH:+:$PYTHONPATH}"
fi

for f in test/*_test.py; do
    printf "${_CYAN}${_BOLD}━━━  %s  ━━━${_R}\n" "$f"
    start=$SECONDS
    if VC_LINECOV_TEST="$f" python3 "$f"; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
        failed_files+=("$f")
    fi
    [ -z "${VC_LINECOV:-}" ] || echo "$f $((SECONDS - start))" >> "$VC_LINECOV/durations"
    echo
done

echo
if [ "$failed" -eq 0 ]; then
    printf "${_GREEN}${_BOLD}  ✓  All %d test files passed.${_R}\n" "$passed"
else
    printf "${_RED}${_BOLD}  ✗  %d of %d test file(s) FAILED:${_R}\n" "$failed" "$((passed + failed))"
    for f in "${failed_files[@]}"; do
        printf "     ${_RED}•${_R}  %s\n" "$f"
    done
    exit 1
fi
