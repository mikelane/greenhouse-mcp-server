@docs @wip @ISSUE-19
Feature: Documentation accuracy
  As a developer evaluating this project
  I need the documentation to be accurate
  So that I can trust the README and get started quickly

  Scenario: README tool table matches implementation
    Given the README tool reference section
    When I compare each tool's documented parameters to the actual function signature
    Then they match exactly

  Scenario: Installation instructions work
    Given a fresh clone of the repository
    When I run uv sync
    Then all dependencies install without errors

  Scenario: MCP server starts successfully
    Given the server is configured with a test profile
    When I start the server
    Then it reports ready on stdio transport

  Scenario: All five tools are documented
    Given the README tool reference section
    Then it documents pipeline_health, candidate_dossier, needs_attention, hiring_velocity, and search_talent
