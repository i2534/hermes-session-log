#!/bin/bash
# Session Log Plugin - Auto Setup Script
# Usage: bash setup.sh [repo-url]

set -e

REPO_URL="${1:-https://github.com/i2534/hermes-session-log.git}"
PLUGIN_DIR="$HOME/.hermes/plugins/session-log"
CONFIG_FILE="$HOME/.hermes/config.yaml"

echo "=== Session Log Plugin Setup ==="

# 1. Remove old installation if exists
if [ -d "$PLUGIN_DIR" ]; then
    echo "Found existing installation at $PLUGIN_DIR"
    read -p "Remove and reinstall? (y/N) " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    rm -rf "$PLUGIN_DIR"
fi

# 2. Clone from repo
echo "Cloning from $REPO_URL ..."
git clone --depth 1 "$REPO_URL" "$PLUGIN_DIR"

# 3. Enable in config.yaml
if grep -q "session-log" "$CONFIG_FILE" 2>/dev/null; then
    echo "Already enabled in config.yaml"
else
    echo "Enabling in config.yaml ..."
    # Check if plugins section exists
    if grep -q "^plugins:" "$CONFIG_FILE"; then
        # Add under plugins.enabled
        if grep -q "^plugins:.*enabled:" "$CONFIG_FILE" || grep -A1 "^plugins:" "$CONFIG_FILE" | grep -q "enabled:"; then
            sed -i '/^plugins:/,/^[a-z]/ { /enabled:/a\  - session-log }' "$CONFIG_FILE"
        else
            # Add enabled section under plugins
            sed -i '/^plugins:/a\  enabled:\n  - session-log' "$CONFIG_FILE"
        fi
    else
        # Append plugins section
        cat >> "$CONFIG_FILE" << 'EOF'
plugins:
  enabled:
    - session-log
EOF
    fi
    echo "Added session-log to config.yaml"
fi

# 4. Verify
echo ""
echo "=== Installation Complete ==="
echo "Plugin dir: $PLUGIN_DIR"
echo "Files:"
ls -1 "$PLUGIN_DIR" | grep -v ".git"
echo ""
echo "To activate: restart Hermes or start a new session."
