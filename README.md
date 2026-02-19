# Jira Ticket Recommender

A smart recommendation system that suggests Jira tickets from an epic based on priority and your domain expertise. Works standalone or as a Claude Code skill.

## Features

- **Smart Scoring**: Combines Jira priority with domain expertise matching
- **Claude Code Integration**: Use as `/recommend-tickets` command
- **Flexible**: Run standalone or integrate with Claude Code
- **Configurable**: Customize domains and keywords for your expertise
- **Cached**: Fast results using cached Jira data

## How It Works

The script scores unassigned "To Do" tickets using:

| Factor | Points | Description |
|--------|--------|-------------|
| **Priority** | 1-4 | Highest=4, High=3, Medium=2, Low=1 |
| **Domain Expertise** | 2x | +2 points for each matched domain |

**Combined Score** = Priority Score + (Expertise Matches × 2)

Tickets are ranked by combined score, with priority as a tiebreaker.

## Prerequisites

- Python 3.6+
- Jira access with Atlassian API credentials
- (Optional) [Claude Code](https://claude.ai/claude-code) with Atlassian MCP server configured

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/jira-ticket-recommender.git
cd jira-ticket-recommender
```

### 2. Configure Your Expertise

Copy the example config and customize it:

```bash
cp config/expertise.example.json config/expertise.json
```

Edit `config/expertise.json`:

```json
{
  "domains": {
    "Frontend": ["react", "ui", "component", "css"],
    "Backend": ["api", "server", "endpoint"],
    "Database": ["migration", "schema", "sql"]
  },
  "default_epic": "PROJ-1234",
  "user_account_id": "YOUR_ACCOUNT_ID",
  "cloud_id": "YOUR_CLOUD_ID"
}
```

**Finding Your IDs:**
- **cloud_id**: Go to Jira → Settings → Products → View cloud ID
- **user_account_id**: Go to your Jira profile → Account settings → Copy account ID

### 3. Populate Cache

If running as Claude skill, skip manual population. Claude instructions should populate the cache on first run.

**Option A: Using Claude Code with Atlassian MCP**

Ask Claude:
```
Query epic PROJ-1234 tickets and save to ~/jira-ticket-recommender/cache/epic_tickets.json
```

**Option B: Manual Export**

1. Run JQL in Jira: `"Epic Link" = PROJ-1234 ORDER BY priority DESC`
2. Export as JSON
3. Save to `cache/epic_tickets.json`

**Option C: Using Jira REST API**

```bash
curl -u YOUR_EMAIL:YOUR_API_TOKEN \
  "https://YOUR_DOMAIN.atlassian.net/rest/api/3/search?jql=parent=PROJ-1234&maxResults=100" \
  > cache/epic_tickets.json
```

## Usage

### Standalone Script

```bash
# Recommend top 3 tickets
python3 recommend-tickets.py 3

# Recommend top 5 tickets
python3 recommend-tickets.py 5

# Use specific epic
python3 recommend-tickets.py 5 --epic PROJ-5678

# Show refresh instructions
python3 recommend-tickets.py --refresh
```

### As Claude Code Skill

1. Copy `recommend-tickets.md` to `~/.claude/commands/`:

```bash
mkdir -p ~/.claude/commands
cp recommend-tickets.md ~/.claude/commands/
```

2. Update paths in `recommend-tickets.md` to point to your installation:

```markdown
python3 /path/to/jira-ticket-recommender/recommend-tickets.py N --epic EPIC_KEY
```

3. Use in Claude Code:

```
/recommend-tickets 3
/recommend-tickets 5 PROJ-1234
```

## Example Output

```
================================================================================
 TOP 3 RECOMMENDED TICKETS — Support Reduction Epic
================================================================================

  1. PROJ-1829
     Score: 7 (Priority: 3, Expertise: 2)
     Priority: High
     Your Domains: Frontend, Database
     Summary: Fix performance issue in user dashboard loading
     URL: https://yourcompany.atlassian.net/browse/PROJ-1829

  2. PROJ-2951
     Score: 6 (Priority: 2, Expertise: 2)
     Priority: Medium
     Your Domains: Backend, API
     Summary: Add pagination to search endpoint
     URL: https://yourcompany.atlassian.net/browse/PROJ-2951

  3. PROJ-3104
     Score: 4 (Priority: 4, Expertise: 0)
     Priority: Highest
     Summary: Critical security patch for authentication
     URL: https://yourcompany.atlassian.net/browse/PROJ-3104

================================================================================
 Total unassigned To Do tickets: 47
================================================================================
```

## Configuration Reference

### `config/expertise.json`

```json
{
  "domains": {
    "DomainName": ["keyword1", "keyword2", "phrase"]
  },
  "default_epic": "PROJ-1234",
  "user_account_id": "account_id_here",
  "cloud_id": "cloud_id_here",
  "cache_ttl_hours": {
    "epic_tickets": 1,
    "user_history": 24
  }
}
```

**Fields:**
- `domains`: Your expertise areas with matching keywords (case-insensitive)
- `default_epic`: Epic to query when not specified
- `user_account_id`: Your Atlassian account ID (for future features)
- `cloud_id`: Your Atlassian cloud instance ID (for API calls)
- `cache_ttl_hours`: Cache refresh recommendations (not enforced yet)

## Refreshing Cache

The script reads from cached data in `cache/epic_tickets.json`. To refresh:

### Via Claude Code (Recommended)

```
Refresh the Jira cache for epic PROJ-1234
```

Claude will query Jira via the Atlassian MCP server and update the cache.

### Manual Refresh

Re-run your JQL query and overwrite `cache/epic_tickets.json`.

## File Structure

```
jira-ticket-recommender/
├── README.md                      # This file
├── recommend-tickets.py           # Main script
├── recommend-tickets.md           # Claude Code skill definition
├── config/
│   ├── expertise.example.json    # Example configuration
│   └── expertise.json            # Your configuration (git-ignored)
├── cache/
│   └── epic_tickets.json         # Cached Jira data (git-ignored)
└── .gitignore
```

## Troubleshooting

**"Error: Cache file not found"**
- Run `python3 recommend-tickets.py --refresh` for instructions
- Make sure `cache/epic_tickets.json` exists and contains valid Jira data

**"No unassigned 'To Do' tickets found"**
- Check your epic has unassigned tickets in "To Do" status
- Verify the cache file contains the correct epic data

**Scores seem wrong**
- Review your `domains` configuration
- Keywords are case-insensitive and match anywhere in the summary
- Adjust keywords to better match your tickets

## Future Improvements

Integrate Entrepret's knowledge graph to power the scoring system with business metrics (churn, ARR, company size)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - feel free to use and modify for your needs.

## Acknowledgments

Built for use with [Claude Code](https://claude.ai/claude-code) and the Atlassian MCP server.
