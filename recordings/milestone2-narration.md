# Demo Narration: Milestone 2 Core Recruiting Tools

## Metadata

- Issues: #18, #41, #53
- Recording date: 2026-03-21

---

## Segments

<!-- SEGMENT: intro -->
This is greenhouse mcp server in action. Three tools, each answering a question a recruiter actually asks. Watch the output, not the code.

<!-- SEGMENT: pipeline_question -->
First question: where are things stuck for the Senior Software Engineer role? The pipeline health tool fetches job stages and applications, groups candidates by stage, and detects bottlenecks.

<!-- SEGMENT: pipeline_result -->
Technical Interview is flagged as a bottleneck. Five candidates, 71 percent of the pipeline, severity high. Average 13 days idle. The recruiter knows exactly where to focus.

<!-- SEGMENT: candidate_question -->
Second question: tell me everything about Maria Chen. The candidate dossier tool fetches her profile, all applications, scorecards, offers, and activity feed in parallel.

<!-- SEGMENT: candidate_result -->
Maria was hired as a Senior Software Engineer. Strong yes on the technical interview, yes on system design. Offer accepted. She also has an active application for Product Manager in the hiring manager screen stage. Eleven activity items show the full story.

<!-- SEGMENT: attention_question -->
Third question: what needs my attention right now? The needs attention tool scans for stale applications, missing scorecards, and pending offers, then ranks them by priority.

<!-- SEGMENT: attention_result -->
Eleven action items. Aisha Patel and Alex Tanaka have missing scorecards at the top. Nathan Park has a pending offer sent five days ago with no response. Three candidates are stuck in technical interview for over twelve days. Every item has a priority score and a suggested action.

<!-- SEGMENT: closing -->
Three questions, three answers. No API coordination, no token waste. The server does the orchestration so the agent does not have to.
