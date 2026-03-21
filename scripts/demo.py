#!/usr/bin/env python3
"""Demo: greenhouse-mcp tools with realistic recruiting data.

Runs all 3 implemented tools against the FakeGreenhouseClient
and prints formatted output showing what a recruiter would see.
"""

from __future__ import annotations

import asyncio

# Force the fake client module to be imported so dioxide discovers the adapter
import greenhouse_mcp.fake_client as _  # noqa: F401
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.attention import needs_attention
from greenhouse_mcp.tools.candidate import candidate_dossier
from greenhouse_mcp.tools.pipeline import pipeline_health

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


async def main() -> None:
    """Run all three tool demos."""
    client = FakeGreenhouseClient()

    await demo_pipeline(client)
    print()
    await demo_candidate(client)
    print()
    await demo_attention(client)

    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{GREEN}  greenhouse-mcp: Workflow-oriented recruiting intelligence{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
