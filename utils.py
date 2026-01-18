#!/usr/bin/env python3
"""
Shared utilities for Granola → Obsidian sync.
"""

import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

# Shared log file location
LOG_DIR = Path.home() / "Library" / "Logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "granola-sync.log"


def setup_logging(name: str = __name__) -> logging.Logger:
    """Configure and return a logger with file and console handlers."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(name)


# Module-level logger for utils
logger = setup_logging("granola-sync")


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path}")
        logger.error("Copy config.example.yaml to config.yaml and update paths")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Validate required keys
    required_keys = {"granola_cache", "obsidian_vault", "transcripts_folder", "daily_folder"}
    missing = required_keys - set(config.keys())
    if missing:
        logger.error(f"Missing required config keys: {missing}")
        sys.exit(1)

    # Expand ~ in paths
    config["granola_cache"] = Path(config["granola_cache"]).expanduser()
    config["obsidian_vault"] = Path(config["obsidian_vault"]).expanduser()

    return config


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].lstrip()
        return frontmatter or {}, body
    except yaml.YAMLError:
        return {}, content


def format_frontmatter(data: dict) -> str:
    """Format a dictionary as YAML frontmatter string."""
    lines = ["---"]
    for key, value in data.items():
        if key == "attendees" and isinstance(value, list):
            lines.append("attendees:")
            for att in value:
                lines.append(f"  - {att}")
        elif isinstance(value, bool):
            lines.append(f"{key}: {str(value).lower()}")
        elif isinstance(value, str) and (":" in value or '"' in value):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def get_unprocessed_transcripts(config: dict, older_than_hours: int = 0) -> list[Path]:
    """
    Find unprocessed transcript files.

    Args:
        config: Configuration dict with obsidian_vault and transcripts_folder
        older_than_hours: If > 0, only return transcripts older than this many hours

    Returns:
        List of Path objects for unprocessed transcripts, sorted by date
    """
    transcripts_dir = config["obsidian_vault"] / config["transcripts_folder"]

    if not transcripts_dir.exists():
        return []

    cutoff = datetime.now() - timedelta(hours=older_than_hours) if older_than_hours > 0 else None
    unprocessed = []

    for file_path in transcripts_dir.glob("*.md"):
        content = file_path.read_text()

        if "processed: false" not in content:
            continue

        if cutoff:
            date_match = re.search(r"date: (\d{4}-\d{2}-\d{2})", content)
            if date_match:
                try:
                    file_date = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                    if file_date >= cutoff:
                        continue  # Skip files newer than cutoff
                except ValueError:
                    pass

        unprocessed.append(file_path)

    return sorted(unprocessed)


def parse_iso_timestamp(ts_string: str) -> datetime | None:
    """Parse ISO 8601 timestamp with Z suffix."""
    if not ts_string:
        return None
    try:
        return datetime.fromisoformat(ts_string.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_notes_text(doc: dict) -> str:
    """Extract notes from document, trying markdown first, then plain, then raw."""
    notes_markdown = doc.get("notes_markdown")
    notes_plain = doc.get("notes_plain")
    notes_raw = doc.get("notes")

    if isinstance(notes_markdown, str) and notes_markdown:
        return notes_markdown
    if isinstance(notes_plain, str) and notes_plain:
        return notes_plain
    if isinstance(notes_raw, str) and notes_raw:
        return notes_raw
    return ""
