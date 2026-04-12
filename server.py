"""Atlassian MCP Server — Jira and Confluence tools for AI IDEs."""

from __future__ import annotations

import base64
import json
import os
import re
from html import escape
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
_FIELD_NAME_CACHE: dict[str, str] | None = None
_FIELD_METADATA_CACHE: list[dict] | None = None
_DEFAULT_CUSTOM_FIELD_EXCLUDE_VALUES = {"Pending", "___________________", "{}"}
_DEFAULT_CUSTOM_FIELD_EXCLUDE_NAMES = {"HARDWARE NEEDED"}
_DEFAULT_RICH_TEXT_FIELD_NAMES = {
    "Back-Out Procedure",
    "(Business) Impact of Change",
    "Planned Activity List",
    "Reason for Change",
    "Test Plan",
}


def _env_set(name: str) -> set[str]:
    return {
        value.strip()
        for value in os.environ.get(name, "").split(",")
        if value.strip()
    }


def _custom_field_exclude_names() -> set[str]:
    return _DEFAULT_CUSTOM_FIELD_EXCLUDE_NAMES | _env_set("JIRA_CUSTOM_FIELD_EXCLUDE_NAMES")


def _custom_field_exclude_values() -> set[str]:
    return _DEFAULT_CUSTOM_FIELD_EXCLUDE_VALUES | _env_set("JIRA_CUSTOM_FIELD_EXCLUDE_VALUES")


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


def _get_field_names() -> dict[str, str]:
    """Return Jira field IDs mapped to display names."""
    global _FIELD_NAME_CACHE
    if _FIELD_NAME_CACHE is not None:
        return _FIELD_NAME_CACHE

    _FIELD_NAME_CACHE = {
        field.get("id"): field.get("name")
        for field in _get_field_metadata()
        if isinstance(field, dict) and field.get("id") and field.get("name")
    }
    return _FIELD_NAME_CACHE


def _get_field_metadata() -> list[dict]:
    """Return Jira field metadata from /field, cached after first lookup."""
    global _FIELD_METADATA_CACHE
    if _FIELD_METADATA_CACHE is not None:
        return _FIELD_METADATA_CACHE

    resp = _api("/field")
    if isinstance(resp, dict) and "error" in resp:
        return []

    _FIELD_METADATA_CACHE = [field for field in resp if isinstance(field, dict)]
    return _FIELD_METADATA_CACHE


def _field_by_id(field_id: str) -> dict | None:
    for field in _get_field_metadata():
        if field.get("id") == field_id:
            return field
    return None


def _field_by_name(field_name: str) -> dict | None:
    target = field_name.casefold()
    matches = [
        field for field in _get_field_metadata()
        if field.get("name", "").casefold() == target
    ]
    return matches[0] if matches else None


def _resolve_field_key(field_key: str) -> tuple[str, dict | None]:
    """Resolve either a Jira field ID or display name to a Jira field ID."""
    if field_key.startswith("customfield_") or _field_by_id(field_key):
        return field_key, _field_by_id(field_key)
    field = _field_by_name(field_key)
    if not field:
        return field_key, None
    return field["id"], field


def _is_empty_field_value(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _normalize_jira_field_value(value):
    """Convert Jira field values to compact JSON-friendly values."""
    if _is_empty_field_value(value):
        return None

    if isinstance(value, dict):
        if value.get("type") == "doc":
            return _extract_text(value)
        if "displayName" in value:
            return value.get("displayName")
        if "value" in value:
            if isinstance(value.get("child"), dict) and value["child"].get("value"):
                return f"{value.get('value')} - {value['child'].get('value')}"
            return value.get("value")
        if "name" in value:
            return value.get("name")
        if "content" in value:
            return _extract_text(value)
        return value

    if isinstance(value, list):
        normalized = [
            item
            for item in (_normalize_jira_field_value(item) for item in value)
            if not _is_empty_field_value(item)
        ]
        return normalized or None

    return value


def _is_noisy_custom_field(field_name: str, value) -> bool:
    if field_name in _custom_field_exclude_names():
        return True

    exclude_values = _custom_field_exclude_values()
    if isinstance(value, str):
        return value.strip() in exclude_values
    if isinstance(value, list):
        return bool(value) and all(_is_noisy_custom_field(field_name, item) for item in value)
    return False


def _custom_fields(fields: dict, include_noise: bool = False) -> dict:
    """Extract populated customfield_* values keyed by human-readable field name."""
    field_names = _get_field_names()
    custom = {}
    for field_id, value in fields.items():
        if not field_id.startswith("customfield_"):
            continue
        normalized = _normalize_jira_field_value(value)
        if _is_empty_field_value(normalized):
            continue
        field_name = field_names.get(field_id, field_id)
        if not include_noise and _is_noisy_custom_field(field_name, normalized):
            continue
        if field_name in custom:
            field_name = f"{field_name} ({field_id})"
        custom[field_name] = normalized
    return custom


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


def _inline_segments(value: str) -> list[tuple[str, str | None]]:
    """Split a text span into plain/marked inline segments."""
    segments: list[tuple[str, str | None]] = []
    pos = 0
    patterns = [
        (re.compile(r"`([^`]+)`"), "code"),
        (re.compile(r"\{\{([^{}]+)\}\}"), "code"),
        (re.compile(r"\*\*([^*]+)\*\*"), "strong"),
        (re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)"), "em"),
    ]

    while pos < len(value):
        matches = [
            (match.start(), match.end(), match.group(1), mark)
            for pattern, mark in patterns
            for match in [pattern.search(value, pos)]
            if match
        ]
        if not matches:
            segments.append((value[pos:], None))
            break
        start, end, marked_text, mark = min(matches, key=lambda item: item[0])
        if start > pos:
            segments.append((value[pos:start], None))
        segments.append((marked_text, mark))
        pos = end

    return [(segment, mark) for segment, mark in segments if segment]


def _adf_inline_nodes(value: str) -> list[dict]:
    mark_types = {
        "code": "code",
        "strong": "strong",
        "em": "em",
    }
    nodes = []
    for segment, mark in _inline_segments(value):
        node = {"type": "text", "text": segment}
        if mark:
            node["marks"] = [{"type": mark_types[mark]}]
        nodes.append(node)
    return nodes


def _storage_inline(value: str) -> str:
    tags = {
        "code": "code",
        "strong": "strong",
        "em": "em",
    }
    parts = []
    for segment, mark in _inline_segments(value):
        escaped = escape(segment)
        if mark:
            tag = tags[mark]
            parts.append(f"<{tag}>{escaped}</{tag}>")
        else:
            parts.append(escaped)
    return "".join(parts)


def _is_fence(line: str) -> re.Match | None:
    return re.match(r"^```(\S*)\s*$", line.strip())


def _heading_match(line: str) -> tuple[int, str] | None:
    stripped = line.strip()
    markdown_heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
    if markdown_heading:
        return len(markdown_heading.group(1)), markdown_heading.group(2)
    jira_heading = re.match(r"^h([1-6])\.\s+(.+)$", stripped)
    if jira_heading:
        return int(jira_heading.group(1)), jira_heading.group(2)
    return None


def _list_match(line: str) -> tuple[str, str, str] | None:
    stripped = line.strip()
    bullet = re.match(r"^[-*]\s+(.+)$", stripped)
    if bullet:
        return "bullet", r"^[-*]\s+(.+)$", bullet.group(1)
    ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
    if ordered:
        return "ordered", r"^\d+\.\s+(.+)$", ordered.group(1)
    return None


def _text_to_storage(text: str) -> str:
    """Convert markdown-ish text to Confluence storage format XHTML.

    If the text already contains HTML tags, it is returned as-is
    (assumed to be pre-formatted storage format).
    """
    if not text:
        return ""
    if "<" in text and ">" in text:
        return text

    content: list[str] = []
    paragraph_lines: list[str] = []
    lines = text.splitlines()
    i = 0

    def flush_paragraph() -> None:
        if paragraph_lines:
            paragraph = " ".join(line.strip() for line in paragraph_lines)
            content.append(f"<p>{_storage_inline(paragraph)}</p>")
            paragraph_lines.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        fence = _is_fence(stripped)
        if fence:
            flush_paragraph()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not _is_fence(lines[i]):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            code = "\n".join(code_lines).replace("]]>", "]]]]><![CDATA[>")
            content.append(
                '<ac:structured-macro ac:name="code">'
                f"<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>"
                "</ac:structured-macro>"
            )
            continue

        heading = _heading_match(stripped)
        if heading:
            flush_paragraph()
            level, heading_text = heading
            content.append(f"<h{level}>{_storage_inline(heading_text)}</h{level}>")
            i += 1
            continue

        list_match = _list_match(stripped)
        if list_match:
            flush_paragraph()
            kind, marker_re, first_item = list_match
            items = [first_item]
            i += 1
            while i < len(lines):
                item_match = re.match(marker_re, lines[i].strip())
                if not item_match:
                    break
                items.append(item_match.group(1))
                i += 1
            tag = "ul" if kind == "bullet" else "ol"
            body = "".join(f"<li>{_storage_inline(item)}</li>" for item in items)
            content.append(f"<{tag}>{body}</{tag}>")
            continue

        paragraph_lines.append(line)
        i += 1

    flush_paragraph()
    return "".join(content)


def _text_to_adf(text: str) -> dict:
    """Convert markdown-ish text to Atlassian Document Format JSON."""
    if not text:
        return {"type": "doc", "version": 1, "content": []}

    def paragraph_node(value: str) -> dict:
        content = _adf_inline_nodes(value)
        return {"type": "paragraph", "content": content} if content else {"type": "paragraph"}

    def heading_node(value: str, level: int) -> dict:
        return {
            "type": "heading",
            "attrs": {"level": max(1, min(level, 6))},
            "content": _adf_inline_nodes(value),
        }

    def code_block_node(value: str, language: str = "") -> dict:
        node = {
            "type": "codeBlock",
            "content": [{"type": "text", "text": value.rstrip("\n")}],
        }
        if language:
            node["attrs"] = {"language": language}
        return node

    def list_node(kind: str, items: list[str]) -> dict:
        return {
            "type": kind,
            "content": [
                {"type": "listItem", "content": [paragraph_node(item)]}
                for item in items
            ],
        }

    content: list[dict] = []
    paragraph_lines: list[str] = []
    lines = text.splitlines()
    i = 0

    def flush_paragraph() -> None:
        if paragraph_lines:
            content.append(paragraph_node(" ".join(line.strip() for line in paragraph_lines)))
            paragraph_lines.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        fence = _is_fence(stripped)
        if fence:
            flush_paragraph()
            language = fence.group(1)
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not _is_fence(lines[i]):
                code_lines.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1
            content.append(code_block_node("\n".join(code_lines), language))
            continue

        heading = _heading_match(stripped)
        if heading:
            flush_paragraph()
            level, heading_text = heading
            content.append(heading_node(heading_text, level))
            i += 1
            continue

        list_match = _list_match(stripped)
        if list_match:
            flush_paragraph()
            kind, marker_re, first_item = list_match
            items = [first_item]
            i += 1
            while i < len(lines):
                item_match = re.match(marker_re, lines[i].strip())
                if not item_match:
                    break
                items.append(item_match.group(1))
                i += 1
            node_type = "bulletList" if kind == "bullet" else "orderedList"
            content.append(list_node(node_type, items))
            continue

        paragraph_lines.append(line)
        i += 1

    flush_paragraph()
    return {"type": "doc", "version": 1, "content": content}


def _is_rich_text_field(field: dict | None) -> bool:
    if not field:
        return False
    field_name = field.get("name", "")
    schema = field.get("schema") or {}
    custom_type = schema.get("custom", "")
    return (
        field_name in _DEFAULT_RICH_TEXT_FIELD_NAMES
        or field_name in _env_set("JIRA_RICH_TEXT_FIELD_NAMES")
        or custom_type.endswith(":textarea")
    )


def _normalize_field_write_value(field_id: str, field: dict | None, value):
    """Convert human-friendly field values to Jira REST field payload values."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value

    schema = (field or {}).get("schema") or {}
    schema_type = schema.get("type")
    schema_items = schema.get("items")
    custom_type = schema.get("custom", "")

    if schema_type == "user":
        return {"accountId": _resolve_user(str(value))}

    if schema_type == "array" and schema_items == "user":
        values = value if isinstance(value, list) else [value]
        return [{"accountId": _resolve_user(str(item))} for item in values]

    if schema_type == "option" or custom_type.endswith(":select"):
        return {"value": str(value)}

    if schema_type == "array" and (
        schema_items == "option" or custom_type.endswith(":multiselect")
    ):
        values = value if isinstance(value, list) else [value]
        return [{"value": str(item)} for item in values]

    if _is_rich_text_field(field):
        return _text_to_adf(str(value))

    return value


def _merge_custom_fields(fields: dict, custom_fields: dict | None) -> dict | str:
    """Merge arbitrary Jira fields into a fields payload."""
    if custom_fields is None:
        return fields
    if not isinstance(custom_fields, dict):
        return "custom_fields must be a JSON object"
    for field_key, value in custom_fields.items():
        field_id, field = _resolve_field_key(field_key)
        try:
            fields[field_id] = _normalize_field_write_value(field_id, field, value)
        except ValueError as e:
            return f"{field_key}: {e}"
    return fields


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


def _summarize_allowed_value(value):
    if not isinstance(value, dict):
        return value
    for key in ("value", "name", "displayName"):
        if value.get(key):
            return value[key]
    if value.get("id"):
        return value["id"]
    return value


@mcp.tool()
def get_create_fields(project_key: str, issue_type: str) -> str:
    """List Jira fields available when creating a ticket, including IDs, names, required flags, schemas, and allowed values."""
    resp = _api(
        f"/issue/createmeta?projectKeys={quote(project_key)}"
        f"&issuetypeNames={quote(issue_type)}"
        "&expand=projects.issuetypes.fields"
    )
    if isinstance(resp, dict) and "error" in resp:
        return json.dumps(resp)

    fields = {}
    for project in resp.get("projects", []):
        for issue_type_meta in project.get("issuetypes", []):
            if issue_type_meta.get("name") == issue_type:
                fields = issue_type_meta.get("fields", {}) or {}
                break
        if fields:
            break

    result = []
    for field_id, meta in fields.items():
        allowed_values = meta.get("allowedValues") or []
        result.append({
            "id": field_id,
            "name": meta.get("name"),
            "required": bool(meta.get("required")),
            "schema": meta.get("schema"),
            "allowed_values": [
                _summarize_allowed_value(value)
                for value in allowed_values[:50]
            ],
        })

    result.sort(key=lambda item: (not item["required"], item.get("name") or item["id"]))
    return json.dumps(result, indent=2)


@mcp.tool()
def get_ticket(issue_key: str, include_noisy_custom_fields: bool = False) -> str:
    """Fetch a Jira ticket by key (e.g. INFOSEC-2239). Returns standard fields, description, and populated custom fields."""
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
        "custom_fields": _custom_fields(fields, include_noise=include_noisy_custom_fields),
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
def create_ticket(project_key: str, summary: str, issue_type: str, description: str = "", assignee: str = "", priority: str = "", parent_key: str = "", custom_fields: dict | None = None) -> str:
    """Create a new Jira ticket. Optionally pass custom_fields for Jira customfield_* or other fields."""
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
    merged_fields = _merge_custom_fields(fields, custom_fields)
    if isinstance(merged_fields, str):
        return json.dumps({"error": "Invalid custom_fields", "detail": merged_fields})
    fields = merged_fields

    resp = _api("/issue", method="POST", data={"fields": fields})
    if "error" in resp:
        return json.dumps(resp)

    key = resp.get("key")
    return get_ticket(key)


@mcp.tool()
def update_ticket(issue_key: str, summary: str = "", description: str = "", assignee: str = "", priority: str = "", transition: str = "", comment: str = "", custom_fields: dict | None = None) -> str:
    """Update a Jira ticket. Can change standard fields, custom_fields, transition status, and/or add a comment."""
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
    merged_fields = _merge_custom_fields(fields, custom_fields)
    if isinstance(merged_fields, str):
        return json.dumps({"error": "Invalid custom_fields", "detail": merged_fields})
    fields = merged_fields
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
