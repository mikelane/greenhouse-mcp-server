@candidate @wip @ISSUE-37
Feature: Candidate Dossier
  As a recruiter or hiring manager using the MCP server,
  I want to get a complete picture of a candidate in one response
  so that I can make informed decisions without multiple lookups.

  Scenario: Assembles complete dossier for candidate with applications
    Given a candidate with 2 applications, 3 scorecards, and 1 offer
    When I call candidate_dossier
    Then I receive all data assembled into one response

  Scenario: Returns profile with empty application list
    Given a candidate with no applications
    When I call candidate_dossier
    Then I receive the profile with empty application list

  Scenario: Groups scorecards by application
    Given a candidate with scorecards across multiple applications
    When I call candidate_dossier
    Then scorecards are grouped by application

  Scenario: Returns clear error for invalid candidate
    Given an invalid candidate_id
    When I call candidate_dossier
    Then I receive a clear error message

  Scenario: Includes pending offer details
    Given a candidate with a pending offer
    When I call candidate_dossier
    Then the offer details are included with status
