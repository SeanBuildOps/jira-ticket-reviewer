"""TimeToCompletionPlugin — measures net active time from In Progress to Done.

No inheritance from ScoringPlugin required — satisfies the protocol structurally.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORING MODEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Active time (not wall-clock time)
   ─────────────────────────────────
   The plugin walks the Jira changelog to reconstruct status segments between
   the first "In Progress" and first "Done" transitions. Time spent in
   excluded_statuses (default: "In Review", "Blocked") is subtracted so that
   only periods of active development count toward the score.

   Example:
     In Progress (2h) → In Review (3h) → In Progress (1h) → Done
     Wall-clock: 6h   |   Active: 3h   |   Excluded: 3h

2. Linear decay scoring
   ─────────────────────
   Given active_hours, ideal_hours, and max_hours:

     active ≤ ideal          →  score = 1.0  (full marks)
     ideal < active < max    →  score = 1 − (active − ideal) / (max − ideal)
     active ≥ max            →  score = 0.0  (exceeded budget)

3. Story point threshold lookup
   ─────────────────────────────
   When scale_by_story_points is true, ideal_hours and max_hours are looked up
   per story point value rather than using flat config values. Thresholds are
   calibrated to the team's Fibonacci estimation guide (see reference below).
   Non-standard SP values fall back to the nearest key in the table.

   Reference: https://buildops.atlassian.net/wiki/spaces/EN/pages/2955116596/Story+Point+Guide

   Default thresholds:
     1 SP  — ideal:  1h  max:  2h   (less than 2 hours)
     2 SP  — ideal:  4h  max:  8h   (half a day)
     3 SP  — ideal:  8h  max: 16h   (up to two days)
     5 SP  — ideal: 16h  max: 32h   (few days)
     8 SP  — ideal: 32h  max: 40h   (around a week — should be split)
    13 SP  — ideal: 40h  max: 80h   (more than one week — must be split)

4. Skipped results
   ─────────────────
   The plugin returns a zero-scored skipped result (not an exception) when:
     - No changelog data is available
     - No "In Progress" transition exists
     - No "Done" transition exists after "In Progress"
     - Timestamps are anomalous (In Progress ≥ Done)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Jira Cloud default story points field. Override via config: story_points_field.
_DEFAULT_SP_FIELD = "customfield_10023"

# Default statuses whose duration is excluded from active time.
_DEFAULT_EXCLUDED_STATUSES: list[str] = ["In Review", "Blocked"]

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
        self._excluded_statuses: set[str] = set(
            config.get("excluded_statuses", _DEFAULT_EXCLUDED_STATUSES)
        )

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

        result = _compute_active_hours(changelog, self._excluded_statuses)

        if result is None:
            return self._skipped(ticket.key, "no In Progress transition",
                                 "no 'In Progress' transition found in changelog")
        if result == "no_done":
            return self._skipped(ticket.key, "no Done transition",
                                 "no 'Done' transition found in changelog")
        if result == "data_anomaly":
            return self._skipped(ticket.key, "data anomaly",
                                 "'In Progress' time is not before 'Done' time — data anomaly")

        active_hours: float = result["active_hours"]
        excluded_hours: float = result["excluded_hours"]

        # ── Linear decay scoring ─────────────────────────────────────────────
        if active_hours <= ideal_hours:
            normalized = 1.0
        elif active_hours >= max_hours:
            normalized = 0.0
        else:
            normalized = 1.0 - (active_hours - ideal_hours) / (max_hours - ideal_hours)

        normalized = max(0.0, min(1.0, normalized))

        midpoint = (ideal_hours + max_hours) / 2
        if active_hours <= ideal_hours:
            label = "Excellent — completed within ideal time"
        elif active_hours <= midpoint:
            label = "Good — completed within acceptable time"
        else:
            label = "Slow — completion time exceeds ideal"

        excluded_note = (
            f", {excluded_hours:.1f}h excluded ({', '.join(sorted(self._excluded_statuses))})"
            if excluded_hours > 0 else ""
        )
        reasoning = (
            f"Active time: {active_hours:.1f}h{excluded_note} "
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
            raw_value=active_hours,
            normalized_score=normalized,
            weight=self.weight,
            contribution=0.0,
            label=label,
            reasoning=reasoning,
            metadata={
                "active_hours": active_hours,
                "excluded_hours": excluded_hours,
                "ideal_hours": ideal_hours,
                "max_hours": max_hours,
                "story_points": story_points,
                "scale_by_story_points": self._scale_by_sp,
                "excluded_statuses": sorted(self._excluded_statuses),
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


def _compute_active_hours(
    changelog: list[dict],
    excluded_statuses: set[str],
) -> dict | None | str:
    """Compute net active hours between first 'In Progress' and first 'Done'.

    Time spent in excluded_statuses (e.g. 'In Review', 'Blocked') is subtracted.

    Returns:
        dict with 'active_hours' and 'excluded_hours' on success.
        None   if no 'In Progress' transition was found.
        'no_done'       if no 'Done' transition was found after In Progress.
        'data_anomaly'  if In Progress timestamp >= Done timestamp.
    """
    # Collect all status transitions sorted by time
    transitions: list[tuple[datetime, str]] = []
    for entry in changelog:
        for item in entry.get("items", []):
            if item.get("field") != "status":
                continue
            try:
                ts = _parse_timestamp(entry["created"])
                transitions.append((ts, item.get("toString", "")))
            except (ValueError, TypeError, KeyError):
                continue

    transitions.sort(key=lambda x: x[0])

    # Find the first In Progress transition
    start_idx: int | None = None
    for i, (_, status) in enumerate(transitions):
        if status == "In Progress":
            start_idx = i
            break

    if start_idx is None:
        return None

    # Find the first Done transition after In Progress
    end_idx: int | None = None
    for i in range(start_idx + 1, len(transitions)):
        if transitions[i][1] == "Done":
            end_idx = i
            break

    if end_idx is None:
        return "no_done"

    start_ts = transitions[start_idx][0]
    end_ts = transitions[end_idx][0]

    if start_ts >= end_ts:
        return "data_anomaly"

    # Walk segments between start and end, accumulating active and excluded time
    active_seconds = 0.0
    excluded_seconds = 0.0
    current_status = "In Progress"  # status after start_idx transition

    for i in range(start_idx, end_idx):
        seg_start, seg_status = transitions[i]
        seg_end, _ = transitions[i + 1]
        duration = (seg_end - seg_start).total_seconds()

        if seg_status in excluded_statuses:
            excluded_seconds += duration
        else:
            active_seconds += duration

        current_status = seg_status  # noqa: F841 (kept for readability)

    return {
        "active_hours": active_seconds / 3600.0,
        "excluded_hours": excluded_seconds / 3600.0,
    }


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
