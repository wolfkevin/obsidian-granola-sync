#!/bin/bash
# Granola Sync Runner
# Called by launchd at midnight

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

# Run sync
python granola_sync.py

# Auto-process old transcripts (older than 48 hours)
python process_transcripts.py --auto
