"""Jira Agent Reviewer MCP Server — entry point."""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from jira_reviewer.tools._helpers import get_engine, make_ticket

logger = logging.getLogger(__name__)

mcp = FastMCP("Jira Agent Reviewer")


# ── Tool: list_plugins ────────────────────────────────────────────────────────
@mcp.tool()
def list_plugins() -> str:
    """Return all configured plugins with name, version, author, description, weight.

    Lists only enabled plugins (those loaded by the engine from scorer.yaml).
    """
    engine = get_engine()
    plugins = engine._plugins

    if not plugins:
        return "No plugins configured. Edit config/scorer.yaml to enable plugins."

    rows = []
    for p in plugins:
        version = getattr(p, "version", "0.0.0")
        author = getattr(p, "author", "unknown")
        rows.append({
            "name": p.name,
            "version": version,
            "author": author,
            "description": p.description,
            "weight": p.weight,
        })

    return json.dumps(rows, indent=2)


# ── Tool: score_tickets ───────────────────────────────────────────────────────
@mcp.tool()
def score_tickets(tickets: list[dict]) -> str:
    """Score completed Jira tickets. Each dict needs at least 'key' and 'fields.status.name'.

    Accepts raw Jira issue JSON (as returned by the Jira REST API).
    Returns a ranked list of ticket scores with per-plugin breakdowns.

    Args:
        tickets: List of raw Jira issue dicts, each with at least:
                 {"key": "PROJ-123", "fields": {"status": {"name": "Done"}}}
    """
    engine = get_engine()

    ticket_objects = []
    errors = []
    for raw in tickets:
        try:
            ticket_objects.append(make_ticket(raw))
        except (KeyError, TypeError) as exc:
            errors.append(f"Skipping malformed ticket {raw.get('key', '?')}: {exc}")
            logger.warning("make_ticket failed for %r: %s", raw, exc)

    results = engine.score_tickets(ticket_objects)

    output = []
    for ts in results:
        row: dict = {
            "key": ts.ticket.key,
            "status": ts.ticket.status,
            "combined_score": round(ts.combined_score, 4),
            "plugins": {},
        }
        for plugin_name, pr in ts.plugin_results.items():
            row["plugins"][plugin_name] = {
                "normalized_score": round(pr.normalized_score, 4),
                "weight": pr.weight,
                "contribution": round(pr.contribution, 4),
                "label": pr.label,
                "reasoning": pr.reasoning,
                "raw_value": pr.raw_value,
                "version": pr.plugin_version,
                "author": pr.plugin_author,
            }
        output.append(row)

    response: dict = {"scores": output}
    if errors:
        response["errors"] = errors

    return json.dumps(response, indent=2)


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
