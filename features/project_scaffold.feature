@scaffold @wip @ISSUE-8
Feature: Project scaffold and quality gates
  As a developer
  I need the project to build, lint, type-check, and test cleanly
  So that I can develop with confidence

  Scenario: Dependencies install successfully
    Given a fresh checkout of the repository
    When I run "uv sync"
    Then the command exits with code 0
    And the greenhouse_mcp package is importable

  Scenario: Ruff reports no lint violations
    Given the project dependencies are installed
    When I run "uv run ruff check ."
    Then the command exits with code 0

  Scenario: Ruff format shows no formatting issues
    Given the project dependencies are installed
    When I run "uv run ruff format --check ."
    Then the command exits with code 0

  Scenario: Mypy strict mode passes
    Given the project dependencies are installed
    When I run "uv run mypy src --strict"
    Then the command exits with code 0

  Scenario: Pytest runs successfully
    Given the project dependencies are installed
    When I run "uv run pytest"
    Then the command exits with code 0
    And the test report shows no failures

  Scenario: Pytest-test-categories is in strict mode
    Given the project dependencies are installed
    When I run a test marked as medium without the medium flag
    Then the test is skipped or excluded

  Scenario: Coverage cannot decrease below baseline
    Given a coverage baseline exists
    When a change would decrease coverage
    Then the coverage ratchet check fails
