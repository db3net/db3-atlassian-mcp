# db3-atlassian-mcp

Lightweight MCP server for Jira and Confluence — read, create, and update from your AI IDE.

## Install

### Step 1: Get an API Token

Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens) and create a new token.

### Step 2: Create your .env file

```bash
mkdir -p ~/.db3-atlassian-mcp

cat > ~/.db3-atlassian-mcp/.env << EOF
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_USER=you@yourcompany.com
JIRA_API_KEY=your-api-token-here

# Optional: Bitbucket Cloud
BITBUCKET_WORKSPACE=your-workspace
BITBUCKET_USER=you@yourcompany.com
BITBUCKET_API_TOKEN=your-bitbucket-api-token
EOF
```

### Step 3: Add to your IDE's MCP config

> **Tip:** If you skip Step 2, you can put your credentials directly in the `env` block below instead of using a `.env` file. Either approach works.

#### Kiro

You can ask Kiro to do this for you: *"Add db3-atlassian-mcp to my MCP config using uvx with my Atlassian credentials"*

Or manually open `~/.kiro/settings/mcp.json` and add inside `"mcpServers"`:

```json
"db3.atlassian-mcp": {
  "command": "uvx",
  "args": ["db3-atlassian-mcp@latest"],
  "disabled": false,
  "autoApprove": [],
  "env": {
    "JIRA_BASE_URL": "https://yourcompany.atlassian.net",
    "JIRA_USER": "you@yourcompany.com",
    "JIRA_API_KEY": "your-api-token-here"
  }
}
```

The `env` block is optional if you already created a `.env` file in Step 2.

#### VS Code / Cursor / Windsurf

Add to `.vscode/mcp.json` in your workspace (or global settings):

```json
{
  "mcpServers": {
    "db3.atlassian-mcp": {
      "command": "uvx",
      "args": ["db3-atlassian-mcp@latest"],
      "env": {
        "JIRA_BASE_URL": "https://yourcompany.atlassian.net",
        "JIRA_USER": "you@yourcompany.com",
        "JIRA_API_KEY": "your-api-token-here"
      }
    }
  }
}
```

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "db3.atlassian-mcp": {
      "command": "uvx",
      "args": ["db3-atlassian-mcp@latest"],
      "env": {
        "JIRA_BASE_URL": "https://yourcompany.atlassian.net",
        "JIRA_USER": "you@yourcompany.com",
        "JIRA_API_KEY": "your-api-token-here"
      }
    }
  }
}
```

### Step 4: Restart your IDE

The MCP server will appear in your sidebar as `db3.atlassian-mcp`.

Once connected, ask Kiro something like "Read Jira ticket PROJECT-123" to verify it's working.

## What You Can Do

### Jira
- Fetch any ticket by key
- Search tickets with JQL
- View sub-tasks for a parent ticket
- Create new tickets with optional parent for sub-task linking
- Update tickets — change fields, transition status, add comments
- Assign tickets by name or email (no account IDs needed)
- Attach files to tickets

### Confluence
- Read any page by pasting its URL or page ID
- Search pages with CQL
- Browse all pages in a space
- Create new pages (with optional parent page)
- Update existing pages with rich formatting

### Bitbucket Cloud
- List repositories in a workspace
- Search repositories by slug, name, or description
- Fetch repository metadata
- List branches and commits
- Fetch commit details and build statuses
- List recent Bitbucket Pipelines runs
- List and inspect pull requests
- Fetch pull request diffs, diffstats, comments, and activity
- Fetch pull request build statuses
- Summarize pull request status with reviewers, approvals, build status results, and changed files
- Create pull requests
- Add pull request comments

## Configuration

The server reads credentials from a `.env` file. It searches in this order:

1. `~/.db3-atlassian-mcp/.env` (recommended)
2. `.env` in the current working directory

You can also pass credentials via your MCP config's `env` block:

```json
"db3.atlassian-mcp": {
  "command": "uvx",
  "args": ["db3-atlassian-mcp@latest"],
  "env": {
    "JIRA_BASE_URL": "https://yourcompany.atlassian.net",
    "JIRA_USER": "you@yourcompany.com",
    "JIRA_API_KEY": "your-api-token-here"
  }
}
```

Either approach works. The `.env` file keeps credentials out of your IDE config.

### Bitbucket Cloud

Bitbucket support is optional. Set these values only if you want Bitbucket tools:

```bash
BITBUCKET_WORKSPACE=your-workspace
BITBUCKET_USER=you@yourcompany.com
BITBUCKET_API_TOKEN=your-bitbucket-api-token
```

`BITBUCKET_WORKSPACE` lets tool calls omit the workspace argument. For
`bitbucket.org/merchante-solutions/...`, use:

```bash
BITBUCKET_WORKSPACE=merchante-solutions
```

Use a Bitbucket Cloud API token scoped to the operations you need. Read-only
tools need repository and pull request read scopes. Pipeline status tools need
pipeline read scope. Creating pull requests or comments needs write access for
pull requests.

## Alternative: Install from Source

```bash
git clone https://github.com/db3net/db3-atlassian-mcp.git
cd db3-atlassian-mcp
bash install.sh
```

The installer prompts for your credentials, sets up a Python venv, validates the connection, and configures Kiro automatically.

## Updating

If using `uvx` with `@latest`, it automatically pulls the newest version each time your IDE starts. If installed from source, run the installer again.

### Version Pinning

Using `@latest` is convenient but means updates are applied automatically. For production or security-sensitive environments, pin to a specific version:

```json
"args": ["db3-atlassian-mcp==1.1.0"]
```

This way you only get updates when you explicitly change the version number. Check [PyPI](https://pypi.org/project/db3-atlassian-mcp/) for available versions.

## Uninstall

```bash
rm -rf ~/.db3-atlassian-mcp
```

Then remove the `"db3.atlassian-mcp"` entry from your IDE's MCP config.

## Troubleshooting

### Server shows "connection failed" or ENOENT
- Make sure `uv` is installed: `pip install uv` or `brew install uv`
- Verify `uvx` is on your PATH: `which uvx`
- Check that Python 3.10+ is available: `python3 --version`

### 401 Unauthorized
- Verify your API token hasn't expired (Atlassian tokens can have expiration dates)
- Check that `JIRA_USER` is your email address, not your username
- Regenerate your token at [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

### .env file not found
- Confirm the file exists: `cat ~/.db3-atlassian-mcp/.env`
- Make sure all three variables are set: `JIRA_BASE_URL`, `JIRA_USER`, `JIRA_API_KEY`
- The URL should not have a trailing slash

### Tools not showing up
- Restart your IDE after adding the MCP config
- Check your IDE's MCP server logs for errors
- In Kiro: look at the MCP Servers panel in the sidebar and click reconnect

## License

MIT
