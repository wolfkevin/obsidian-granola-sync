#!/usr/bin/env python3
"""
Process meeting transcripts with Claude.

Analyzes transcripts to:
1. Extract action items → adds to daily Work section
2. Identify relevant projects → adds summaries to project files
3. Generate notes if missing
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from utils import (
    setup_logging,
    load_config,
    parse_frontmatter,
    format_frontmatter,
    get_unprocessed_transcripts,
)

logger = setup_logging(__name__)


def load_api_key() -> str:
    """Load Anthropic API key from environment."""
    # Try ~/.config/granola-sync/.env first
    env_path = Path.home() / ".config" / "granola-sync" / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Also try local .env
    local_env = Path(__file__).parent / ".env"
    if local_env.exists():
        load_dotenv(local_env)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not found. Set it in ~/.config/granola-sync/.env")
        sys.exit(1)

    return api_key


def load_projects_index(config: dict) -> str:
    """Load the projects index file for routing context."""
    index_path = config["obsidian_vault"] / config["projects_index"]
    if index_path.exists():
        return index_path.read_text()
    return ""


def update_frontmatter(content: str, updates: dict) -> str:
    """Update frontmatter values in markdown content."""
    frontmatter, body = parse_frontmatter(content)
    if not frontmatter and not content.startswith("---"):
        return content

    frontmatter.update(updates)
    return format_frontmatter(frontmatter) + "\n" + body


def extract_transcript_section(content: str) -> str:
    """Extract the transcript section from markdown content."""
    if "## Transcript" in content:
        parts = content.split("## Transcript", 1)
        if len(parts) == 2:
            return parts[1].strip()
    return content


def analyze_transcript(
    client: Anthropic,
    transcript: str,
    title: str,
    projects_index: str,
    model: str
) -> dict:
    """
    Use Claude to analyze a transcript.

    Returns:
        {
            "action_items": ["item1", "item2"],
            "project_updates": [
                {"project": "MMM", "file": "1-projects/mmm/context.md", "summary": "..."}
            ],
            "summary": "Brief meeting summary if notes were missing"
        }
    """
    prompt = f"""Analyze this meeting transcript and extract structured information.

Meeting Title: {title}

## Projects Index (for routing)
{projects_index}

## Transcript
{transcript[:15000]}  # Limit to avoid token limits

---

Please analyze and return a JSON object with:

1. "action_items": List of specific action items mentioned (tasks someone needs to do).
   - Only include concrete, actionable items
   - Format: "Person: Task" or just "Task" if person unclear
   - Maximum 10 items

2. "project_updates": List of objects for relevant projects from the index.
   - Match based on keywords in the projects index
   - Each object: {{"project": "Project Name", "file": "path/to/file.md", "summary": "2-3 bullet points of relevant discussion"}}
   - Only include if there's meaningful content for that project
   - Maximum 3 projects

3. "summary": A brief 3-5 bullet point summary of the meeting (for daily notes).

Return ONLY valid JSON, no markdown formatting or explanation."""

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text.strip()

        # Try to extract JSON if wrapped in markdown
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        import json
        return json.loads(response_text)

    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return {
            "action_items": [],
            "project_updates": [],
            "summary": ""
        }


def add_action_items_to_daily(
    action_items: list,
    meeting_date: str,
    meeting_title: str,
    config: dict
) -> bool:
    """Add action items to the daily file's Work section."""
    if not action_items:
        return False

    # Parse date
    try:
        dt = datetime.strptime(meeting_date, "%Y-%m-%d")
    except ValueError:
        return False

    daily_path = config["obsidian_vault"] / config["daily_folder"] / f"{meeting_date}.md"

    if not daily_path.exists():
        logger.warning(f"Daily file not found: {daily_path}")
        return False

    content = daily_path.read_text()

    # Format action items
    items_text = f"\n*From {meeting_title}:*\n"
    for item in action_items[:10]:  # Limit to 10
        items_text += f"- [ ] {item}\n"

    # Find Work section and add items
    if "## Work" in content:
        # Check if items already added (by checking for meeting title)
        if f"*From {meeting_title}:*" in content:
            logger.debug(f"Action items already in daily file for: {meeting_title}")
            return False

        # Insert after ## Work line
        parts = content.split("## Work", 1)
        if len(parts) == 2:
            # Find next section
            after = parts[1]
            next_section = re.search(r'\n---\n|\n## ', after)

            if next_section:
                insert_pos = next_section.start()
                new_after = after[:insert_pos] + items_text + after[insert_pos:]
            else:
                new_after = after.rstrip() + items_text + "\n"

            content = parts[0] + "## Work" + new_after
            daily_path.write_text(content)
            logger.info(f"Added {len(action_items)} action items to {daily_path.name}")
            return True

    return False


def update_project_file(
    project_update: dict,
    meeting_date: str,
    meeting_title: str,
    config: dict
) -> bool:
    """Add meeting summary to a project file."""
    file_path = config["obsidian_vault"] / project_update["file"]

    if not file_path.exists():
        logger.warning(f"Project file not found: {file_path}")
        return False

    content = file_path.read_text()

    # Create update entry
    entry = f"""
### {meeting_date} - {meeting_title}
{project_update["summary"]}
"""

    # Check if already added
    if f"### {meeting_date} - {meeting_title}" in content:
        logger.debug(f"Update already in project file: {file_path.name}")
        return False

    # Try to add under a "Meeting Notes" or "Updates" section
    # Or append before the last section
    if "## Meeting Notes" in content:
        content = content.replace("## Meeting Notes", f"## Meeting Notes\n{entry}")
    elif "## Updates" in content:
        content = content.replace("## Updates", f"## Updates\n{entry}")
    else:
        # Append to end
        content = content.rstrip() + f"\n\n## Meeting Notes\n{entry}"

    file_path.write_text(content)
    logger.info(f"Added update to project file: {file_path.name}")
    return True


def update_notes_section(transcript_path: Path, summary: str) -> bool:
    """Update the Notes section if it's empty."""
    content = transcript_path.read_text()

    # Check if notes section is empty/placeholder
    if "*No AI notes available" not in content and "*Notes pending*" not in content:
        return False

    if not summary:
        return False

    # Replace placeholder with actual summary
    if "*No AI notes available - will be generated during processing*" in content:
        content = content.replace(
            "*No AI notes available - will be generated during processing*",
            summary
        )
        transcript_path.write_text(content)
        logger.info(f"Updated notes in: {transcript_path.name}")
        return True

    return False


def process_transcript(transcript_path: Path, config: dict, client: Anthropic) -> bool:
    """Process a single transcript file."""
    logger.info(f"Processing: {transcript_path.name}")

    content = transcript_path.read_text()
    frontmatter, body = parse_frontmatter(content)

    # Skip if already processed
    if frontmatter.get("processed", False):
        logger.debug(f"Already processed: {transcript_path.name}")
        return False

    title = frontmatter.get("title", "Unknown Meeting")
    meeting_date = frontmatter.get("date", "")

    # Extract transcript text
    transcript_text = extract_transcript_section(body)

    if not transcript_text or len(transcript_text) < 100:
        logger.warning(f"Transcript too short: {transcript_path.name}")
        return False

    # Load projects index for routing
    projects_index = load_projects_index(config)

    # Analyze with Claude
    model = config.get("model", "claude-sonnet-4-20250514")
    analysis = analyze_transcript(client, transcript_text, title, projects_index, model)

    # Process results
    changes_made = False

    # 1. Add action items to daily file
    if analysis.get("action_items"):
        if add_action_items_to_daily(
            analysis["action_items"],
            meeting_date,
            title,
            config
        ):
            changes_made = True

    # 2. Update project files
    for project_update in analysis.get("project_updates", []):
        if update_project_file(project_update, meeting_date, title, config):
            changes_made = True

    # 3. Update notes section if empty
    if analysis.get("summary"):
        summary_text = "\n".join(f"- {line}" for line in analysis["summary"].split("\n") if line.strip())
        if update_notes_section(transcript_path, summary_text):
            changes_made = True

    # Mark as processed
    updated_content = update_frontmatter(content, {"processed": True})
    transcript_path.write_text(updated_content)
    logger.info(f"Marked as processed: {transcript_path.name}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Process meeting transcripts with Claude")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all unprocessed transcripts regardless of age"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-process only transcripts older than configured hours"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Process a specific transcript file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes"
    )

    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("Starting transcript processing")

    config = load_config()
    api_key = load_api_key()
    client = Anthropic(api_key=api_key)

    # Determine which transcripts to process
    if args.file:
        file_path = Path(args.file).expanduser()
        if not file_path.exists():
            # Try relative to transcripts folder
            file_path = config["obsidian_vault"] / config["transcripts_folder"] / args.file
        if not file_path.exists():
            logger.error(f"File not found: {args.file}")
            sys.exit(1)
        transcripts = [file_path]

    elif args.auto:
        hours = config.get("auto_process_after_hours", 48)
        transcripts = get_unprocessed_transcripts(config, hours)
        logger.info(f"Found {len(transcripts)} transcripts older than {hours} hours")

    else:  # --all or default
        transcripts = get_unprocessed_transcripts(config, 0)
        logger.info(f"Found {len(transcripts)} unprocessed transcripts")

    if args.dry_run:
        logger.info("DRY RUN - would process:")
        for t in transcripts:
            logger.info(f"  - {t.name}")
        return

    # Process each transcript
    processed = 0
    for transcript_path in transcripts:
        try:
            if process_transcript(transcript_path, config, client):
                processed += 1
        except Exception as e:
            logger.error(f"Error processing {transcript_path.name}: {e}")

    logger.info(f"Processed {processed}/{len(transcripts)} transcripts")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
