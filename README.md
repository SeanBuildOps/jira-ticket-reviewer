# Jira Ticket Reviewer

A plugin-driven MCP server for scoring AI agent performance on Jira tickets.

For architecture details, see [`plans/`](./plans/).

## Available Plugins

### `time_to_completion`

Measures elapsed time from the first "In Progress" status transition to the "Done" transition in a ticket's changelog.

**Config fields:**

| Field | Type | Default | Description |
|---|---|---|---|
| `ideal_hours` | float | `4.0` | Tickets completed at or under this time score 1.0 (perfect). |
| `max_hours` | float | `24.0` | Tickets at or over this time score 0.0. Must be greater than `ideal_hours`. |

**Score meaning:** Linear decay between `ideal_hours` (score 1.0) and `max_hours` (score 0.0). Tickets with no changelog, missing status transitions, or malformed timestamps are skipped and returned with a score of 0.0 and a `skipped: true` metadata flag.
