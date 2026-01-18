# Obsidian Granola Sync

Automatically sync meeting transcripts from [Granola](https://granola.ai) to your Obsidian vault.

## 🚀 Claude Code Plugin (Recommended)

Install in Claude Code:

```
/plugin marketplace add wolfkevin/obsidian-granola-sync
/plugin install granola@granola-obsidian
```

Then restart Claude Code and configure your Obsidian vault path:
```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your paths
```

### Usage

Once installed, run `/granola:sync` or just ask *"Sync my Granola transcripts"*

---

<details>
<summary><strong>Alternative: Manual MCP Setup</strong></summary>

If you prefer manual installation or want to use with Claude Desktop:

1. **Clone and install:**
   ```bash
   git clone https://github.com/wolfkevin/obsidian-granola-sync.git
   cd obsidian-granola-sync
   pip install -r requirements.txt
   ```

2. **Configure paths:**
   ```bash
   cp config.example.yaml config.yaml
   ```

3. **Add to Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json`):
   ```json
   {
     "mcpServers": {
       "granola-sync": {
         "command": "python3",
         "args": ["mcp_server.py"],
         "cwd": "/path/to/obsidian-granola-sync"
       }
     }
   }
   ```

📖 **[Full MCP Setup Guide](MCP_SETUP.md)**

</details>

---

## Features

- **Export transcripts** from Granola's local cache to Obsidian markdown files
- **Add meeting summaries** to daily reflection files
- **AI-powered processing** with Claude to:
  - Extract action items → adds to daily tasks
  - Route updates to project files based on keywords
  - Generate meeting notes if Granola didn't create them
- **Scheduled sync** via macOS launchd (runs daily at midnight)
- **48-hour auto-processing** for transcripts you haven't manually reviewed

## Requirements

- macOS (uses Granola's local cache)
- Python 3.10+
- [Granola](https://granola.ai) app installed
- Anthropic API key (for AI processing)

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/wolfkevin/obsidian-granola-sync.git
cd obsidian-granola-sync
```

### 2. Create virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure paths

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your Obsidian vault path
```

### 4. Set up API key

```bash
mkdir -p ~/.config/granola-sync
echo "ANTHROPIC_API_KEY=sk-ant-api03-xxxxx" > ~/.config/granola-sync/.env
```

### 5. Install launchd job (optional, for daily automation)

```bash
# Run the setup script (automatically configures paths)
./setup_launchd.sh
```

Or manually:
```bash
cp launchd/com.granola-sync.plist.template ~/Library/LaunchAgents/com.granola-sync.plist
# Edit the file to replace $HOME with your actual home directory
nano ~/Library/LaunchAgents/com.granola-sync.plist
launchctl load ~/Library/LaunchAgents/com.granola-sync.plist
```

## Usage

### Claude Code Skill (Recommended)

Add the `/process-transcripts` skill to your Obsidian vault's `CLAUDE.md`. See [SKILL.md](SKILL.md) for instructions.

This lets you process transcripts directly in Claude Code:
```
/process-transcripts        # Process today's transcripts
/process-transcripts all    # Process all unprocessed
```

**Benefits over the Python script:**
- Uses your existing Claude Code session (no separate API costs)
- Interactive - you can guide the processing
- No API key needed beyond Claude Code

### Manual sync

```bash
# Sync new transcripts to Obsidian
python3 granola_sync.py

# Process transcripts with Claude (extract action items, update projects)
python3 process_transcripts.py --all
```

### Processing options

```bash
# Process all unprocessed transcripts
python3 process_transcripts.py --all

# Only process transcripts older than 48 hours (auto mode)
python3 process_transcripts.py --auto

# Process a specific file
python3 process_transcripts.py --file "2026-01-15 - Team Standup.md"

# Dry run (see what would be processed)
python3 process_transcripts.py --all --dry-run
```

### Check logs

```bash
tail -f ~/Library/Logs/granola-sync.log
```

## Configuration

Edit `config.yaml`:

```yaml
# Path to Granola's local cache
granola_cache: ~/Library/Application Support/Granola/cache-v3.json

# Path to your Obsidian vault
obsidian_vault: ~/Obsidian Vault

# Relative paths within the vault
transcripts_folder: 4-archive/transcripts
daily_folder: 5-reflections/daily
projects_index: 1-projects/index.md

# Auto-process transcripts older than this many hours
auto_process_after_hours: 48

# Claude model for processing
model: claude-sonnet-4-20250514
```

## File Structure

### Transcript files

Created in `4-archive/transcripts/`:

```markdown
---
date: 2026-01-15
title: Team Standup
source: granola
granola_id: abc123
duration_minutes: 45
entry_count: 1280
attendees:
  - kevin@example.com
processed: false
---

## Notes

- Key discussion point 1
- Key discussion point 2

---

## Transcript

Full transcript text...
```

### Daily reflection updates

Adds to `5-reflections/daily/YYYY-MM-DD.md`:

```markdown
## Meetings

### Team Standup
- Discussion summary
*→ [[4-archive/transcripts/2026-01-15 - Team Standup]]*

## Work
- [ ] Action item from Team Standup
```

## How it works

1. **Sync** (`granola_sync.py`):
   - Reads Granola's local cache (`cache-v3.json`)
   - Creates markdown files for new transcripts
   - Adds meeting entries to daily reflection files

2. **Process** (`process_transcripts.py`):
   - Sends transcript to Claude for analysis
   - Extracts action items → adds to daily Work section
   - Matches keywords to projects → adds summaries to project files
   - Marks transcript as `processed: true`

3. **Schedule** (launchd):
   - Runs sync daily at midnight
   - Auto-processes transcripts older than 48 hours

## Projects Index

The `projects_index` file should contain keywords for routing:

```markdown
## MMM (Marketing Mix Modeling)
**File:** `1-projects/mmm/context.md`
**Keywords:** MMM, marketing mix, ROAS, budget optimization
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install -e ".[test]"

# Run tests
pytest

# Run with verbose output
pytest -v
```

Tests cover:
- Skill file format validation
- MCP server tool definitions
- Tool execution with mocked data
- Sync functionality

## License

MIT
