# Atlassian MCP Server

Connect your IDE to Jira and Confluence. Read, create, and update tickets and wiki pages right from your editor.

## Install

```bash
curl -sSL https://raw.githubusercontent.com/MerchantE/atlassian-mcp/main/install.sh | bash
```

You'll be prompted for:
- Your Atlassian instance URL (e.g. `https://yourcompany.atlassian.net`)
- Your email address
- An API token ([create one here](https://id.atlassian.com/manage-profile/security/api-tokens))

That's it. The script sets up everything and configures your IDE automatically.

## What You Can Do

### Jira
- Fetch any ticket by key (e.g. `INFOSEC-2239`)
- Search tickets with JQL
- View sub-tasks for a parent ticket
- Create new tickets
- Update tickets — change fields, transition status, add comments

### Confluence
- Read any page by pasting its URL or page ID
- Search pages with CQL
- Browse all pages in a space
- Create new pages
- Update existing pages

## Updating

Run the install command again. It will pull the latest code and update dependencies without overwriting your credentials.

## Uninstall

```bash
rm -rf ~/.atlassian-mcp
```

Then remove the `"jira"` entry from your MCP config if you'd like (`~/.kiro/settings/mcp.json`).

## License

Copyright © 2026 MerchantE, Inc. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, distribution, or use of this software, via any medium, is strictly prohibited.
