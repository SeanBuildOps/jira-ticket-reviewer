"""score_tickets tool — scores a list of raw Jira issue dicts."""

from __future__ import annotations

import logging

from jira_reviewer.tools._helpers import get_engine, make_ticket

logger = logging.getLogger(__name__)


def score_tickets(tickets: list[dict]) -> str:
    """Score a list of raw Jira issue dicts. Returns formatted results."""
    engine = get_engine()

    ticket_objects = []
    errors = []
    for raw in tickets:
        try:
            ticket_objects.append(make_ticket(raw))
        except (KeyError, TypeError) as exc:
            errors.append(f"Skipping malformed ticket {raw.get('key', '?')}: {exc}")
            logger.warning("make_ticket failed for %r: %s", raw, exc)

    scores = engine.score_tickets(ticket_objects)

    lines = []
    for ts in scores:
        lines.append(f"{ts.ticket.key}  combined_score={ts.combined_score:.4f}")
        for plugin_name, pr in ts.plugin_results.items():
            contribution_pct = round(pr.contribution * 100, 1)
            lines.append(
                f"  [{plugin_name}] score={pr.normalized_score:.4f} "
                f"contribution={contribution_pct}% label={pr.label!r}"
            )
            lines.append(f"    {pr.reasoning}")
        lines.append("")

    if errors:
        lines.append("Errors:")
        for err in errors:
            lines.append(f"  {err}")

    return "\n".join(lines).rstrip()
