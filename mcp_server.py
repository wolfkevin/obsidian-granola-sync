#!/usr/bin/env python3
"""
MCP Server for Granola → Obsidian Sync

Exposes Granola sync functionality as tools that Claude can use directly.
"""

import json
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from utils import (
    setup_logging,
    load_config,
    parse_frontmatter,
    get_unprocessed_transcripts,
)
from granola_sync import (
    load_granola_cache,
    sync_transcripts,
)

logger = setup_logging(__name__)

# Initialize the MCP server
app = Server("granola-sync")


def format_transcript_info(file_path: Path) -> dict[str, Any]:
    """Extract basic info from a transcript file."""
    try:
        content = file_path.read_text()
        frontmatter, _ = parse_frontmatter(content)

        return {
            "filename": file_path.name,
            "title": frontmatter.get("title", "Unknown"),
            "date": frontmatter.get("date", ""),
            "duration_minutes": frontmatter.get("duration_minutes", 0),
            "processed": frontmatter.get("processed", False),
            "attendees": frontmatter.get("attendees", []),
        }
    except Exception as e:
        logger.error(f"Error reading {file_path}: {e}")
        return {
            "filename": file_path.name,
            "error": str(e)
        }


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="sync_transcripts",
            description=(
                "Sync new meeting transcripts from Granola's local cache to Obsidian. "
                "This will create markdown files for new transcripts and add meeting "
                "summaries to daily reflection files. Returns statistics about what was synced."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_unprocessed_transcripts",
            description=(
                "List all unprocessed meeting transcripts. You can optionally filter to "
                "only show transcripts older than a certain number of hours. Returns a list "
                "of transcript files with their metadata (title, date, duration, attendees)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "older_than_hours": {
                        "type": "integer",
                        "description": "Only return transcripts older than this many hours (default: 0 = all)",
                        "default": 0,
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="get_transcript",
            description=(
                "Get the full content of a specific transcript file by filename. "
                "Returns the complete transcript including frontmatter, notes, and transcript text."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The filename of the transcript (e.g., '2026-01-15 - Team Standup.md')",
                    }
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="get_granola_cache_info",
            description=(
                "Get information about Granola's local cache, including the number of "
                "documents and transcripts available. Useful for debugging or checking "
                "if new meetings are available to sync."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls."""
    try:
        config = load_config()

        if name == "sync_transcripts":
            stats = sync_transcripts(config)
            result = {
                "status": "success",
                "message": "Sync completed",
                "transcripts_created": stats["transcripts_created"],
                "transcripts_skipped": stats["transcripts_skipped"],
                "daily_entries_added": stats["daily_entries_added"],
                "errors": stats["errors"],
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "list_unprocessed_transcripts":
            older_than_hours = arguments.get("older_than_hours", 0)
            transcripts = get_unprocessed_transcripts(config, older_than_hours)

            transcript_list = [format_transcript_info(t) for t in transcripts]

            result = {
                "status": "success",
                "count": len(transcript_list),
                "older_than_hours": older_than_hours,
                "transcripts": transcript_list,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_transcript":
            filename = arguments.get("filename")
            if not filename:
                return [TextContent(
                    type="text",
                    text=json.dumps({"status": "error", "message": "filename is required"})
                )]

            transcripts_dir = config["obsidian_vault"] / config["transcripts_folder"]
            file_path = transcripts_dir / filename

            if not file_path.exists():
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "status": "error",
                        "message": f"Transcript not found: {filename}"
                    })
                )]

            content = file_path.read_text()
            frontmatter, body = parse_frontmatter(content)

            result = {
                "status": "success",
                "filename": filename,
                "frontmatter": frontmatter,
                "content": body,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_granola_cache_info":
            cache = load_granola_cache(config["granola_cache"])

            result = {
                "status": "success",
                "cache_path": str(config["granola_cache"]),
                "documents_count": len(cache.get("documents", {})),
                "transcripts_count": len(cache.get("transcripts", {})),
                "has_events": len(cache.get("events", [])) > 0,
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [TextContent(
                type="text",
                text=json.dumps({"status": "error", "message": f"Unknown tool: {name}"})
            )]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({"status": "error", "message": str(e)})
        )]


async def main():
    """Run the MCP server."""
    logger.info("Starting Granola Sync MCP server")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
