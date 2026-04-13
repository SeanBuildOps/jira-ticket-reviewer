"""score_tickets tool — accepts ticket keys, fetches from Jira, scores them."""

from __future__ import annotations

import logging

from jira_reviewer.tools._helpers import get_engine, make_ticket

logger = logging.getLogger(__name__)


def score_tickets(ticket_keys: list[str]) -> str:
    """Fetch each ticket from Jira by key, then score with all loaded plugins.

    Args:
        ticket_keys: Jira issue keys, e.g. ["LE-1288", "LE-1290"]

    Returns:
        Human-readable scoring report as a string.
    """
    engine = get_engine()
    jira = engine._jira

    ticket_objects = []
    errors = []

    for key in ticket_keys:
        key = key.strip().upper()
        if not key:
            continue
        try:
            if jira is None:
                errors.append(f"{key}: Jira client not configured — set JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN")
                continue
            issue = jira.get_issue(key)
            ticket_objects.append(make_ticket(issue))
        except Exception as exc:
            errors.append(f"{key}: failed to fetch from Jira — {exc}")
            logger.warning("get_issue failed for %r: %s", key, exc)

    if not ticket_objects and errors:
        return "No tickets could be scored.\n\nErrors:\n" + "\n".join(f"  {e}" for e in errors)

    scores = engine.score_tickets(ticket_objects)

    lines = []
    for ts in scores:
        lines.append(f"{ts.ticket.key}  combined_score={ts.combined_score:.4f}  status={ts.ticket.status!r}")
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
