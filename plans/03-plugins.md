# Phase 3 — Plugin Implementations

**Branch:** `phase/3-tools`

---

## Goal

Add real plugin implementations and wire complete tool logic in `src/jira_reviewer/tools/`. The microkernel from Phase 2 is already in place — this phase only adds plugins and fills in the MCP tool bodies.

> Note: `recommend-tickets.py` is gone after Phase 1. No CLI is added — the MCP server is the sole interface.

---

## Files Touched

| Action | File |
|--------|------|
| Create | `src/jira_reviewer/tools/score_tickets.py` |
| Create | `src/jira_reviewer/tools/list_plugins.py` |
| Create | `src/jira_reviewer/plugins/<plugin_name>.py` (one per plugin) |
| Modify | `src/jira_reviewer/server.py` — fill in tool bodies |
| Modify | `src/jira_reviewer/plugins/__init__.py` — register new plugins |
| Modify | `config/scorer.example.yaml` — add new plugin examples |
| Modify | `README.md` — document available plugins |

---

## How to Add a New Plugin

1. **Implement the Protocol shape** — create `src/jira_reviewer/plugins/<name>.py`. The class does not inherit from anything. It must implement:
   - `name` property → `str` (must match the registry key)
   - `description` property → `str` (one sentence describing what is measured)
   - `weight` property → `float` (read from `self._config`)
   - `score(ticket, context) -> PluginResult`
   - Optionally: `version` property → `str` and `author` property → `str`

2. **Register in `PLUGIN_REGISTRY`** — add an entry to `src/jira_reviewer/plugins/__init__.py`:
   ```python
   from jira_reviewer.plugins.<name> import <ClassName>

   PLUGIN_REGISTRY: dict[str, type[ScoringPlugin]] = {
       "example_plugin": ExamplePlugin,
       "<name>": <ClassName>,   # ← add here
   }
   ```

3. **Add to `scorer.yaml`** — add a block to `config/scorer.yaml` (and `scorer.example.yaml`):
   ```yaml
   plugins:
     - name: <name>
       enabled: true
       weight: 1.0
       config: {}   # any plugin-specific settings go here
   ```

---

## Planned Plugins

### `time_to_completion`

**File:** `src/jira_reviewer/plugins/time_to_completion.py`

Measures elapsed time between when a ticket transitioned to "In Progress" and when it transitioned to "Done". A shorter elapsed time (relative to a configurable ideal) yields a higher normalized score.

- **Data source:** `context.get_changelog(ticket.key)` — parses status transition history
- **`raw_value`:** elapsed hours as a float
- **`normalized_score`:** 1.0 at or below ideal duration; decays toward 0.0 as duration increases beyond ideal
- **Key config fields:** `ideal_hours` (the target completion time)
- **Primary use case:** Evaluating AI agent performance — an agent that resolves tickets quickly scores higher

---

### `comment_count`

**File:** `src/jira_reviewer/plugins/comment_count.py`

Counts the number of comments on a ticket. Fewer comments indicate that the agent (or developer) resolved the ticket with minimal back-and-forth — higher autonomy and clearer understanding. More comments suggest clarification was needed.

- **Data source:** `context.get_comments(ticket.key)` — counts returned comment objects
- **`raw_value`:** integer comment count
- **`normalized_score`:** 1.0 at 0 comments; decays toward 0.0 as count increases beyond a configurable threshold
- **Key config fields:** `ideal_max` (comment count at or below which score is 1.0), `zero_score_at` (count at which score reaches 0.0)
- **Primary use case:** Evaluating AI agent performance — agents that ask fewer questions score higher

---

## Future Improvements

These are intentionally deferred. Log deviations in `CHANGELOG.txt` when implemented.

### Parallel Plugin Execution

Replace the sequential `for plugin in plugins` loop in `ScoringEngine` with `ThreadPoolExecutor` + `asyncio.gather()`. Plugins stay synchronous — the engine owns concurrency.

When implemented:
- Add `engine.max_workers` and `engine.plugin_timeout` to `scorer.yaml`
- Session cache will require per-key `threading.Lock` with double-checked locking to remain safe under concurrent access:
  ```python
  # Per-key locking pattern
  if cache_key not in self._cache:
      with self._locks[cache_key]:
          if cache_key not in self._cache:   # double-checked
              self._cache[cache_key] = self._jira.fetch(...)
  ```
- Revisit when plugin count or ticket volume makes sequential execution a measurable bottleneck

### Reporting

Generate structured reports from `list[TicketScore]`. All data needed is already in `TicketScore.plugin_results` — each result carries contribution percentage, reasoning, raw value, and plugin metadata.

Possible formats: Markdown, JSON, HTML.

Possible delivery: a `report_tickets` MCP tool, or a standalone reporting module.

Ideas for report content:
- Per-agent summaries across a set of tickets
- Plugin contribution breakdowns across a sprint
- Trend over time (requires storing historical `TicketScore` data)
