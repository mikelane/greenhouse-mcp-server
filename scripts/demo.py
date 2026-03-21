#!/usr/bin/env python3
"""Demo: greenhouse-mcp tools with realistic recruiting data.

Runs all 5 implemented tools against the FakeGreenhouseClient
and prints formatted output showing what a recruiter would see.
"""

from __future__ import annotations

import asyncio

# Force the fake client module to be imported so dioxide discovers the adapter
import greenhouse_mcp.fake_client as _  # noqa: F401
from datetime import UTC, datetime

from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.attention import needs_attention
from greenhouse_mcp.tools.candidate import candidate_dossier
from greenhouse_mcp.tools.pipeline import pipeline_health
from greenhouse_mcp.tools.search import search_talent
from greenhouse_mcp.tools.velocity import hiring_velocity

BLUE = "\033[1;34m"
GREEN = "\033[1;32m"
CYAN = "\033[1;36m"
YELLOW = "\033[1;33m"
RED = "\033[1;31m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _header(title: str) -> None:
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}  {title}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def _subheader(title: str) -> None:
    print(f"\n  {CYAN}{title}{RESET}")
    print(f"  {DIM}{'-' * 50}{RESET}")


def _kv(key: str, value: object, indent: int = 4) -> None:
    pad = " " * indent
    print(f"{pad}{DIM}{key}:{RESET} {value}")


def _severity_color(severity: str) -> str:
    if severity == "HIGH":
        return RED
    if severity == "MEDIUM":
        return YELLOW
    return DIM


async def demo_pipeline(client: FakeGreenhouseClient) -> None:
    """Demo 1: Where are things stuck for the Senior SWE role?"""
    _header("pipeline_health: Where are things stuck?")
    print(f"  {DIM}Recruiter asks:{RESET} {BOLD}Show me the Senior SWE pipeline{RESET}\n")

    result = await pipeline_health(job_id=1001, client=client)

    _kv("Job", f"{result['job_name']} (ID: {result['job_id']})")
    _kv("Total active candidates", result["total_active"])

    _subheader("Stages")
    for stage in result["stages"]:
        sev = stage.get("severity") or "NONE"
        color = _severity_color(sev)
        bottleneck = f" {RED}BOTTLENECK{RESET}" if stage.get("is_bottleneck") else ""
        avg_days = stage.get("avg_days_since_activity", 0)
        print(
            f"    {stage['stage_name']:30s}  "
            f"{stage['count']:2d} candidates  "
            f"{stage['share']:.0%} share  "
            f"avg {avg_days:.0f}d idle  "
            f"{color}{sev:6s}{RESET}{bottleneck}"
        )

    if result["bottlenecks"]:
        print(f"\n  {RED}Bottlenecks: {', '.join(result['bottlenecks'])}{RESET}")
    else:
        print(f"\n  {GREEN}No bottlenecks detected{RESET}")


async def demo_candidate(client: FakeGreenhouseClient) -> None:
    """Demo 2: Tell me everything about Maria Chen."""
    _header("candidate_dossier: Tell me everything about this person")
    print(f"  {DIM}Recruiter asks:{RESET} {BOLD}Pull up Maria Chen's file{RESET}\n")

    # Find Maria Chen's candidate ID
    candidates = await client.get_candidates()
    maria = next(c for c in candidates if "Maria" in c.get("first_name", ""))

    result = await candidate_dossier(candidate_id=maria["id"], client=client)

    summary = result["summary"]
    _kv("Name", summary["name"])
    _kv("Status", summary["overall_status"])
    _kv("Active applications", summary["active_application_count"])
    _kv("Pending offers", "Yes" if summary["has_pending_offers"] else "No")

    for app in result["applications"]:
        _subheader(f"Application: {app['job_name']}")
        _kv("Status", app["status"], indent=6)
        _kv("Stage", app.get("current_stage", "N/A"), indent=6)
        _kv("Applied", app.get("applied_at", "N/A"), indent=6)

        if app.get("scorecards"):
            print(f"      {DIM}Scorecards:{RESET}")
            for sc in app["scorecards"]:
                rec = sc.get("overall_recommendation", "pending")
                submitted = "submitted" if sc.get("submitted_at") else "DRAFT"
                print(f"        {sc.get('interview', 'Interview')}: {rec} ({submitted})")

        if app.get("offers"):
            print(f"      {DIM}Offers:{RESET}")
            for offer in app["offers"]:
                print(f"        Status: {offer.get('status', 'unknown')}")

    feed = result.get("activity_feed", {})
    total = feed.get("total_notes", 0) + feed.get("total_emails", 0) + feed.get("total_activities", 0)
    if total:
        _subheader(f"Activity Feed ({total} items)")
        for note in feed.get("recent_notes", [])[:3]:
            body = note.get("body", "")[:80]
            print(f"      {DIM}Note:{RESET} {body}...")


async def demo_attention(client: FakeGreenhouseClient) -> None:
    """Demo 3: What needs my attention?"""
    _header("needs_attention: What's falling through the cracks?")
    print(f"  {DIM}Recruiter asks:{RESET} {BOLD}What needs my attention right now?{RESET}\n")

    result = await needs_attention(client=client, days_stale=7)

    summary = result["summary"]
    _kv("Total action items", result["total_items"])
    print()
    _kv("Stuck applications", summary.get("stuck_applications", 0))
    _kv("Missing scorecards", summary.get("missing_scorecards", 0))
    _kv("Pending offers", summary.get("pending_offers", 0))
    _kv("No activity", summary.get("no_activity", 0))

    _subheader("Priority Action Items")
    for item in result["items"][:8]:
        priority = item.get("priority_score", 0)
        item_type = item["type"].replace("_", " ").title()

        if priority >= 0.7:  # noqa: PLR2004
            color = RED
        elif priority >= 0.4:  # noqa: PLR2004
            color = YELLOW
        else:
            color = DIM

        print(
            f"    {color}[{priority:.2f}]{RESET}  "
            f"{item_type:25s}  "
            f"{item.get('candidate_name', 'Unknown'):20s}  "
            f"{item.get('detail', '')[:50]}"
        )


async def demo_velocity(client: FakeGreenhouseClient) -> None:
    """Demo 4: Are we getting faster or slower at hiring?"""
    _header("hiring_velocity: Are we getting faster at hiring?")
    print(f"  {DIM}Recruiter asks:{RESET} {BOLD}Show me hiring velocity for Senior SWE{RESET}\n")

    now = datetime(2026, 3, 15, tzinfo=UTC)
    result = await hiring_velocity(job_id=1001, client=client, now=now)

    time_range = result["time_range"]
    _kv("Time range", f"{time_range['start']} to {time_range['end']} ({time_range['days']} days)")
    _kv("Total applications", result["total_applications"])
    _kv("Trend", result["trend"])

    details = result["trend_details"]
    _kv("Recent avg", f"{details['recent_avg']:.1f} apps/week")
    _kv("Previous avg", f"{details['previous_avg']:.1f} apps/week")
    _kv("Change", f"{details['change_pct']:.0f}%")

    if result.get("warning"):
        print(f"\n  {YELLOW}Warning: {result['warning']}{RESET}")

    offers = result["offer_metrics"]
    _subheader("Offer Metrics")
    _kv("Acceptance rate", f"{offers['acceptance_rate_pct']:.0f}%")
    _kv("Accepted", offers["accepted"])
    _kv("Rejected", offers["rejected"])
    _kv("Scope", offers["offer_scope"])

    _subheader("Weekly Buckets")
    for bucket in result["weekly_buckets"][-6:]:
        bar = "=" * bucket["count"]
        print(f"    {bucket['week_start']}  {bucket['count']:2d}  {GREEN}{bar}{RESET}")

    # Department breakdown
    print(f"\n  {DIM}Recruiter asks:{RESET} {BOLD}Show me velocity across all departments{RESET}\n")
    dept_result = await hiring_velocity(client=client, now=now)

    if "departments" in dept_result:
        for dept in dept_result["departments"]:
            _subheader(f"Department: {dept['department_name']}")
            _kv("Applications", dept["total_applications"])
            _kv("Trend", dept["trend"])


async def demo_search(client: FakeGreenhouseClient) -> None:
    """Demo 5: Find candidates matching criteria."""
    _header("search_talent: Find me candidates matching...")

    # Search by name
    print(f"  {DIM}Recruiter asks:{RESET} {BOLD}Find candidates named Maria{RESET}\n")
    result = await search_talent(query="Maria", client=client)

    _kv("Query", result["query"])
    _kv("Results", result["total_results"])
    for r in result["results"]:
        print(
            f"\n    {BOLD}{r['name']}{RESET}  "
            f"(relevance: {r['relevance_score']:.0f})"
        )
        _kv("Email", r["email"], indent=6)
        _kv("Tags", ", ".join(r["tags"]) if r["tags"] else "none", indent=6)
        for app in r["current_applications"]:
            print(
                f"      {DIM}Application:{RESET} {app['job_name']} "
                f"({app['status']}) - {app['stage']}"
            )

    # Search by tags
    print(f"\n\n  {DIM}Recruiter asks:{RESET} {BOLD}Find all senior candidates{RESET}\n")
    tag_result = await search_talent(tags=["senior"], client=client)

    _kv("Filter", "tags=senior")
    _kv("Results", tag_result["total_results"])
    for r in tag_result["results"]:
        apps_summary = ", ".join(f"{a['job_name']} ({a['stage']})" for a in r["current_applications"])
        print(f"    {BOLD}{r['name']}{RESET}  tags={r['tags']}  {DIM}{apps_summary}{RESET}")


async def main() -> None:
    """Run all five tool demos."""
    client = FakeGreenhouseClient()

    await demo_pipeline(client)
    print()
    await demo_candidate(client)
    print()
    await demo_attention(client)
    print()
    await demo_velocity(client)
    print()
    await demo_search(client)

    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{GREEN}  greenhouse-mcp: Workflow-oriented recruiting intelligence{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
