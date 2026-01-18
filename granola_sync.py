#!/usr/bin/env python3
"""
Granola → Obsidian Sync

Exports meeting transcripts from Granola's local cache to Obsidian vault.
Adds meeting summaries to daily reflection files.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from utils import (
    setup_logging,
    load_config,
    format_frontmatter,
    get_unprocessed_transcripts,
    parse_iso_timestamp,
    get_notes_text,
)

logger = setup_logging(__name__)


def load_granola_cache(cache_path: Path) -> dict:
    """Load and parse Granola's cache file."""
    if not cache_path.exists():
        logger.error(f"Granola cache not found: {cache_path}")
        return {"documents": {}, "transcripts": {}}

    try:
        with open(cache_path) as f:
            data = json.load(f)

        cache = json.loads(data.get("cache", "{}"))
        state = cache.get("state", {})

        return {
            "documents": state.get("documents", {}),
            "transcripts": state.get("transcripts", {}),
            "events": state.get("events", [])
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to parse Granola cache: {e}")
        return {"documents": {}, "transcripts": {}}


def sanitize_filename(title: str) -> str:
    """Sanitize a string for use as a filename."""
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = sanitized.strip()
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100].strip()
    return sanitized


def get_transcript_text(entries: list) -> str:
    """Join transcript entries into flowing paragraphs."""
    if not entries:
        return ""

    texts = []
    for e in entries:
        text = e.get("text", "")
        # Handle case where text might be a dict or other type
        if isinstance(text, str) and text:
            texts.append(text)
        elif isinstance(text, dict):
            # Try to extract text from dict if possible
            texts.append(str(text.get("content", text.get("text", ""))))

    if not texts:
        return ""

    # Group into paragraphs (roughly every 5-10 sentences or by speaker change)
    paragraphs = []
    current_paragraph = []

    for text in texts:
        current_paragraph.append(text)
        # Start new paragraph every ~10 sentences or at natural breaks
        if len(current_paragraph) >= 10 or text.endswith((".", "!", "?")):
            if len(" ".join(current_paragraph)) > 500:
                paragraphs.append(" ".join(current_paragraph))
                current_paragraph = []

    if current_paragraph:
        paragraphs.append(" ".join(current_paragraph))

    return "\n\n".join(paragraphs)


def calculate_duration(entries: list) -> int:
    """Calculate meeting duration in minutes from transcript entries."""
    if not entries or len(entries) < 2:
        return 0

    start = parse_iso_timestamp(entries[0].get("start_timestamp", ""))
    end = parse_iso_timestamp(entries[-1].get("end_timestamp", ""))

    if not start or not end:
        return 0

    return int((end - start).total_seconds() / 60)


def get_meeting_date(entries: list, doc: dict) -> datetime:
    """Extract meeting date from transcript or document."""
    # Try transcript timestamp first
    if entries:
        dt = parse_iso_timestamp(entries[0].get("start_timestamp", ""))
        if dt:
            return dt

    # Fall back to document created_at
    dt = parse_iso_timestamp(doc.get("created_at", ""))
    if dt:
        return dt

    return datetime.now()


def get_attendees(doc: dict) -> list:
    """Extract attendees from document."""
    people = doc.get("people", {})
    attendees = []

    # Handle different structures of the people field
    if isinstance(people, dict):
        # New structure: people is a dict with 'attendees' key
        attendees_list = people.get("attendees", [])
        if isinstance(attendees_list, list):
            for p in attendees_list:
                if isinstance(p, dict):
                    email = p.get("email") or p.get("name", "")
                    if email:
                        attendees.append(email)
                elif isinstance(p, str):
                    attendees.append(p)
    elif isinstance(people, list):
        # Old structure: people is a list directly
        for p in people:
            if isinstance(p, dict):
                email = p.get("email") or p.get("name", "")
                if email:
                    attendees.append(email)
            elif isinstance(p, str):
                attendees.append(p)

    return attendees


def generate_transcript_file(
    doc_id: str,
    doc: dict,
    entries: list,
    config: dict
) -> tuple[Path, bool]:
    """
    Generate a transcript markdown file.
    Returns (file_path, was_created).
    """
    title = doc.get("title", "Untitled Meeting")
    meeting_dt = get_meeting_date(entries, doc)
    date_str = meeting_dt.strftime("%Y-%m-%d")
    time_str = meeting_dt.strftime("%H%M")

    # Build filename
    safe_title = sanitize_filename(title)
    base_filename = f"{date_str} - {safe_title}"

    transcripts_dir = config["obsidian_vault"] / config["transcripts_folder"]
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    # Check for conflicts (same title, same day)
    file_path = transcripts_dir / f"{base_filename}.md"
    if file_path.exists():
        # Check if it's the same document (by granola_id in frontmatter)
        existing_content = file_path.read_text()
        if f"granola_id: {doc_id}" in existing_content:
            logger.debug(f"Skipping existing transcript: {file_path.name}")
            return file_path, False
        # Different meeting, same title - add time suffix
        file_path = transcripts_dir / f"{date_str} - {safe_title} ({time_str}).md"
        if file_path.exists():
            logger.debug(f"Skipping existing transcript: {file_path.name}")
            return file_path, False

    # Get notes (Granola's AI summary)
    notes = get_notes_text(doc)

    # Calculate metadata
    duration = calculate_duration(entries)
    attendees = get_attendees(doc)

    # Build frontmatter
    frontmatter_data = {
        "date": date_str,
        "title": title,
        "source": "granola",
        "granola_id": doc_id,
        "duration_minutes": duration,
        "entry_count": len(entries),
        "processed": False
    }
    if attendees:
        frontmatter_data["attendees"] = attendees

    frontmatter = format_frontmatter(frontmatter_data)

    # Get transcript text
    transcript_text = get_transcript_text(entries)

    # Build content
    content_parts = [frontmatter, ""]

    if notes:
        content_parts.extend(["## Notes", "", notes, "", "---", ""])
    else:
        content_parts.extend(["## Notes", "", "*No AI notes available - will be generated during processing*", "", "---", ""])

    content_parts.extend(["## Transcript", "", transcript_text])

    content = "\n".join(content_parts)

    # Write file
    file_path.write_text(content)
    logger.info(f"Created transcript: {file_path.name}")

    return file_path, True


def get_daily_file_path(meeting_dt: datetime, config: dict) -> Path:
    """Get path to daily reflection file for a given date."""
    date_str = meeting_dt.strftime("%Y-%m-%d")
    daily_dir = config["obsidian_vault"] / config["daily_folder"]
    return daily_dir / f"{date_str}.md"


def create_daily_file(meeting_dt: datetime, config: dict) -> Path:
    """Create a new daily reflection file from template."""
    file_path = get_daily_file_path(meeting_dt, config)

    if file_path.exists():
        return file_path

    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Get day of week
    day_name = meeting_dt.strftime("%A")
    date_str = meeting_dt.strftime("%Y-%m-%d")

    template = f"""# {date_str} ({day_name})

## Schedule
| Time | What |
|------|------|

---

## Work

---

## Meetings

---

## Social / Follow-ups

---

## Brain Dump

---
"""

    file_path.write_text(template)
    logger.info(f"Created daily file: {file_path.name}")

    return file_path


def add_meeting_to_daily(
    meeting_dt: datetime,
    title: str,
    notes: str,
    transcript_path: Path,
    config: dict
) -> bool:
    """Add meeting summary to daily reflection file."""
    daily_path = get_daily_file_path(meeting_dt, config)

    # Create file if it doesn't exist
    if not daily_path.exists():
        create_daily_file(meeting_dt, config)

    content = daily_path.read_text()

    # Get relative path for Obsidian link
    vault_path = config["obsidian_vault"]
    rel_path = transcript_path.relative_to(vault_path)
    # Remove .md extension for Obsidian wiki link
    link_path = str(rel_path).replace(".md", "")

    # Check if this meeting is already in the file
    if f"[[{link_path}]]" in content:
        logger.debug(f"Meeting already in daily file: {title}")
        return False

    # Prepare meeting entry
    # Truncate notes for summary
    summary_notes = notes.strip() if notes else "*Notes pending*"
    if len(summary_notes) > 500:
        summary_notes = summary_notes[:500] + "..."

    # Format as bullet points if it's not already
    if summary_notes and not summary_notes.startswith("-") and not summary_notes.startswith("*Notes"):
        # Try to convert to bullet points
        lines = summary_notes.split("\n")
        bullet_lines = []
        for line in lines[:5]:  # Max 5 lines
            line = line.strip()
            if line and not line.startswith("-"):
                bullet_lines.append(f"- {line}")
            elif line:
                bullet_lines.append(line)
        summary_notes = "\n".join(bullet_lines) if bullet_lines else summary_notes

    meeting_entry = f"""
### {title}
{summary_notes}
*→ [[{link_path}]]*
"""

    # Find ## Meetings section and add entry
    if "## Meetings" in content:
        # Insert after ## Meetings line
        parts = content.split("## Meetings")
        if len(parts) == 2:
            before = parts[0]
            after = parts[1]

            # Find the next section (starts with ##)
            next_section_match = re.search(r'\n## ', after)
            if next_section_match:
                meetings_content = after[:next_section_match.start()]
                rest = after[next_section_match.start():]
                new_content = before + "## Meetings" + meetings_content + meeting_entry + rest
            else:
                new_content = before + "## Meetings" + after.rstrip() + meeting_entry + "\n"

            daily_path.write_text(new_content)
            logger.info(f"Added '{title}' to daily file: {daily_path.name}")
            return True

    # If no Meetings section, try to add one before Brain Dump
    if "## Brain Dump" in content:
        content = content.replace(
            "## Brain Dump",
            f"## Meetings\n{meeting_entry}\n---\n\n## Brain Dump"
        )
        daily_path.write_text(content)
        logger.info(f"Created Meetings section and added '{title}' to: {daily_path.name}")
        return True

    # Last resort: append to end
    content = content.rstrip() + f"\n\n## Meetings\n{meeting_entry}"
    daily_path.write_text(content)
    logger.info(f"Appended Meetings section with '{title}' to: {daily_path.name}")
    return True


def sync_transcripts(config: dict) -> dict:
    """
    Main sync function.
    Returns stats about what was synced.
    """
    stats = {
        "transcripts_created": 0,
        "transcripts_skipped": 0,
        "daily_entries_added": 0,
        "errors": 0
    }

    cache = load_granola_cache(config["granola_cache"])
    documents = cache["documents"]
    transcripts = cache["transcripts"]

    logger.info(f"Found {len(documents)} documents, {len(transcripts)} with transcripts")

    for doc_id, entries in transcripts.items():
        if not entries:
            continue

        doc = documents.get(doc_id, {})
        if not doc:
            logger.warning(f"Document not found for transcript: {doc_id}")
            continue

        try:
            # Create transcript file
            file_path, was_created = generate_transcript_file(
                doc_id, doc, entries, config
            )

            if was_created:
                stats["transcripts_created"] += 1

                # Add to daily reflections
                meeting_dt = get_meeting_date(entries, doc)
                title = doc.get("title", "Untitled Meeting")
                notes = doc.get("notes_markdown") or doc.get("notes_plain") or ""

                if add_meeting_to_daily(meeting_dt, title, notes, file_path, config):
                    stats["daily_entries_added"] += 1
            else:
                stats["transcripts_skipped"] += 1

        except Exception as e:
            logger.error(f"Error processing document {doc_id}: {e}")
            stats["errors"] += 1

    return stats


def main():
    """Main entry point."""
    logger.info("=" * 50)
    logger.info("Starting Granola → Obsidian sync")

    try:
        config = load_config()
        logger.info(f"Vault: {config['obsidian_vault']}")

        # Run sync
        stats = sync_transcripts(config)

        logger.info(f"Sync complete: {stats['transcripts_created']} created, "
                   f"{stats['transcripts_skipped']} skipped, "
                   f"{stats['daily_entries_added']} daily entries, "
                   f"{stats['errors']} errors")

        # Check for unprocessed transcripts (for auto-processing later)
        auto_hours = config.get("auto_process_after_hours", 48)
        unprocessed = get_unprocessed_transcripts(config, auto_hours)

        if unprocessed:
            logger.info(f"Found {len(unprocessed)} unprocessed transcripts older than {auto_hours}h")
            # Auto-processing is handled by process_transcripts.py
            # This just logs the count for visibility

        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
