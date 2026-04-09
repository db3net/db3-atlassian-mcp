# Atlassian MCP Server

Connect your IDE to Jira and Confluence. Read, create, and update tickets and wiki pages right from your editor.

## Install

### Quick (via uvx)

If you have `uv` installed:

```bash
uvx db3-atlassian-mcp@latest
```

### From source

```bash
git clone https://github.com/db3net/db3-atlassian-mcp.git
cd db3-atlassian-mcp
bash install.sh
```

You'll be prompted for:
- Your Atlassian instance URL (e.g. `https://yourcompany.atlassian.net`)
- Your email address
- An API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens))

That's it. The script sets up everything and configures your IDE automatically.

Once installed, open Kiro and ask it something like "Can you check if my Atlassian MCP server is connected?" to verify everything is working.

## Configuration

The server reads credentials from a `.env` file. The installer creates this automatically, but you can also set it up manually.

### .env file

Create `~/.atlassian-mcp/.env` with:

```
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_USER=you@yourcompany.com
JIRA_API_KEY=your-api-token-here
```

The server searches for `.env` in this order:
1. `~/.atlassian-mcp/.env` (recommended — created by the installer)
2. `.env` in the current working directory

### MCP config (alternative)

You can also pass credentials via your IDE's MCP config (`~/.kiro/settings/mcp.json`):

```json
{
  "mcpServers": {
    "me-atlassian": {
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

Either approach works. The `.env` file keeps credentials out of your IDE config.

## What You Can Do

### Jira
- Fetch any ticket by key (e.g. `INFOSEC-2239`)
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

## Updating

Run the installer again. It pulls the latest code and updates dependencies without overwriting your credentials.

## Uninstall

```bash
rm -rf ~/.atlassian-mcp
```

Then remove the `"me-atlassian"` entry from `~/.kiro/settings/mcp.json`.

## License

MIT
