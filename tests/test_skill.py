"""
Tests for the Granola Sync skill and MCP server.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml


# ============================================================================
# SKILL.md Format Tests
# ============================================================================

class TestSkillFormat:
    """Test that SKILL.md follows the correct format."""

    @pytest.fixture
    def skill_path(self):
        return Path(__file__).parent.parent / "skills" / "sync" / "SKILL.md"

    def test_skill_file_exists(self, skill_path):
        """SKILL.md should exist in skills/sync/."""
        assert skill_path.exists(), f"SKILL.md not found at {skill_path}"

    def test_skill_has_frontmatter(self, skill_path):
        """SKILL.md should have valid YAML frontmatter."""
        content = skill_path.read_text()

        assert content.startswith("---"), "SKILL.md should start with ---"

        # Find the closing ---
        parts = content.split("---", 2)
        assert len(parts) >= 3, "SKILL.md should have opening and closing ---"

        frontmatter_yaml = parts[1].strip()
        frontmatter = yaml.safe_load(frontmatter_yaml)

        assert isinstance(frontmatter, dict), "Frontmatter should be a dict"

    def test_skill_has_required_fields(self, skill_path):
        """SKILL.md frontmatter should have name and description."""
        content = skill_path.read_text()
        parts = content.split("---", 2)
        frontmatter = yaml.safe_load(parts[1].strip())

        assert "name" in frontmatter, "Frontmatter must have 'name'"
        assert "description" in frontmatter, "Frontmatter must have 'description'"

    def test_skill_name_is_sync(self, skill_path):
        """Skill name should be 'sync'."""
        content = skill_path.read_text()
        parts = content.split("---", 2)
        frontmatter = yaml.safe_load(parts[1].strip())

        assert frontmatter["name"] == "sync"

    def test_skill_has_body_content(self, skill_path):
        """SKILL.md should have instructions in the body."""
        content = skill_path.read_text()
        parts = content.split("---", 2)
        body = parts[2].strip()

        assert len(body) > 0, "SKILL.md should have body content"
        assert "sync_transcripts" in body, "Body should mention sync_transcripts tool"


# ============================================================================
# MCP Server Tool Tests
# ============================================================================

class TestMCPServerTools:
    """Test MCP server tool definitions."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock config for testing."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        transcripts_path = vault_path / "Meetings" / "Transcripts"
        transcripts_path.mkdir(parents=True)

        cache_path = tmp_path / "granola_cache.json"
        cache_data = {
            "cache": json.dumps({
                "state": {
                    "documents": {},
                    "transcripts": {},
                    "events": []
                }
            })
        }
        cache_path.write_text(json.dumps(cache_data))

        return {
            "granola_cache": cache_path,
            "obsidian_vault": vault_path,
            "transcripts_folder": "Meetings/Transcripts",
            "daily_folder": "Daily",
        }

    @pytest.mark.asyncio
    async def test_list_tools_returns_expected_tools(self):
        """list_tools should return the expected tool definitions."""
        from mcp_server import list_tools

        tools = await list_tools()
        tool_names = {t.name for t in tools}

        expected_tools = {
            "sync_transcripts",
            "list_unprocessed_transcripts",
            "get_transcript",
            "get_granola_cache_info",
        }

        assert tool_names == expected_tools

    @pytest.mark.asyncio
    async def test_sync_transcripts_tool_schema(self):
        """sync_transcripts tool should have correct schema."""
        from mcp_server import list_tools

        tools = await list_tools()
        sync_tool = next(t for t in tools if t.name == "sync_transcripts")

        assert sync_tool.inputSchema["type"] == "object"
        assert sync_tool.inputSchema["required"] == []

    @pytest.mark.asyncio
    async def test_get_transcript_requires_filename(self):
        """get_transcript tool should require filename parameter."""
        from mcp_server import list_tools

        tools = await list_tools()
        get_tool = next(t for t in tools if t.name == "get_transcript")

        assert "filename" in get_tool.inputSchema["required"]


# ============================================================================
# Tool Execution Tests
# ============================================================================

class TestToolExecution:
    """Test actual tool execution with mocked dependencies."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock config and file structure."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        transcripts_path = vault_path / "Meetings" / "Transcripts"
        transcripts_path.mkdir(parents=True)
        daily_path = vault_path / "Daily"
        daily_path.mkdir()

        # Create a sample transcript (use quoted date to avoid YAML date parsing)
        transcript_content = """---
title: Test Meeting
date: "2026-01-15"
duration_minutes: 30
attendees:
  - Alice
  - Bob
processed: false
---

## Notes

This is a test meeting.

## Transcript

Alice: Hello
Bob: Hi there
"""
        (transcripts_path / "2026-01-15 - Test Meeting.md").write_text(transcript_content)

        cache_path = tmp_path / "granola_cache.json"
        cache_data = {
            "cache": json.dumps({
                "state": {
                    "documents": {
                        "doc1": {
                            "id": "doc1",
                            "title": "New Meeting",
                            "createdAt": "2026-01-16T10:00:00Z"
                        }
                    },
                    "transcripts": {
                        "doc1": [
                            {"text": "Hello everyone", "timestamp": 1000}
                        ]
                    },
                    "events": []
                }
            })
        }
        cache_path.write_text(json.dumps(cache_data))

        config_path = tmp_path / "config.yaml"
        config_yaml = f"""
granola_cache: {cache_path}
obsidian_vault: {vault_path}
transcripts_folder: Meetings/Transcripts
daily_folder: Daily
"""
        config_path.write_text(config_yaml)

        return {
            "granola_cache": cache_path,
            "obsidian_vault": vault_path,
            "transcripts_folder": "Meetings/Transcripts",
            "daily_folder": "Daily",
            "config_path": config_path,
        }

    @pytest.mark.asyncio
    async def test_get_granola_cache_info(self, mock_config):
        """get_granola_cache_info should return cache statistics."""
        from mcp_server import call_tool

        with patch("mcp_server.load_config", return_value=mock_config):
            result = await call_tool("get_granola_cache_info", {})

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert data["status"] == "success"
        assert data["documents_count"] == 1
        assert data["transcripts_count"] == 1

    @pytest.mark.asyncio
    async def test_get_transcript_success(self, mock_config):
        """get_transcript should return transcript content."""
        from mcp_server import call_tool

        with patch("mcp_server.load_config", return_value=mock_config):
            result = await call_tool("get_transcript", {
                "filename": "2026-01-15 - Test Meeting.md"
            })

        assert len(result) == 1
        data = json.loads(result[0].text)

        assert data["status"] == "success"
        assert data["frontmatter"]["title"] == "Test Meeting"
        assert "Alice" in data["frontmatter"]["attendees"]

    @pytest.mark.asyncio
    async def test_get_transcript_not_found(self, mock_config):
        """get_transcript should return error for missing file."""
        from mcp_server import call_tool

        with patch("mcp_server.load_config", return_value=mock_config):
            result = await call_tool("get_transcript", {
                "filename": "nonexistent.md"
            })

        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "not found" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_get_transcript_missing_filename(self, mock_config):
        """get_transcript should require filename."""
        from mcp_server import call_tool

        with patch("mcp_server.load_config", return_value=mock_config):
            result = await call_tool("get_transcript", {})

        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "filename" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, mock_config):
        """Unknown tool names should return an error."""
        from mcp_server import call_tool

        with patch("mcp_server.load_config", return_value=mock_config):
            result = await call_tool("nonexistent_tool", {})

        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "unknown tool" in data["message"].lower()


# ============================================================================
# Sync Transcripts Tests
# ============================================================================

class TestSyncTranscripts:
    """Test the sync_transcripts functionality."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create complete mock environment for sync testing."""
        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        transcripts_path = vault_path / "Meetings" / "Transcripts"
        transcripts_path.mkdir(parents=True)
        daily_path = vault_path / "Daily"
        daily_path.mkdir()

        cache_path = tmp_path / "granola_cache.json"
        cache_data = {
            "cache": json.dumps({
                "state": {
                    "documents": {
                        "doc1": {
                            "id": "doc1",
                            "title": "Team Standup",
                            "createdAt": "2026-01-15T10:00:00Z",
                            "notes_markdown": "## Action Items\n- Review PR"
                        }
                    },
                    "transcripts": {
                        "doc1": [
                            {"text": "Good morning everyone", "timestamp": 1000},
                            {"text": "Let's start the standup", "timestamp": 2000}
                        ]
                    },
                    "events": []
                }
            })
        }
        cache_path.write_text(json.dumps(cache_data))

        return {
            "granola_cache": cache_path,
            "obsidian_vault": vault_path,
            "transcripts_folder": "Meetings/Transcripts",
            "daily_folder": "Daily",
        }

    def test_sync_creates_transcript_file(self, mock_config):
        """sync_transcripts should create new transcript files."""
        from granola_sync import sync_transcripts

        stats = sync_transcripts(mock_config)

        assert stats["transcripts_created"] == 1
        assert stats["errors"] == 0

        # Check file was created
        transcripts_dir = mock_config["obsidian_vault"] / mock_config["transcripts_folder"]
        files = list(transcripts_dir.glob("*.md"))
        assert len(files) == 1
        assert "Team Standup" in files[0].name

    def test_sync_skips_existing_transcripts(self, mock_config):
        """sync_transcripts should skip already synced files."""
        from granola_sync import sync_transcripts

        # First sync
        stats1 = sync_transcripts(mock_config)
        assert stats1["transcripts_created"] == 1

        # Second sync should skip
        stats2 = sync_transcripts(mock_config)
        assert stats2["transcripts_created"] == 0
        assert stats2["transcripts_skipped"] == 1

    def test_sync_handles_empty_cache(self, tmp_path):
        """sync_transcripts should handle empty cache gracefully."""
        from granola_sync import sync_transcripts

        vault_path = tmp_path / "vault"
        vault_path.mkdir()
        transcripts_path = vault_path / "Meetings" / "Transcripts"
        transcripts_path.mkdir(parents=True)

        cache_path = tmp_path / "granola_cache.json"
        cache_data = {
            "cache": json.dumps({
                "state": {
                    "documents": {},
                    "transcripts": {},
                    "events": []
                }
            })
        }
        cache_path.write_text(json.dumps(cache_data))

        config = {
            "granola_cache": cache_path,
            "obsidian_vault": vault_path,
            "transcripts_folder": "Meetings/Transcripts",
            "daily_folder": "Daily",
        }

        stats = sync_transcripts(config)

        assert stats["transcripts_created"] == 0
        assert stats["transcripts_skipped"] == 0
        assert stats["errors"] == 0
