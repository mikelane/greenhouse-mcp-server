@velocity @wip @ISSUE-23
Feature: hiring_velocity tool
  As a recruiter or hiring manager
  I need to know whether we are getting faster or slower at hiring
  So that I can adjust sourcing, process, or headcount accordingly

  Scenario: Weekly application counts
    Given applications created on known dates across several weeks
    When I call hiring_velocity with default parameters
    Then it returns weekly buckets each with a start date and count

  Scenario: Trend direction improving
    Given weekly application counts that increase over time
    When I call hiring_velocity
    Then the trend is "improving"

  Scenario: Trend direction worsening
    Given weekly application counts that decrease over time
    When I call hiring_velocity
    Then the trend is "worsening"

  Scenario: Offer acceptance rate
    Given 3 accepted offers and 1 rejected offer
    When I call hiring_velocity
    Then the acceptance rate is 75.0 percent

  Scenario: Department aggregation
    Given applications across two departments and no job_id filter
    When I call hiring_velocity
    Then it returns metrics grouped by department with an overall summary

  Scenario: Insufficient data warning
    Given fewer than 5 applications in the time range
    When I call hiring_velocity
    Then it returns data with insufficient_data set to true and a warning message
