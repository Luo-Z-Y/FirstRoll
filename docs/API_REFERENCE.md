# FirstRoll API Reference

**API version:** `0.1.0`  
**Last reconciled:** 21 August 2026

FirstRoll uses one FastAPI application in two modes. The local edition serves the web interface and
API from `http://127.0.0.1:8000`. The hosted public beta serves the Azure frontend at
`https://firstroll.app` and the Azure Container Apps API at `https://api.firstroll.app`. This
document uses relative paths so it remains correct when those deployment URLs change.

FastAPI also exposes generated OpenAPI documentation at `/docs` and the machine-readable schema at
`/openapi.json` unless deployment configuration disables them in future.

## Access Classes

| Label | Meaning |
|---|---|
| Public | No FirstRoll account required |
| Local only | Available only when `FIRSTROLL_PUBLIC_MODE` is false and the client is loopback |
| Hosted bearer | Requires `Authorization: Bearer <access token>` from the configured identity provider |
| Conditional bearer | Public operation, but a personal request-scoped provider key requires a valid bearer token in hosted mode |
| Feature gated | Availability depends on explicit backend configuration |

Authentication is not inferred from an email or browser field. Production currently validates
Supabase access tokens, UUIDs and the `authenticated` role. A staged Entra External ID verifier
instead validates the configured issuer, API audience, signature, expiry and `access_as_user`
scope. Exactly one provider is selected by configuration. FastAPI returns HTTP 401 with
`WWW-Authenticate: Bearer` when a session is missing or rejected.

## Header Dictionary

| Header | Direction | Required | Meaning |
|---|---|---:|---|
| `Authorization: Bearer …` | Request | Hosted account, study and run endpoints | Access token from the configured provider; maximum accepted length 16,384 characters |
| `Content-Type: application/json` | Request | JSON writes | Request body encoding |
| `Content-Type: multipart/form-data` | Request | Library upload and clip analysis | Browser-generated multipart boundary required |
| `X-FirstRoll-DeepSeek-Key` | Request | Optional | Personal DeepSeek key for one authenticated request; 16–512 characters, `[A-Za-z0-9._-]` only |
| `X-FirstRoll-YouTube-Key` | Request | Optional | Personal YouTube key for one authenticated video-search request; same syntax boundary |
| `X-FirstRoll-Run-ID` | Response | Streaming study | Opaque UUID used for the separate result request; exposed through CORS |
| `Retry-After` | Response | HTTP 429 | Seconds until the next quota reset, with a minimum of 60 |
| `Cache-Control: no-store` | Response | Auth, config, stream/result boundaries where specified | Prevents browser/proxy retention of sensitive or mutable responses |

Personal provider keys live in browser memory for one tab, are cleared on refresh/sign-out and are
never returned in an API response. They do not remove the hosted account/global quota boundary.

## Common Error Contract

FastAPI errors use:

```json
{
  "detail": "Human-readable public error"
}
```

| Status | General meaning |
|---:|---|
| 400 | Invalid query, form field, connector credential or personal-key syntax |
| 401 | Missing, expired or unauthorised Supabase session |
| 403 | Non-loopback caller attempted a local-only operation |
| 404 | Resource absent, feature deliberately unpublished, or owner-scoped run concealed |
| 409 | State conflict: environment-controlled credential, missing cached source, running study result |
| 429 | Account or public-demo Deep Study allowance exhausted |
| 500 | Local index, filesystem or analysis failure |
| 501 | Known connector exists but its test operation is not implemented |
| 502 | Upstream provider, quota store or model returned no trustworthy result |
| 503 | Required hosted configuration absent, feature disabled or hosted clip analysis unavailable |

Provider endpoints fail independently. A 502 from one criticism source does not invalidate the film
identity record or previously cached evidence from another source.

## Endpoint Dictionary

### Service, configuration and account

| Method | Path | Access | Request | Success response |
|---|---|---|---|---|
| GET | `/` | Public | — | Local: `index.html`; hosted API: service/status/health JSON |
| GET | `/assets/config.js` | Public | — | Non-cacheable browser runtime configuration; only public Supabase values may appear |
| GET | `/api/health` | Public | — | `{"status":"ok"}` |
| GET | `/api/contract` | Public | — | Compact endpoint and clip-analysis shape summary |
| GET | `/api/discovery/status` | Public | — | Provider status and feature flags; local mode also includes private-library counts |
| GET | `/api/auth/me` | Hosted bearer | Bearer token | Verified `id`, optional `email` and `role` |
| GET | `/api/account/integrations` | Hosted bearer; hosted mode only | Bearer token | Account identity, non-consuming quota status, platform/personal provider capability and privacy statement |

### Local settings and private library

All routes in this table return 404 in public mode and 403 to a non-loopback local caller.

| Method | Path | Request | Success response | Important errors |
|---|---|---|---|---|
| GET | `/settings` | — | Local settings HTML | 404/403 mode boundary |
| GET | `/api/settings` | — | Masked connector states and storage description | Secrets are never returned |
| PUT | `/api/settings/connectors/{connector_id}` | `{"value":"…"}` for one field or `{"credentials":{"client_id":"…","client_secret":"…"}}` | Updated masked connector state | 400 unknown/empty field; 404 connector; 409 environment owns value |
| DELETE | `/api/settings/connectors/{connector_id}` | — | Updated masked connector state | 404 connector; 409 environment value must be unset externally |
| POST | `/api/settings/connectors/{connector_id}/test` | — | Provider-specific readiness result | 501 planned test; 502 provider failure |
| GET | `/api/settings/library` | — | Catalogue, index status, supported formats, 500 MB limit and rebuild requirement | — |
| POST | `/api/settings/library` | Multipart field `document` | Added document metadata and refreshed catalogue | 400 empty, oversized or unsupported file |
| DELETE | `/api/settings/library/{document_id}` | — | Removed catalogue entry and refreshed catalogue | 404 unknown document; managed source is not deleted |
| POST | `/api/settings/library/rebuild` | — | Rebuilt catalogue/index status | 500 redacted rebuild failure |
| GET | `/api/library/status` | Local mode | — | Public-safe document metadata and index status | 404 in public mode |

Supported catalogue formats are PDF, EPUB, Markdown and text. The current indexer extracts PDF
content; other formats can be catalogued but are not counted as indexable documents.

Implemented connector IDs are `tmdb`, `deepseek`, `douban`, `letterboxd` and `youtube`; `nyt` and
`guardian` are declared but their credential tests remain planned. The `tmdb` connector accepts one
Read Access Token and can also be controlled by backend environment variable `TMDB_BEARER_TOKEN`.

### Film discovery and dossier

| Method | Path | Access | Parameters | Success response |
|---|---|---|---|---|
| GET | `/api/discovery/search` | Public | `q` 1–160 chars; optional `year` 1888–2100; optional `director` ≤120 chars | Candidate films from TMDb when configured, otherwise the open fallback, with identity evidence and provider policy |
| GET | `/api/discovery/films/{film_id}` | Public | Canonical path ID | Full dossier; local mode adds library/retrieval, both modes add cached criticism/video bundles |
| GET | `/api/discovery/films/{film_id}/related` | Public | `limit` 1–60, default 12; `fast` boolean, default true; `director_only` boolean, default false. `fast=false` enables cached, batched poster enrichment | Same-director and relationship groups for the native filmography shelf |
| GET | `/api/discovery/films/{film_id}/reception` | Public | Canonical path ID | Available Douban/Letterboxd scores, optional equal-weight aggregate, provider state and up to three awards |

Search can return more than one candidate. The browser must require an explicit user choice before
opening a dossier or starting Deep Study; the API does not silently promote the first same-title
result. IDs are opaque, provider-qualified paths: current values begin with `tmdb:` or `wikidata:`.
TMDb results include available `external_ids.imdb` and `external_ids.wikidata` values. A configured
TMDb search hydrates at most eight candidates through at most four concurrent detail calls; year and
director filters are rechecked locally. Missing TMDb credentials use Wikidata/Wikipedia normally,
while a live TMDb failure marks the response `mode=degraded` and records
`provider_policy=wikidata_failover`.

Example:

```http
GET /api/discovery/search?q=The%20Thing&year=1982&director=John%20Carpenter
```

```json
{
  "query": "The Thing",
  "results": [
    {
      "id": "tmdb:1091",
      "title": "The Thing",
      "year": 1982,
      "directors": ["John Carpenter"],
      "external_ids": {"imdb": "tt0084787", "wikidata": "Q210756"}
    }
  ]
}
```

Provider response models may contain additional attributed metadata; clients should ignore unknown
response fields but must not reinterpret provider summaries as direct film observation.

### Criticism and research acquisition

| Method | Path | Access | Operation | Success response |
|---|---|---|---|---|
| POST | `/api/discovery/films/{film_id}/criticism/crossref` | Public | Search matched scholarly metadata/abstracts | `critical_research` bundle with pending claims |
| POST | `/api/discovery/films/{film_id}/criticism/douban` | Public; connector required | Call optional Douban MCP tools | Attributed review-summary bundle |
| POST | `/api/discovery/films/{film_id}/criticism/letterboxd-web` | Public | Retrieve bounded public Letterboxd review pages | Attributed review bundle |
| POST | `/api/discovery/films/{film_id}/criticism/guardian-web` | Public | Retrieve Guardian search/pages | Attributed professional-criticism bundle |
| POST | `/api/discovery/films/{film_id}/criticism/letterboxd` | Public; OAuth credentials required | Use official Letterboxd API | Attributed review bundle |
| POST | `/api/discovery/films/{film_id}/criticism/{provider}/structure` | Local only | Structure an existing cached bundle with DeepSeek | Same bundle with validated `CriticalClaim[]` and `claim_status=structured` |

Valid structure-provider path values are `crossref`, `douban`, `letterboxd`, `letterboxd-web` and
`guardian-web`. Structuring never fetches the provider implicitly; a missing cached review bundle
returns 409. Refreshing raw reviews preserves previous claims only when the source review IDs are
unchanged.

### Video catalogue

| Method | Path | Access | Request | Success response |
|---|---|---|---|---|
| POST | `/api/discovery/films/{film_id}/videos` | Public; conditional bearer for personal YouTube key | Optional `X-FirstRoll-YouTube-Key` | Merged `video_sources` bundle with up to 48 deduplicated resources |

Results are classified as `full_film`, `interview`, `video_essay`, `lecture`, `trailer`,
`scene_extract`, `behind_the_scenes` or `other`. The catalogue records public links and embed URLs;
it does not assert that every upload is authorised or that every claim in a video is correct.

### Deep Study

| Method | Path | Access | Request | Success response |
|---|---|---|---|---|
| POST | `/api/discovery/films/{film_id}/study` | Local public; hosted bearer + quota | `{"question":"…"}`; optional personal DeepSeek header | Complete study with redacted observability, credential source and hosted quota remainder |
| POST | `/api/discovery/films/{film_id}/study/stream` | Hosted bearer | Same JSON and optional personal DeepSeek header | `text/event-stream`; run ID in response header |
| GET | `/api/research/runs/{run_id}` | Hosted bearer and run owner | Run UUID | Complete non-cacheable study; 409 running, 502 failed, 404 unknown/cross-owner/expired |

The synchronous route remains the local workflow and production fallback. Hosted browser clients use
the stream followed by the result route. A completed study contains:

```json
{
  "observability": {
    "schema_version": 1,
    "status": "completed",
    "stages": [
      {
        "name": "packet_assembly",
        "status": "completed",
        "duration_ms": 1.25,
        "attempts": 1,
        "failures": 0
      }
    ],
    "counts": {
      "theory_sources": 4,
      "model_calls": 1,
      "prompt_tokens": 4200
    }
  }
}
```

The real array always contains the twelve ordered stages from film context through end to end.
Statuses are `completed`, `failed`, `degraded`, `skipped` or `not_run`. Count keys are restricted to
retrieval plan/candidate totals, evidence-layer totals, attributed candidate/omission/truncation
counts, prompt characters, model/repair calls, provider-reported token totals and output sections.
Prompts, excerpts, credentials, responses and exception text have no field. Failed runs retain their
trace only in a redacted server log and keep
the existing safe HTTP/SSE error contract.

Study request:

```http
POST /api/discovery/films/wikidata:Q1056853/study/stream
Authorization: Bearer <supabase-access-token>
Content-Type: application/json

{"question":"How does constrained framing organise offscreen space?"}
```

The stream is marked `no-store, no-transform`, disables proxy buffering and uses only `progress`
events:

```text
event: progress
data: {"run_id":"…","kind":"evidence_assessed","sequence":3,"message":"The evidence boundary is ready for synthesis.","elapsed_ms":42,"counts":{"theory_sources":4,"critical_claims":8}}
```

#### SSE event dictionary

| `kind` | Public meaning |
|---|---|
| `film_resolving` | Confirm selected identity |
| `film_needs_choice` | A bounded user choice is required |
| `existing_evidence_loading` | Load permitted existing evidence |
| `research_planning` | Plan one bounded research action |
| `tool_started` | Start one authorised public-provider call |
| `tool_completed` | Provider call completed |
| `tool_failed` | Provider call failed without exposing raw exception text |
| `evidence_assessed` | Typed evidence boundary is ready |
| `study_drafting` | Structured synthesis is running |
| `quality_checked` | Deterministic checks completed |
| `study_repairing` | Single permitted repair is running |
| `run_completed` | Separate result is ready |
| `run_failed` | Run stopped at a redacted public boundary |

Allowed event fields are `run_id`, `kind`, `sequence`, `message`, `elapsed_ms` and optional
`counts`. Allowed count keys are `theory_sources`, `critical_claims`, `attributed_sources` and
`sections`. Event messages are selected from a server-side allow-list. Prompts, credentials, private
passages, review bodies, model output and hidden reasoning have no stream field.

The result store retains at most 50 runs for ten minutes in one API process. A complete result is
not durable across restart and cannot be read by another API instance.

### Clip analysis

| Method | Path | Access | Multipart fields | Success response |
|---|---|---|---|---|
| POST | `/api/analyze` | Feature gated; enabled locally by default | `video` required; `scene_sensitivity` default 6; `shot_threshold` default 0.35; `include_object_detection` default true; `include_shot_scale` default true | `meta`, `global`, `shots`, `scenes` and `outputs` |

The upload is written to a temporary file, analysed and removed in `finally`. Hosted mode returns
503 unless `FIRSTROLL_VIDEO_ANALYSIS_ENABLED` is explicitly enabled. Current public product policy
keeps it disabled because the computer-vision dependency and compute surface are too large for the
beta service.

## Rate and Cost Boundaries

- Hosted Deep Study: three reserved calls per authenticated account per UTC day.
- Public demo: thirty reserved calls across all accounts per UTC day.
- Reservation occurs before DeepSeek. A later provider timeout still consumes the reservation.
- Provider adapters have bounded request timeouts and response sizes in code, but no shared public
  request-rate table is currently implemented.
- Render may impose platform-level request and cold-start limits outside FirstRoll's API contract.

## Compatibility Rules

1. Additive response fields are allowed within the `0.1.x` prototype.
2. Removing or renaming a field, endpoint, event kind or error meaning requires an API version
   decision and an update to this document.
3. Private local routes must remain absent in public mode rather than relying on UI hiding.
4. New progress fields or messages must pass the explicit allow-lists and privacy tests.
5. Any new durable endpoint data must first be described in [Data Model](DATA_MODEL.md).
