@bdd-infra @wip @ISSUE-26
Feature: Cross-language BDD infrastructure
  As a test engineer
  I need cucumber-js to drive a Python process
  So that BDD step definitions cannot import Python internals

  Scenario: Server starts and responds to health check
    Given a running Python test server
    When I request GET /health
    Then the response status is 200
    And the response body contains "ok"

  Scenario: Server returns 404 for unknown routes
    Given a running Python test server
    When I request GET /nonexistent
    Then the response status is 404
