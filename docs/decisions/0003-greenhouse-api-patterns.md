# ADR 0003: Greenhouse Harvest API Patterns

## Status

Accepted

## Context

Before building `client.py`, we need precise answers about how Greenhouse authenticates,
throttles, paginates, and reports errors. Guessing wrong on any of these means debugging
against a remote API with rate limits -- not fun.

Sources: the [official Harvest API docs](https://developers.greenhouse.io/harvest.html) and
the [docs source repo](https://github.com/grnhse/greenhouse-api-docs) (useful when the
rendered page is too large for a single pass).

## Authentication

**Scheme:** HTTP Basic Auth over HTTPS only (HTTP returns `403 Forbidden`).

**Credentials:**
- Username: Greenhouse Harvest API token
- Password: empty string

**Header construction:**
```
Authorization: Basic <base64("{api_token}:")>
```

Note the trailing colon after the token -- Basic Auth encodes `username:password`, and the
password is blank, so it becomes `token:` before base64 encoding.

**Failure modes:**

| Status | Meaning |
|--------|---------|
| `401 Unauthorized` | Missing or invalid API token |
| `403 Forbidden` | Valid token but insufficient permissions, OR request body supplied on a GET, OR HTTP (not HTTPS) |

**Token permissions:** Each API credential has per-endpoint permissions configured in the
Greenhouse Dev Center under "API Credential Management > Manage Permissions". Tokens created
before 2017-01-18 have blanket access to all endpoints that existed at that time. Newer tokens
require explicit grants.

**Special headers:**

| Header | Required | Purpose |
|--------|----------|---------|
| `On-Behalf-Of` | POST/PATCH/DELETE only | User ID for audit trail. Not needed for our read-only client. |

## Rate Limiting

**Window:** Per 10-second sliding window.

**Response headers (present on every response):**

| Header | Type | Description |
|--------|------|-------------|
| `X-RateLimit-Limit` | integer | Max requests allowed in current window |
| `X-RateLimit-Remaining` | integer | Requests remaining in current window |
| `X-RateLimit-Reset` | unix timestamp | When the current window resets |

**When exceeded:** HTTP `429 Too Many Requests` with an additional `Retry-After` header
(seconds until retry is safe).

**Limit value:** The docs never pin down a number. The limit is dynamic and returned in
`X-RateLimit-Limit` on every response -- examples show `50`, but Greenhouse reserves the
right to vary it by credential type. "Approved partners" get one allowance; "unlisted
vendors" may get a tighter one. The limit is global across all endpoints for a credential,
with no per-endpoint differentiation documented.

**What this means for our client:** Read `X-RateLimit-Remaining` after every response. When
it drops below a safety margin (say, 5), sleep until `X-RateLimit-Reset`. On `429`, honor
`Retry-After` and fall back to exponential backoff with jitter.

## Pagination

**Mechanism:** Link header (RFC 5988) with `rel` attributes.

**Query parameters:**

| Parameter | Type | Default | Max | Description |
|-----------|------|---------|-----|-------------|
| `per_page` | integer | 100 | 500 | Results per page (range 1-500) |
| `page` | integer | 1 | - | Page number (cursor for nth chunk) |
| `skip_count` | boolean | false | - | Omits `rel="last"` from Link header; improves server performance |

**Example Link header:**
```
Link: <https://harvest.greenhouse.io/v1/candidates?page=2&per_page=100>; rel="next",
      <https://harvest.greenhouse.io/v1/candidates?page=474&per_page=100>; rel="last"
```

**Rel values:**

| Rel | When present |
|-----|-------------|
| `next` | More pages remain |
| `prev` | Not the first page |
| `last` | Always, unless `skip_count=true` |

**Last page detection:** No `Link` header at all (single page of results), or no `rel="next"`
in the Link header.

**What this means for our client:** Build a generic async iterator that parses the Link
header, extracts the `rel="next"` URL, and follows it until it disappears. Always request
`per_page=500` and `skip_count=true` -- we never need the `last` link, and skipping the
count query makes Greenhouse's life easier (and our responses faster).

## Error Handling

**Status codes:**

| Code | Meaning | Response body |
|------|---------|--------------|
| `401` | Unauthorized (bad/missing token) | Not documented (likely `{"message": "..."}`) |
| `403` | Forbidden (no access or body on GET) | Not documented |
| `404` | Not Found (resource does not exist) | Not documented |
| `422` | Unprocessable Entity (validation error) | Structured (see below) |
| `429` | Rate limit exceeded | Headers: `Retry-After` |
| `500` | Server error | Not documented; retry after delay |

**Validation error body (422):**
```json
{
  "message": "Validation error",
  "errors": [
    {
      "message": "Must be one of: candidate, prospect",
      "field": "type"
    }
  ]
}
```

The `errors` array contains objects with `message` (human-readable) and `field` (the
offending parameter name).

**Deleted resources:** Return a success message, not 404:
```json
{"message": "Application 29622362 has been deleted."}
```

**Empty collections:** Return an empty JSON array `[]`.

**What this means for our client:** Each status code maps to a typed exception so callers
can handle them distinctly. Since we're read-only, `401` means "your token is wrong" (fail
fast), `403` means "your token can't access this endpoint" (also fail fast), `404` means
"that resource doesn't exist" (return None or raise, depending on context), and `429`/`500`
mean "try again later" (retry with backoff).

## General API Behavior

**Base URL:** `https://harvest.greenhouse.io/v1`

**Content type:** JSON responses. Requests requiring a body use `Content-Type: application/json`.

**Timestamp format:** ISO 8601 with UTC timezone: `"2016-08-22T19:52:38.384Z"`

**Date-only format:** `"YYYY-MM-DD"` (used in offers for `starts_at`, `sent_at`).

**Backward compatibility:** "We reserve the right to add more properties to objects, but will
never change or remove them." New fields may appear at any time -- the client must tolerate
unknown keys (Pydantic's `model_config = {"extra": "ignore"}`).

**URL expiry:** Document/attachment URLs (S3 pre-signed) expire after 7 days.

**Null handling:** Missing optional fields are `null`, not omitted.

**Legacy typo:** The activity feed note object has both `"visiblity"` (typo) and `"visibility"`
(correct) fields. Both are present for backward compatibility.

## Key Endpoint Shapes

### Jobs

**List:** `GET /v1/jobs`

Query params: `per_page`, `page`, `skip_count`, `created_before`, `created_after`,
`updated_before`, `updated_after`, `requisition_id`, `opening_id`, `status`,
`department_id`, `external_department_id`, `office_id`, `external_office_id`,
`custom_field_option_id`

Status enum: `open`, `closed`, `draft`

Key response fields:
```
id, name, requisition_id, status, confidential, is_template,
created_at, opened_at, closed_at, updated_at, notes,
departments[{id, name}], offices[{id, name}],
hiring_team{hiring_managers[], recruiters[], coordinators[], sourcers[]},
openings[{id, opening_id, status, opened_at, closed_at, application_id, close_reason}],
custom_fields, keyed_custom_fields
```

### Job Stages

**List for job:** `GET /v1/jobs/{id}/stages`

Query params: `created_before`, `created_after`, `updated_before`, `updated_after`

Key response fields:
```
id, name, created_at, updated_at, active, job_id, priority,
interviews[{
  id, name, schedulable, estimated_minutes,
  default_interviewer_users[{id, first_name, last_name, name, employee_id}],
  interview_kit{id, content, questions[{id, question}]}
}]
```

`priority` is numeric, lowest values ordered first. `active: false` means the stage was
deleted (soft delete).

### Applications

**List:** `GET /v1/applications`

Query params: `per_page`, `page`, `skip_count`, `created_before`, `created_after`,
`last_activity_after`, `job_id`, `status`

Status enum: `active`, `rejected`, `hired`, `converted`

Key response fields:
```
id, candidate_id, prospect, applied_at, rejected_at, last_activity_at,
location{address}, source{id, public_name},
credited_to{id, first_name, last_name, name, employee_id},
recruiter{...}, coordinator{...},
rejection_reason{id, name, type{id, name}},
rejection_details{custom_fields, keyed_custom_fields},
jobs[{id, name}], job_post_id, status,
current_stage{id, name},
answers[{question, answer}],
prospective_office, prospective_department,
prospect_detail{prospect_pool, prospect_stage, prospect_owner},
custom_fields, keyed_custom_fields,
attachments[{filename, url, type, created_at}]
```

**Sub-endpoints:**
- `GET /v1/applications/{id}/scorecards`
- `GET /v1/applications/{id}/scheduled_interviews`
- `GET /v1/applications/{id}/offers`

### Candidates

**List:** `GET /v1/candidates`

Query params: `per_page`, `page`, `skip_count`, `created_before`, `created_after`,
`updated_before`, `updated_after`, `job_id`, `email`, `candidate_ids` (comma-separated, max 50)

Key response fields:
```
id, first_name, last_name, middle_name, name,
created_at, updated_at, external_id,
phone_numbers[{value, type}],
email_addresses[{value, type}],
addresses[{value, type}],
website_addresses[{value, type}],
social_media_addresses[{value, type}],
employment_history[{company, title, key_fields{start_date, end_date}}],
education[{school_name, degree, discipline, start_date}],
recruiter{...}, coordinator{...},
applications[{id, status}],
attachments[{filename, url, type}],
custom_fields, keyed_custom_fields,
can_email, tags[]
```

### Activity Feed

**Retrieve:** `GET /v1/candidates/{id}/activity_feed`

No pagination -- returns all activity for the candidate.

Response structure:
```json
{
  "notes": [{id, created_at, body, user{...}, private, visiblity, visibility}],
  "emails": [{id, created_at, subject, body, to, from, cc, user{...}}],
  "activities": [{id, created_at, subject, body, user{...}}]
}
```

Visibility values: `"admin_only"`, `"public"`, `"private"`

### Scorecards

**List:** `GET /v1/scorecards`
**List for application:** `GET /v1/applications/{id}/scorecards`

Query params (list all): `per_page`, `page`, `skip_count`, `created_before`, `created_after`,
`updated_before`, `updated_after`

Overall recommendation enum: `definitely_not`, `no`, `yes`, `strong_yes`, `no_decision`

Key response fields:
```
id, created_at, updated_at, interviewed_at, submitted_at,
interview (string -- interview name),
interview_step{id, name},
candidate_id, application_id,
submitted_by{id, first_name, last_name, name, employee_id},
interviewer{...},
overall_recommendation,
attributes[{name, type, note, rating}],
ratings{definitely_not[], no[], mixed[], yes[], strong_yes[]},
questions[{id, question, answer}]
```

`submitted_at` is null for unsubmitted scorecards. Question `id` is null for system
questions ("Key Take-Aways", "Private Notes"). Question answers support basic HTML.

### Scheduled Interviews

**List:** `GET /v1/scheduled_interviews`
**List for application:** `GET /v1/applications/{id}/scheduled_interviews`

Query params: `per_page`, `page`, `skip_count`, `created_before`, `created_after`,
`updated_before`, `updated_after`, `starts_before`, `starts_after`, `ends_before`,
`ends_after`, `external_event_id`, `actionable`

Status enum: `scheduled`, `awaiting_feedback`, `complete`

Interviewer response_status enum: `needs_action`, `declined`, `tentative`, `accepted`

Key response fields:
```
id, application_id, external_event_id,
start{date_time | date}, end{date_time | date},
location, video_conferencing_url, status,
created_at, updated_at,
interview{id, name},
organizer{id, first_name, last_name, name, employee_id},
interviewers[{id, employee_id, name, email, response_status, scorecard_id}]
```

### Offers

**List:** `GET /v1/offers`
**List for application:** `GET /v1/applications/{id}/offers`
**Current offer:** `GET /v1/applications/{id}/offers/current_offer`

Query params (list all): `per_page`, `page`, `skip_count`, `created_before`, `created_after`,
`updated_before`, `updated_after`, `resolved_after`, `resolved_before`, `status`,
`sent_after`, `sent_before`, `starts_after`, `starts_before`

Status enum: `unresolved`, `accepted`, `rejected`, `deprecated`

Key response fields:
```
id, version, application_id, job_id, candidate_id,
opening{id, opening_id, status, opened_at, closed_at, application_id, close_reason},
created_at, updated_at,
sent_at (date YYYY-MM-DD), resolved_at,
starts_at (date YYYY-MM-DD), status,
custom_fields, keyed_custom_fields
```

### Departments

**List:** `GET /v1/departments`
**Retrieve:** `GET /v1/departments/{id}`

Available for filtering jobs by department when computing velocity metrics.

## Consequences

These findings shape `client.py` in concrete ways:

1. **Auth adapter.** Implement as an httpx `Auth` class that injects the `Authorization:
   Basic ...` header on every request. The token comes from `GREENHOUSE_API_TOKEN` (env
   var, 12-Factor style). No `On-Behalf-Of` needed since we're read-only.

2. **Rate limiter.** Check `X-RateLimit-Remaining` after every response. When it drops
   below a safety margin, sleep until `X-RateLimit-Reset`. On `429`, honor `Retry-After`.
   Fall back to exponential backoff with jitter if the header is missing.

3. **Paginator.** A generic async iterator that chases `rel="next"` in the Link header.
   Always request `per_page=500` and `skip_count=true` to minimize round-trips and avoid
   making Greenhouse count total pages we'll never use.

4. **Error hierarchy.** `GreenhouseError` at the root, with subtypes: `AuthenticationError`
   (401), `PermissionError` (403), `NotFoundError` (404), `ValidationError` (422, carries
   the `errors` array), `RateLimitError` (429, carries `retry_after`), `ServerError` (500).

5. **Pydantic models.** Set `model_config = ConfigDict(extra="ignore")` on every model so
   new fields from Greenhouse don't blow up deserialization. Define enums for the known
   value sets: `JobStatus`, `ApplicationStatus`, `OfferStatus`, `OverallRecommendation`,
   `InterviewStatus`, `InterviewerResponseStatus`.

6. **Prefer scoped endpoints.** Use `/applications/{id}/scorecards` instead of fetching all
   scorecards and filtering client-side. Same for scheduled interviews and offers per
   application. Fewer bytes over the wire, fewer requests burned against the rate limit.

7. **Timestamp handling.** ISO 8601 UTC for most fields (`datetime.fromisoformat()`).
   Date-only fields on offers (`starts_at`, `sent_at`) use `YYYY-MM-DD`
   (`date.fromisoformat()`). Two parsers, no ambiguity.

8. **Activity feed has no pagination.** `GET /candidates/{id}/activity_feed` dumps
   everything in one response. For candidates with years of history, that response could be
   large. Set a generous read timeout.

9. **Soft-deleted stages.** Job stages with `active: false` are "deleted" but still returned
   by the API. The pipeline health tool needs to filter these out unless the caller
   explicitly asks for them.
