#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

B='\033[1;34m'
G='\033[1;32m'
C='\033[1;36m'
D='\033[1m'
R='\033[0m'

# --- intro (14.16s) ---
echo -e "\n${B}============================================================${R}"
echo -e "${B}  greenhouse-mcp: Milestone 3 — Analytics and Search${R}"
echo -e "${B}============================================================${R}\n"
echo -e "${C}Two tools. Two questions recruiters ask every day.${R}\n"
sleep 14.5

# --- velocity_question (14.07s) ---
echo -e "\n${D}Recruiter asks:${R} Are we getting faster at hiring for Senior SWE?\n"
sleep 2.0
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
asyncio.run(run())
" 2>/dev/null
sleep 12.5

# --- velocity_result (14.86s) ---
echo -e "\n  ${D}Offer Metrics:${R}"
uv run python -c "
import asyncio
from datetime import datetime, UTC
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.velocity import hiring_velocity
async def run():
    c = FakeGreenhouseClient()
    now = datetime(2026, 3, 15, tzinfo=UTC)
    r = await hiring_velocity(job_id=1001, client=c, now=now)
    o = r['offer_metrics']
    print(f'    Acceptance rate: {o[\"acceptance_rate_pct\"]:.0f}%')
    print(f'    Accepted: {o[\"accepted\"]}')
    print(f'    Rejected: {o[\"rejected\"]}')
    print(f'    Scope: {o[\"offer_scope\"]}')
    print()
    print('  Weekly Buckets (last 6):')
    for b in r['weekly_buckets'][-6:]:
        bar = '=' * b['count']
        print(f'    {b[\"week_start\"]}  {b[\"count\"]:2d}  {bar}')
asyncio.run(run())
" 2>/dev/null
sleep 15.0

# --- velocity_department (12.21s) ---
echo -e "\n\n${D}Recruiter asks:${R} Show me velocity across all departments\n"
sleep 2.0
uv run python -c "
import asyncio
from datetime import datetime, UTC
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.velocity import hiring_velocity
async def run():
    c = FakeGreenhouseClient()
    now = datetime(2026, 3, 15, tzinfo=UTC)
    r = await hiring_velocity(client=c, now=now)
    if 'departments' in r:
        for d in r['departments']:
            print(f'  {d[\"department_name\"]:15s}  {d[\"total_applications\"]:2d} applications  trend: {d[\"trend\"]}')
        print()
        o = r['overall']
        print(f'  Overall: {o[\"total_applications\"]} applications, trend: {o[\"trend\"]}')
asyncio.run(run())
" 2>/dev/null
sleep 10.5

# --- search_question (11.61s) ---
echo -e "\n\n${B}------------------------------------------------------------${R}"
echo -e "${B}  search_talent: Find me candidates matching...${R}"
echo -e "${B}------------------------------------------------------------${R}\n"
sleep 12.0

# --- search_name (15.98s) ---
echo -e "${D}Recruiter asks:${R} Find candidates named Maria\n"
sleep 2.0
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.search import search_talent
async def run():
    c = FakeGreenhouseClient()
    r = await search_talent(query='Maria', client=c)
    print(f'  Query: {r[\"query\"]}')
    print(f'  Results: {r[\"total_results\"]}')
    for res in r['results']:
        print(f'  {res[\"name\"]}  (relevance: {res[\"relevance_score\"]:.0f})')
        print(f'    Email: {res[\"email\"]}')
        tags = ', '.join(res['tags']) if res['tags'] else 'none'
        print(f'    Tags: {tags}')
        for app in res['current_applications']:
            print(f'    Application: {app[\"job_name\"]} ({app[\"status\"]}) - {app[\"stage\"]}')
asyncio.run(run())
" 2>/dev/null
sleep 14.5

# --- search_tags (13.1s) ---
echo -e "\n\n${D}Recruiter asks:${R} Find all senior candidates\n"
sleep 2.0
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.search import search_talent
async def run():
    c = FakeGreenhouseClient()
    r = await search_talent(tags=['senior'], client=c)
    print(f'  Filter: tags=senior')
    print(f'  Results: {r[\"total_results\"]}')
    print()
    for res in r['results']:
        apps = ', '.join(f'{a[\"job_name\"]} ({a[\"stage\"]})' for a in res['current_applications'])
        print(f'  {res[\"name\"]:20s}  tags={res[\"tags\"]}')
        print(f'    {apps}')
asyncio.run(run())
" 2>/dev/null
sleep 11.5

# --- closing (10.59s) ---
echo -e "\n\n${B}============================================================${R}"
echo -e "${G}  Five tools. Five questions. Zero token waste.${R}"
echo -e "${B}============================================================${R}\n"
sleep 12.0
