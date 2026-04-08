#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/.atlassian-mcp"
VENV_DIR="$INSTALL_DIR/venv"
ENV_FILE="$INSTALL_DIR/.env"
REPO_URL="https://github.com/omise-us-secops/atlassian-mcp.git"
MCP_CONFIG_DIR="$HOME/.kiro/settings"
MCP_CONFIG_FILE="$MCP_CONFIG_DIR/mcp.json"

# ── Welcome banner ──────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       Atlassian MCP Server — Installer           ║"
echo "║  Jira + Confluence tools for your IDE            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Collect credentials ─────────────────────────────────────────────
read -p "Atlassian instance URL (e.g. https://yourco.atlassian.net): " INSTANCE_URL
# Strip trailing slash
INSTANCE_URL="${INSTANCE_URL%/}"

read -p "Atlassian email address: " EMAIL
read -sp "Atlassian API token: " API_TOKEN
echo ""  # newline after hidden input

if [ -z "$INSTANCE_URL" ] || [ -z "$EMAIL" ] || [ -z "$API_TOKEN" ]; then
  echo "❌ All three fields are required. Aborting."
  exit 1
fi

# ── Clone or update repo ────────────────────────────────────────────
echo ""
echo "📦 Setting up repository..."
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "   Repository exists — pulling latest changes..."
  git -C "$INSTALL_DIR" pull --quiet
else
  if [ -d "$INSTALL_DIR" ]; then
    # Directory exists but isn't a git repo — clone into it
    # (handles case where only venv/env existed from a partial install)
    git clone "$REPO_URL" "$INSTALL_DIR.tmp"
    cp -r "$INSTALL_DIR.tmp/." "$INSTALL_DIR/"
    rm -rf "$INSTALL_DIR.tmp"
  else
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi
  echo "   Cloned repository into $INSTALL_DIR"
fi

# ── Python virtual environment ──────────────────────────────────────
echo ""
echo "🐍 Setting up Python virtual environment..."

if [ -d "$VENV_DIR" ]; then
  echo "   Existing venv found — reusing it."
else
  python3 -m venv "$VENV_DIR"
  echo "   Created venv at $VENV_DIR"
fi

echo "   Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet fastmcp python-dotenv

# ── Write credentials ───────────────────────────────────────────────
echo ""
echo "🔑 Writing credentials..."

cat > "$ENV_FILE" <<EOF
JIRA_BASE_URL=$INSTANCE_URL
JIRA_USER=$EMAIL
JIRA_API_KEY=$API_TOKEN
EOF

echo "   Credentials saved to $ENV_FILE"

# ── Validate credentials ────────────────────────────────────────────
echo ""
echo "🔍 Validating credentials..."

AUTH_HEADER=$(echo -n "$EMAIL:$API_TOKEN" | base64)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Basic $AUTH_HEADER" \
  -H "Accept: application/json" \
  "$INSTANCE_URL/rest/api/3/myself")

if [ "$HTTP_CODE" = "200" ]; then
  echo "   ✅ Credentials are valid!"
  CREDS_VALID=true
else
  echo "   ⚠️  Credential check returned HTTP $HTTP_CODE."
  echo "   The server will still be configured, but please verify your credentials."
  CREDS_VALID=false
fi

# ── Configure Kiro MCP settings ─────────────────────────────────────
echo ""
echo "⚙️  Configuring Kiro MCP settings..."

mkdir -p "$MCP_CONFIG_DIR"

PYTHON_PATH="$VENV_DIR/bin/python3"
SERVER_PATH="$INSTALL_DIR/server.py"

if [ -f "$MCP_CONFIG_FILE" ]; then
  echo "   Existing mcp.json found — merging jira server entry..."
  python3 -c "
import json, sys

config_path = '$MCP_CONFIG_FILE'
with open(config_path, 'r') as f:
    config = json.load(f)

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['jira'] = {
    'command': '$PYTHON_PATH',
    'args': ['$SERVER_PATH'],
    'disabled': False,
    'autoApprove': []
}

with open(config_path, 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
"
else
  echo "   Creating new mcp.json..."
  python3 -c "
import json

config = {
    'mcpServers': {
        'jira': {
            'command': '$PYTHON_PATH',
            'args': ['$SERVER_PATH'],
            'disabled': False,
            'autoApprove': []
        }
    }
}

with open('$MCP_CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
"
fi

echo "   Updated $MCP_CONFIG_FILE"

# ── Summary ─────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
if [ "$CREDS_VALID" = true ]; then
  echo "  ✅ Installation complete!"
else
  echo "  ⚠️  Installation complete (credentials could not be verified)."
fi
echo ""
echo "  Server code:  $INSTALL_DIR/server.py"
echo "  Python venv:  $VENV_DIR"
echo "  Credentials:  $ENV_FILE"
echo "  MCP config:   $MCP_CONFIG_FILE"
echo ""
echo "  Restart Kiro to pick up the new MCP server."
echo "════════════════════════════════════════════════════"
echo ""
