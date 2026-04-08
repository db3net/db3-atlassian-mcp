"""Lightweight Jira MCP server using FastMCP."""

import base64
import json
import os
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pathlib import Path

from dotenv import load_dotenv
from fastmcp import FastMCP

# Load .env from the venv directory (Kiro doesn't inherit shell env)
load_dotenv(Path.home() / ".atlassian-mcp" / ".env")

mcp = FastMCP("jira")

JIRA_USER = os.environ.get("JIRA_USER", "dblack@merchante.com")
JIRA_API_KEY = os.environ.get("JIRA_API_KEY", "")
JIRA_BASE_URL = os.environ.get("JIRA_BASE_URL", "https://merchante.atlassian.net")


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
            return json.loads(resp.read().decode())
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
    resp = _api(f"/search/jql?jql={quote(jql)}&maxResults={max_results}")
    if "error" in resp:
        return json.dumps(resp)
    issues = []
    for issue in resp.get("issues", []):
        f = issue.get("fields", {})
        assignee = f.get("assignee")
        issues.append({
            "key": issue.get("key"),
            "summary": f.get("summary"),
            "status": f.get("status", {}).get("name"),
            "assignee": assignee.get("displayName") if assignee else None,
        })
    return json.dumps(issues, indent=2)


@mcp.tool()
def get_child_issues(issue_key: str) -> str:
    """Get all child/sub-task issues for a given parent ticket."""
    jql = f'parent = {issue_key} ORDER BY rank ASC'
    return search_tickets(jql, max_results=50)


if __name__ == "__main__":
    mcp.run()
