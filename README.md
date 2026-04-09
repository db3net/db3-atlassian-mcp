# Atlassian MCP Server

Connect your IDE to Jira and Confluence. Read, create, and update tickets and wiki pages right from your editor.

## Install

### Quick (via uvx)

If you have `uv` installed:

```bash
uvx atlassian-mcp-server@latest
```

### From source

```bash
git clone https://github.com/omise-us-secops/atlassian-mcp.git
cd atlassian-mcp
bash install.sh
```

You'll be prompted for:
- Your Atlassian instance URL (e.g. `https://yourcompany.atlassian.net`)
- Your email address
- An API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens))

That's it. The script sets up everything and configures your IDE automatically.

Once installed, open Kiro and ask it something like "Can you check if my Atlassian MCP server is connected?" to verify everything is working.

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
