#!/usr/bin/env bash
# Section 3: Candidate (question 11.5s + result 17.0s = 28.5s)
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
echo -e "\n\033[1mRecruiter asks:\033[0m Tell me everything about Maria Chen\n"
sleep 3.0
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.candidate import candidate_dossier
async def run():
    client = FakeGreenhouseClient()
    candidates = await client.get_candidates()
    maria = next(c for c in candidates if 'Maria' in c.get('first_name',''))
    result = await candidate_dossier(candidate_id=maria['id'], client=client)
    s = result['summary']
    print(f'  Name: {s[\"name\"]}')
    print(f'  Status: {s[\"overall_status\"]}')
    print(f'  Active applications: {s[\"active_application_count\"]}')
    print(f'  Pending offers: {\"Yes\" if s[\"has_pending_offers\"] else \"No\"}\n')
    for app in result['applications']:
        print(f'  Application: {app[\"job_name\"]} ({app[\"status\"]})')
        print(f'    Stage: {app.get(\"current_stage\", \"N/A\")}')
        if app.get('scorecards'):
            for sc in app['scorecards']:
                sub = 'submitted' if sc.get('submitted_at') else 'DRAFT'
                print(f'    Scorecard: {sc.get(\"interview\",\"?\")} - {sc.get(\"overall_recommendation\",\"?\")} ({sub})')
        if app.get('offers'):
            for o in app['offers']:
                print(f'    Offer: {o.get(\"status\",\"?\")}')
        print()
    feed = result.get('activity_feed', {})
    total = feed.get('total_notes',0) + feed.get('total_emails',0) + feed.get('total_activities',0)
    print(f'  Activity feed: {total} items')
    for n in feed.get('recent_notes',[])[:2]:
        print(f'    Note: {n.get(\"body\",\"\")[:70]}...')
asyncio.run(run())
" 2>/dev/null
sleep 24.0
