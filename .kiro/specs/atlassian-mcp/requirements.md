# Atlassian MCP Server
## Confluence & Jira Integration

**Requirements Document**

Author: dblack

Version 1.1 | April 2026

---

## Introduction

The Atlassian MCP Server gives developers a way to interact with Jira and Confluence directly from their IDE. Instead of switching between browser tabs to look up tickets, search for documentation, create issues, or update wiki pages, developers can do all of it through natural language prompts in their editor.

The server currently supports reading Jira tickets. This project extends it to support full read and write access to both Jira and Confluence, along with a simple installer that gets new users up and running in under a minute.

## Glossary

- **MCP_Server**: The server process that exposes tools to the IDE
- **Confluence_API**: The Atlassian Confluence REST API used for reading and writing wiki pages
- **Page**: A Confluence page identified by its numeric page ID, containing a title and body
- **Space**: A Confluence space identified by its space key (e.g. `SECENG`), which contains pages organized in a hierarchy
- **Storage_Format**: Confluence's XHTML-based storage representation used for reading and writing page bodies
- **ADF**: Atlassian Document Format, a JSON-based document representation
- **Jira_API**: The Atlassian Jira REST API used for reading and writing tickets
- **Jira_Ticket**: A Jira issue identified by its issue key (e.g. `INFOSEC-2239`)
- **Issue_Type**: The type of a Jira ticket (e.g. Task, Bug, Story, Epic) as defined in the target project
- **Transition**: A workflow status change for a Jira ticket (e.g. moving from "Open" to "In Progress")

## Problem Statement

### Developers

**Who they are:** Software engineers and DevOps team members who use Jira for task tracking and Confluence for documentation on a daily basis.

**Their workflow:** Developers work primarily in their IDE. When they need to reference a Jira ticket, check a wiki page, file a new issue, or update documentation, they switch to a browser, navigate to the Atlassian interface, perform the action, and switch back. This happens dozens of times per day.

**Problems and challenges:**
- Context switching between the IDE and browser breaks flow and costs time
- Looking up ticket details requires navigating Jira's UI, finding the right project, and locating the issue
- Creating tickets for bugs or tasks found during development requires leaving the editor, filling out forms, and returning
- Updating Confluence documentation means opening the wiki, finding the page, entering the editor, making changes, and publishing
- Searching across Jira and Confluence requires separate searches in separate interfaces
- New team members need to manually configure credentials and server settings to use the existing Jira integration

### Team Leads

**Who they are:** Engineering managers and team leads who need visibility into project status and maintain team documentation.

**Their workflow:** Team leads review tickets, update statuses, add comments during code reviews, and maintain runbooks and process documentation in Confluence.

**Problems and challenges:**
- Adding comments or transitioning ticket status during code review requires switching to Jira
- Keeping Confluence documentation up to date is tedious enough that it often falls behind
- There is no quick way to create or update wiki pages from the development environment

## Available MCP Tools

### Jira (existing)
- `get_ticket` — Fetch a Jira ticket by issue key
- `search_tickets` — Search Jira tickets using JQL
- `get_child_issues` — Get child/sub-task issues for a parent ticket

### Jira (new)
- `create_ticket` — Create a new Jira ticket in a project
- `update_ticket` — Update fields, transition status, or add comments on an existing ticket

### Confluence (new)
- `get_confluence_page` — Fetch a Confluence page by ID or URL
- `search_confluence` — Search Confluence pages using CQL
- `get_space_pages` — List pages in a Confluence space
- `create_confluence_page` — Create a new page in a space
- `update_confluence_page` — Update an existing page's content

## Requirements

### Requirement 1: Read a Confluence Page by ID or URL

**User Story:** As a developer, I want to fetch a Confluence page by its ID or by pasting a Confluence URL, so that I can read its title and content through the MCP server without needing to know the page ID.

#### Acceptance Criteria

1. WHEN a valid page ID is provided, THE MCP_Server SHALL return the page title, space key, version number, and body content as plain text
2. WHEN a Confluence page URL is provided (e.g. `https://instance.atlassian.net/wiki/spaces/KEY/pages/123456/Page+Title`), THE MCP_Server SHALL extract the page ID from the URL and fetch the page
3. WHEN the Confluence_API returns the page body in Storage_Format or ADF, THE MCP_Server SHALL convert the body to readable plain text
4. IF the input is neither a valid page ID nor a recognizable Confluence URL, THEN THE MCP_Server SHALL return a descriptive error message
5. IF the page ID does not exist or the user lacks permission, THEN THE MCP_Server SHALL return a JSON object containing the HTTP error code and error detail from the Confluence_API

### Requirement 2: Search Confluence Pages

**User Story:** As a developer, I want to search Confluence pages by title or CQL query, so that I can find relevant pages without knowing their IDs.

#### Acceptance Criteria

1. WHEN a CQL query string is provided, THE MCP_Server SHALL return a list of matching pages with each entry containing the page ID, title, space key, and last-modified date
2. WHEN a max_results parameter is provided, THE MCP_Server SHALL limit the number of returned results to that value
3. WHEN no max_results parameter is provided, THE MCP_Server SHALL default to returning at most 10 results
4. IF the CQL query is malformed, THEN THE MCP_Server SHALL return the error detail from the Confluence_API response

### Requirement 3: Get Pages in a Confluence Space

**User Story:** As a developer, I want to list pages in a given Confluence space, so that I can browse the contents of a space like SECENG.

#### Acceptance Criteria

1. WHEN a valid space key is provided, THE MCP_Server SHALL return a list of pages in that space with each entry containing the page ID, title, and status
2. WHEN a max_results parameter is provided, THE MCP_Server SHALL limit the number of returned pages to that value
3. WHEN no max_results parameter is provided, THE MCP_Server SHALL default to returning at most 25 results
4. IF the space key does not exist or the user lacks permission, THEN THE MCP_Server SHALL return a JSON object containing the HTTP error code and error detail from the Confluence_API

### Requirement 4: Create a Confluence Page

**User Story:** As a developer, I want to create a new Confluence page in a given space, so that I can publish documentation through the MCP server.

#### Acceptance Criteria

1. WHEN a space key, title, and body content string are provided, THE MCP_Server SHALL create a new page in the specified space using the Confluence_API
2. WHEN the page is created successfully, THE MCP_Server SHALL return the new page ID, title, and version number
3. WHEN an optional parent page ID is provided, THE MCP_Server SHALL create the page as a child of the specified parent
4. IF the space key is invalid or the user lacks create permission, THEN THE MCP_Server SHALL return a JSON object containing the HTTP error code and error detail from the Confluence_API

### Requirement 5: Update an Existing Confluence Page

**User Story:** As a developer, I want to update the content of an existing Confluence page, so that I can keep documentation current through the MCP server.

#### Acceptance Criteria

1. WHEN a page ID, title, and new body content string are provided, THE MCP_Server SHALL update the page by incrementing the current version number and submitting the new content to the Confluence_API
2. WHEN the page is updated successfully, THE MCP_Server SHALL return the page ID, title, and new version number
3. IF the page ID does not exist or the user lacks edit permission, THEN THE MCP_Server SHALL return a JSON object containing the HTTP error code and error detail from the Confluence_API
4. IF the version number is stale (concurrent edit conflict), THEN THE MCP_Server SHALL return the conflict error detail from the Confluence_API

### Requirement 6: Reuse Existing Authentication

**User Story:** As a developer, I want Confluence tools to use the same Atlassian credentials as the Jira tools, so that I do not need to configure separate authentication.

#### Acceptance Criteria

1. THE MCP_Server SHALL authenticate Confluence_API requests using the same credentials used for Jira API requests
2. THE MCP_Server SHALL construct Confluence_API URLs using the same base URL with the `/wiki` path prefix

### Requirement 7: Confluence API HTTP Helper

**User Story:** As a developer, I want a dedicated HTTP helper for Confluence API calls, so that Confluence endpoints are cleanly separated from Jira endpoints in the codebase.

#### Acceptance Criteria

1. THE MCP_Server SHALL provide a Confluence-specific API helper function that targets the Confluence API endpoints
2. THE MCP_Server SHALL reuse the existing authentication mechanism for the Confluence API helper
3. WHEN the Confluence_API returns an HTTP error, THE MCP_Server SHALL return a structured error object containing the HTTP status code and error body, consistent with the existing error handling pattern

### Requirement 8: Create a Jira Ticket

**User Story:** As a developer, I want to create a new Jira ticket through the MCP server, so that I can file issues without leaving my development workflow.

#### Acceptance Criteria

1. WHEN a project key, summary, and Issue_Type name are provided, THE MCP_Server SHALL create a new Jira_Ticket in the specified project using the Jira_API
2. WHEN the Jira_Ticket is created successfully, THE MCP_Server SHALL return the new issue key, summary, status, and issue type
3. WHEN an optional description string is provided, THE MCP_Server SHALL include the description in the created Jira_Ticket
4. WHEN optional fields (assignee, priority) are provided, THE MCP_Server SHALL set those fields on the created Jira_Ticket
5. IF the project key is invalid or the user lacks create permission, THEN THE MCP_Server SHALL return a structured error object containing the HTTP error code and error detail from the Jira_API
6. IF a required field (project key, summary, or Issue_Type) is missing, THEN THE MCP_Server SHALL return a descriptive error message identifying the missing field

### Requirement 9: Update an Existing Jira Ticket

**User Story:** As a developer, I want to update fields on an existing Jira ticket and add comments, so that I can manage issues through the MCP server.

#### Acceptance Criteria

1. WHEN an issue key and one or more editable fields (summary, description, assignee, priority) are provided, THE MCP_Server SHALL update the specified fields on the Jira_Ticket using the Jira_API
2. WHEN the Jira_Ticket is updated successfully, THE MCP_Server SHALL return the issue key and the updated field values
3. WHEN a transition name is provided, THE MCP_Server SHALL look up the matching Transition ID from the available transitions for the Jira_Ticket and apply the status change
4. IF the specified transition name does not match any available Transition for the Jira_Ticket, THEN THE MCP_Server SHALL return an error listing the valid transition names
5. WHEN a comment string is provided, THE MCP_Server SHALL add the comment to the Jira_Ticket using the Jira_API
6. IF the issue key does not exist or the user lacks edit permission, THEN THE MCP_Server SHALL return a structured error object containing the HTTP error code and error detail from the Jira_API

### Requirement 10: Easy Installation and Setup

**User Story:** As a developer setting up this MCP server for the first time, I want to run a single command to install and configure everything, so that I can get up and running quickly without reading docs or manually editing config files.

#### Acceptance Criteria

1. THE project SHALL provide an `install.sh` script at the root of the repository
2. WHEN the install script is run, it SHALL prompt the user for their Atlassian instance URL, email address, and API token
3. WHEN credentials are provided, the install script SHALL store them securely in a hidden directory
4. THE install script SHALL download the server code and install all required dependencies
5. WHEN the install script completes, it SHALL configure the user's IDE to use the MCP server automatically
6. IF the installation directory already exists, the install script SHALL reuse it and update dependencies rather than recreating it
7. THE install script SHALL validate that the provided credentials can authenticate against the Atlassian API and report success or failure to the user
