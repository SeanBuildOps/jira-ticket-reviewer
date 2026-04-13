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

# Project root is three levels up from this file:
# src/jira_reviewer/tools/_helpers.py -> tools/ -> jira_reviewer/ -> src/ -> project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
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


def _build_jira_client():
    """Build a JiraClient from environment variables, or return None if not configured.

    Reads JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN from the environment.
    Returns None (with a warning) if any variable is missing.
    """
    import os

    from jira_reviewer.core.jira_client import JiraClient

    url = os.environ.get("JIRA_URL", "").strip()
    username = os.environ.get("JIRA_USERNAME", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()

    if not url or not username or not token:
        missing = [k for k, v in [("JIRA_URL", url), ("JIRA_USERNAME", username), ("JIRA_API_TOKEN", token)] if not v]
        logger.warning("Jira client not configured — missing env vars: %s. Plugins that fetch Jira data will skip.", missing)
        return None

    logger.debug("Jira client configured for %s", url)
    return JiraClient(base_url=url, username=username, api_token=token)


def get_engine() -> "ScoringEngine":
    """Return the singleton ScoringEngine, instantiating it on first call."""
    global _engine
    if _engine is None:
        from jira_reviewer.core.engine import ScoringEngine

        config = load_config()
        jira_client = _build_jira_client()
        _engine = ScoringEngine(config, jira_client=jira_client)
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
