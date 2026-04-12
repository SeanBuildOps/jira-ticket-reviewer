"""jira_reviewer: Jira Agent Reviewer MCP Server."""

from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from this __init__.py).
# Runs once on first import of jira_reviewer — covers all entry points (server, CLI, tests).
load_dotenv(Path(__file__).resolve().parents[3] / ".env")
