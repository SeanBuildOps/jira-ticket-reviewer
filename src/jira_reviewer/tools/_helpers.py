"""Helper utilities for MCP tool implementations.

Provides:
- load_config(): loads scorer.yaml (falls back to scorer.example.yaml)
- get_engine(): singleton ScoringEngine
- make_ticket(): extracts Ticket from raw Jira issue JSON
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jira_reviewer.core.engine import ScoringEngine
    from jira_reviewer.core.models import Ticket

logger = logging.getLogger(__name__)

_engine: "ScoringEngine | None" = None

# Project root is four levels up from this file:
# src/jira_reviewer/tools/_helpers.py -> tools -> jira_reviewer -> src -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_CONFIG_DIR = _PROJECT_ROOT / "config"


def load_config() -> dict:
    """Load scorer.yaml from config/. Falls back to scorer.example.yaml if not found.

    Returns an empty dict with a "plugins" key if neither file exists.
    """
    import yaml

    user_config = _CONFIG_DIR / "scorer.yaml"
    example_config = _CONFIG_DIR / "scorer.example.yaml"

    if user_config.exists():
        logger.debug("Loading config from %s", user_config)
        with user_config.open() as f:
            return yaml.safe_load(f) or {}

    if example_config.exists():
        logger.debug("scorer.yaml not found — falling back to scorer.example.yaml")
        with example_config.open() as f:
            return yaml.safe_load(f) or {}

    logger.warning("No scorer config found at %s — using empty config", _CONFIG_DIR)
    return {"plugins": []}


def get_engine() -> "ScoringEngine":
    """Return the singleton ScoringEngine, instantiating it on first call."""
    global _engine
    if _engine is None:
        from jira_reviewer.core.engine import ScoringEngine

        config = load_config()
        _engine = ScoringEngine(config)
    return _engine


def make_ticket(jira_issue: dict) -> "Ticket":
    """Extract a Ticket from raw Jira issue JSON.

    Expects:
        jira_issue["key"]                     — e.g. "PROJ-123"
        jira_issue["fields"]["status"]["name"] — e.g. "Done"
    """
    from jira_reviewer.core.models import Ticket

    return Ticket(
        key=jira_issue["key"],
        status=jira_issue["fields"]["status"]["name"],
    )
