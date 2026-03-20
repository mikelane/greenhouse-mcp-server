@server @wip @ISSUE-49
Feature: MCP server shell
  As a user of the greenhouse-mcp-server
  I need the server to start and respond to MCP protocol messages
  So that AI agents can discover and use the available tools

  Scenario: Server starts and lists no tools
    Given the MCP server is running
    When I request the list of available tools
    Then I receive an empty tool list

  Scenario: Server reports its name
    Given the MCP server is running
    When I request server information
    Then the server name is "greenhouse-mcp"

  Scenario: Server requires API token configuration
    Given no GREENHOUSE_API_TOKEN is set
    When the server starts
    Then it reports a configuration error

  Scenario: Server initializes the DI container
    Given valid server configuration
    When the server starts
    Then the dioxide container is available to tools
