"""JiraClient — thin HTTP wrapper for the Jira REST API v3.

Uses httpx (already a transitive dependency via mcp[cli]).
Authentication: Basic auth with JIRA_USERNAME:JIRA_API_TOKEN.

All methods return parsed JSON dicts/lists. Pagination is handled
internally for changelog (which Jira caps at 100 per page).
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class JiraClient:
    """Read-only Jira REST API v3 client."""

    def __init__(self, base_url: str, username: str, api_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.Client(
            auth=(username, api_token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30.0,
        )

    def get_issue(self, key: str) -> dict:
        """Fetch a Jira issue by key. Returns the raw issue dict."""
        url = f"{self._base}/rest/api/3/issue/{key}"
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_changelog(self, key: str) -> list:
        """Fetch ALL changelog entries for a Jira issue (handles pagination).

        Returns a flat list of history objects, each with:
          - "created": ISO 8601 timestamp string
          - "items": list of field-change dicts with "field", "fromString", "toString"
        """
        results: list[dict] = []
        start_at = 0

        while True:
            url = f"{self._base}/rest/api/3/issue/{key}/changelog"
            resp = self._client.get(url, params={"startAt": start_at, "maxResults": 100})
            resp.raise_for_status()
            data = resp.json()

            values: list[dict] = data.get("values", [])
            results.extend(values)

            total: int = data.get("total", 0)
            fetched = start_at + len(values)
            logger.debug("get_changelog(%r): fetched %d/%d entries", key, fetched, total)

            if fetched >= total:
                break
            start_at = fetched

        return results

    def get_comments(self, key: str) -> list:
        """Fetch comments for a Jira issue. Returns list of comment dicts."""
        url = f"{self._base}/rest/api/3/issue/{key}/comment"
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json().get("comments", [])

    def get_worklogs(self, key: str) -> list:
        """Fetch worklogs for a Jira issue. Returns list of worklog dicts."""
        url = f"{self._base}/rest/api/3/issue/{key}/worklog"
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json().get("worklogs", [])

    def search(self, jql: str, fields: list) -> list:
        """Execute a JQL search. Returns list of raw issue dicts."""
        url = f"{self._base}/rest/api/3/issue/search"
        resp = self._client.post(url, json={"jql": jql, "fields": fields})
        resp.raise_for_status()
        return resp.json().get("issues", [])

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()
