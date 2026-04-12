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
- **Jira-first**: Plugins access Jira through a controlled `PluginContext` — no raw API clients.
- **Capability model**: Each plugin declares a whitelist of Jira operations in `scorer.yaml`. Undeclared operations raise `CapabilityError`.
- **Session cache**: All plugins share a single in-memory cache per `score_tickets()` call. First plugin to request a Jira resource fetches it; subsequent plugins get the cached result.
- **Graceful degradation**: Plugin failures return a null result and are excluded from aggregation — they never crash the engine.
- **Normalized scores**: Every plugin outputs a `0.0–1.0` float. The engine computes a weighted mean.

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
