# Requirements Document

## Introduction

Transform an existing single-file Jira MCP server (`server.py`) into a distributable Python package called `atlassian-mcp`. The package will be restructured following Python packaging best practices, broadened in scope to support the wider Atlassian ecosystem, and accompanied by local and Confluence-hosted documentation. The goal is a product that can be installed via `pip`, configured via environment variables or `.env`, and extended with additional Atlassian service integrations over time.

## Glossary

- **MCP_Server**: The FastMCP-based server process that exposes Atlassian tools to MCP clients
- **Package**: The distributable Python package named `atlassian-mcp`, installable via pip
- **ADF_Extractor**: The module responsible for converting Atlassian Document Format content into plain text
- **API_Client**: The internal HTTP client module that handles authenticated requests to Atlassian REST APIs
- **Jira_Tools**: The set of MCP tool functions that interact with the Jira REST API (get_ticket, search_tickets, get_child_issues)
- **Configuration**: The set of environment variables (JIRA_USER, JIRA_API_KEY, JIRA_BASE_URL) and optional `.env` file used to configure the server
- **Local_Docs**: A Markdown instruction file shipped with the package for local reference
- **Confluence_Docs**: Documentation published to a Confluence space describing setup, usage, and extension of the package
- **CLI_Entry_Point**: A console script entry point that allows users to start the MCP server from the command line

## Requirements

### Requirement 1: Python Package Structure

**User Story:** As a developer, I want the project structured as a proper Python package, so that I can install, distribute, and maintain it using standard Python tooling.

#### Acceptance Criteria

1. THE Package SHALL use a `pyproject.toml` file as the single source of build configuration and metadata
2. THE Package SHALL define the package name as `atlassian-mcp` in `pyproject.toml`
3. THE Package SHALL declare `fastmcp`, `python-dotenv` as runtime dependencies in `pyproject.toml`
4. THE Package SHALL organize source code under an `atlassian_mcp/` directory containing an `__init__.py` module
5. THE Package SHALL be installable via `pip install .` from the project root without errors
6. THE Package SHALL include a `README.md` at the project root describing the package purpose and quickstart instructions

### Requirement 2: Modular Code Organization

**User Story:** As a developer, I want the monolithic server.py split into focused modules, so that the codebase is maintainable and extensible.

#### Acceptance Criteria

1. THE Package SHALL contain a `config.py` module responsible for loading and validating Configuration from environment variables and `.env` files
2. THE Package SHALL contain a `client.py` module encapsulating the API_Client logic for authenticated HTTP requests to Atlassian REST APIs
3. THE Package SHALL contain an `adf.py` module encapsulating the ADF_Extractor logic for converting Atlassian Document Format to plain text
4. THE Package SHALL contain a `tools/jira.py` module defining all Jira_Tools (get_ticket, search_tickets, get_child_issues)
5. THE Package SHALL contain a `server.py` module that initializes the FastMCP instance and registers all tool modules
6. WHEN a new Atlassian service integration is added, THE Package SHALL allow registering new tool modules without modifying existing tool files

### Requirement 3: Configuration Management

**User Story:** As a user, I want flexible configuration options, so that I can set up the server in different environments without modifying code.

#### Acceptance Criteria

1. THE Configuration SHALL support loading values from environment variables `JIRA_USER`, `JIRA_API_KEY`, and `JIRA_BASE_URL`
2. THE Configuration SHALL support loading values from a `.env` file in the current working directory
3. THE Configuration SHALL support loading values from a `.env` file specified via the `ATLASSIAN_MCP_ENV_FILE` environment variable
4. IF `JIRA_API_KEY` is not set or is empty, THEN THE MCP_Server SHALL raise a clear error message at startup indicating the missing credential
5. IF `JIRA_BASE_URL` is not set or is empty, THEN THE MCP_Server SHALL raise a clear error message at startup indicating the missing base URL

### Requirement 4: Jira Tool Functionality Preservation

**User Story:** As a user, I want all existing Jira capabilities preserved in the new package, so that the migration does not break any current functionality.

#### Acceptance Criteria

1. WHEN a valid issue key is provided, THE Jira_Tools get_ticket function SHALL return a JSON object containing key, summary, status, assignee, priority, type, and description fields
2. WHEN an invalid or non-existent issue key is provided, THE Jira_Tools get_ticket function SHALL return a JSON object containing an error field with the HTTP status code
3. WHEN a valid JQL query is provided, THE Jira_Tools search_tickets function SHALL return a JSON array of matching issues each containing key, summary, status, and assignee fields
4. WHEN a valid parent issue key is provided, THE Jira_Tools get_child_issues function SHALL return all child and sub-task issues ordered by rank ascending
5. THE ADF_Extractor SHALL recursively extract plain text from nested Atlassian Document Format content, joining text nodes with newline separators
6. WHEN the ADF_Extractor receives empty or null content, THE ADF_Extractor SHALL return an empty string

### Requirement 5: CLI Entry Point

**User Story:** As a user, I want to start the MCP server from the command line after installing the package, so that I do not need to know the internal module structure.

#### Acceptance Criteria

1. THE Package SHALL define a console script entry point named `atlassian-mcp` in `pyproject.toml`
2. WHEN the user runs `atlassian-mcp` from the command line, THE CLI_Entry_Point SHALL start the MCP_Server
3. WHEN the user runs `python -m atlassian_mcp`, THE Package SHALL start the MCP_Server

### Requirement 6: Local Documentation

**User Story:** As a developer, I want a local Markdown instruction file, so that I can reference setup and usage without leaving my editor.

#### Acceptance Criteria

1. THE Local_Docs SHALL include a prerequisites section listing Python version requirements and required environment variables
2. THE Local_Docs SHALL include step-by-step installation instructions covering virtual environment creation, package installation, and `.env` configuration
3. THE Local_Docs SHALL include usage examples showing how to start the server and configure it with an MCP client
4. THE Local_Docs SHALL include a section describing each available Jira tool with its parameters and example output
5. THE Local_Docs SHALL include a section describing how to add new Atlassian service integrations

### Requirement 7: Confluence Documentation

**User Story:** As a team member, I want documentation published to Confluence, so that the wider team can discover and reference the tool without accessing the source repository.

#### Acceptance Criteria

1. THE Package SHALL include a `tools/confluence.py` module defining MCP tools for interacting with the Confluence REST API
2. WHEN a page title, space key, and body content are provided, THE Confluence_Docs tool SHALL create or update a Confluence page via the Confluence REST API
3. THE Local_Docs SHALL include instructions for publishing documentation to Confluence using the provided Confluence tool
4. IF the Confluence API returns an error, THEN THE Confluence_Docs tool SHALL return a JSON object containing the error code and detail message

### Requirement 8: Distribution Readiness

**User Story:** As a maintainer, I want the package ready for distribution, so that other teams can install it from a package index or directly from the repository.

#### Acceptance Criteria

1. THE Package SHALL include a `LICENSE` file at the project root
2. THE Package SHALL build a distributable wheel and sdist via `python -m build` without errors
3. THE Package SHALL include a `.gitignore` file covering Python build artifacts, virtual environments, `.env` files, and IDE configuration directories
4. THE Package SHALL pin minimum versions for all runtime dependencies in `pyproject.toml`
