@pipeline @wip @ISSUE-12
Feature: Pipeline health analysis
  As a recruiter or hiring manager
  I need to see where candidates are piling up in my hiring pipeline
  So that I can take action on bottlenecks before they delay hiring

  Scenario: Single job with applications across multiple stages
    Given a job with 10 applications across 4 stages
    When I call pipeline_health with that job_id
    Then I receive counts per stage and days since last activity for each

  Scenario: Bottleneck detection by candidate concentration
    Given a job where stage "Technical Interview" has 5 of 10 candidates with 4 stale
    When I call pipeline_health
    Then "Technical Interview" is flagged as a bottleneck with severity "HIGH"

  Scenario: All open jobs aggregation
    Given no job_id is provided
    When I call pipeline_health
    Then I receive pipeline data for all open jobs with a jobs_needing_attention summary

  Scenario: Job with zero applications
    Given a job with zero applications
    When I call pipeline_health with that job_id
    Then I receive an empty pipeline with zero counts and no bottlenecks

  Scenario: Job ID that does not exist
    Given a job_id that does not exist
    When I call pipeline_health with that job_id
    Then I receive a clear error indicating the job was not found
