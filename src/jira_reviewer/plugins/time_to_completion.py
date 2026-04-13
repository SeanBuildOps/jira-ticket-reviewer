"""TimeToCompletionPlugin — measures elapsed time from In Progress to Done.

No inheritance from ScoringPlugin required — satisfies the protocol structurally.

Story point scaling:
  When scale_by_story_points is true, the plugin looks up ideal_hours / max_hours
  from story_points_thresholds using the ticket's story point count.

  Threshold lookup:
    - Exact match used when the SP value is in the table.
    - Nearest key used when an exact match is not found.
    - Falls back to top-level ideal_hours / max_hours when story points are
      missing, zero, or the thresholds table is empty.

  Default thresholds are derived from the standard Fibonacci story point cheat
  sheet (1=<2h, 2=half day, 3=2 days, 5=few days, 8=~1 week, 13=>1 week).
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Jira Cloud default story points field. Override via config: story_points_field.
_DEFAULT_SP_FIELD = "customfield_10023"

# Default thresholds derived from the Fibonacci story point estimation cheat sheet.
# Keys are story point values; values are (ideal_hours, max_hours) tuples.
_DEFAULT_THRESHOLDS: dict[int, tuple[float, float]] = {
    1:  (1.0,  2.0),   # < 2 hours
    2:  (4.0,  8.0),   # half a day
    3:  (8.0,  16.0),  # up to two days
    5:  (16.0, 32.0),  # few days
    8:  (32.0, 40.0),  # around a week (should be split)
    13: (40.0, 80.0),  # more than one week (must be split)
}


class TimeToCompletionPlugin:
    """Measures elapsed time from In Progress to Done, optionally scaled by story points."""

    name = "time_to_completion"
    version = "1.2.0"
    author = "BuildOps Platform Team"
    description = (
        "Measures elapsed time from In Progress to Done status transition. "
        "Optionally maps story points to Fibonacci-calibrated time thresholds."
    )

    def __init__(self, config: dict) -> None:
        self._config = config
        self._ideal_hours: float = float(config.get("ideal_hours", 4.0))
        self._max_hours: float = float(config.get("max_hours", 24.0))
        self._scale_by_sp: bool = bool(config.get("scale_by_story_points", False))
        self._sp_field: str = config.get("story_points_field", _DEFAULT_SP_FIELD)

        # Build threshold table: config overrides default, then validate each entry.
        raw_thresholds: dict = config.get("story_points_thresholds", _DEFAULT_THRESHOLDS)
        self._sp_thresholds: dict[int, tuple[float, float]] = {}
        for sp_key, bounds in raw_thresholds.items():
            if isinstance(bounds, dict):
                ideal = float(bounds["ideal_hours"])
                max_h = float(bounds["max_hours"])
            else:
                ideal, max_h = float(bounds[0]), float(bounds[1])
            if max_h <= ideal:
                raise ValueError(
                    f"time_to_completion: story_points_thresholds[{sp_key}] — "
                    f"max_hours ({max_h}) must be > ideal_hours ({ideal})"
                )
            self._sp_thresholds[int(sp_key)] = (ideal, max_h)

        if self._max_hours <= self._ideal_hours:
            raise ValueError(
                f"time_to_completion: max_hours ({self._max_hours}) must be greater than "
                f"ideal_hours ({self._ideal_hours})"
            )

    @property
    def weight(self) -> float:
        return float(self._config.get("weight", 1.0))

    def score(self, ticket, context):
        from jira_reviewer.core.models import PluginResult

        ideal_hours = self._ideal_hours
        max_hours = self._max_hours
        sp_note = ""

        # ── Story point threshold lookup ─────────────────────────────────────
        if self._scale_by_sp:
            story_points = _extract_story_points(context.get_issue(ticket.key), self._sp_field)
            if story_points and story_points > 0 and self._sp_thresholds:
                ideal_hours, max_hours = _lookup_thresholds(story_points, self._sp_thresholds)
                sp_note = f" ({int(story_points)} SP)"
                logger.debug(
                    "time_to_completion: %s — %.0f SP → ideal=%.1fh max=%.1fh",
                    ticket.key, story_points, ideal_hours, max_hours,
                )
            else:
                sp_note = " (no story points — using default thresholds)"
                logger.warning(
                    "time_to_completion: %s — story points missing or zero, using default thresholds",
                    ticket.key,
                )

        # ── Changelog traversal ──────────────────────────────────────────────
        changelog = context.get_changelog(ticket.key)

        if not changelog:
            return self._skipped(ticket.key, "no changelog data", "no changelog data available")

        in_progress_time: datetime | None = None
        done_time: datetime | None = None

        for entry in changelog:
            for item in entry.get("items", []):
                if item.get("field") != "status":
                    continue
                to_string = item.get("toString", "")
                if to_string == "In Progress" and in_progress_time is None:
                    try:
                        in_progress_time = _parse_timestamp(entry["created"])
                    except (ValueError, TypeError, KeyError):
                        continue
                elif to_string == "Done" and done_time is None:
                    try:
                        done_time = _parse_timestamp(entry["created"])
                    except (ValueError, TypeError, KeyError):
                        continue

        if in_progress_time is None:
            return self._skipped(ticket.key, "no In Progress transition",
                                 "no 'In Progress' transition found in changelog")

        if done_time is None:
            return self._skipped(ticket.key, "no Done transition",
                                 "no 'Done' transition found in changelog")

        if in_progress_time >= done_time:
            return self._skipped(
                ticket.key,
                "data anomaly",
                f"'In Progress' time ({in_progress_time.isoformat()}) is not before "
                f"'Done' time ({done_time.isoformat()}) — data anomaly",
            )

        # ── Linear decay scoring ─────────────────────────────────────────────
        elapsed_hours = (done_time - in_progress_time).total_seconds() / 3600.0

        if elapsed_hours <= ideal_hours:
            normalized = 1.0
        elif elapsed_hours >= max_hours:
            normalized = 0.0
        else:
            normalized = 1.0 - (elapsed_hours - ideal_hours) / (max_hours - ideal_hours)

        normalized = max(0.0, min(1.0, normalized))

        midpoint = (ideal_hours + max_hours) / 2
        if elapsed_hours <= ideal_hours:
            label = "Excellent — completed within ideal time"
        elif elapsed_hours <= midpoint:
            label = "Good — completed within acceptable time"
        else:
            label = "Slow — completion time exceeds ideal"

        reasoning = (
            f"Completed in {elapsed_hours:.1f}h "
            f"(ideal: {ideal_hours:.1f}h, max: {max_hours:.1f}h{sp_note}). "
            f"Score: {normalized:.2f}."
        )

        story_points = (
            _extract_story_points(context.get_issue(ticket.key), self._sp_field)
            if self._scale_by_sp else None
        )

        return PluginResult(
            plugin_name=self.name,
            plugin_version=self.version,
            plugin_author=self.author,
            plugin_description=self.description,
            raw_value=elapsed_hours,
            normalized_score=normalized,
            weight=self.weight,
            contribution=0.0,
            label=label,
            reasoning=reasoning,
            metadata={
                "elapsed_hours": elapsed_hours,
                "ideal_hours": ideal_hours,
                "max_hours": max_hours,
                "story_points": story_points,
                "scale_by_story_points": self._scale_by_sp,
            },
        )

    def _skipped(self, key: str, reason: str, detail: str) -> "PluginResult":
        from jira_reviewer.core.models import PluginResult
        return PluginResult(
            plugin_name=self.name,
            plugin_version=self.version,
            plugin_author=self.author,
            plugin_description=self.description,
            raw_value=None,
            normalized_score=0.0,
            weight=self.weight,
            contribution=0.0,
            label="No score — " + reason,
            reasoning=f"Could not score {key}: {detail}.",
            metadata={"skipped": True, "reason": reason},
        )


def _lookup_thresholds(story_points: float, table: dict[int, tuple[float, float]]) -> tuple[float, float]:
    """Return (ideal_hours, max_hours) for the given story points.

    Uses an exact match when available; otherwise picks the nearest key in the table.
    """
    sp_int = int(story_points)
    if sp_int in table:
        return table[sp_int]

    # Nearest-key fallback
    nearest = min(table.keys(), key=lambda k: abs(k - sp_int))
    logger.debug("time_to_completion: SP=%d not in thresholds table — using nearest key %d", sp_int, nearest)
    return table[nearest]


def _extract_story_points(issue: dict, field: str) -> float | None:
    """Extract story points from a Jira issue dict.

    Tries the configured field first, then the canonical 'story_points' key.
    Returns None if the value is missing, zero, or not numeric.
    """
    fields = issue.get("fields", {})
    value = fields.get(field) or fields.get("story_points")
    if value is None:
        return None
    try:
        sp = float(value)
        return sp if sp > 0 else None
    except (TypeError, ValueError):
        return None


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a timezone-aware datetime.

    Handles Jira's format: "2024-01-15T10:00:00.000+0000"
    Uses only stdlib — no dateutil dependency.
    """
    if len(ts) > 5 and ts[-5] in ("+", "-") and ":" not in ts[-5:]:
        ts = ts[:-2] + ":" + ts[-2:]
    return datetime.fromisoformat(ts)
