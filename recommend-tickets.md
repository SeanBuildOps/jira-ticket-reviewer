# recommend-tickets

Recommend top N Jira tickets from the Support Reduction epic based on priority and the user's domain expertise.

## Arguments

- `$ARGUMENTS` - Space-separated: `N [EPIC_KEY]`
  - **N** — Number of tickets to recommend (e.g., `3`, `5`, `10`). Defaults to 3 if not provided.
  - **EPIC_KEY** — Jira epic key (e.g., `ASSETS-2678`). Defaults to the value of `default_epic` in config/expertise.json if not provided.

## Instructions

When this command is invoked:

1. **Parse arguments**: Split `$ARGUMENTS` on spaces. Extract N (first numeric value) and EPIC_KEY (first value matching pattern `[A-Z]+-\d+`). Apply defaults for any missing values.

2. **Run the recommendation script**:
   ```bash
   python3 ~/scripts/jira/recommend-tickets.py N --epic EPIC_KEY
   ```

3. **If the script fails due to missing cache**, refresh the cache by:
   - Query Jira using MCP tool `searchJiraIssuesUsingJql`:
     - cloudId: `da8bb18a-8218-4f15-9cda-bb779bad7542`
     - JQL: `parent = EPIC_KEY`
     - fields: `["key", "summary", "status", "priority", "assignee", "labels"]`
     - maxResults: 100
   - Save the result to `~/scripts/jira/cache/epic_tickets.json`
   - Re-run the script

4. **Present the results** in a clear table format showing:
   - Rank
   - Ticket key (with link)
   - Score breakdown
   - Matched expertise domains
   - Summary

## Example Usage

```
/recommend-tickets 3
/recommend-tickets 5 ASSETS-2678
/recommend-tickets 10 ASSETS-3001
```

## Configuration

- Epic: ASSETS-2678 (2025Q4 Support Reduction)
- User: tahasun.tarannum@buildops.com
- Expertise domains: ACV, Revenue, ServiceAgreementYear, MaintenancePreview, SA Cloning, SA Wizard, Billing/Invoice, Migration, Bulk Operations

## Files

- Script: `~/scripts/jira/recommend-tickets.py`
- Config: `~/scripts/jira/config/expertise.json`
- Cache: `~/scripts/jira/cache/epic_tickets.json`
