# Process Transcripts Skill

Add this to your Obsidian vault's `CLAUDE.md` to enable the `/process-transcripts` command in Claude Code.

## Installation

Copy the following section into your `CLAUDE.md` file:

---

## Process Transcripts (`/process-transcripts`)

Sync and process meeting transcripts from Granola to extract action items, metrics, and updates.

### Your Role Context
Customize this section for your role to identify implicit responsibilities:
```markdown
### Your Role Context
Use this to identify implicit responsibilities even when not explicitly assigned:
- **PM for [Product A]** — owns roadmap, tracks product metrics
- **PM for [Product B]** — geo-lift tests, customer qualification
- When meetings with product/design folks identify metrics or KPIs for your products, those are your responsibility to track
```

### Trigger
- User says `/process-transcripts` or "process my transcripts"
- Can specify: `/process-transcripts today` or `/process-transcripts all`

### Workflow

1. **Sync new transcripts from Granola:**
   ```bash
   cd ~/repos/obsidian-granola-sync && source venv/bin/activate && python granola_sync.py
   ```
   - This pulls any new meetings from Granola's local cache
   - Creates transcript files in `4-archive/transcripts/`
   - Adds meeting entries to daily files

2. **Find unprocessed transcripts** in `4-archive/transcripts/`
   - Look for files with `processed: false` in frontmatter
   - Default: process today's transcripts only
   - With `all`: process all unprocessed

3. **For each transcript:**
   a. Read the transcript content and attendees

   b. **Infer meeting type from attendees:**
      - Product/design folks → likely roadmap/strategy meeting
      - Engineering/data science → likely technical discussion
      - Customer success/servicing → likely customer or ops discussion
      - Roadmap/strategy meetings often have implicit responsibilities

   c. **Analyze to extract:**
      - **Action items** — explicit tasks ("Can you do X", "let's make a to-do")
      - **Metrics to track** — KPIs, success metrics, traction metrics for your products
      - **Follow-ups** — things you committed to or need to circle back on
      - **Decisions** — choices made that affect your products
      - **Project-relevant updates** — match against `1-projects/index.md` keywords

   d. **Update daily file** (`5-reflections/daily/YYYY-MM-DD.md`):
      - Add action items as checkboxes under `## Work`
      - Format: `- [ ] Action item (from Meeting Name)`
      - If new metrics identified, add under `## Tracking` section (create if needed)
      - Format: `- **Product:** metric name — context`

   e. **Update project files** (if relevant):
      - Add summary under `## Meeting Notes` section
      - Format: `### YYYY-MM-DD - Meeting Title` with bullet points
      - Include any new metrics/KPIs in the project context

   f. **Mark transcript as processed:**
      - Change frontmatter `processed: false` → `processed: true`

4. **Report what was done:**
   - List processed transcripts
   - Summarize action items added
   - Note any metrics/tracking items identified
   - Note any project files updated

### Example Output
```
Processed 3 transcripts:

1. Team Standup (2026-01-15)
   - Added 1 action item to daily Work section
   - Updated 1-projects/mmm/context.md

2. Product Roadmap Review (2026-01-15)
   - Added 3 metrics to track:
     - % active users who take action
     - Average model quality score
     - Total accounts viewing results biweekly
   - Updated 1-projects/mmm/context.md with roadmap themes

3. Marketing Daily (2026-01-15)
   - No action items found
   - No project updates
```

### Key Files
- Transcripts: `4-archive/transcripts/*.md`
- Projects index: `1-projects/index.md`
- Daily files: `5-reflections/daily/YYYY-MM-DD.md`

### What to Capture (Quick Reference)

| Type | Example | Where it goes |
|------|---------|---------------|
| Explicit task | "Can you find a customer to test?" | Daily → Work |
| Metric/KPI | "Track % users taking actions" | Daily → Tracking + Project file |
| Commitment | "I'll look into that" | Daily → Work |
| Follow-up | "Circle back with X on Y" | Daily → Work |
| Decision | "We'll use biweekly cadence" | Project file only |
| Context/insight | "Users prefer biweekly reviews" | Project file only |

---

## Customization

Adjust these paths to match your Obsidian vault structure:

| Setting | Default | Description |
|---------|---------|-------------|
| Transcripts folder | `4-archive/transcripts/` | Where synced transcripts are stored |
| Daily files | `5-reflections/daily/YYYY-MM-DD.md` | Daily reflection files |
| Projects index | `1-projects/index.md` | Keywords for routing to project files |

## How It Works

This skill uses Claude Code's native capabilities (no external API calls) to:

1. **Read transcripts** using the Read tool
2. **Analyze content** using Claude's understanding of your role context
3. **Update files** using the Edit tool
4. **Track progress** by modifying frontmatter

This is more cost-effective than the automated `process_transcripts.py` script since it uses your existing Claude Code session instead of separate API calls.

## Usage Examples

```
# Process today's meetings
/process-transcripts

# Process all unprocessed transcripts
/process-transcripts all

# Process a specific meeting
Process the Team Standup transcript from today
```
