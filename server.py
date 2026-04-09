"""Atlassian MCP Server — Jira and Confluence tools for AI IDEs."""

import base64
import json
import os
import re
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load .env — check common locations
for env_path in [
    Path.home() / ".db3-atlassian-mcp" / ".env",
    Path(".env"),
]:
    if env_path.exists():
        load_dotenv(env_path)
        break

mcp = FastMCP("atlassian")

JIRA_USER = os.environ.get("JIRA_USER", "")
JIRA_API_KEY = os.environ.get("JIRA_API_KEY", "")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "")


def _auth_header():
    token = base64.b64encode(f"{JIRA_USER}:{JIRA_API_KEY}".encode()).decode()
    return f"Basic {token}"


def _api(path, method="GET", data=None):
    url = f"{JIRA_BASE_URL}/rest/api/3{path}"
    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            body_bytes = resp.read().decode()
            if not body_bytes:
                return {}
            return json.loads(body_bytes)
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": error_body}


def _extract_text(content):
    """Recursively extract plain text from Atlassian Document Format."""
    if not content:
        return ""
    parts = []
    if isinstance(content, dict):
        if content.get("type") == "text":
            return content.get("text", "")
        for child in content.get("content", []):
            parts.append(_extract_text(child))
    elif isinstance(content, list):
        for item in content:
            parts.append(_extract_text(item))
    return "\n".join(p for p in parts if p)


class _HTMLTextExtractor(HTMLParser):
    """HTMLParser subclass that converts HTML to plain text."""

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._linebreak_tags = {"p", "br", "li"}

    def handle_starttag(self, tag, attrs):
        if tag in self._linebreak_tags:
            self._pieces.append("\n")

    def handle_endtag(self, tag):
        if tag == "p":
            self._pieces.append("\n")

    def handle_data(self, data):
        self._pieces.append(data)

    def handle_entityref(self, name):
        from html import unescape
        self._pieces.append(unescape(f"&{name};"))

    def handle_charref(self, name):
        from html import unescape
        self._pieces.append(unescape(f"&#{name};"))

    def get_text(self) -> str:
        return "".join(self._pieces)


def _strip_html(html_string: str) -> str:
    """Convert Confluence storage format XHTML to plain text."""
    if not html_string:
        return ""
    parser = _HTMLTextExtractor()
    parser.feed(html_string)
    text = parser.get_text()
    # Collapse multiple consecutive newlines into at most two
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            result.append(stripped)
        elif result and result[-1] != "":
            result.append("")
    # Strip leading/trailing blank entries
    while result and result[-1] == "":
        result.pop()
    while result and result[0] == "":
        result.pop(0)
    return "\n".join(result)


def _text_to_storage(text: str) -> str:
    """Convert plain text to Confluence storage format XHTML.

    If the text already contains HTML tags, it is returned as-is
    (assumed to be pre-formatted storage format).
    """
    if not text:
        return ""
    if "<" in text and ">" in text:
        return text
    return "".join(f"<p>{line}</p>" for line in text.split("\n") if line)


def _text_to_adf(text: str) -> dict:
    """Convert plain text to Atlassian Document Format JSON."""
    if not text:
        return {"type": "doc", "version": 1, "content": []}
    paragraphs = [
        {"type": "paragraph", "content": [{"type": "text", "text": line}]}
        for line in text.split("\n")
        if line
    ]
    return {"type": "doc", "version": 1, "content": paragraphs}


def _resolve_user(query: str) -> str:
    """Resolve a display name or email to a Jira account ID.

    Accepts an account ID (returned as-is), email address, or display name.
    Returns the accountId string, or raises ValueError if no match is found.
    """
    # If it looks like an account ID already (hex string), return as-is
    if len(query) >= 20 and query.replace("-", "").isalnum() and "@" not in query and " " not in query:
        return query

    resp = _api(f"/user/search?query={quote(query)}&maxResults=5")
    if isinstance(resp, dict) and "error" in resp:
        raise ValueError(f"User search failed: {resp.get('detail', resp.get('error'))}")
    if isinstance(resp, list) and resp:
        return resp[0].get("accountId")
    raise ValueError(f"No user found matching '{query}'")


_CONFLUENCE_URL_RE = re.compile(
    r"https?://[^/]+/wiki/spaces/[^/]+/pages/(\d+)(?:/|$)"
)


def _parse_confluence_url(input_str: str) -> str:
    """Extract a numeric page ID from a raw ID string or Confluence page URL.

    Args:
        input_str: Either a raw numeric page ID (e.g. "12345") or a full
            Confluence URL like
            ``https://instance.atlassian.net/wiki/spaces/KEY/pages/123456/Page+Title``.

    Returns:
        The numeric page ID as a string.

    Raises:
        ValueError: If *input_str* is neither a numeric ID nor a recognised
            Confluence URL pattern.
    """
    if input_str.isdigit():
        return input_str

    match = _CONFLUENCE_URL_RE.search(input_str)
    if match:
        return match.group(1)

    raise ValueError(
        f"Expected a numeric page ID or a Confluence URL matching "
        f"https://{{instance}}/wiki/spaces/{{KEY}}/pages/{{pageId}}/..., "
        f"got: {input_str!r}"
    )


def _confluence_api(path, method="GET", data=None, api_version="v2"):
    prefix = "/wiki/api/v2" if api_version == "v2" else "/wiki/rest/api"
    url = f"{JIRA_BASE_URL}{prefix}{path}"
    headers = {
        "Authorization": _auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            body_bytes = resp.read().decode()
            if not body_bytes:
                return {}
            return json.loads(body_bytes)
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": error_body}


@mcp.tool()
def get_ticket(issue_key: str) -> str:
    """Fetch a Jira ticket by key (e.g. INFOSEC-2239). Returns summary, status, assignee, and description."""
    resp = _api(f"/issue/{issue_key}")
    if "error" in resp:
        return json.dumps(resp)
    fields = resp.get("fields", {})
    assignee = fields.get("assignee")
    result = {
        "key": resp.get("key"),
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "assignee": assignee.get("displayName") if assignee else None,
        "priority": fields.get("priority", {}).get("name"),
        "type": fields.get("issuetype", {}).get("name"),
        "description": _extract_text(fields.get("description")),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def search_tickets(jql: str, max_results: int = 10) -> str:
    """Search Jira tickets using JQL. Example: 'project = INFOSEC AND status = Open'"""
    resp = _api(f"/search/jql?jql={quote(jql)}&maxResults={max_results}&fields=summary,status,assignee")
    if "error" in resp:
        return json.dumps(resp)
    issues = []
    for issue in resp.get("issues", []):
        f = issue.get("fields") or {}
        assignee = f.get("assignee")
        issues.append({
            "key": issue.get("key") or issue.get("id"),
            "summary": f.get("summary"),
            "status": (f.get("status") or {}).get("name"),
            "assignee": assignee.get("displayName") if assignee else None,
        })
    return json.dumps(issues, indent=2)


@mcp.tool()
def get_child_issues(issue_key: str) -> str:
    """Get all child/sub-task issues for a given parent ticket."""
    jql = f'parent = {issue_key} ORDER BY rank ASC'
    return search_tickets(jql, max_results=50)


@mcp.tool()
def create_ticket(project_key: str, summary: str, issue_type: str, description: str = "", assignee: str = "", priority: str = "", parent_key: str = "") -> str:
    """Create a new Jira ticket. Requires project key, summary, and issue type name. Optionally set a parent issue key to create a sub-task."""
    for field_name, value in [("project_key", project_key), ("summary", summary), ("issue_type", issue_type)]:
        if not value:
            return json.dumps({"error": "Missing required field", "detail": f"{field_name} is required"})

    fields = {
        "project": {"key": project_key},
        "summary": summary,
        "issuetype": {"name": issue_type},
    }
    if parent_key:
        fields["parent"] = {"key": parent_key}
    if description:
        fields["description"] = _text_to_adf(description)
    if assignee:
        try:
            account_id = _resolve_user(assignee)
            fields["assignee"] = {"accountId": account_id}
        except ValueError as e:
            return json.dumps({"error": "Invalid assignee", "detail": str(e)})
    if priority:
        fields["priority"] = {"name": priority}

    resp = _api("/issue", method="POST", data={"fields": fields})
    if "error" in resp:
        return json.dumps(resp)

    key = resp.get("key")
    return get_ticket(key)


@mcp.tool()
def update_ticket(issue_key: str, summary: str = "", description: str = "", assignee: str = "", priority: str = "", transition: str = "", comment: str = "") -> str:
    """Update a Jira ticket. Can change fields, transition status, and/or add a comment."""
    # 1. Field updates
    fields = {}
    if summary:
        fields["summary"] = summary
    if description:
        fields["description"] = _text_to_adf(description)
    if assignee:
        try:
            account_id = _resolve_user(assignee)
            fields["assignee"] = {"accountId": account_id}
        except ValueError as e:
            return json.dumps({"error": "Invalid assignee", "detail": str(e)})
    if priority:
        fields["priority"] = {"name": priority}
    if fields:
        resp = _api(f"/issue/{issue_key}", method="PUT", data={"fields": fields})
        if resp and "error" in resp:
            return json.dumps(resp)

    # 2. Transition
    if transition:
        resp = _api(f"/issue/{issue_key}/transitions")
        if "error" in resp:
            return json.dumps(resp)
        available = resp.get("transitions", [])
        matched = None
        for t in available:
            if t.get("name", "").lower() == transition.lower():
                matched = t
                break
        if matched:
            resp = _api(f"/issue/{issue_key}/transitions", method="POST", data={"transition": {"id": matched["id"]}})
            if resp and "error" in resp:
                return json.dumps(resp)
        else:
            names = ", ".join(t.get("name", "") for t in available)
            return json.dumps({"error": "Invalid transition", "detail": f"'{transition}' not found. Available: {names}"})

    # 3. Comment
    if comment:
        resp = _api(f"/issue/{issue_key}/comment", method="POST", data={"body": _text_to_adf(comment)})
        if resp and "error" in resp:
            return json.dumps(resp)

    # 4. Return updated ticket
    return get_ticket(issue_key)


@mcp.tool()
def attach_file(issue_key: str, file_path: str) -> str:
    """Attach a file to a Jira ticket. Provide the issue key and absolute file path."""
    import mimetypes
    from pathlib import Path as FilePath

    path = FilePath(file_path).expanduser().resolve()
    if not path.exists():
        return json.dumps({"error": "File not found", "detail": f"{file_path} does not exist"})

    filename = path.name
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    boundary = "----KiroMCPBoundary"
    body_parts = []
    body_parts.append(f"--{boundary}".encode())
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    body_parts.append(f"Content-Type: {content_type}".encode())
    body_parts.append(b"")
    body_parts.append(path.read_bytes())
    body_parts.append(f"--{boundary}--".encode())
    body = b"\r\n".join(body_parts)

    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}/attachments"
    headers = {
        "Authorization": _auth_header(),
        "X-Atlassian-Token": "no-check",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=60) as resp:
            body_bytes = resp.read().decode()
            if not body_bytes:
                return json.dumps({"status": "attached", "file": filename, "issue": issue_key})
            result = json.loads(body_bytes)
            if isinstance(result, list) and result:
                return json.dumps({"status": "attached", "file": filename, "issue": issue_key, "id": result[0].get("id")})
            return json.dumps({"status": "attached", "file": filename, "issue": issue_key})
    except HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        return json.dumps({"error": f"HTTP {e.code}", "detail": error_body})


@mcp.tool()
def get_confluence_page(page_id: str) -> str:
    """Fetch a Confluence page by numeric ID or full URL. Returns title, space, version, and body as plain text."""
    try:
        parsed_id = _parse_confluence_url(page_id)
    except ValueError as e:
        return json.dumps({"error": "Invalid input", "detail": str(e)})

    resp = _confluence_api(f"/pages/{parsed_id}?body-format=storage")
    if "error" in resp:
        return json.dumps(resp)

    raw_storage = resp.get("body", {}).get("storage", {}).get("value", "")
    result = {
        "id": resp.get("id"),
        "title": resp.get("title"),
        "space_id": resp.get("spaceId"),
        "version": resp.get("version", {}).get("number"),
        "body": _strip_html(raw_storage),
        "body_storage": raw_storage,
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def search_confluence(cql: str, max_results: int = 10) -> str:
    """Search Confluence pages using CQL. Example: 'space = SECENG AND type = page'"""
    encoded_cql = quote(cql)
    resp = _confluence_api(
        f"/content/search?cql={encoded_cql}&limit={max_results}", api_version="v1"
    )
    if "error" in resp:
        return json.dumps(resp)
    results = []
    for item in resp.get("results", []):
        space_key = None
        space = item.get("space")
        if space and isinstance(space, dict):
            space_key = space.get("key")
        if not space_key:
            expandable = item.get("_expandable", {})
            space_path = expandable.get("space", "")
            # space path looks like "/rest/api/space/KEY"
            if space_path:
                space_key = space_path.rstrip("/").rsplit("/", 1)[-1]

        last_modified = None
        history = item.get("history")
        if history and isinstance(history, dict):
            last_updated = history.get("lastUpdated")
            if last_updated and isinstance(last_updated, dict):
                last_modified = last_updated.get("when")
        if not last_modified:
            version = item.get("version")
            if version and isinstance(version, dict):
                last_modified = version.get("when")

        results.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "space_key": space_key,
            "last_modified": last_modified,
        })
    return json.dumps(results, indent=2)


@mcp.tool()
def get_space_pages(space_key: str, max_results: int = 25) -> str:
    """List pages in a Confluence space. Example: space_key='SECENG'"""
    resp = _confluence_api(f"/spaces?keys={space_key}")
    if "error" in resp:
        return json.dumps(resp)
    spaces = resp.get("results", [])
    if not spaces:
        return json.dumps({"error": "Not found", "detail": f"No space found for key '{space_key}'"})
    space_id = spaces[0].get("id")
    if not space_id:
        return json.dumps({"error": "Not found", "detail": f"No space ID returned for key '{space_key}'"})

    pages_resp = _confluence_api(f"/spaces/{space_id}/pages?limit={max_results}")
    if "error" in pages_resp:
        return json.dumps(pages_resp)

    pages = []
    for page in pages_resp.get("results", []):
        pages.append({
            "id": page.get("id"),
            "title": page.get("title"),
            "status": page.get("status"),
        })
    return json.dumps(pages, indent=2)


@mcp.tool()
def create_confluence_page(space_key: str, title: str, body: str, parent_id: str = "") -> str:
    """Create a new Confluence page in a space. Optionally specify a parent page ID."""
    resp = _confluence_api(f"/spaces?keys={space_key}")
    if "error" in resp:
        return json.dumps(resp)
    spaces = resp.get("results", [])
    if not spaces:
        return json.dumps({"error": "Not found", "detail": f"No space found for key '{space_key}'"})
    space_id = spaces[0].get("id")
    if not space_id:
        return json.dumps({"error": "Not found", "detail": f"No space ID returned for key '{space_key}'"})

    payload = {
        "spaceId": space_id,
        "title": title,
        "status": "current",
        "body": {
            "representation": "storage",
            "value": _text_to_storage(body),
        },
    }
    if parent_id:
        payload["parentId"] = parent_id

    create_resp = _confluence_api("/pages", method="POST", data=payload)
    if "error" in create_resp:
        return json.dumps(create_resp)

    result = {
        "id": create_resp.get("id"),
        "title": create_resp.get("title"),
        "version": create_resp.get("version", {}).get("number"),
    }
    return json.dumps(result, indent=2)


@mcp.tool()
def update_confluence_page(page_id: str, title: str, body: str) -> str:
    """Update an existing Confluence page's content."""
    resp = _confluence_api(f"/pages/{page_id}")
    if "error" in resp:
        return json.dumps(resp)

    current_version = resp.get("version", {}).get("number", 0)

    payload = {
        "id": page_id,
        "title": title,
        "status": "current",
        "body": {
            "representation": "storage",
            "value": _text_to_storage(body),
        },
        "version": {
            "number": current_version + 1,
        },
    }

    update_resp = _confluence_api(f"/pages/{page_id}", method="PUT", data=payload)
    if "error" in update_resp:
        return json.dumps(update_resp)

    result = {
        "id": update_resp.get("id"),
        "title": update_resp.get("title"),
        "version": update_resp.get("version", {}).get("number"),
    }
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    mcp.run()
