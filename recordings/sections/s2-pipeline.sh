#!/usr/bin/env bash
# Section 2: Pipeline (question 12.3s + result 11.8s = 24.1s)
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
echo -e "\n\033[1mRecruiter asks:\033[0m Where are things stuck for Senior SWE?\n"
sleep 3.0
uv run python -c "
import asyncio
from greenhouse_mcp.fake_client import FakeGreenhouseClient
from greenhouse_mcp.tools.pipeline import pipeline_health
async def run():
    client = FakeGreenhouseClient()
    result = await pipeline_health(job_id=1001, client=client)
    print(f'  Job: {result[\"job_name\"]}')
    print(f'  Total active: {result[\"total_active\"]} candidates\n')
    for s in result['stages']:
        sev = s.get('severity') or '-'
        bn = ' << BOTTLENECK' if s.get('is_bottleneck') else ''
        print(f'    {s[\"stage_name\"]:30s}  {s[\"count\"]:2d} candidates  {s[\"share\"]:.0%} share  avg {s.get(\"avg_days_since_activity\",0):.0f}d idle  {sev}{bn}')
    if result['bottlenecks']:
        print(f'\n  Bottlenecks: {\", \".join(result[\"bottlenecks\"])}')
asyncio.run(run())
" 2>/dev/null
sleep 20.0
