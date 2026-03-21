#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

B='\033[1;34m'
G='\033[1;32m'
C='\033[1;36m'
D='\033[1m'
R='\033[0m'

echo -e "\n${B}============================================================${R}"
echo -e "${B}  greenhouse-mcp: Recruiting Intelligence Tools${R}"
echo -e "${B}============================================================${R}\n"
echo -e "${C}Three questions. Three answers. Real recruiting data.${R}\n"
sleep 9.0

echo -e "\n${D}Recruiter asks:${R} Where are things stuck for Senior SWE?\n"
sleep 2.0
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
sleep 22.0

echo -e "\n\n${D}Recruiter asks:${R} Tell me everything about Maria Chen\n"
sleep 2.0
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.candidate import candidate_dossier
async def run():
    c = FakeGreenhouseClient()
    cs = await c.get_candidates()
    m = next(x for x in cs if 'Maria' in x.get('first_name',''))
    r = await candidate_dossier(candidate_id=m['id'], client=c)
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
sleep 26.0

echo -e "\n\n${D}Recruiter asks:${R} What needs my attention right now?\n"
sleep 2.0
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.attention import needs_attention
async def run():
    c = FakeGreenhouseClient()
    r = await needs_attention(client=c, days_stale=7)
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
        d = item.get('detail','')[:45]
        print(f'    [{p:.2f}]  {t:25s}  {nm:20s}  {d}')
asyncio.run(run())
" 2>/dev/null
sleep 26.0

echo -e "\n\n${B}============================================================${R}"
echo -e "${G}  Three questions. Three answers. Zero token waste.${R}"
echo -e "${B}============================================================${R}\n"
sleep 12.0
