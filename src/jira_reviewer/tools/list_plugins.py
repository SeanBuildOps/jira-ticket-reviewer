"""list_plugins tool — returns all configured plugins as a formatted string."""

from __future__ import annotations

from jira_reviewer.tools._helpers import get_engine


def list_plugins() -> str:
    """Return all configured plugins as a formatted string."""
    engine = get_engine()
    plugins = engine.plugins

    if not plugins:
        return "No plugins configured."

    lines = []
    for p in plugins:
        version = getattr(p, "version", "0.0.0")
        description = getattr(p, "description", "(no description)")
        lines.append(
            f"- {p.name} v{version} (weight: {p.weight}) — {description}"
        )

    return "\n".join(lines)
