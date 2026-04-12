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
- **Controlled Jira access via `PluginContext`**: Plugins never receive raw API clients. `PluginContext` exposes a fixed set of read-only methods — that interface boundary is sufficient control. No per-plugin whitelist needed.
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
| Config validation | `ConfigError` raised at engine init for: unknown plugin name, protocol not satisfied (`score`/`description` missing), wrong return types, or `weight <= 0`. Never fails mid-run. |
| Plugin interface | `ScoringPlugin` is a `typing.Protocol` — no inheritance required. Plugins satisfy it by implementing the required properties and method. Zero coupling to this package. |
| Contract enforcement | `normalized_score` clamped to `[0.0, 1.0]` if out of range |
| Plugin timeouts | `timeout_seconds` per plugin in YAML. Exceeded = null result |
| Structured logging | `DEBUG`: plugin name, raw value, score, weight. `WARNING`: errors |
| No side effects | Plugins are read-only. Mutations raise `PluginSideEffectError` |
| Controlled Jira access | `PluginContext` is the only Jira interface plugins see. The interface itself is the boundary — no per-plugin whitelist |

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

## Future Improvements

| Improvement | When to revisit |
|---|---|
| **Parallel plugin execution** | `ThreadPoolExecutor` + `asyncio.gather()` — when plugin count or ticket volume makes sequential execution a measurable bottleneck. Plugins stay synchronous; engine owns concurrency. Requires per-key `threading.Lock` on session cache. |
| **Reporting** | Generate structured reports from `list[TicketScore]` — per-agent summaries, trend over time, plugin contribution breakdowns across a sprint. All data is already in `TicketScore.plugin_results`. Format options: Markdown, JSON, HTML. Could be a `report_tickets` MCP tool or a separate reporting module. |
