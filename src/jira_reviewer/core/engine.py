"""ScoringEngine — orchestrates plugin loading, sequential execution, and aggregation."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from jira_reviewer.core.models import PluginResult, Ticket, TicketScore
from jira_reviewer.core.plugin import PluginContext, ScoringPlugin

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ConfigError(ValueError):
    """Raised when the scoring engine configuration is invalid."""


class ScoringEngine:
    """Microkernel: loads plugins from config, runs them sequentially, aggregates scores.

    All plugin validation happens at __init__ time. score_tickets() never raises
    ConfigError — only plugin runtime errors, which are caught and logged.
    """

    def __init__(self, config: dict) -> None:
        self._config = config
        self._jira = None  # Phase 2: no real Jira client yet
        self._plugins: list[ScoringPlugin] = self._load_plugins(config)
        logger.debug("ScoringEngine initialised with %d plugin(s)", len(self._plugins))

    def score_tickets(self, tickets: list[Ticket]) -> list[TicketScore]:
        """Score a list of tickets. Returns results sorted descending by combined_score.

        Creates ONE session_cache shared across all plugins and all tickets
        in this call. Cache is discarded when this method returns.
        """
        if not tickets:
            return []

        session_cache: dict = {}
        results: list[TicketScore] = []

        for ticket in tickets:
            score = self.score_ticket(ticket, session_cache=session_cache)
            results.append(score)

        results.sort(key=lambda ts: ts.combined_score, reverse=True)
        return results

    def score_ticket(self, ticket: Ticket, session_cache: dict | None = None) -> TicketScore:
        """Score a single ticket. Uses a fresh cache if none is provided."""
        if session_cache is None:
            session_cache = {}

        plugin_results: dict[str, PluginResult] = {}

        for plugin in self._plugins:
            context = PluginContext(jira_client=self._jira, cache=session_cache)
            try:
                result = plugin.score(ticket, context)
                if result is not None:
                    # Clamp normalized_score to [0.0, 1.0]
                    if not (0.0 <= result.normalized_score <= 1.0):
                        logger.warning(
                            "Plugin %r returned out-of-range normalized_score %.3f for %s — clamping",
                            plugin.name,
                            result.normalized_score,
                            ticket.key,
                        )
                        result = replace(
                            result,
                            normalized_score=max(0.0, min(1.0, result.normalized_score)),
                        )
                    plugin_results[plugin.name] = result
                    logger.debug(
                        "Plugin %r scored %s: raw=%r normalized=%.3f weight=%.2f",
                        plugin.name,
                        ticket.key,
                        result.raw_value,
                        result.normalized_score,
                        result.weight,
                    )
                else:
                    logger.warning("Plugin %r returned None for %s — excluded from aggregation", plugin.name, ticket.key)
            except Exception as exc:
                logger.warning("Plugin %r raised an exception for %s — excluded: %s", plugin.name, ticket.key, exc)

        combined_score = self._aggregate(plugin_results)
        return TicketScore(ticket=ticket, plugin_results=plugin_results, combined_score=combined_score)

    def _aggregate(self, results: dict[str, PluginResult]) -> float:
        """Compute weighted mean and set contribution on each result.

        contribution = (normalized_score * weight) / total_weight
        Returns 0.0 if no results.

        Design note (deviation from plan): the plan specifies returning tuple[float, dict] with
        contributions. Instead, this method mutates PluginResult.contribution directly as a
        side effect and returns only the combined float. This avoids reconstructing the dict and
        is simpler since PluginResult is mutable. See CHANGELOG.txt for full rationale.
        """
        if not results:
            return 0.0

        total_weight = sum(r.weight for r in results.values())
        if total_weight == 0.0:
            return 0.0

        combined = sum(r.normalized_score * r.weight for r in results.values()) / total_weight

        # Set contribution on each result (mutate in place — PluginResult is not frozen)
        for result in results.values():
            result.contribution = (result.normalized_score * result.weight) / total_weight

        return combined

    def _load_plugins(self, config: dict) -> list[ScoringPlugin]:
        """Validate and instantiate plugins from config. Raises ConfigError on any issue."""
        from jira_reviewer.plugins import PLUGIN_REGISTRY

        plugin_configs: list[dict] = config.get("plugins", [])
        plugins: list[ScoringPlugin] = []

        for entry in plugin_configs:
            name = entry.get("name")
            if not name:
                raise ConfigError("plugin entry missing required field: name")

            enabled = entry.get("enabled", True)
            if not enabled:
                logger.debug("Plugin %r is disabled — skipping", name)
                continue

            if name not in PLUGIN_REGISTRY:
                raise ConfigError(f"unknown plugin: {name}")

            weight = entry.get("weight", 1.0)
            plugin_config = dict(entry.get("config", {}))
            plugin_config["weight"] = weight

            plugin_class = PLUGIN_REGISTRY[name]
            instance = plugin_class(plugin_config)

            self._validate_plugin(instance, name)
            plugins.append(instance)
            logger.debug("Loaded plugin %r (weight=%.2f)", name, weight)

        return plugins

    def _validate_plugin(self, instance: object, name: str) -> None:
        """Validate a plugin instance against the ScoringPlugin protocol.

        Raises ConfigError with a precise message for every violation.
        """
        from jira_reviewer.plugins import PLUGIN_REGISTRY

        if name not in PLUGIN_REGISTRY:
            raise ConfigError(f"unknown plugin: {name}")

        # Check each required attribute individually for precise error messages
        required_attrs = ["name", "description", "weight", "score"]
        for attr in required_attrs:
            if not hasattr(instance, attr):
                raise ConfigError(f"{name} missing: {attr}")

        # Validate weight type and value
        weight = getattr(instance, "weight")
        if not isinstance(weight, (int, float)):
            raise ConfigError(f"{name}.weight must be float")
        if float(weight) <= 0:
            raise ConfigError(f"{name}.weight must be > 0")
