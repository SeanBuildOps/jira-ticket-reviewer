"""jira_reviewer: Jira Agent Reviewer MCP Server."""

from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (three levels up from this file).
# parents[0] = src/jira_reviewer/, parents[1] = src/, parents[2] = project root
# Runs once on first import of jira_reviewer — covers all entry points (server, CLI, tests).
load_dotenv(Path(__file__).resolve().parents[2] / ".env")
