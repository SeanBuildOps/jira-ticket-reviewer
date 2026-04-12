# Jira Ticket Reviewer — Overall Architecture

## Vision

A general-purpose, plugin-driven scoring engine exposed as an MCP server. The first use case is evaluating AI agent performance on completed Jira tickets.

```
┌──────────────────────────────────────────────────────┐
│                   MCP Clients                        │
│         Claude Code / Claude / any MCP host          │
└───────────────────────┬──────────────────────────────┘
                        │  MCP protocol (stdio/SSE)
                        ▼
┌──────────────────────────────────────────────────────┐
│                  MCP Server (server.py)              │
│  Exposes tools: score_tickets, list_plugins, ...     │
└───────────────────────┬──────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│              ScoringEngine (microkernel)             │
│  - Loads plugins from scorer.yaml                   │
│  - Runs each plugin → normalised 0.0–1.0 score      │
│  - Weighted aggregation → combined score            │
│  - Returns ranked TicketScore list                  │
└──────────────────────┬───────────────────────────────┘
                       │  Plugin interface
          ┌────────────┼────────────┐
          ▼            ▼            ▼
      [Plugin A]   [Plugin B]   [Plugin C]
      (future)     (future)     (future)
```

## Core Design Principles

- **Microkernel**: The engine only aggregates. All scoring logic is in plugins.
- **Slim `Ticket` as identity anchor**: `Ticket` holds only `key` and `status` — just enough to guarantee all plugins operate on the same ticket and that the engine can gate on "Done" before scoring. Nothing else is pre-fetched.
- **Session cache for all data**: One in-memory cache per `score_tickets()` call, shared across all plugins and all tickets. First plugin to request any Jira data (issue fields, changelog, comments) fetches it; every subsequent plugin gets it free from cache.
- **Jira-first**: Plugins access Jira through a controlled `PluginContext` — no raw API clients.
- **Capability model**: Each plugin declares a whitelist of Jira operations in `scorer.yaml`. Undeclared operations raise `CapabilityError`.
- **Graceful degradation**: Plugin failures return a null result and are excluded from aggregation — they never crash the engine.
- **Normalized scores**: Every plugin outputs a `0.0–1.0` float. The engine computes a weighted mean.

## Data Flow

```
MCP tool receives raw Jira JSON list
        ↓
make_ticket(issue) → Ticket(key, status)   # identity only — thin extraction
        ↓
engine.assert status == "Done"             # gate before any plugin runs
        ↓
ScoringEngine.score_tickets(tickets)
  creates one session_cache = {}           # shared across all plugins + tickets
        ↓
  for each plugin:
    PluginContext(allowed=plugin.capabilities, cache=session_cache)
    plugin.score(ticket, context)
      → ticket.key / ticket.status: free (already in Ticket)
      → anything else: context.get_issue(key) / get_changelog(key) / ...
           → cache hit?  return cached value (zero cost)
           → cache miss? fetch Jira, store in cache, return
        ↓
  _aggregate(plugin_results) → combined_score
        ↓
return sorted list[TicketScore]
```

## Non-Functional Requirements

| Requirement | Design Decision |
|---|---|
| Plugin isolation | `try/except` per plugin. Crash = null result + warning log |
| Graceful degradation | Null results excluded from weighted aggregation |
| Config validation | `ConfigError` raised at engine init on bad config — not mid-run |
| Contract enforcement | `normalized_score` clamped to `[0.0, 1.0]` if out of range |
| Plugin timeouts | `timeout_seconds` per plugin in YAML. Exceeded = null result |
| Structured logging | `DEBUG`: plugin name, raw value, score, weight. `WARNING`: errors |
| No side effects | Plugins are read-only. Mutations raise `PluginSideEffectError` |
| Jira-first capability model | `PluginContext` gates all data access. Only declared capabilities exposed |

## Branching Strategy

- `main` — stable. Plans, architecture docs, and merged phase work.
- `phase/1-cleanup` — removes old code
- `phase/2-microkernel` — engine, plugin interface, MCP server shell
- `phase/3-tools` — plugin implementations (future)

Each phase branch is reviewed and user-approved before merging to `main`.

## Phases

| Phase | Branch | Goal |
|-------|--------|------|
| 0 | `main` | Plans folder + architecture doc + CHANGELOG |
| 1 | `phase/1-cleanup` | Delete old recommender code |
| 2 | `phase/2-microkernel` | Engine + plugin contract + MCP server shell |
| 3 | `phase/3-tools` | Plugin implementations (future) |

See `plans/01-cleanup.md`, `plans/02-microkernel-core.md`, `plans/03-plugins.md` for phase detail.
