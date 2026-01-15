#!/bin/bash
# Setup script for launchd job

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOME_DIR="$HOME"
PLIST_TEMPLATE="$SCRIPT_DIR/launchd/com.granola-sync.plist.template"
PLIST_DEST="$HOME_DIR/Library/LaunchAgents/com.granola-sync.plist"

echo "Setting up Granola Sync launchd job..."

# Check if template exists
if [ ! -f "$PLIST_TEMPLATE" ]; then
    echo "Error: Template not found at $PLIST_TEMPLATE"
    exit 1
fi

# Create LaunchAgents directory if needed
mkdir -p "$HOME_DIR/Library/LaunchAgents"

# Generate plist with actual paths
sed "s|\$HOME|$HOME_DIR|g" "$PLIST_TEMPLATE" > "$PLIST_DEST"

echo "Created: $PLIST_DEST"

# Unload if already loaded
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Load the job
launchctl load "$PLIST_DEST"

echo "Launchd job loaded successfully!"
echo "The sync will run daily at midnight."
echo ""
echo "To test it now, run:"
echo "  cd $SCRIPT_DIR && source venv/bin/activate && python granola_sync.py"
