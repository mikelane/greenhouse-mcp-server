#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

B='\033[1;34m'
G='\033[1;32m'
C='\033[1;36m'
Y='\033[1;33m'
D='\033[1m'
R='\033[0m'

# --- intro (14.3s) ---
echo -e "\n${B}============================================================${R}"
echo -e "${B}  greenhouse-mcp-server${R}"
echo -e "${B}  Five tools. Five questions. Zero token waste.${R}"
echo -e "${B}============================================================${R}\n"
echo -e "${C}Each tool composes multiple Greenhouse API calls into one response.${R}"
echo -e "${C}No coordination overhead. Let me show you.${R}\n"
sleep 14.8

# --- pipeline (18.48s) ---
echo -e "\n${Y}[1/5]${R} ${D}Where are things stuck?${R}\n"
sleep 1.5
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.pipeline import pipeline_health
async def run():
    c = FakeGreenhouseClient()
    r = await pipeline_health(job_id=1001, client=c)
    print(f'  Job: {r[\"job_name\"]}')
    print(f'  Total active: {r[\"total_active\"]} candidates\n')
    for s in r['stages']:
        sv = s.get('severity') or '-'
        bn = ' << BOTTLENECK' if s.get('is_bottleneck') else ''
        print(f'    {s[\"stage_name\"]:30s}  {s[\"count\"]:2d} candidates  {s[\"share\"]:.0%} share  avg {s.get(\"avg_days_since_activity\",0):.0f}d idle  {sv}{bn}')
    if r['bottlenecks']:
        print(f'\n  Bottlenecks: {\", \".join(r[\"bottlenecks\"])}')
asyncio.run(run())
" 2>/dev/null
sleep 17.0

# --- candidate (17.41s) ---
echo -e "\n\n${Y}[2/5]${R} ${D}Tell me everything about Maria Chen${R}\n"
sleep 1.5
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.candidate import candidate_dossier
async def run():
    c = FakeGreenhouseClient()
    r = await candidate_dossier(candidate_id=101, client=c)
    s = r['summary']
    print(f'  Name: {s[\"name\"]}')
    print(f'  Status: {s[\"overall_status\"]}')
    print(f'  Active applications: {s[\"active_application_count\"]}')
    print(f'  Pending offers: {\"Yes\" if s[\"has_pending_offers\"] else \"No\"}\n')
    for app in r['applications']:
        print(f'  Application: {app[\"job_name\"]} ({app[\"status\"]})')
        print(f'    Stage: {app.get(\"current_stage\",\"N/A\")}')
        for sc in app.get('scorecards',[]):
            sub = 'submitted' if sc.get('submitted_at') else 'DRAFT'
            print(f'    Scorecard: {sc.get(\"interview\",\"?\")} - {sc.get(\"overall_recommendation\",\"?\")} ({sub})')
        for o in app.get('offers',[]):
            print(f'    Offer: {o.get(\"status\",\"?\")}')
        print()
    feed = r.get('activity_feed',{})
    total = feed.get('total_notes',0)+feed.get('total_emails',0)+feed.get('total_activities',0)
    print(f'  Activity feed: {total} items')
    for n in feed.get('recent_notes',[])[:2]:
        print(f'    Note: {n.get(\"body\",\"\")[:70]}...')
asyncio.run(run())
" 2>/dev/null
sleep 16.0

# --- attention (16.39s) ---
echo -e "\n\n${Y}[3/5]${R} ${D}What needs my attention right now?${R}\n"
sleep 1.5
uv run python -c "
import asyncio
from datetime import datetime, UTC
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.attention import needs_attention
async def run():
    c = FakeGreenhouseClient()
    now = datetime.now(tz=UTC)
    r = await needs_attention(client=c, days_stale=7, now=now)
    s = r['summary']
    print(f'  Total action items: {r[\"total_items\"]}\n')
    print(f'    Stuck applications: {s.get(\"stuck_applications\",0)}')
    print(f'    Missing scorecards: {s.get(\"missing_scorecards\",0)}')
    print(f'    Pending offers:     {s.get(\"pending_offers\",0)}')
    print(f'    No activity:        {s.get(\"no_activity\",0)}\n')
    print('  Priority Action Items:')
    for item in r['items'][:8]:
        p = item.get('priority_score',0)
        t = item['type'].replace('_',' ').title()
        nm = item.get('candidate_name','?')
        d = item.get('detail','')[:50]
        print(f'    [{p:.2f}]  {t:25s}  {nm:20s}  {d}')
asyncio.run(run())
" 2>/dev/null
sleep 15.0

# --- velocity (17.51s) ---
echo -e "\n\n${Y}[4/5]${R} ${D}Are we getting faster or slower?${R}\n"
sleep 1.5
uv run python -c "
import asyncio
from datetime import datetime, UTC
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.velocity import hiring_velocity
async def run():
    c = FakeGreenhouseClient()
    now = datetime(2026, 3, 15, tzinfo=UTC)
    r = await hiring_velocity(job_id=1001, client=c, now=now)
    tr = r['time_range']
    print(f'  Time range: {tr[\"start\"]} to {tr[\"end\"]} ({tr[\"days\"]} days)')
    print(f'  Total applications: {r[\"total_applications\"]}')
    print(f'  Trend: {r[\"trend\"]}')
    d = r['trend_details']
    print(f'  Recent avg: {d[\"recent_avg\"]:.1f} apps/week')
    print(f'  Previous avg: {d[\"previous_avg\"]:.1f} apps/week')
    print(f'  Change: {d[\"change_pct\"]:.0f}%')
    if r.get('warning'):
        print(f'  Warning: {r[\"warning\"]}')
    print()
    o = r['offer_metrics']
    print(f'  Offer acceptance rate: {o[\"acceptance_rate_pct\"]:.0f}%')
    print(f'  Accepted: {o[\"accepted\"]}  Rejected: {o[\"rejected\"]}')
    print()
    print('  Weekly Buckets (last 6):')
    for b in r['weekly_buckets'][-6:]:
        bar = '=' * b['count']
        print(f'    {b[\"week_start\"]}  {b[\"count\"]:2d}  {bar}')
asyncio.run(run())
" 2>/dev/null
sleep 16.0

# --- search (17.6s) ---
echo -e "\n\n${Y}[5/5]${R} ${D}Find senior engineers${R}\n"
sleep 1.5
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.search import search_talent
async def run():
    c = FakeGreenhouseClient()
    r = await search_talent(tags=['senior'], client=c)
    print(f'  Filter: tags=senior')
    print(f'  Results: {r[\"total_results\"]}\n')
    for res in r['results']:
        tags = ', '.join(res['tags']) if res['tags'] else 'none'
        print(f'  {res[\"name\"]}  (tags: {tags})')
        for app in res['current_applications']:
            print(f'    {app[\"job_name\"]} ({app[\"status\"]}) - {app[\"stage\"]}')
        print()
asyncio.run(run())
" 2>/dev/null
sleep 16.0

# --- quality (16.11s) ---
echo -e "\n\n${B}------------------------------------------------------------${R}"
echo -e "${B}  Quality Gates${R}"
echo -e "${B}------------------------------------------------------------${R}\n"
sleep 2.0

set +eo pipefail
echo -e "  ${D}Linting (ruff):${R}"
uv run ruff check src/ --quiet 2>&1 && echo "    All checks passed."
echo ""

echo -e "  ${D}Type checking (mypy --strict):${R}"
uv run mypy src 2>&1 | tail -1
echo ""

echo -e "  ${D}Tests (pytest):${R}"
uv run pytest tests/ --no-header -q 2>&1 | tail -3
echo ""
set -euo pipefail
sleep 8.0

# --- architecture (14.4s) ---
echo -e "\n${B}------------------------------------------------------------${R}"
echo -e "${B}  Architecture${R}"
echo -e "${B}------------------------------------------------------------${R}\n"
echo -e "  ${D}Hexagonal design${R}"
echo -e "    Tools depend on protocols (ports), not concrete classes"
echo -e "    dioxide container wires adapters by profile\n"
echo -e "  ${D}Profiles${R}"
echo -e "    PRODUCTION  ->  GreenhouseHttpClient (real API)"
echo -e "    TEST        ->  FakeGreenhouseClient (same interface)\n"
echo -e "  ${D}Read-only${R}"
echo -e "    No write operations. Safe in any environment."
echo ""
sleep 14.5

# --- closing (13.84s + 4s buffer) ---
echo -e "\n${B}============================================================${R}"
echo -e "${G}  Five questions. Five tools. Zero token waste.${R}"
echo -e "${B}============================================================${R}\n"
echo -e "  pipeline_health   ->  Where are things stuck?"
echo -e "  candidate_dossier ->  Tell me everything about this person"
echo -e "  needs_attention   ->  What needs my attention?"
echo -e "  hiring_velocity   ->  Are we getting faster?"
echo -e "  search_talent     ->  Find candidates matching...\n"
echo -e "${C}  Tools answer questions. They do not mirror endpoints.${R}\n"
sleep 18.0
