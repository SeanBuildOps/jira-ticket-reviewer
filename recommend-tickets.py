#!/usr/bin/env python3
"""
recommend-tickets: Recommend Jira tickets based on priority and domain expertise.

Usage:
    python3 recommend-tickets.py N [--epic EPIC_KEY] [--refresh]

Arguments:
    N           Number of tickets to recommend (required)
    --epic      Epic key (default: ASSETS-2678)
    --refresh   Force refresh cached data (requires manual cache update)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "config" / "expertise.json"
CACHE_DIR = SCRIPT_DIR / "cache"


def load_config():
    """Load configuration from expertise.json"""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_cached_data(filename):
    """Load cached JSON data"""
    cache_path = CACHE_DIR / filename
    if not cache_path.exists():
        print(f"Error: Cache file not found: {cache_path}")
        print("Run 'recommend-tickets.py --refresh' to update cache via Claude Code")
        sys.exit(1)

    with open(cache_path) as f:
        return json.load(f)


def calculate_expertise_score(summary, domains):
    """Calculate expertise match score based on domain keywords"""
    summary_lower = summary.lower()
    matched_domains = []

    for domain, keywords in domains.items():
        for keyword in keywords:
            if keyword.lower() in summary_lower:
                matched_domains.append(domain)
                break

    return len(matched_domains), matched_domains


def calculate_priority_score(priority):
    """Convert priority to numeric score"""
    scores = {"Highest": 4, "High": 3, "Medium": 2, "Low": 1, "Lowest": 0}
    return scores.get(priority, 1)


def score_tickets(epic_data, config):
    """Score all unassigned To Do tickets"""
    domains = config["domains"]
    scored_tickets = []

    for ticket in epic_data.get("issues", {}).get("nodes", []):
        fields = ticket.get("fields", {})
        status = fields.get("status", {}).get("name", "")
        assignee = fields.get("assignee")

        # Filter: only unassigned "To Do" tickets
        if status != "To Do" or assignee is not None:
            continue

        key = ticket.get("key", "")
        summary = fields.get("summary", "")
        priority = fields.get("priority", {}).get("name", "Medium")

        # Calculate scores
        priority_score = calculate_priority_score(priority)
        expertise_score, matched_domains = calculate_expertise_score(summary, domains)

        # Combined score: priority + (expertise * 2)
        combined_score = priority_score + (expertise_score * 2)

        scored_tickets.append({
            "key": key,
            "summary": summary,
            "priority": priority,
            "priority_score": priority_score,
            "expertise_score": expertise_score,
            "matched_domains": matched_domains,
            "combined_score": combined_score,
            "url": f"https://buildops.atlassian.net/browse/{key}"
        })

    # Sort by combined score (descending), then priority score
    scored_tickets.sort(key=lambda x: (-x["combined_score"], -x["priority_score"]))

    return scored_tickets


def print_recommendations(tickets, n, epic_summary=""):
    """Print top N recommended tickets"""
    print()
    print("=" * 80)
    print(f" TOP {n} RECOMMENDED TICKETS — {epic_summary}" if epic_summary else f" TOP {n} RECOMMENDED TICKETS")
    print("=" * 80)

    for i, ticket in enumerate(tickets[:n], 1):
        print()
        print(f"  {i}. {ticket['key']}")
        print(f"     Score: {ticket['combined_score']} (Priority: {ticket['priority_score']}, Expertise: {ticket['expertise_score']})")
        print(f"     Priority: {ticket['priority']}")
        if ticket['matched_domains']:
            print(f"     Your Domains: {', '.join(ticket['matched_domains'])}")
        print(f"     Summary: {ticket['summary'][:70]}{'...' if len(ticket['summary']) > 70 else ''}")
        print(f"     URL: {ticket['url']}")

    print()
    print("=" * 80)
    print(f" Total unassigned To Do tickets: {len(tickets)}")
    print("=" * 80)
    print()


def show_refresh_instructions():
    """Show instructions for refreshing cache"""
    print("""
To refresh cache, run these queries in Claude Code:

1. Epic tickets:
   Use Atlassian MCP: searchJiraIssuesUsingJql
   JQL: "Epic Link" = ASSETS-2678 ORDER BY priority DESC
   Save result to: ~/scripts/jira/cache/epic_tickets.json

2. User history (optional, for dynamic expertise):
   JQL: project = Assets AND assignee = currentUser()
   Save result to: ~/scripts/jira/cache/user_history.json
""")


def main():
    parser = argparse.ArgumentParser(
        description="Recommend Jira tickets based on priority and domain expertise"
    )
    parser.add_argument("n", type=int, nargs="?", help="Number of tickets to recommend")
    parser.add_argument("--epic", default=None, help="Epic key (default from config)")
    parser.add_argument("--refresh", action="store_true", help="Show refresh instructions")

    args = parser.parse_args()

    if args.refresh:
        show_refresh_instructions()
        return

    if args.n is None:
        parser.print_help()
        sys.exit(1)

    if args.n < 1:
        print("Error: N must be at least 1")
        sys.exit(1)

    # Load configuration
    config = load_config()

    # Resolve epic key
    epic_key = args.epic or config.get("default_epic", "ASSETS-2678")

    # Load cached epic data
    cache_filename = f"epic_tickets_{epic_key}.json" if args.epic else "epic_tickets.json"
    epic_data = load_cached_data(cache_filename)

    # Extract epic summary from cached data
    epic_summary = epic_data.get("summary", epic_key)

    # Score tickets
    scored_tickets = score_tickets(epic_data, config)

    if not scored_tickets:
        print("No unassigned 'To Do' tickets found in epic.")
        return

    # Print recommendations
    print_recommendations(scored_tickets, args.n, epic_summary)


if __name__ == "__main__":
    main()
