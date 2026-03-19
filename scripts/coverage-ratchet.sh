#!/usr/bin/env bash
# Coverage ratchet: ensures coverage never decreases.
#
# Usage:
#   scripts/coverage-ratchet.sh          # Check against baseline
#   scripts/coverage-ratchet.sh --update # Update baseline to current coverage

set -euo pipefail

BASELINE_FILE=".coverage-baseline.json"

get_current_coverage() {
    uv run pytest --cov=src --cov-branch --cov-report=json --quiet 2>/dev/null
    python3 -c "
import json, sys
with open('coverage.json') as f:
    data = json.load(f)
print(data['totals']['percent_covered'])
"
}

if [[ "${1:-}" == "--update" ]]; then
    current=$(get_current_coverage)
    echo "{\"baseline\": ${current}}" > "${BASELINE_FILE}"
    echo "Updated coverage baseline to ${current}%"
    rm -f coverage.json
    exit 0
fi

if [[ ! -f "${BASELINE_FILE}" ]]; then
    echo "No coverage baseline found. Run with --update to create one."
    exit 1
fi

baseline=$(python3 -c "
import json, sys
with open('${BASELINE_FILE}') as f:
    data = json.load(f)
print(data['baseline'])
")

current=$(get_current_coverage)
rm -f coverage.json

echo "Baseline: ${baseline}%"
echo "Current:  ${current}%"

result=$(python3 -c "
baseline = float(${baseline})
current = float(${current})
if current < baseline:
    print(f'FAIL: Coverage decreased from {baseline}% to {current}%')
    exit(1)
else:
    print(f'PASS: Coverage {current}% >= baseline {baseline}%')
")

echo "${result}"
if echo "${result}" | grep -q "FAIL"; then
    exit 1
fi
