"""Jira Agent Reviewer MCP Server — entry point."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from jira_reviewer.tools.list_plugins import list_plugins as _list_plugins
from jira_reviewer.tools.score_tickets import score_tickets as _score_tickets

logger = logging.getLogger(__name__)

mcp = FastMCP("Jira Agent Reviewer")


# ── Tool: list_plugins ────────────────────────────────────────────────────────
@mcp.tool()
def list_plugins() -> str:
    """Return all configured plugins with name, version, author, description and weight."""
    return _list_plugins()


# ── Tool: score_tickets ───────────────────────────────────────────────────────
@mcp.tool()
def score_tickets(tickets: list[dict]) -> str:
    """Score completed Jira tickets. Each dict needs 'key' and 'fields.status.name'."""
    return _score_tickets(tickets)


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
