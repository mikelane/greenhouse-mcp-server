#!/usr/bin/env bash
set -euo pipefail

# Milestone 2 Demo Script — timing calibrated for headless asciinema
# Each segment sleep = narration duration (display adds negligible time in headless)

BLUE='\033[1;34m'
GREEN='\033[1;32m'
CYAN='\033[1;36m'
YELLOW='\033[1;33m'
RESET='\033[0m'

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

show_lines() {
    bat --style=plain --theme="Monokai Extended" --color=always --line-range="$2" "$1" | pv -qL 2000
}

replay() {
    cat "$1" | pv -qL 1500
}

# -- intro (11.3s) --
echo -e "\n${BLUE}━━━ Milestone 2: Core Recruiting Tools ━━━${RESET}\n"
echo -e "${CYAN}Three tools that answer real recruiting questions${RESET}\n"
echo -e "  pipeline_health   → Where are things stuck?"
echo -e "  candidate_dossier → Tell me everything about this person"
echo -e "  needs_attention   → What's falling through the cracks?\n"
sleep 11.0

# -- pipeline_intro (12.5s) --
echo -e "\n${BLUE}━━━ pipeline_health ━━━${RESET}\n"
show_lines src/greenhouse_mcp/tools/pipeline.py 1:40
sleep 9.0

# -- pipeline_tests (17.4s) --
echo -e "\n${BLUE}━━━ Pipeline Tests ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run pytest tests/test_pipeline.py -q${RESET}\n"
sleep 0.8
replay /tmp/m2-pipeline-tests.txt
sleep 15.0

# -- candidate_intro (15.0s) --
echo -e "\n\n${BLUE}━━━ candidate_dossier ━━━${RESET}\n"
show_lines src/greenhouse_mcp/tools/candidate.py 1:40
sleep 11.0

# -- candidate_tests (11.7s) --
echo -e "\n${BLUE}━━━ Candidate Tests ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run pytest tests/test_candidate.py -q${RESET}\n"
sleep 0.8
replay /tmp/m2-candidate-tests.txt
sleep 10.0

# -- attention_intro (17.6s) --
echo -e "\n\n${BLUE}━━━ needs_attention ━━━${RESET}\n"
show_lines src/greenhouse_mcp/tools/attention.py 1:40
sleep 13.0

# -- attention_tests (14.0s) --
echo -e "\n${BLUE}━━━ Attention Tests ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run pytest tests/test_attention.py -q${RESET}\n"
sleep 0.8
replay /tmp/m2-attention-tests.txt
sleep 12.0

# -- closing (16.2s + 4s buffer) --
echo -e "\n\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}  Milestone 2: Core Recruiting Tools — Complete${RESET}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
echo -e "  141 tests  •  100% mutation coverage  •  3 tools\n"
sleep 24.0
