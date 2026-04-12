"""ExamplePlugin — stub demonstrating the ScoringPlugin protocol shape.

No inheritance from ScoringPlugin required — just satisfy the interface.
This plugin is disabled by default in scorer.example.yaml.
Replace with a real implementation for actual scoring.
"""

from __future__ import annotations


class ExamplePlugin:
    """Stub plugin — demonstrates the required protocol shape without inheriting from it."""

    def __init__(self, config: dict) -> None:
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

    def score(self, ticket, context):  # type hints optional — protocol validates at runtime
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
