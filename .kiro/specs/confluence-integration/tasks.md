# Implementation Plan: Confluence & Jira Integration

## Overview

Extend `server.py` with helper functions, five Confluence tools, and two Jira write tools, following the existing patterns. Then create the `install.sh` setup script. All new code goes into `server.py` (single-file architecture) plus `install.sh` at the repo root.

## Tasks

- [ ] 1. Add Confluence helper functions
  - [ ] 1.1 Implement `_strip_html` to convert storage format XHTML to plain text
    - Strip HTML tags, decode entities, preserve line breaks from `<p>`, `<br/>`, `<li>`
    - Use `html.parser` or regex (no new dependencies)
    - _Requirements: 1.3_

  - [ ] 1.2 Implement `_text_to_storage` to convert plain text to Confluence storage format
    - Split on newlines, wrap each non-empty line in `<p>...</p>`
    - _Requirements: 4.1, 5.1_

  - [ ] 1.3 Implement `_parse_confluence_url` to extract page ID from URL or raw ID
    - Accept raw numeric IDs and full Confluence URLs (`/wiki/spaces/{KEY}/pages/{id}/...`)
    - Raise `ValueError` for unrecognized input
    - _Requirements: 1.2, 1.4_

  - [ ] 1.4 Implement `_confluence_api` HTTP helper
    - Prepend `/wiki/api/v2` (default) or `/wiki/rest/api` (v1) to path
    - Reuse `_auth_header()`, same timeout and error pattern as `_api`
    - Support GET, POST, PUT methods with optional JSON body
    - _Requirements: 7.1, 7.2, 7.3, 6.1, 6.2_

  - [ ]* 1.5 Write property tests for helper functions (Properties 1, 2, 4, 5)
    - **Property 1: Confluence URL parsing extracts correct page ID**
    - **Property 2: Storage format round trip preserves text content**
    - **Property 4: Confluence API helper constructs correct URL prefix**
    - **Property 5: HTTP errors produce structured JSON error objects**
    - Use Hypothesis with min 100 examples per property
    - **Validates: Requirements 1.2, 1.3, 7.1, 7.3**

- [ ] 2. Implement Confluence read tools
  - [ ] 2.1 Implement `get_confluence_page` tool
    - Use `_parse_confluence_url` to accept page ID or URL
    - Call `_confluence_api` with v2 endpoint, extract id/title/spaceId/version/body
    - Convert body via `_strip_html`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ] 2.2 Implement `search_confluence` tool
    - Accept CQL string and optional `max_results` (default 10)
    - Use v1 search endpoint, map results to id/title/space_key/last_modified
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 2.3 Implement `get_space_pages` tool
    - Resolve space key to space ID via v2 `/spaces?keys=` endpoint
    - Fetch pages via `/spaces/{id}/pages?limit=`, default 25 results
    - Map to id/title/status
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 2.4 Write unit tests for Confluence read tools
    - Mock API responses, verify correct field extraction and defaults
    - Test error passthrough for 404, 403
    - _Requirements: 1.1, 1.5, 2.1, 2.3, 2.4, 3.1, 3.4_

- [ ] 3. Checkpoint - Verify Confluence read tools
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Confluence write tools
  - [ ] 4.1 Implement `create_confluence_page` tool
    - Resolve space key to space ID
    - Build payload with `_text_to_storage` for body, optional `parentId`
    - POST to v2 `/pages`, return id/title/version
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ] 4.2 Implement `update_confluence_page` tool
    - Fetch current page to get version number
    - Build payload with incremented version and `_text_to_storage` body
    - PUT to v2 `/pages/{id}`, return id/title/version
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 4.3 Write unit tests for Confluence write tools
    - Mock API responses for create and update
    - Test parent_id inclusion, version increment, error passthrough (409 conflict)
    - _Requirements: 4.2, 4.3, 4.4, 5.2, 5.3, 5.4_

- [ ] 5. Implement Jira write tools
  - [ ] 5.1 Implement `_text_to_adf` helper to convert plain text to ADF JSON
    - Split on newlines, create paragraph nodes, return ADF doc structure
    - _Requirements: 8.3_

  - [ ] 5.2 Implement `create_ticket` tool
    - Build fields payload with project key, summary, issue type
    - Convert optional description via `_text_to_adf`, add optional assignee/priority
    - Validate required fields, return descriptive error if missing
    - POST to `/issue`, fetch created issue, return key/summary/status/type
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ] 5.3 Implement `update_ticket` tool
    - Build fields dict from non-empty params, PUT to `/issue/{key}`
    - If transition provided: fetch available transitions, case-insensitive match, POST transition; error with valid names if no match
    - If comment provided: convert to ADF, POST to `/issue/{key}/comment`
    - Return updated ticket via `get_ticket`
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 5.4 Write property tests for Jira helpers (Properties 3, 6, 7)
    - **Property 3: ADF round trip preserves text content**
    - **Property 6: Missing required fields produce descriptive errors**
    - **Property 7: Transition name lookup is case-insensitive and correct**
    - Use Hypothesis with min 100 examples per property
    - **Validates: Requirements 8.3, 8.6, 9.3**

  - [ ]* 5.5 Write unit tests for Jira write tools
    - Mock API responses for create and update
    - Test optional fields, transition not found error, comment addition
    - _Requirements: 8.1, 8.2, 8.5, 8.6, 9.1, 9.4, 9.6_

- [ ] 6. Checkpoint - Verify all tools
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Create install.sh setup script
  - [ ] 7.1 Implement `install.sh` at repository root
    - Prompt for Atlassian instance URL, email, API token
    - Create `~/.atlassian-mcp/` directory, clone/pull repo
    - Create/reuse Python venv, install dependencies
    - Write credentials to `~/.atlassian-mcp/.env`
    - Validate credentials via `/rest/api/3/myself` test call
    - Create/update `~/.kiro/settings/mcp.json` (merge with existing config)
    - Print success/failure summary
    - Script must be idempotent
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- All new code goes into `server.py` (single-file architecture) plus `install.sh`
- Property tests use Hypothesis; each references a design property number
- Checkpoints ensure incremental validation after each major group
