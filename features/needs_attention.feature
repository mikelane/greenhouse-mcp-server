@attention @wip @ISSUE-50
Feature: needs_attention tool
  As a recruiter or hiring manager
  I need to know what is falling through the cracks
  So that I can take action before candidates are lost

  Scenario: Stale application detected
    Given an application in "Phone Screen" for 10 days with a 7-day threshold
    When I call needs_attention
    Then it appears in the stale applications list

  Scenario: Missing scorecard detected
    Given an interview completed 3 days ago with no scorecard
    When I call needs_attention
    Then it appears in the missing scorecards list

  Scenario: Pending offer detected
    Given an offer pending approval for 5 days
    When I call needs_attention
    Then it appears in the pending offers list

  Scenario: Nothing needs attention
    Given all applications are within SLA and all scorecards submitted
    When I call needs_attention
    Then the response indicates no items need attention

  Scenario: Filter by job_id
    Given a job_id filter
    When I call needs_attention
    Then only items for that job are returned

  Scenario: Custom days_stale threshold
    Given a custom days_stale threshold of 3
    When I call needs_attention
    Then it uses 3 days instead of default 7
