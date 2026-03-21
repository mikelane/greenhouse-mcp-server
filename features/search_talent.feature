@search @wip @ISSUE-31
Feature: search_talent tool
  As a recruiter or hiring manager
  I need to find candidates matching specific criteria
  So that I can quickly locate talent in my pipeline

  Scenario: Search by name
    Given candidates with names "Maria Chen" and "James Wilson"
    When I search for "maria"
    Then the results include "Maria Chen"
    And the results do not include "James Wilson"

  Scenario: Filter by stage
    Given candidates at stages "Phone Screen" and "Technical Interview"
    When I search with stage filter "Phone Screen"
    Then only candidates in "Phone Screen" are returned

  Scenario: Filter by source
    Given candidates sourced from "Referral" and "LinkedIn"
    When I search with source filter "Referral"
    Then only candidates sourced from "Referral" are returned

  Scenario: Date range filtering
    Given candidates created 10 days ago and 60 days ago
    When I search with created_after set to 30 days ago
    Then only the recently created candidate is returned

  Scenario: Empty result handling
    Given no candidates match the search criteria
    When I search for "nonexistent"
    Then the response contains zero results
    And the response includes a helpful message

  Scenario: Tag filtering
    Given candidates tagged "senior" and candidates with no tags
    When I search with tag filter "senior"
    Then only candidates tagged "senior" are returned
