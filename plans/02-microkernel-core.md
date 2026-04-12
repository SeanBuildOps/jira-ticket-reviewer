# Phase 2 — Microkernel Core

**Branch:** `phase/2-microkernel`

---

## Goal

Build the engine, plugin contract, and MCP server shell. No real plugins yet — only the `ExamplePlugin` stub. The framework mirrors the `TimeTrackingMcp` prototype (`/Users/sean/Workspace/prototypes/claude/TimeTrackingMcp`).

**Framework choices:**
- `FastMCP` from `mcp.server.fastmcp`
- `pyproject.toml` + `uv_build` (no `requirements.txt`)
- `uv run jira-reviewer-mcp` entry point
- `.mcp.json` for Claude Code registration
- `.env` / `.env.example` for secrets; `config/scorer.yaml` for plugin config

---

## File Structure

```
jira-ticket-reviewer/
├── src/
│   └── jira_reviewer/
│       ├── __init__.py          # load_dotenv() on first import
│       ├── server.py            # FastMCP instance + @mcp.tool() wrappers
│       ├── core/
│       │   ├── __init__.py
│       │   ├── engine.py        # ScoringEngine
│       │   ├── plugin.py        # ScoringPlugin Protocol + PluginContext
│       │   └── models.py        # Ticket, TicketScore, PluginResult dataclasses
│       ├── plugins/
│       │   ├── __init__.py      # PLUGIN_REGISTRY: dict[str, type[ScoringPlugin]]
│       │   └── example.py       # ExamplePlugin — disabled stub, shows required contract
│       └── tools/
│           └── _helpers.py      # config loader singleton (loads scorer.yaml)
├── config/
│   ├── scorer.example.yaml      # committed — plugin config schema
│   └── scorer.yaml              # git-ignored — user's active config
├── plans/
├── cache/
├── CHANGELOG.txt
├── pyproject.toml
├── .env.example
├── .env                         # git-ignored
├── .mcp.json
├── .gitignore
└── README.md
```

### File Purposes

| File | Purpose |
|------|---------|
| `src/jira_reviewer/__init__.py` | Calls `load_dotenv()` on first import so secrets are available to all modules |
| `src/jira_reviewer/server.py` | FastMCP instance; exposes `score_tickets` and `list_plugins` as MCP tools |
| `src/jira_reviewer/core/engine.py` | `ScoringEngine` — orchestrates plugin loading, sequential execution, aggregation |
| `src/jira_reviewer/core/plugin.py` | `ScoringPlugin` Protocol (structural) and `PluginContext` (cache-backed Jira access) |
| `src/jira_reviewer/core/models.py` | `Ticket`, `PluginResult`, `TicketScore` dataclasses |
| `src/jira_reviewer/plugins/__init__.py` | `PLUGIN_REGISTRY` dict — maps plugin name strings to their classes |
| `src/jira_reviewer/plugins/example.py` | `ExamplePlugin` stub — demonstrates Protocol shape without inheriting from it |
| `src/jira_reviewer/tools/_helpers.py` | `get_engine()` singleton — loads `scorer.yaml` and constructs a `ScoringEngine` |
| `config/scorer.example.yaml` | Committed example showing valid plugin config schema |
| `config/scorer.yaml` | Git-ignored; user's active config (copy and edit the example) |
| `pyproject.toml` | Project metadata, dependencies, entry point |
| `.env.example` | Committed template listing required env vars (values blank) |
| `.env` | Git-ignored; user's actual secrets |
| `.mcp.json` | Claude Code server registration |

---

## Key Contracts

### `Ticket` dataclass (`src/jira_reviewer/core/models.py`)

Identity anchor — not a data bag. Frozen so plugins cannot mutate it.

```python
@dataclass(frozen=True)
class Ticket:
    key: str     # e.g. "PROJ-123"  — guarantees all plugins operate on same ticket
    status: str  # e.g. "Done"      — basic gate; engine can assert before scoring
```

**Why only `key` + `status`:**
- `key` ensures every plugin unambiguously targets the same Jira issue
- `status` lets the engine (or caller) gate on "Done" before any plugin runs
- Everything else — summary, assignee, priority, changelog, comments — is fetched lazily via `PluginContext` and stored in the session cache for free reuse

Populated by a single thin extraction before scoring:

```python
def make_ticket(jira_issue: dict) -> Ticket:
    return Ticket(
        key=jira_issue["key"],
        status=jira_issue["fields"]["status"]["name"],
    )
```

No other transformation. Plugins call `context.get_issue(ticket.key)` if they need summary, assignee, priority, etc. — fetched once, cached for all plugins.

---

### `ScoringPlugin` Protocol (`src/jira_reviewer/core/plugin.py`)

Structural interface — no inheritance required. Any class that implements the required properties and method satisfies the Protocol.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ScoringPlugin(Protocol):
    """Structural interface — no inheritance required.
    Any class that implements these properties and method satisfies the protocol.
    Plugin authors do not need to import or subclass ScoringPlugin.
    """

    @property
    def name(self) -> str: ...
    # Unique identifier matching the key in PLUGIN_REGISTRY and scorer.yaml

    @property
    def version(self) -> str: ...
    # Optional. Semver string e.g. "1.0.0". Defaults to "0.0.0" if not provided.
    # Allows multiple versions of the same plugin to coexist.

    @property
    def author(self) -> str: ...
    # Optional. e.g. "sean@buildops.com". Defaults to "unknown" if not provided.

    @property
    def weight(self) -> float: ...
    # Relative importance of this plugin in the weighted aggregation. Must be > 0.

    @property
    def description(self) -> str: ...
    # One sentence describing what this plugin measures.
    # e.g. "Measures elapsed time from In Progress to Done status."

    def score(self, ticket: Ticket, context: PluginContext) -> PluginResult: ...
    # ticket.key    — use to fetch data via context
    # ticket.status — pre-verified "Done" by engine before this call
```

**Required fields** (missing any raises `ConfigError` at engine init):
- `name`
- `description`
- `weight` (must be a float > 0)
- `score()`

**Optional fields** (engine supplies defaults if absent):
- `version` — defaults to `"0.0.0"`
- `author` — defaults to `"unknown"`

**Benefits over ABC inheritance:**
- Plugin authors import nothing from this package — zero coupling
- Plugins can live in any codebase or be loaded dynamically
- Engine validates via `isinstance(instance, ScoringPlugin)` at init (enabled by `@runtime_checkable`)
- Granular check for precise error messages: engine also inspects each required attribute individually

---

### `PluginContext` (`src/jira_reviewer/core/plugin.py`)

Cache-backed, read-only access to Jira. The interface itself is the boundary — no per-plugin capability whitelist.

```python
class PluginContext:
    """Cache-backed, read-only access to Jira. The interface itself is the boundary."""
    def __init__(self, jira_client, cache: dict): ...

    def get_issue(self, key: str) -> dict: ...
    def get_changelog(self, key: str) -> list: ...
    def get_comments(self, key: str) -> list: ...
    def get_worklogs(self, key: str) -> list: ...
    def search(self, jql: str, fields: list) -> list: ...
    # All methods are read-only. Cache is checked before every Jira call.
```

---

### `PluginResult` dataclass (`src/jira_reviewer/core/models.py`)

```python
@dataclass
class PluginResult:
    plugin_name: str
    plugin_version: str = "0.0.0"   # optional — engine defaults to "0.0.0" if not declared
    plugin_author: str  = "unknown" # optional — engine defaults to "unknown" if not declared
    plugin_description: str  # copied from plugin.description — travels with the result
    raw_value: Any           # e.g. 4.5, 320, 3 — the measured value before normalisation
    normalized_score: float  # 0.0–1.0, higher = better
    weight: float
    contribution: float      # engine-set: (normalized_score * weight) / total_weight — % of final score
    label: str               # short: "Completed in 3.5h"
    reasoning: str           # full: "Completed in 3.5h vs ideal 4h. Top tier. Contributes 34% to score."
    metadata: dict           # any extra structured data the plugin wants to expose
```

---

### `TicketScore` dataclass (`src/jira_reviewer/core/models.py`)

```python
@dataclass
class TicketScore:
    ticket: Ticket
    plugin_results: dict[str, PluginResult]  # keyed by plugin name
    combined_score: float                    # weighted mean of (normalized_score × weight)
    # combined_score breakdown is fully derivable from plugin_results:
    # each result carries its contribution %, reasoning, and raw value
```

---

### `ScoringEngine` (`src/jira_reviewer/core/engine.py`)

Sequential plugin execution. One `session_cache` per `score_tickets()` call, shared across all plugins and all tickets in that call.

```python
class ScoringEngine:
    def __init__(self, config: dict): ...
    def score_ticket(self, ticket: Ticket) -> TicketScore: ...
    def score_tickets(self, tickets: list[Ticket]) -> list[TicketScore]: ...  # one shared cache
    def _aggregate(self, results: dict[str, PluginResult]) -> tuple[float, dict]: ...
    # _aggregate returns (combined_score, results_with_contribution)
    # contribution is set here: result.contribution = (score * weight) / total_weight
    def _load_plugins(self, config: dict) -> list[ScoringPlugin]: ...
```

**Early plugin validation rules** — raised at `__init__`, never mid-run:

| Condition | Error |
|-----------|-------|
| `name not in PLUGIN_REGISTRY` | `ConfigError("unknown plugin: X")` |
| `score()` not implemented | `ConfigError("X missing: score")` |
| `description` not implemented | `ConfigError("X missing: description")` |
| `weight` not a float | `ConfigError("X.weight must be float")` |
| `weight <= 0` | `ConfigError("X.weight must be > 0")` |
| `version` missing or None | Default `"0.0.0"` (no error) |
| `author` missing or None | Default `"unknown"` (no error) |

---

### `PLUGIN_REGISTRY` (`src/jira_reviewer/plugins/__init__.py`)

Central registry — maps plugin name strings to their classes. New plugins are registered here.

```python
from jira_reviewer.plugins.example import ExamplePlugin

PLUGIN_REGISTRY: dict[str, type[ScoringPlugin]] = {
    "example_plugin": ExamplePlugin,
    # new plugins registered here
}
```

---

### `ExamplePlugin` stub (`src/jira_reviewer/plugins/example.py`)

Disabled stub that shows the required Protocol shape. No inheritance from `ScoringPlugin`.

```python
# No import of ScoringPlugin needed — just satisfy the shape.
class ExamplePlugin:
    def __init__(self, config: dict):
        self._config = config

    @property
    def name(self) -> str:
        return "example_plugin"

    @property
    def description(self) -> str:
        return "Stub plugin — replace with a real implementation."

    @property
    def weight(self) -> float:
        return self._config.get("weight", 1.0)

    def score(self, ticket, context):   # type hints optional — protocol validates at runtime
        from jira_reviewer.core.models import PluginResult
        return PluginResult(
            plugin_name=self.name,
            plugin_description=self.description,
            raw_value=None,
            normalized_score=0.0,
            weight=self.weight,
            contribution=0.0,
            label="No score — stub plugin",
            reasoning="ExamplePlugin is a stub. Implement a real plugin.",
            metadata={},
        )
```

---

### `server.py` shell (`src/jira_reviewer/server.py`)

Mirrors the TimeTrackingMcp pattern.

```python
from mcp.server.fastmcp import FastMCP
from jira_reviewer.tools._helpers import get_engine

mcp = FastMCP("Jira Agent Reviewer")

@mcp.tool()
def list_plugins() -> str:
    """Return names, weights, and enabled state of all configured plugins."""
    ...

@mcp.tool()
def score_tickets(tickets: list[dict]) -> str:
    """Score a list of completed Jira tickets (raw Jira issue JSON) using configured plugins."""
    # normalizes each dict → Ticket, then passes to engine
    ...

def main() -> None:
    mcp.run()
```

---

### `scorer.example.yaml` (`config/scorer.example.yaml`)

```yaml
plugins:
  - name: example_plugin
    enabled: false
    weight: 1.0
    config: {}
```

No `capabilities` list — `PluginContext` already defines the boundary of what's callable.

---

### `pyproject.toml`

```toml
[project]
name = "jira-reviewer-mcp"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["mcp[cli]>=1.0.0", "python-dotenv>=1.0.0", "pyyaml>=6.0.0"]

[build-system]
requires = ["uv_build>=0.10.0,<0.11.0"]
build-backend = "uv_build"

[project.scripts]
jira-reviewer-mcp = "jira_reviewer.server:main"
```

---

### `.mcp.json`

```json
{
  "mcpServers": {
    "jira-reviewer": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/sean/Workspace/repos/jira-ticket-reviewer", "jira-reviewer-mcp"]
    }
  }
}
```

---

## Session Cache Design

One `session_cache: dict` is created per `score_tickets()` call and injected into every `PluginContext`. All plugins for the same scoring session share it.

- The first plugin to request `get_changelog("PROJ-123")` fetches from Jira and stores the result
- Every subsequent plugin gets the cached value at zero cost
- Cache key format: `(operation_name, jira_key)` — e.g. `("changelog", "PROJ-123")`
- Cache is in-memory only — never written to disk
- Cache lives for the duration of one `score_tickets()` call and is discarded after

```python
# In ScoringEngine.score_tickets():
session_cache: dict = {}
for ticket in tickets:
    context = PluginContext(
        jira_client=self._jira,
        cache=session_cache      # ← shared across all plugins, all tickets
    )
    result = plugin.score(ticket, context)

# In PluginContext.get_changelog():
def get_changelog(self, key: str) -> list:
    cache_key = ("changelog", key)
    if cache_key not in self._cache:
        self._cache[cache_key] = self._jira.get_changelog(key)
    return self._cache[cache_key]
```

**Note on future parallel execution:** When `ThreadPoolExecutor` is added (deferred), the cache will need per-key `threading.Lock` with double-checked locking to remain safe. This is intentionally deferred — sequential execution is correct and sufficient for now.

---

## Example Output Shape

```
TicketScore(
  ticket = Ticket(key="PROJ-123", status="Done"),
  combined_score = 0.74,
  plugin_results = {
    "time_to_completion": PluginResult(
      plugin_name        = "time_to_completion",
      plugin_version     = "1.0.0",
      plugin_author      = "BuildOps Platform Team",
      plugin_description = "Measures elapsed time from In Progress to Done.",
      raw_value          = 3.5,           # hours
      normalized_score   = 0.87,
      weight             = 2.0,
      contribution       = 0.41,          # 41% of final score
      label              = "Completed in 3.5h",
      reasoning          = "3.5h vs 4h ideal. Excellent. Contributes 41% to score.",
    ),
    "comment_count": PluginResult(
      plugin_name        = "comment_count",
      plugin_version     = "1.2.0",
      plugin_author      = "sean@buildops.com",
      plugin_description = "Fewer Jira comments indicate higher agent autonomy.",
      raw_value          = 6,
      normalized_score   = 0.60,
      weight             = 1.0,
      contribution       = 0.21,          # 21% of final score
      label              = "6 comments",
      reasoning          = "6 comments exceeds ideal of ≤3. Some clarification needed.",
    ),
  }
)
```

---

## Verification Checklist

- [ ] `uv run jira-reviewer-mcp` starts without errors
- [ ] `from jira_reviewer.core.engine import ScoringEngine` imports cleanly
- [ ] `from jira_reviewer.core.plugin import ScoringPlugin` imports cleanly
- [ ] `from jira_reviewer.core.models import TicketScore, PluginResult` imports cleanly
- [ ] `ScoringEngine` with empty plugins list: `score_tickets([])` returns `[]`
- [ ] `ScoringEngine` with unknown plugin name raises `ConfigError("unknown plugin: X")` at init
- [ ] A plugin class missing `description` raises `ConfigError("X missing: description")` at init
- [ ] A plugin class missing `score()` raises `ConfigError("X missing: score")` at init
- [ ] A plugin with `weight <= 0` raises `ConfigError("X.weight must be > 0")` at init
- [ ] `ExamplePlugin` loads cleanly and returns a valid `PluginResult` stub
- [ ] `PLUGIN_REGISTRY` in `plugins/__init__.py` contains `"example_plugin"`
- [ ] `scorer.example.yaml` is valid YAML with all required keys
- [ ] `pyyaml` listed in dependencies and `scorer.yaml` is loaded via PyYAML (not JSON)
- [ ] `.mcp.json` present and references correct entry point
- [ ] All files committed, `git status` clean
- [ ] Code review passes (no critical/blocker issues)
- [ ] **User approves → Phase 3 begins**
