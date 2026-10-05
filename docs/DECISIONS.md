# FirstRoll Architecture Decision Register

**Decision owner:** FirstRoll maintainer  
**Last reconciled:** 1 October 2026

This register captures the major decisions that shape the current product. It does not attempt to
record every CSS or parsing implementation detail. A choice belongs here when changing it would
alter trust boundaries, persistence, deployment, evidence semantics, provider policy, cost or the
public API.

Superseded and parked entries keep their number but are condensed to a short summary of context,
decision and why they no longer apply. Their full original text is in Git history, for example
`git show archive/azure:docs/DECISIONS.md`.

## Decision Index

| ADR | Decision | Status | Main trade-off |
|---|---|---|---|
| 001 | Evolve pyCinemetrics with preserved attribution | Accepted | Faster foundation versus inherited complexity |
| 002 | Local-first private edition plus constrained hosted beta | Accepted | Private depth versus public convenience |
| 003 | Split static frontend and FastAPI service across Azure and Render | Superseded by ADR-015, then ADR-027 | Explicit boundary and fast shell versus multi-platform configuration |
| 004 | Use Wikidata identity and explicit ambiguity confirmation | Superseded by ADR-018 | Correct identity versus one-click speed |
| 005 | Use bounded provider adapters, not unconstrained LLM browsing | Accepted | Provenance and control versus breadth |
| 006 | Type evidence by epistemic role | Accepted | Honest uncertainty versus simpler prose generation |
| 007 | Keep private RAG in local SQLite FTS5 and embeddings | Accepted | Privacy and portability versus shared hosted search |
| 008 | Use DeepSeek structured output, deterministic validation and one repair | Accepted | Reliability versus latency and model cost |
| 009 | Use Supabase bearer verification and atomic quota RPCs without service-role keys | Accepted; active quota default (sign-in method superseded by ADR-017) | Least privilege versus an extra network dependency |
| 010 | Stream allow-listed SSE progress and fetch the full result separately | Accepted | Privacy and authentication versus transient run state |
| 011 | Keep the bounded LangGraph Agent behind a production gate | Parked by ADR-026 | Measured benefit versus premature orchestration complexity |
| 012 | Keep clip analysis local in the public beta | Accepted | Privacy and feasible hosting versus no hosted visual analysis yet |
| 013 | Make secondary providers optional and independently degradable | Accepted | Resilience versus uneven evidence coverage |
| 014 | Avoid durable study/project storage in the beta | Accepted, temporary | Smaller data-risk surface versus no history/resume |
| 015 | Consolidate hosting on Azure and stage Entra External ID | Superseded by ADR-017 and ADR-027 | Simpler cloud boundary versus customer-tenant and quota migration work |
| 016 | Decouple quota persistence from browser identity tokens | Accepted; staged, not the active default | Provider portability versus a protected backend database credential |
| 017 | Keep Supabase Auth and add RLS-owned account data | Accepted | Low-cost persistence versus an additional managed platform boundary |
| 018 | Use TMDb as the optional primary catalogue with an open fallback | Accepted | Rich, fast metadata versus one optional credential and attribution duty |
| 019 | Keep transient Discover continuity in per-tab session storage | Accepted | Refresh resilience versus bounded browser-local staleness |
| 020 | Require autonomous Agent value against a deterministic baseline | Parked by ADR-026 | Honest capability evidence versus slower staged development |
| 021 | Activate autonomous value ablations sequentially | Parked by ADR-026 | Exact cost isolation versus parallel execution |
| 022 | Use native planner tool calls without delegating execution authority | Parked by ADR-026 | Standard protocol versus a deliberately policy-owned loop |
| 023 | Use third-party benchmark tools as bounded diagnostics, not product gates | Parked by ADR-026 | Broader standard metrics versus preserving causal and human evidence |
| 024 | Use GitHub environment review and Azure OIDC for backend delivery | Superseded by ADR-027 | Simpler least-privilege delivery versus trusting two managed platforms |
| 025 | Standardise release rules, not frontend/backend hosting | Partially superseded by ADR-027 | Consistent release evidence versus per-service recovery work |
| 026 | Park the autonomous research Agent programme | Accepted | A smaller, honest product surface versus losing in-tree Agent code |
| 027 | Retire Azure and host the public beta on one VPS | Accepted; live since v219 | Flat cost and one control plane versus a self-managed single point of failure |

## ADR-001: Evolve pyCinemetrics with preserved attribution

**Status:** Accepted  
**Date:** Project inception

### Context

pyCinemetrics already supplied working shot, colour, object and shot-scale analysis. Replacing it
would delay the film-study product and erase the lineage of the computational foundation.

### Decision

Develop FirstRoll as an independent evolution in the same Git history, retain the GPL-3.0 licence,
the `upstream` remote and explicit README attribution, while moving new web, discovery, research and
evidence code under the FirstRoll identity.

### Options considered

| Option | Benefit | Cost |
|---|---|---|
| Preserve and adapt upstream | Reuses tested film analysis and preserves history | Carries large dependencies and historical code style |
| Clean-room rewrite | Uniform architecture | High schedule risk and duplicated work |
| Treat upstream as a remote service | Isolates dependencies | Adds deployment and data-transfer complexity |

### Consequences

- Inherited algorithms remain attributable and reviewable.
- New code must coexist with heavyweight model assets and pragmatic fallbacks.
- Releases must preserve upstream notices and never push FirstRoll changes to `upstream`.

### Revisit when

Individual inherited modules can be replaced with verified, licence-compatible implementations
without losing measured behaviour.

## ADR-002: Local-first private edition plus constrained hosted beta

**Status:** Accepted  
**Date:** 15 August 2026

### Context

The deepest product requires private books, extracted text, embeddings, provider credentials and
film clips. A public site is still important for access, demonstration and film discovery.

### Decision

Maintain two explicit runtime modes. Local mode enables the private library, connector settings and
clip analysis. Hosted public mode publishes discovery, the native director shelf and authenticated
quota-bounded Deep Study, but returns 404/503 for private or expensive local features.

### Alternatives considered

| Option | Privacy | UX | Operational cost |
|---|---|---|---|
| Local only | Strong | Installation required | Low hosted cost |
| Upload all private material | Weakest | Seamless across devices | Highest storage/compliance cost |
| Two explicit modes | Strong for private material | Public discovery plus deeper local workflow | Moderate complexity |

### Consequences

- “Local-first” is a data-placement rule, not a claim that no website exists.
- Backend gates, not hidden buttons, enforce the mode boundary.
- Some features intentionally differ between the hosted and local editions.

### Revisit when

Encrypted user-owned storage, deletion policy, consent and operating budget justify hosted private
projects.

## ADR-003: Split static frontend and FastAPI service across Azure and Render

**Status:** Superseded by ADR-015, then by ADR-027
**Date:** 15 August 2026

- **Context:** the frontend had to load while a free backend instance slept, and the API needed
  Docker for Python and the optional Douban MCP runtime.
- **Decision:** serve the static bundle from Azure Static Web Apps and FastAPI as a separate Render
  Docker service, inject the API origin at build time and allow exact CORS origins only.
- **Why it no longer applies:** ADR-015 moved the API to Azure Container Apps and ADR-027 moved both
  origins to one server. The separate-origin boundary and exact CORS allow-list survive.

## ADR-004: Use Wikidata identity and explicit ambiguity confirmation

**Status:** Superseded by ADR-018
**Date:** 15 August 2026

- **Context:** film titles are not unique; taking the first search result can attach reviews, crew,
  videos and a study to the wrong work.
- **Decision:** key discovery on Wikidata IDs, validate title, year and director, reconcile providers
  through IMDb IDs where available, and require an explicit browser choice whenever more than one
  candidate remains.
- **Why it no longer applies:** ADR-018 made TMDb the optional primary catalogue with
  provider-qualified IDs and kept Wikidata/Wikipedia as the key-free fallback. Explicit ambiguity
  confirmation remains in force.

## ADR-005: Use bounded provider adapters, not unconstrained LLM browsing

**Status:** Accepted  
**Date:** 8–14 August 2026

### Context

Critical writing comes from sources with different APIs, markup, identity conventions and failure
modes. Asking a model to “research the web” would obscure provenance and make cost, safety and
reproduction difficult.

### Decision

Implement one bounded adapter per provider, with an identity check, response-size/time boundary,
normalised attributed record and typed failure. Retrieval and model-based structuring are separate
operations.

### Alternatives considered

| Option | Provenance | Maintenance | Coverage |
|---|---:|---:|---:|
| Model browsing | Weak | Hidden provider coupling | Broad but unpredictable |
| One generic scraper | Medium | Brittle shared parser | Uneven |
| Provider adapters | Strong | More explicit code | Bounded and testable |

### Consequences

- Markup changes can break one source without breaking the platform.
- Provider details and repair techniques are documented independently.
- Acquired reviews remain secondary evidence, never direct observation.

## ADR-006: Type evidence by epistemic role

**Status:** Accepted  
**Date:** 12 August 2026

### Context

A film record, textbook framework, critic interpretation, creator statement, measured clip and model
hypothesis do not support the same claims. A single untyped context block encourages fluent
overstatement.

### Decision

Build an inspectable `EvidencePacket` with explicit evidence types, source IDs, locators, permitted
claims and boundaries. Require the final study to distinguish critic reports, theory explanations,
hypotheses, mechanisms, alternatives and verification tasks.

### Alternatives considered

| Option | Assessment |
|---|---|
| Concatenate all text | Simplest prompt, weakest epistemic control |
| Retrieval metadata only | Better attribution but no permitted-claim boundary |
| Typed evidence packet | More schema work, strongest validation and inspectability |

### Consequences

- Citation validators can reject invented source IDs.
- Theory can define a concept but cannot prove that a film uses it.
- Without clip evidence, formal claims remain viewing hypotheses.

## ADR-007: Keep private RAG in local SQLite FTS5 and embeddings

**Status:** Accepted  
**Date:** 7–12 August 2026

### Context

The source books are private and potentially copyrighted. Retrieval needs page citations,
multilingual semantics and a distributable setup without a hosted vector account.

### Decision

Extract and chunk PDFs locally, store canonical chunks in SQLite, use FTS5 BM25 plus optional local
Sentence Transformer embeddings, fuse rankings and return page-cited excerpts. Rebuild atomically
and exclude all derived data from Git.

### Options considered

| Option | Privacy | Operations | Search quality |
|---|---:|---:|---:|
| Hosted vector database | Lower | Account/service required | Strong semantic search |
| FTS5 only | Strong | Simple | Weaker multilingual conceptual matches |
| Local hybrid index | Strong | Larger first build | Lexical plus multilingual semantic recall |

### Consequences

- First build may download and load an embedding model.
- SQLite is excellent for one device, not a shared multi-user corpus.
- EPUB/Markdown/text can be catalogued, while the current extractor indexes PDFs.

## ADR-008: Use DeepSeek structured output, deterministic validation and one repair

**Status:** Accepted  
**Date:** 7–18 August 2026

### Context

Early prose was generic and difficult to verify. Free-form retries could increase cost without a
clear acceptance boundary.

### Decision

Use DeepSeek Pro by default in both editions (`deepseek-v4-pro`, overridable with `DEEPSEEK_MODEL`),
request the Pydantic `GroundedStudy` structure, validate citations, score
specificity/calibration/mechanisms with the deterministic `StudyQualityGate` and permit at most one
repair: a schema retry or a quality repair, never both, so a study makes no more than two model
calls. Generic wording and weak causal signalling lower quality scores; missing mechanisms and
unsupported central assertions remain blocking.

### Alternatives considered

| Option | Assessment |
|---|---|
| Free-form article | Natural presentation but weak machine validation |
| Reject every wording defect | High false-rejection rate |
| Structured draft plus scored gate | More code, clearer distinction between prose quality and safety |

### Consequences

- A study can complete with explicit limitations instead of looping.
- Quality scores are proxies for structure and grounding, not proof that unseen film form is true.
- Model latency remains the largest fixed-workflow cost.

## ADR-009: Use Supabase bearer verification and atomic quota RPCs without service-role keys

**Status:** Accepted; the active default quota path. Passwordless sign-in was superseded by
ADR-017, and ADR-016 staged a portable alternative that is not active.
**Date:** 15 August 2026 (status corrected 1 October 2026)

### Context

Hosted model calls cost money and must be tied to real user sessions. Concurrent requests must not
overshoot account or demo limits. Shipping a service-role key would unnecessarily enlarge impact.

### Decision

Use Supabase passwordless email sessions, verify each bearer through Supabase Auth and call two
`authenticated`-only `SECURITY DEFINER` RPCs with the user's token and publishable key. Store only
UUID/day/counters. Serialise reservations with a per-day advisory transaction lock.

### Alternatives considered

| Option | Assessment |
|---|---|
| In-memory counters | Lost on restart and inconsistent across instances |
| Service-role writes | Powerful but violates least privilege |
| User-token RPCs | Durable, atomic and least privilege; adds Supabase dependency |

### Consequences

- Three account calls and thirty demo calls per UTC day are enforced atomically.
- A call is charged at reservation, even if DeepSeek later fails.
- Prompts and studies never enter Supabase quota tables.

## ADR-010: Stream allow-listed SSE progress and fetch the full result separately

**Status:** Accepted  
**Date:** 18 August 2026

### Context

Deep Study can take tens of seconds. The browser needs meaningful progress but must never receive
hidden reasoning, private passages, credentials or raw provider errors in a trace stream.

### Decision

Use an authenticated POST whose response body is SSE. Project internal work onto a fixed event and
message vocabulary. Store the complete result separately under a run UUID and owner UUID; require a
second authenticated GET after `run_completed`.

### Alternatives considered

| Option | Assessment |
|---|---|
| Poll only | Simple but less responsive and repeats requests |
| Native `EventSource` | Automatic reconnect but cannot attach the required bearer header cleanly |
| WebSocket | Unnecessary bidirectional operational surface |
| Fetch-readable SSE | Fits one-way progress and authenticated POST |

### Consequences

- Public progress has a small auditable schema and fixed copy.
- The result store is process-local, capped at 50 and expires after ten minutes.
- Durable or multi-instance runs require a new owner-scoped store and resume protocol.

## ADR-011: Keep the bounded LangGraph Agent behind a production gate

**Status:** Parked by ADR-026 (1 October 2026)
**Date:** 18 August 2026

- **Context:** LangGraph could make tool choice, interrupts and bounded recovery explicit, but a
  framework does not prove better answers, and agency adds latency, cost and failure surface.
- **Decision:** build a tested, default-off local graph core and keep the fixed workflow as production
  and fallback until a frozen comparison showed a justified gain. The Agent never had an HTTP route.
- **Outcome:** on 24 August the fixed control completed 5/5 and the Agent 4/5, below the 96.94
  mean-quality floor (NO-GO). The 25 August text-only successor completed 15/15 with +0.63 mean
  quality but failed both frozen latency limits (P50/P95 ratios 1.100/1.993). The structural-repair
  rerun passed its machine targets, but the changed packet's study scored 2.28 points below fixed
  and no human review was possible.
- **Why parked:** ADR-026 removed the programme from `master`; see tag `archive/agent-programme`.

## ADR-012: Keep clip analysis local in the public beta

**Status:** Accepted  
**Date:** 15 August 2026

### Context

Clip analysis uses large computer-vision dependencies, user-supplied media and potentially long CPU
or GPU work. The hosted API container has an ephemeral filesystem and deliberately bounded compute
(one 2 GB server since ADR-027).

### Decision

Enable `/api/analyze` locally by default and return 503 in public mode unless an explicit future
deployment enables it. Keep uploads temporary and remove them after analysis.

### Consequences

- Film clips remain on the user's machine in the supported workflow.
- The hosted product cannot yet provide scene-by-scene visual analysis.
- A future hosted design requires upload limits, job storage, deletion, malware/media validation,
  worker isolation and a cost model.

## ADR-013: Make secondary providers optional and independently degradable

**Status:** Accepted  
**Date:** 7–15 August 2026

### Context

Douban MCP and public-web adapters are unofficial; official APIs may require credentials or return no
match. Treating any one provider as core would make discovery fragile.

### Decision

Keep catalogue film identity (TMDb or Wikidata, ADR-018) independent of criticism. Represent
provider readiness and failure in the UI, cache each bundle separately and let Deep Study proceed
with available evidence or report insufficiency.

### Consequences

- A provider outage reduces breadth instead of taking down the film dossier.
- Results differ by configured credentials and current public availability.
- Provider-specific technical details and limitations must remain documented.

## ADR-014: Avoid durable study/project storage in the beta

**Status:** Accepted, temporary  
**Date:** 18 August 2026

### Context

Persisting prompts, evidence, studies, clips and notes would create deletion, ownership, retention,
export and breach responsibilities. The immediate goal is to validate study quality and workflow.

### Decision

Do not create hosted film-project or study-history tables yet. Keep only Supabase account/quota data
durable; keep final streamed results in a bounded ten-minute process store.

### Consequences

- Refreshing after expiry or backend restart loses the generated result.
- Horizontal scaling and resume are not supported.
- The data model remains small while product requirements are still changing.

### Revisit when

The product specifies project ownership, retention, deletion, export, encryption, multi-device sync
and the legal basis for retaining user-submitted material. Any replacement must include a migration,
RLS policy, owner checks, operational runbook and deletion tests.

## ADR-015: Consolidate hosting on Azure and stage Entra External ID

**Status:** Superseded: identity staging by ADR-017, Azure hosting by ADR-027
**Date:** 20 August 2026

- **Context:** the frontend ran on Azure Static Web Apps and FastAPI on Render: two control planes, a
  backend cold start and a provider-bound API address. Magic-link sign-in did not match the desired
  email-and-password experience.
- **Decision:** run FastAPI on Azure Container Apps behind `api.firstroll.app`, manage Azure with
  Terraform, keep Render briefly for rollback and stage Microsoft Entra External ID as a second,
  explicitly selected identity provider.
- **Why it no longer applies:** ADR-017 kept Supabase Auth, so Entra was never activated. The Azure
  Free Trial subscription was found disabled on 27 September 2026 and ADR-027 moved hosting to one
  server.
  Terraform and the Entra code were removed on 1 October 2026 (tag `archive/azure`). The stable
  `firstroll.app` and `api.firstroll.app` domains survive.

## ADR-016: Decouple quota persistence from browser identity tokens

**Status:** Accepted; staged and selectable, not the active default
**Date:** 20 August 2026 (reconciled 1 October 2026)

### Context

The original quota RPC derived `auth.uid()` from a Supabase bearer token. That was least-privilege
for the first beta, but it coupled paid-operation accounting to one identity product. A token from
another identity provider (Entra External ID was then being staged) cannot authorise a Supabase
authenticated-only RPC, and forwarding visitor tokens into persistence expands the trust boundary.

### Decision

Introduce an identity-neutral PostgreSQL quota function and a backend-owned connection. FastAPI
first verifies the access token, then passes only a normalised identity provider and immutable
subject to `deep_study_quota_decision`. Keep the three-per-account and thirty-global UTC limits and
the transaction-scoped advisory lock.

The migration (`database/migrations/202608200001_identity_neutral_deep_study_quotas.sql`) is
portable: it can run on Supabase PostgreSQL, avoiding a new database charge, or on any other
PostgreSQL service. Select persistence explicitly with `FIRSTROLL_QUOTA_PROVIDER`: `supabase`
(default, the ADR-009 RPC) or `postgres` (`PostgresQuotaClient`) with `FIRSTROLL_DATABASE_URL`.

**1 October 2026:** with Entra and Azure retired (ADR-027), the adapter and migration are kept as a
portable option. Production still uses the Supabase RPC; no cut-over has been verified, and the
former Entra-activation and Azure Key Vault steps are withdrawn.

### Options considered

| Option | Assessment |
|---|---|
| Keep the visitor-token Supabase RPC | Cheapest short term, but couples identity to quota storage |
| Use a Supabase service-role REST key | Identity-neutral, but grants a broad backend credential and retains a provider-specific API |
| Use generic PostgreSQL with a restricted login | Portable and narrow at the SQL boundary; introduces a backend secret and connection management |
| Store counters in API process memory | No database cost, but loses state and breaks under restart or multiple replicas |

### Consequences

- Any verified identity provider can share one quota contract without sharing identifier namespaces.
- Quota rows use `(usage_day, identity_provider, subject)` rather than a foreign key to
  `auth.users`.
- The database sees no bearer token, email, prompt, film, evidence or generated study.
- A dedicated login needs only schema usage and function execute permission; the security-definer
  function owns table access.
- Activation makes the database URL a protected backend credential. On the current server it would
  live only in the owner-only `.env` file, never in the repository.
- Daily counters need no historical account migration. The cut-over should begin at a UTC boundary
  or accept that the first transition day can reset a small demo allowance.

### Action items (if activated)

1. Install, or confirm, the migration on the chosen PostgreSQL service.
2. Create the restricted `firstroll_backend` login and store its URL in the server's private
   configuration.
3. Switch `FIRSTROLL_QUOTA_PROVIDER` while Supabase Auth remains active and test status,
   concurrency and 429s.
4. Observe a full UTC day before removing the legacy Supabase RPC.

## ADR-017: Keep Supabase Auth and add RLS-owned account data

**Status:** Accepted
**Date:** 20 August 2026
**Decider:** FirstRoll maintainer

### Context

The public beta needs ordinary email-and-password accounts and durable data that follows a user
between devices. The maintainer's personal Azure account is not eligible for the expected credit,
and an administrable Entra External ID customer tenant would add cost and setup work without
improving the current film-study experience. Supabase is already deployed, supports password auth
and supplies PostgreSQL plus row-level security on its free tier.

### Decision

Keep Supabase Auth as the production identity provider. Replace magic-link-only login with
`signUp()` and `signInWithPassword()`, preserve Supabase's browser session, and support password
recovery. Store FirstRoll application data in three public PostgreSQL tables:

- one profile per `auth.users` primary key;
- one preferences row per account;
- a user-owned saved-film collection keyed by canonical film identity.

Every exposed table enables RLS and grants access only to `authenticated`. Every policy compares
`(select auth.uid())` with `user_id`; `anon` receives no table privileges. A small, idempotent
`auth.users` trigger creates profile and preferences rows, and the migration backfills existing
accounts. The browser uses only the publishable key. Passwords stay inside Supabase Auth, while API
keys, prompts, evidence and generated studies remain outside these account tables.

### Options considered

| Option | Complexity | Cost | Portability | Current fit |
|---|---|---|---|---|
| Supabase Auth + RLS account tables | Low | Free-tier friendly | Moderate | Best: already deployed and directly solves persistence |
| Entra External ID now | High | Uncertain without credit | Azure-native | Poor until a customer tenant is justified |
| Custom auth in FastAPI | Very high | Infrastructure dependent | High | Rejected: credentials and recovery become FirstRoll's security burden |

### Trade-off analysis

This retained a second managed platform alongside Azure hosting, but avoids inventing an
authentication system and gives the browser a well-defined data-isolation mechanism.
Provider-neutral quota code from ADR-016 remains valuable for later database portability; it does
not require an immediate identity migration. The staged Entra implementation was an optional
architecture exercise, never a production dependency, and was removed with ADR-027.

### Consequences

- A user can create an account, sign in with a password, recover access and keep a durable saved
  film list across devices.
- Account deletion cascades application rows from the referenced `auth.users(id)` primary key.
- A policy mistake would be a cross-account data risk, so migration tests and RLS acceptance tests
  are release requirements.
- Saved films are durable; studies, evidence and personal provider keys are deliberately not.
- Supabase remains an operational dependency separate from the application host (Azure at the
  time; one server since ADR-027).

### Action items

1. [x] Add the password-account browser flow.
2. [x] Add profile, preference and saved-film tables with RLS policies.
3. [x] Add saved-film controls to dossiers and Settings.
4. [x] Apply `supabase/migrations/202608200002_persistent_accounts.sql` to production.
5. [ ] Run two-account isolation, refresh-session and password-recovery acceptance tests.

## ADR-018: Use TMDb as the optional primary catalogue with an open fallback

**Status:** Accepted
**Date:** 21 August 2026
**Decider:** FirstRoll maintainer

### Context

Wikidata and Wikipedia keep FirstRoll distributable without a catalogue credential, but film crew
coverage, poster availability and query latency are uneven. The catalogue must improve dossier
quality without making discovery depend on HTML scraping, an LLM choice or one mandatory vendor.
Same-title films must still interrupt for user confirmation, and secondary evidence adapters need a
stable IMDb identity whenever one exists.

### Decision

Use the official TMDb API as the primary catalogue only when a server-side Read Access Token is
configured. Search a bounded set of movie candidates, hydrate at most eight through four concurrent
detail requests with credits and external IDs appended, then deterministically validate title, year
and director. Keep the browser's explicit ambiguity confirmation. Key results as `tmdb:{id}` and
retain IMDb/Wikidata external IDs as reconciliation bridges.

Route `wikidata:` records to the existing adapter. If TMDb is unconfigured, use the open adapter as
the normal key-free path. If a configured TMDb search fails, expose degraded mode and fail over to
Wikidata/Wikipedia. Do not scrape IMDb. Preserve an interface boundary for a future licensed IMDb
adapter if enterprise requirements justify AWS Data Exchange access.

### Options considered

| Option | Quality and latency | Access and maintenance | Outcome |
|---|---|---|---|
| TMDb official API | Rich search, posters, credits and identity links; candidate calls parallelise well | One bearer token; attribution and commercial-use review required | Accepted primary |
| Wikidata/Wikipedia only | Open and key-free, but uneven credits and occasional slow relationship queries | Existing CC0/CC BY-SA adapter | Accepted fallback |
| IMDb official API | Authoritative real-time GraphQL title graph | AWS Data Exchange subscription, API key, SigV4 credentials and licensed access | Defer as enterprise adapter |
| OMDb | Simple lookup but shallower crew/poster coverage | API key plus published usage restrictions | Reject as primary |
| IMDb page scraping | Potentially broad visible data | Brittle markup, blocking and unclear application contract | Reject |

### Consequences

- Most configured searches gain high-quality posters, synopses, runtime and field-level crew data.
- Search uses one catalogue request plus at most eight concurrent detail requests; the cap protects
  latency and provider load while supplying directors for every displayed candidate.
- TMDb becomes an optional operational dependency, not a system-wide availability dependency.
- FirstRoll must display TMDb attribution and review commercial terms before monetising the product.
- A provider-qualified film ID replaces the assumption that every canonical ID is a Wikidata QID.
- IMDb and Wikidata external IDs remain evidence-routing hints, never proof of creator intention.

### Action items

1. [x] Add the TMDb settings connector and server-side connection test.
2. [x] Add bounded parallel search hydration, deterministic filters and director filmography.
3. [x] Add provider-qualified routing and Wikidata/Wikipedia failover.
4. [x] Add dossier attribution and provider-policy tests.
5. [ ] Record live p50/p95 catalogue latency after a token is configured and the hosted cache has
   observed representative same-title and non-English-title searches.

## ADR-019: Keep transient Discover continuity in per-tab session storage

**Status:** Accepted
**Date:** 21 August 2026
**Decider:** FirstRoll maintainer

### Context

Discover results previously existed only in JavaScript memory. Product-view buttons did not need to
replace the DOM, but a refresh always lost the query, selected shelf and browsing position. Saving
this transient workspace to an account would require authentication and create unnecessary durable
records; putting the complete result in a URL would be large and expose provider payloads through
history and sharing.

### Decision

Keep one versioned Discover snapshot and product-navigation record in `sessionStorage`. Persist only
public query and film-summary data, shelf readiness, an optional dossier film ID, active product view
and scroll offsets. Cap the snapshot at 500 KB, reject data older than twenty-four hours and restore a
completed shelf synchronously without repeating provider calls. If refresh interrupts a request,
restore the form and reissue only the latest query.

Do not store dossier bodies, criticism, reviews, studies, credentials, authentication tokens or
account data. Treat the snapshot as same-tab continuity rather than durable or cross-device history.

### Options considered

| Option | Assessment |
|---|---|
| JavaScript memory only | Keeps view switches cheap but cannot survive refresh |
| `localStorage` workspace | Survives browser restarts but leaves stale catalogue payloads indefinitely |
| URL-encoded state | Shareable, but too large for hydrated shelves and leaks data into history |
| Account-backed workspace | Cross-device, but requires sign-in and creates an unjustified durable-data boundary |
| Bounded `sessionStorage` | Survives refresh, clears with the tab session and needs no backend write; accepted |

### Consequences

- Discover, Analyse and Settings preserve their DOM and scroll position when switching.
- A refreshed tab returns to its active view with the prior Discover shelf available behind it.
- Completed search and related-film requests are not repeated solely because of refresh.
- Open dossier content is fetched again from its canonical ID rather than copied into browser storage.
- Schema, age, shape and size guards turn corrupt or obsolete snapshots into a clean initial state.

### Action items

1. [x] Persist and restore query, ambiguity choices, shelves and optional dossier identity.
2. [x] Preserve active product view and per-view scroll offsets.
3. [x] Add refresh and three-view Chromium acceptance coverage.
4. [ ] Revisit only if users need explicit cross-device projects rather than transient continuity.

## ADR-020: Require autonomous Agent value against a deterministic baseline

**Status:** Parked by ADR-026 (1 October 2026)
**Date:** 28 August 2026

- **Context:** the bounded Agent's single-provider choice could be reproduced by a simple rule, and
  several excerpts from one domain flipped a packet to `passed` without genuine source diversity.
- **Decision:** redefine the successor as an autonomous research-and-coaching Agent with typed
  evidence gaps, independent-origin recovery and separate acquisition, repair and changed-packet
  ablations. Model planning had to beat, or match with fewer actions, a deterministic no-model
  gap router over the same providers.
- **Outcome:** the harnesses and synthetic tests were built; provider, reliability and owner-attested
  evidence never followed.
- **Why parked:** ADR-026 (tag `archive/agent-programme`). The deterministic-baseline rule is one of
  its revival conditions.

## ADR-021: Activate autonomous value ablations sequentially

**Status:** Parked by ADR-026 (1 October 2026)
**Date:** 28 August 2026

- **Context:** the A01 acquisition and A02 repair ablations used different paid capabilities and
  denominators.
- **Decision:** activate them one at a time, each with an exact budget, fixed report paths and a
  private consumption lock written before the first paid action.
- **Outcome:** A01 used three planner and four provider calls, but both active lanes ended
  budget-exhausted with the evidence-class gap open. A02 produced 9/9 valid field patches versus 4/9
  valid regenerations, failing its regeneration-completion target. Corrected A01R/A02R harnesses
  were built but never funded.
- **Why parked:** ADR-026 (tag `archive/agent-programme`).

## ADR-022: Use native planner tool calls without delegating execution authority

**Status:** Parked by ADR-026 (1 October 2026)
**Date:** 28 August 2026

- **Context:** the local planner returned tool proposals as JSON inside ordinary assistant content.
- **Decision:** use DeepSeek's native `tools`/`tool_calls` with a single `target_gap` argument, treat
  each call as an untrusted proposal, build execution arguments from verified application state and
  never return raw provider output to the model as a `role: tool` message.
- **Outcome:** implemented with synthetic tests only; provider compatibility and planner value were
  never validated under a paid A01R run.
- **Why parked:** ADR-026 (tag `archive/agent-programme`). The fixed Deep Study workflow uses
  structured output without tool calls.

## ADR-023: Use third-party benchmark tools as bounded diagnostics, not product gates

**Status:** Parked by ADR-026 (1 October 2026)
**Date:** 31 August 2026

- **Context:** the bespoke evaluators lacked standard serving and model-task metrics, but GuideLLM
  and lm-evaluation-harness do not understand FirstRoll's packets, lane controls or human gates.
- **Decision:** pin both as `uvx` development tools, qualify them only against a loopback mock and
  never let them replace causal product gates or owner review.
- **Outcome:** mock qualification and a 12-case claim-support diagnostic were committed; no
  real-model or load profile ran.
- **Why parked:** ADR-026 removed the profiles, tasks and audit tooling with `evals/` (tag
  `archive/agent-programme`). FirstRoll makes no TTFT, throughput or Agent-quality claim.

## ADR-024: Use GitHub environment review and Azure OIDC for backend delivery

**Status:** Superseded by ADR-027
**Date:** 4 September 2026

- **Context:** a proposed HMAC Approval Broker was not runnable, and the backend workflow still used
  long-lived Azure and registry credentials.
- **Decision:** make the protected GitHub `production` environment the sole human approval authority
  and deploy immutable image digests through two narrowly scoped Azure OIDC managed identities, with
  exact revision checks and automatic image rollback.
- **Outcome:** activated on 4 September 2026, but no owner-approved proof deployment was recorded
  before the Azure subscription was found disabled on 27 September.
- **Why it no longer applies:** ADR-027 retired Azure (tag `archive/azure`). The single protected
  `production` environment gate, with no custom broker, carries forward unchanged.

## ADR-025: Standardise release rules, not frontend/backend hosting

**Status:** Partially superseded by ADR-027; the shared release rules remain in force
**Date:** 10 September 2026

- **Context:** the separate Azure frontend and backend workflows had different freshness,
  verification, retention and recovery behaviour.
- **Decision:** share a tested, standard-library release-receipt protocol binding source SHA,
  component, run, build attempt, payload hash and a seven-day approval expiry; fetch only reviewed
  control modules from the approved commit; refuse a stale revision after approval; retain evidence
  for 90 days; never cancel an active production deployment automatically.
- **Still in force:** these rules and `tools/release/protocol.py`, now used by the single
  `VPS Release` workflow together with `tools/release/vps.py`.
- **Retired by ADR-027:** the separate Azure workflows, frontend package recovery and the Azure-only
  manifest, risk, summary, frontend and CLI modules (tag `archive/azure`).

## ADR-026: Park the autonomous research Agent programme

**Status:** Accepted
**Date:** 1 October 2026
**Decider:** FirstRoll maintainer

### Context

ADR-011 and ADR-020–023 kept a default-off local LangGraph Agent, its evaluation harness and frozen
results beside the fixed Deep Study workflow. The Agent never had an HTTP route.

- None of the paid comparisons run from 24 August 2026 cleared its full gate: the paired run missed
  the quality floor, the text-only successor failed its latency limits, the structural-repair run
  lowered the changed packet's study score without human review, A01 exhausted its budget with the
  gap still open and A02 failed its regeneration-completion target.
- No evaluation budget was released after 31 August; the corrected A01R and A02R harnesses never ran.
  Production stayed NO-GO throughout.
- The Agent code, its evaluation harness and their tests consumed review and dependency effort on
  every change, while the open product work (live acceptance, responsiveness, persistence) lay
  elsewhere.

### Decision

Remove the programme from `master` and keep it recoverable at tag `archive/agent-programme`:
`local_research_agent`, `autonomous_runs`, `autonomous_agent`, `research_agent_contract`,
`autonomous_study`, `agent_evidence`, `research_graph/`, the Agent-only DeepSeek methods, the
evaluation, review and benchmark tools, `evals/`, their tests and the eight Agent and evaluation
documents. Drop `langgraph`.

The fixed workflow of ADR-008, with at most two model calls per study, is the only study path.
Packet-quality assessment (`app/backend/packet_quality.py`) stays a product feature; its synthetic
six-case fixture now lives at `tests/fixtures/packet_quality_cases.json`.

### Options considered

| Option | Assessment |
|---|---|
| Keep the Agent default-off in `master` | No code lost, but every change keeps paying review and dependency cost for an unused path |
| Fund another bounded A01R/A02R run | Could add evidence, but no budget was released and earlier runs showed no route to a product gain |
| Remove from `master` behind an archive tag | Smaller, honest product surface; revival needs a rebase onto current code; accepted |

### Consequences

- `FIRSTROLL_LOCAL_AGENT_ENABLED` and the `langgraph` dependency no longer exist.
- Historical outcomes remain summarised in ADR-011 and ADR-020–023 and recorded in
  `docs/PROGRESS_ARCHIVE_2026-08.md`. The frozen evaluation results, including the fixed-workflow
  baseline, the 21 August accessibility audit and the 12 September synthetic responsiveness report,
  are readable only from the tag.
- Claim audit, targeted editing and filmmaker coaching, which were Agent-programme stages, are not
  planned work.
- Archived code will drift from `master`; it is a reference, not a ready-to-run branch.

### Revival conditions

All must hold before any of it returns:

1. A named product question that the fixed workflow demonstrably cannot answer.
2. An owner-approved numeric budget for model calls, provider calls and human review, recorded
   before any paid call.
3. Restoration on a fresh `feat/` branch from current `origin/master`, reconciled with the current
   study service, with `langgraph` re-added deliberately.
4. Frozen comparisons against both the unchanged fixed workflow and a deterministic no-model
   baseline (ADR-020), including blinded owner packet review.
5. No HTTP route, hosted execution or durable checkpoint store until those comparisons pass and a new
   ADR accepts the result.

## ADR-027: Retire Azure and host the public beta on one VPS

**Status:** Accepted; live since v219 (29 September 2026)
**Date:** 28 September 2026 (hosting choice); 1 October 2026 (Azure code retired)
**Decider:** FirstRoll maintainer

### Context

- The Azure Free Trial subscription was found disabled on 27 September 2026. The Container Apps
  environment was suspended, `api.firstroll.app` timed out and `firstroll.app` returned 404; Supabase
  stayed active.
- Restoring Azure meant pay-as-you-go charges for Container Apps, Container Registry and Log
  Analytics. A later read showed the API resource in failed provisioning with nothing to recover.
- On 28 September the owner chose a rented server instead and by 29 September had bought a Tencent
  Lighthouse Starter instance in Singapore (2 vCPUs, 2 GB memory, 40 GB SSD). The owner approved the
  v219 launch on 29 September.
- Entra External ID had never been activated (ADR-017). Keeping Terraform, the OIDC identities and
  the Azure workflows would have left an unused, credential-bearing delivery path in the repository.

### Decision

Host the public beta on one server and remove the Azure path:

- **Stack (`infra/vps`):** Docker Compose runs Caddy and the API container. Caddy terminates TLS for
  `firstroll.app` and `api.firstroll.app`, serves the static release and proxies the API; separate
  origins and the exact CORS allow-list stay. `bootstrap.sh` prepares Ubuntu 24.04; `deploy.sh`
  releases, rolls back and reports status, switching the site only after the API reports the baked
  commit.
- **Release (`.github/workflows/vps-release.yml`):** a CI-gated build without production credentials
  pushes the API image to GitHub Container Registry and seals a receipt with
  `tools/release/protocol.py` and `tools/release/vps.py`. A human repository owner must approve that
  exact run in the protected `production` environment. The deploy job verifies the receipt before the
  deploy key is available, refuses a revision that is no longer current `master`, connects over a
  pinned SSH host key, deploys by image digest and checks the live site and API. A failed activation
  restores the previous state on the server; a failed live check triggers `deploy.sh rollback`.
- **Identity and quota:** Supabase Auth is the only provider (`FIRSTROLL_AUTH_PROVIDER` accepts only
  `supabase`); `EntraAuthVerifier`, `app/web/entra-auth.js`, `@azure/msal-browser`, the
  `ENTRA_*`/`FIRSTROLL_ENTRA_*` variables, the browser `authProvider`/`entra*` fields and PyJWT are
  removed. Quota uses the Supabase RPC by default; the portable PostgreSQL adapter of ADR-016 is
  retained.
- **Retired:** `infra/terraform`, the Static Web Apps and backend-release workflows, the Azure-only
  release modules and `app/web/staticwebapp.config.json`, all at tag `archive/azure`. Any local
  Terraform state is gitignored. Spaceship remains the DNS provider.

### Options considered

| Option | Assessment |
|---|---|
| Upgrade Azure to pay-as-you-go | Keeps the reviewed OIDC path, but adds ongoing multi-service charges and a failed API resource to rebuild |
| Use the server but keep the Azure code dormant in `master` | Easy return path, but two delivery stories, unused credential configuration and stale tests |
| One server, Azure archived at a tag | Flat prepaid cost and one control plane, at the price of a self-managed host; accepted |

### Consequences

- One server is a single point of failure: no autoscaling, no CDN, and a few seconds of API restart
  on every release while Caddy keeps serving the static shell.
- The deploy key is a long-lived credential, unlike the former OIDC exchange: its private half is
  held in the approval-bound `production` environment and on the operator's machine. Membership of
  the `docker` group is root-equivalent. Rotate the key if exposed.
- The host holds no durable product data. Accounts, saved films and quotas stay in Supabase, whose
  Free plan pauses a project after seven idle days and then breaks sign-in.
- Rollback needs the previous image and site directory; v219 was the first server release and had no
  rollback target. Stack, configuration and database rollback are not automated.
- Paid Deep Study stays disabled on the server until authenticated quota readiness is verified.
- Returning to Azure would mean restoring from `archive/azure` and re-reviewing every workflow,
  identity and credential.

### Revisit when

Sustained traffic, an availability target or a second region justifies managed hosting or a CDN, and
in any case before the server term ends on 29 September 2027.

## How to Add or Change a Decision

1. Add a numbered entry to the index with `Proposed` status.
2. State the constraint and at least two credible alternatives.
3. Record privacy, cost, reliability and maintenance consequences.
4. Link the implementation and acceptance evidence in `docs/PROGRESS.md`.
5. Mark the old ADR `Superseded by ADR-0NN` or `Parked`, keep its number and condense its body to
   a short summary of context, decision and why it no longer applies; Git history keeps the full
   text.
