"""Data models for the Jira Ticket Reviewer scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Ticket:
    """Identity anchor for a Jira ticket. Frozen so plugins cannot mutate it.

    Only key + status are stored here. Everything else (summary, assignee,
    changelog, comments) is fetched lazily via PluginContext and cached.
    """

    key: str    # e.g. "PROJ-123"
    status: str # e.g. "Done"


@dataclass
class PluginResult:
    """Result produced by a single plugin for a single ticket."""

    plugin_name: str
    plugin_description: str
    raw_value: Any
    normalized_score: float
    weight: float
    contribution: float
    label: str
    reasoning: str
    plugin_version: str = "0.0.0"
    plugin_author: str = "unknown"
    metadata: dict = field(default_factory=dict)


@dataclass
class TicketScore:
    """Aggregated score for a single ticket across all plugins."""

    ticket: Ticket
    plugin_results: dict[str, PluginResult]  # keyed by plugin name
    combined_score: float                    # weighted mean of (normalized_score x weight)
