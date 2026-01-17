# MCP Server Setup Guide

This guide will help you set up Granola Obsidian Sync as an MCP (Model Context Protocol) server for use with Claude Desktop or Claude Code.

## What is MCP?

MCP (Model Context Protocol) is a standard that allows Claude to directly access tools and data sources. By installing this as an MCP server, Claude can:

- Sync your Granola transcripts to Obsidian with a simple request
- List and search through your meeting transcripts
- Read transcript content directly
- Monitor your Granola cache status

## Installation Steps

### 1. Install the Package

You can install this package directly from GitHub:

```bash
# Clone the repository
git clone https://github.com/wolfkevin/obsidian-granola-sync.git
cd obsidian-granola-sync

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Or install it as a package:

```bash
pip install git+https://github.com/wolfkevin/obsidian-granola-sync.git
```

### 2. Configure Your Paths

Copy the example config and customize it:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your settings:

```yaml
# Path to Granola's local cache
granola_cache: ~/Library/Application Support/Granola/cache-v3.json

# Path to your Obsidian vault
obsidian_vault: ~/Obsidian Vault

# Relative paths within the vault
transcripts_folder: 4-archive/transcripts
daily_folder: 5-reflections/daily
projects_index: 1-projects/index.md

# Processing settings
auto_process_after_hours: 48
model: claude-sonnet-4-20250514
```

### 3. Add to Claude Desktop

Edit your Claude Desktop configuration file:

**macOS:**
```bash
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```bash
~/.config/Claude/claude_desktop_config.json
```

Add the MCP server configuration:

```json
{
  "mcpServers": {
    "granola-sync": {
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/absolute/path/to/obsidian-granola-sync"
    }
  }
}
```

**Important:** Replace `/absolute/path/to/obsidian-granola-sync` with the actual path to where you cloned this repository.

If you're using a virtual environment, use the full path to the Python executable:

```json
{
  "mcpServers": {
    "granola-sync": {
      "command": "/absolute/path/to/obsidian-granola-sync/venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/absolute/path/to/obsidian-granola-sync"
    }
  }
}
```

### 4. Restart Claude Desktop

After adding the configuration, restart Claude Desktop for the changes to take effect.

### 5. Verify Installation

Open Claude Desktop and try asking:

> "What Granola sync tools do you have available?"

Claude should be able to see and describe the four available tools.

## Using the MCP Server

### Syncing Transcripts

Ask Claude to sync your transcripts:

> "Sync my new Granola transcripts to Obsidian"

Claude will use the `sync_transcripts` tool and report how many transcripts were created or updated.

### Listing Unprocessed Transcripts

To see what transcripts need processing:

> "Show me my unprocessed meeting transcripts"
>
> "List meetings from the last 48 hours that I haven't reviewed"

### Getting Transcript Content

To read a specific transcript:

> "Get the transcript from the Team Standup meeting from January 15th"
>
> "Show me the content of '2026-01-15 - Team Standup.md'"

### Checking Cache Status

To see what's in your Granola cache:

> "How many meetings do I have in my Granola cache?"
>
> "Check my Granola cache status"

## Troubleshooting

### MCP Server Not Appearing

1. Check that the `config.yaml` file exists in the repository directory
2. Verify the paths in `claude_desktop_config.json` are absolute (not relative)
3. Check Claude Desktop logs:
   - macOS: `~/Library/Logs/Claude/mcp*.log`
   - Windows: `%APPDATA%\Claude\logs\mcp*.log`

### Permission Errors

Make sure the Python script has execute permissions:

```bash
chmod +x mcp_server.py
```

### Python Module Not Found

If you see "No module named 'mcp'", install the dependency:

```bash
pip install mcp
```

### Config File Not Found

The `config.yaml` file must be in the same directory as `mcp_server.py`. Check:

```bash
ls -la /path/to/obsidian-granola-sync/config.yaml
```

## Alternative: Using with Claude Code

You can also use this MCP server with Claude Code CLI. Add it to your MCP settings:

```bash
claude config mcp add granola-sync
```

Then provide the same command and working directory as shown above.

## Benefits of MCP vs Python Scripts

| Feature | MCP Server | Python Scripts |
|---------|-----------|----------------|
| Ease of use | Just ask Claude | Run commands manually |
| Integration | Native in Claude Desktop | Separate terminal |
| Interactive | Yes, conversational | No |
| API costs | Uses Claude Desktop | Uses Anthropic API directly |
| Automation | On-demand via Claude | Scheduled via launchd |

## Next Steps

Once you have the MCP server running:

1. Try syncing your transcripts through Claude
2. Ask Claude to help you process and organize meetings
3. Use Claude to extract insights from your transcripts

The MCP server can work alongside the Python scripts - use whichever workflow fits your needs!
