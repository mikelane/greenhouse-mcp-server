# ADR 0009: Greenhouse Search Capabilities and search_talent Design

## Status

Accepted

## Context

The `search_talent` tool needs to answer "find candidates matching X" but the Greenhouse Harvest API has limited server-side filtering: `GET /candidates` supports `per_page`, `page`, `job_id`, `email`, `candidate_ids`, `created_before`, `created_after`, `updated_before`, `updated_after` -- no full-text name search, no tag filtering, and no source filtering (source lives on the application object, not the candidate).

## Decision

The `search_talent` tool will compose: (1) fetch candidates using available API filters (`job_id`, `email`, `created_after`, `updated_after`), (2) apply client-side filters for name substring matching (case-insensitive on `first_name`/`last_name`/`name`) and tag matching, (3) enrich each match with application data to resolve stage, source, and job info, (4) rank results by relevance (exact name match > partial match, more recent activity ranked higher).

## Consequences

The `GreenhousePort.get_candidates` method gains `created_after` and `updated_after` optional parameters to push date filtering to the API and reduce client-side data volume. Name and tag filtering remain client-side, meaning large candidate pools will transfer more data than ideal -- acceptable for a read-only tool, and the API offers no alternative.
