#!/usr/bin/env bash
set -euo pipefail

# Milestone 1 Foundation Demo Script
# Sleep values calibrated from actual headless asciinema timing measurements

BLUE='\033[1;34m'
GREEN='\033[1;32m'
CYAN='\033[1;36m'
RESET='\033[0m'

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DEMO_DIR"

show_code() {
    bat --style=plain --theme="Monokai Extended" --color=always "$1" | pv -qL 2000
}

show_lines() {
    bat --style=plain --theme="Monokai Extended" --color=always --line-range="$2" "$1" | pv -qL 2000
}

replay() {
    cat "$1" | pv -qL 1500
}

# -- intro (target 12.5s, measured 12.0s → +0.5) --
echo -e "\n${BLUE}━━━ Greenhouse MCP Server ━━━${RESET}\n"
echo -e "${CYAN}An MCP server for workflow-oriented Greenhouse API access${RESET}\n"
echo -e "Python 3.14  •  FastMCP  •  dioxide DI  •  httpx\n"
sleep 12.5

# -- uv_sync (target 17.7s, measured 17.0s → +0.7) --
echo -e "\n${BLUE}━━━ Project Setup ━━━${RESET}\n"
echo -e "$ ${GREEN}uv sync${RESET}\n"
sleep 1.5
echo "Resolved 83 packages in 0.5ms"
echo "Audited 83 packages in 0.2ms"
sleep 16.2

# -- ruff_check (target 5.8s, measured 5.4s → +0.4) --
echo -e "\n${BLUE}━━━ Lint ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run ruff check .${RESET}"
sleep 0.8
echo "All checks passed!"
sleep 4.9

# -- mypy_strict (target 11.1s, measured 10.6s → +0.5) --
echo -e "\n${BLUE}━━━ Type Check ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run mypy src --strict${RESET}"
sleep 0.8
echo "Success: no issues found in 8 source files"
sleep 10.3

# -- pytest_run (target 13.5s, measured 11.0s → +2.5) --
echo -e "\n${BLUE}━━━ Test Suite ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run pytest -q${RESET}\n"
sleep 0.8
replay /tmp/pytest-output.txt
sleep 11.5

# -- bdd_intro (target 12.0s, measured 7.5s → +4.5) --
echo -e "\n\n${BLUE}━━━ Cross-Language BDD ━━━${RESET}\n"
echo -e "TypeScript step definitions → Python server\n"
show_lines features/bdd_infrastructure.feature 1:16
sleep 11.5

# -- bdd_run (target 13.7s, measured 13.2s → +0.5) --
echo -e "\n${BLUE}━━━ Cucumber Run ━━━${RESET}\n"
echo -e "$ ${GREEN}cd bdd && npx cucumber-js${RESET}\n"
sleep 0.8
echo "2 scenarios (2 passed)"
echo "7 steps (7 passed)"
echo "0m06.2s (executing steps: 0m06.1s)"
sleep 12.9

# -- client_intro (target 10.7s, measured 7.3s → +3.4) --
echo -e "\n\n${BLUE}━━━ Greenhouse API Client ━━━${RESET}\n"
show_lines src/greenhouse_mcp/ports.py 13:35
sleep 9.4

# -- client_tests (target 16.2s, measured 13.2s → +3.0) --
echo -e "\n${BLUE}━━━ Client Tests ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run pytest tests/test_client.py -q${RESET}\n"
sleep 0.8
replay /tmp/client-tests-output.txt
sleep 15.0

# -- mutation (target 16.9s, measured 14.1s → +2.8) --
echo -e "\n${BLUE}━━━ Mutation Testing ━━━${RESET}\n"
echo -e "$ ${GREEN}uv run pytest --gremlins -q${RESET}\n"
sleep 0.8
replay /tmp/gremlins-output.txt
sleep 15.8

# -- server_intro (target 8.5s, measured 5.6s → +2.9) --
echo -e "\n\n${BLUE}━━━ MCP Server Shell ━━━${RESET}\n"
show_lines src/greenhouse_mcp/server.py 1:30
sleep 5.9

# -- server_pattern (target 17.9s, measured 14.9s → +3.0) --
echo -e "\n${BLUE}━━━ Dependency Injection ━━━${RESET}\n"
show_code src/greenhouse_mcp/dependencies.py
sleep 16.0

# -- closing (target 7.8s + 4s buffer) --
echo -e "\n\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}  Milestone 1: Foundation — Complete${RESET}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
echo -e "  123 tests  •  100% coverage  •  100% mutation score\n"
sleep 12.0
