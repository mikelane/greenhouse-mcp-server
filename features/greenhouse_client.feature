@client @wip @ISSUE-42
Feature: Greenhouse API client
  As the MCP server
  I need a reliable client for the Greenhouse Harvest API
  So that tools can fetch recruiting data without worrying about auth, rate limits, or pagination

  Scenario: Client authenticates with Basic Auth
    Given valid Greenhouse API credentials
    When the client makes a request to the Harvest API
    Then the request includes a Basic Auth header with the token as username and blank password

  Scenario: Client tracks rate limit headers
    Given the API response includes X-RateLimit-Remaining: 2
    When the client processes the response
    Then the client records 2 remaining requests in the current window

  Scenario: Client backs off when rate limit is low
    Given the API response includes X-RateLimit-Remaining: 0
    And the API response includes X-RateLimit-Reset with a future timestamp
    When the client prepares the next request
    Then the client waits until the reset timestamp before sending

  Scenario: Client retries on HTTP 429
    Given the API returns HTTP 429 with Retry-After: 5
    When the client processes the response
    Then the client retries the request after the specified delay

  Scenario: Client retries on HTTP 500 with exponential backoff
    Given the API returns HTTP 500
    When the client retries
    Then it uses exponential backoff up to the configured retry limit

  Scenario: Client follows pagination via Link headers
    Given the API returns a response with Link header containing rel="next"
    When the client fetches a paginated resource
    Then it follows all pages until no rel="next" is present
    And returns the combined results

  Scenario: Client raises authentication error on HTTP 401
    Given invalid API credentials
    When the client makes a request
    Then it raises an AuthenticationError

  Scenario: Client raises not found error on HTTP 404
    Given a request for a non-existent resource
    When the client makes the request
    Then it raises a NotFoundError

  Scenario: Client handles empty collections
    Given the API returns an empty JSON array
    When the client fetches a list resource
    Then it returns an empty list without error
