"""ScoringPlugin Protocol and PluginContext."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from jira_reviewer.core.models import PluginResult, Ticket

logger = logging.getLogger(__name__)


@runtime_checkable
class ScoringPlugin(Protocol):
    """Structural interface — no inheritance required.

    Any class that implements these properties and method satisfies the protocol.
    Plugin authors do not need to import or subclass ScoringPlugin.
    """

    @property
    def name(self) -> str:
        """Unique identifier matching the key in PLUGIN_REGISTRY and scorer.yaml."""
        ...

    @property
    def version(self) -> str:
        """Optional. Semver string e.g. "1.0.0". Defaults to "0.0.0" if not provided."""
        ...

    @property
    def author(self) -> str:
        """Optional. e.g. "sean@example.com". Defaults to "unknown" if not provided."""
        ...

    @property
    def weight(self) -> float:
        """Relative importance of this plugin in the weighted aggregation. Must be > 0."""
        ...

    @property
    def description(self) -> str:
        """One sentence describing what this plugin measures."""
        ...

    def score(self, ticket: "Ticket", context: "PluginContext") -> "PluginResult":
        """Score the ticket. ticket.status is pre-verified "Done" by engine."""
        ...


class PluginContext:
    """Cache-backed, read-only access to Jira.

    The interface itself is the boundary — no per-plugin capability whitelist.
    All methods check the session cache before making any Jira call.

    Since jira_client is None in Phase 2 (no real Jira integration yet),
    methods return empty stubs and log a warning on cache miss.
    """

    def __init__(self, jira_client: object | None, cache: dict) -> None:
        self._jira = jira_client
        self._cache = cache

    def get_issue(self, key: str) -> dict:
        """Fetch a Jira issue by key. Returns {} if Jira client not configured."""
        cache_key = ("issue", key)
        if cache_key not in self._cache:
            if self._jira is None:
                logger.warning("PluginContext.get_issue(%r): no Jira client configured — returning {}", key)
                self._cache[cache_key] = {}
            else:
                self._cache[cache_key] = self._jira.get_issue(key)  # type: ignore[attr-defined]
        return self._cache[cache_key]

    def get_changelog(self, key: str) -> list:
        """Fetch the changelog for a Jira issue. Returns [] if Jira client not configured."""
        cache_key = ("changelog", key)
        if cache_key not in self._cache:
            if self._jira is None:
                logger.warning("PluginContext.get_changelog(%r): no Jira client configured — returning []", key)
                self._cache[cache_key] = []
            else:
                self._cache[cache_key] = self._jira.get_changelog(key)  # type: ignore[attr-defined]
        return self._cache[cache_key]

    def get_comments(self, key: str) -> list:
        """Fetch comments for a Jira issue. Returns [] if Jira client not configured."""
        cache_key = ("comments", key)
        if cache_key not in self._cache:
            if self._jira is None:
                logger.warning("PluginContext.get_comments(%r): no Jira client configured — returning []", key)
                self._cache[cache_key] = []
            else:
                self._cache[cache_key] = self._jira.get_comments(key)  # type: ignore[attr-defined]
        return self._cache[cache_key]

    def get_worklogs(self, key: str) -> list:
        """Fetch worklogs for a Jira issue. Returns [] if Jira client not configured."""
        cache_key = ("worklogs", key)
        if cache_key not in self._cache:
            if self._jira is None:
                logger.warning("PluginContext.get_worklogs(%r): no Jira client configured — returning []", key)
                self._cache[cache_key] = []
            else:
                self._cache[cache_key] = self._jira.get_worklogs(key)  # type: ignore[attr-defined]
        return self._cache[cache_key]

    def search(self, jql: str, fields: list) -> list:
        """Execute a JQL search. Returns [] if Jira client not configured."""
        cache_key = ("search", jql)
        if cache_key not in self._cache:
            if self._jira is None:
                logger.warning("PluginContext.search(%r): no Jira client configured — returning []", jql)
                self._cache[cache_key] = []
            else:
                self._cache[cache_key] = self._jira.search(jql, fields)  # type: ignore[attr-defined]
        return self._cache[cache_key]
