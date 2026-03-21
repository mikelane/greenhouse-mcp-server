#!/usr/bin/env bash
# Section 4: Attention + closing (question 11.3s + result 17.4s + closing 7.1s = 35.8s)
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
echo -e "\n\033[1mRecruiter asks:\033[0m What needs my attention right now?\n"
sleep 3.0
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.attention import needs_attention
async def run():
    client = FakeGreenhouseClient()
    result = await needs_attention(client=client, days_stale=7)
    s = result['summary']
    print(f'  Total action items: {result[\"total_items\"]}\n')
    print(f'    Stuck applications: {s.get(\"stuck_applications\",0)}')
    print(f'    Missing scorecards: {s.get(\"missing_scorecards\",0)}')
    print(f'    Pending offers:     {s.get(\"pending_offers\",0)}')
    print(f'    No activity:        {s.get(\"no_activity\",0)}\n')
    print('  Priority Action Items:')
    for item in result['items'][:8]:
        p = item.get('priority_score', 0)
        t = item['type'].replace('_', ' ').title()
        name = item.get('candidate_name', '?')
        detail = item.get('detail', '')[:45]
        print(f'    [{p:.2f}]  {t:25s}  {name:20s}  {detail}')
asyncio.run(run())
" 2>/dev/null
sleep 20.0

echo -e "\n\n\033[1;34m============================================================\033[0m"
echo -e "\033[1;32m  Three questions. Three answers. Zero token waste.\033[0m"
echo -e "\033[1;34m============================================================\033[0m\n"
sleep 12.0
