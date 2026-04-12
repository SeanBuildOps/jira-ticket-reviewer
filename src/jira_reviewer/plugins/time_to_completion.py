"""TimeToCompletionPlugin — measures elapsed time from In Progress to Done.

No inheritance from ScoringPlugin required — satisfies the protocol structurally.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TimeToCompletionPlugin:
    """Measures elapsed time from In Progress to Done status transition."""

    name = "time_to_completion"
    version = "1.0.0"
    author = "BuildOps Platform Team"
    description = "Measures elapsed time from In Progress to Done status transition."

    def __init__(self, config: dict) -> None:
        self._config = config
        self._ideal_hours: float = config.get("ideal_hours", 4.0)
        self._max_hours: float = config.get("max_hours", 24.0)
        if self._max_hours <= self._ideal_hours:
            raise ValueError(
                f"time_to_completion: max_hours ({self._max_hours}) must be greater than ideal_hours ({self._ideal_hours})"
            )

    @property
    def weight(self) -> float:
        return self._config.get("weight", 1.0)

    def score(self, ticket, context):
        from jira_reviewer.core.models import PluginResult

        ideal_hours: float = self._config.get("ideal_hours", 4.0)
        max_hours: float = self._config.get("max_hours", 24.0)

        changelog = context.get_changelog(ticket.key)

        # Edge case: no changelog data
        if not changelog:
            return PluginResult(
                plugin_name=self.name,
                plugin_description=self.description,
                raw_value=None,
                normalized_score=0.0,
                weight=self.weight,
                contribution=0.0,
                label="No score — missing data",
                reasoning=f"Could not score: no changelog data available for {ticket.key}.",
                plugin_version=self.version,
                plugin_author=self.author,
                metadata={"skipped": True, "reason": "no changelog data"},
            )

        in_progress_time: datetime | None = None
        done_time: datetime | None = None

        for entry in changelog:
            items = entry.get("items", [])
            for item in items:
                if item.get("field") != "status":
                    continue
                to_string = item.get("toString", "")
                if to_string == "In Progress" and in_progress_time is None:
                    try:
                        in_progress_time = _parse_timestamp(entry["created"])
                    except (ValueError, TypeError, KeyError):
                        continue  # skip malformed changelog entries
                elif to_string == "Done" and done_time is None:
                    try:
                        done_time = _parse_timestamp(entry["created"])
                    except (ValueError, TypeError, KeyError):
                        continue  # skip malformed changelog entries

        if in_progress_time is None:
            return PluginResult(
                plugin_name=self.name,
                plugin_description=self.description,
                raw_value=None,
                normalized_score=0.0,
                weight=self.weight,
                contribution=0.0,
                label="No score — missing transition",
                reasoning="Could not score: no 'In Progress' transition found in changelog.",
                plugin_version=self.version,
                plugin_author=self.author,
                metadata={"skipped": True, "reason": "no In Progress transition"},
            )

        if done_time is None:
            return PluginResult(
                plugin_name=self.name,
                plugin_description=self.description,
                raw_value=None,
                normalized_score=0.0,
                weight=self.weight,
                contribution=0.0,
                label="No score — missing transition",
                reasoning="Could not score: no 'Done' transition found in changelog.",
                plugin_version=self.version,
                plugin_author=self.author,
                metadata={"skipped": True, "reason": "no Done transition"},
            )

        if in_progress_time >= done_time:
            return PluginResult(
                plugin_name=self.name,
                plugin_description=self.description,
                raw_value=None,
                normalized_score=0.0,
                weight=self.weight,
                contribution=0.0,
                label="No score — data anomaly",
                reasoning=(
                    f"Could not score: 'In Progress' time ({in_progress_time.isoformat()}) "
                    f"is not before 'Done' time ({done_time.isoformat()}) — data anomaly."
                ),
                plugin_version=self.version,
                plugin_author=self.author,
                metadata={"skipped": True, "reason": "in_progress_time >= done_time"},
            )

        elapsed_hours = (done_time - in_progress_time).total_seconds() / 3600.0

        # Linear decay normalization
        if elapsed_hours <= ideal_hours:
            normalized = 1.0
        elif elapsed_hours >= max_hours:
            normalized = 0.0
        else:
            normalized = 1.0 - (elapsed_hours - ideal_hours) / (max_hours - ideal_hours)

        # Clamp to [0.0, 1.0]
        normalized = max(0.0, min(1.0, normalized))

        if elapsed_hours <= ideal_hours:
            label = "Excellent — completed within ideal time"
        elif elapsed_hours <= (ideal_hours + max_hours) / 2:
            label = "Good — completed within acceptable time"
        else:
            label = "Slow — completion time exceeds ideal"

        reasoning = (
            f"Completed in {elapsed_hours:.1f}h (ideal: {ideal_hours}h, max: {max_hours}h). "
            f"Score: {normalized:.2f}."
        )

        return PluginResult(
            plugin_name=self.name,
            plugin_description=self.description,
            raw_value=elapsed_hours,
            normalized_score=normalized,
            weight=self.weight,
            contribution=0.0,  # set by engine aggregation
            label=label,
            reasoning=reasoning,
            plugin_version=self.version,
            plugin_author=self.author,
            metadata={"elapsed_hours": elapsed_hours, "ideal_hours": ideal_hours, "max_hours": max_hours},
        )


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime.

    Handles Jira's format: "2024-01-15T10:00:00.000+0000"
    Uses only stdlib — no dateutil dependency.
    """
    # Normalize "+0000" to "+00:00" for Python's %z
    if len(ts) > 5 and ts[-5] in ("+", "-") and ":" not in ts[-5:]:
        ts = ts[:-2] + ":" + ts[-2:]
    return datetime.fromisoformat(ts)
