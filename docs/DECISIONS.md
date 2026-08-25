# FirstRoll Architecture Decision Register

**Decision owner:** FirstRoll maintainer  
**Last reconciled:** 21 August 2026

This register captures the major decisions that shape the current product. It does not attempt to
record every CSS or parsing implementation detail. A choice belongs here when changing it would
alter trust boundaries, persistence, deployment, evidence semantics, provider policy, cost or the
public API.

## Decision Index

| ADR | Decision | Status | Main trade-off |
|---|---|---|---|
| 001 | Evolve pyCinemetrics with preserved attribution | Accepted | Faster foundation versus inherited complexity |
| 002 | Local-first private edition plus constrained hosted beta | Accepted | Private depth versus public convenience |
| 003 | Split static frontend and FastAPI service across Azure and Render | Superseded by ADR-015 | Explicit boundary and fast shell versus multi-platform configuration |
| 004 | Use Wikidata identity and explicit ambiguity confirmation | Superseded by ADR-018 | Correct identity versus one-click speed |
| 005 | Use bounded provider adapters, not unconstrained LLM browsing | Accepted | Provenance and control versus breadth |
| 006 | Type evidence by epistemic role | Accepted | Honest uncertainty versus simpler prose generation |
| 007 | Keep private RAG in local SQLite FTS5 and embeddings | Accepted | Privacy and portability versus shared hosted search |
| 008 | Use DeepSeek structured output, deterministic validation and one repair | Accepted | Reliability versus latency and model cost |
| 009 | Use Supabase bearer verification and atomic quota RPCs without service-role keys | Superseded by ADR-016 | Least privilege versus an extra network dependency |
| 010 | Stream allow-listed SSE progress and fetch the full result separately | Accepted | Privacy and authentication versus transient run state |
| 011 | Keep the bounded LangGraph Agent behind a production gate | Accepted | Measured benefit versus premature orchestration complexity |
| 012 | Keep clip analysis local in the public beta | Accepted | Privacy and feasible hosting versus no hosted visual analysis yet |
| 013 | Make secondary providers optional and independently degradable | Accepted | Resilience versus uneven evidence coverage |
| 014 | Avoid durable study/project storage in the beta | Accepted, temporary | Smaller data-risk surface versus no history/resume |
| 015 | Consolidate hosting on Azure and stage Entra External ID | Partially superseded by ADR-017 | Simpler cloud boundary versus customer-tenant and quota migration work |
| 016 | Decouple quota persistence from browser identity tokens | Accepted, deployment staged | Provider portability versus a protected backend database credential |
| 017 | Keep Supabase Auth and add RLS-owned account data | Accepted | Low-cost persistence versus an additional managed platform boundary |
| 018 | Use TMDb as the optional primary catalogue with an open fallback | Accepted | Rich, fast metadata versus one optional credential and attribution duty |
| 019 | Keep transient Discover continuity in per-tab session storage | Accepted | Refresh resilience versus bounded browser-local staleness |

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
- Some features intentionally differ between the Render and local editions.

### Revisit when

Encrypted user-owned storage, deletion policy, consent and operating budget justify hosted private
projects.

## ADR-003: Split static frontend and FastAPI service across Azure and Render

**Status:** Superseded by ADR-015
**Date:** 15 August 2026

### Context

The frontend should load even when a free backend instance is asleep. The API also needs Docker for
Python and the optional Douban MCP runtime.

### Decision

Deploy the browser bundle through Azure Static Web Apps and FastAPI as a separate Render Docker Web
Service from `master`. Inject the API origin at static build time and configure exact CORS origins
in the API. Define the planned Render-to-Azure Container Apps migration in Terraform without
importing the existing Static Web App during the first infrastructure milestone.

### Options considered

| Option | Assessment |
|---|---|
| One combined Web Service | Simpler origin model, but every page load waits for backend cold start |
| Separate Azure static and Render API services | Faster shell and explicit boundary; requires CORS and multi-platform operations |
| Serverless functions | Poor fit for heavyweight Python/provider runtime and longer study requests |

### Consequences

- Public values are supplied to Azure's frontend build and the Render backend with different
  variable names.
- Bearer and request-scoped-key headers must be explicitly allowed by CORS.
- The backend root identifies the API instead of serving a second visitor website.

### Revisit when

The Container Apps migration is complete and `api.firstroll.app` has passed the rollback window.

## ADR-004: Use Wikidata identity and explicit ambiguity confirmation

**Status:** Superseded by ADR-018
**Date:** 15 August 2026

### Context

Film titles are not unique. Choosing the first search result can attach reviews, crew, videos and a
study to the wrong work.

### Decision

Use Wikidata IDs as the canonical discovery identity, validate title/year/director signals and
require a bounded browser choice whenever more than one candidate remains. IMDb identity is used
where available to reconcile provider records. When an IMDb claim is absent, a title-derived
provider candidate is accepted only if its structured title, release year and director all match the
canonical film; a provider-local title alone remains insufficient.

### Alternatives considered

| Option | Risk |
|---|---|
| Always choose first result | Fast but silently wrong for remakes and reused titles |
| Ask the model | Non-deterministic and difficult to audit |
| Explicit identity confirmation | One extra action but preserves downstream provenance |

### Consequences

- Discovery can interrupt instead of pretending certainty.
- Every downstream bundle is keyed to a canonical film ID.
- Optional poster coverage can use a verified title-derived page without relaxing the canonical
  identity boundary.
- Multilingual title matching remains a provider-adapter responsibility.

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

Use DeepSeek Pro by default for the local study, request a Pydantic-compatible structure, validate
citations, score specificity/calibration/mechanisms deterministically and permit at most one repair.
Generic wording and weak causal signalling lower quality scores; missing mechanisms and unsupported
central assertions remain blocking.

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

**Status:** Superseded by ADR-016
**Date:** 15 August 2026

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

**Status:** Accepted  
**Date:** 18 August 2026

### Context

LangGraph can make tool choice, interrupts and bounded recovery explicit, but installing a framework
does not prove better answers. Agency adds latency, cost, persistence and failure surface.

### Decision

Implement and test the graph core with fake service interfaces, deterministic tool authorisation,
bounded reducers and explicit terminal states. Keep the fixed workflow as production and fallback
until a real adapter runs the same frozen cases and demonstrates a justified gain.

**24 August 2026 update:** after the fixed-workflow entry gate passed, the owner authorised a
fail-closed local adapter and paired evaluation only. The adapter may acquire ephemeral attributed
sources for a diagnostically limited packet and must skip planning for a passing packet. No HTTP
route, hosted execution or production cut-over is authorised; the original decision boundary remains
in force until the frozen comparison passes and receives separate review.

**24 August 2026 outcome:** the fixed control completed 5/5, while the Agent completed 4/5 and fell
below the 96.94 mean-quality floor. Although one bounded Letterboxd acquisition improved the target
packet's automated sufficiency, the predeclared candidate failed. Production Agent integration is
therefore NO-GO and the fixed workflow remains authoritative.

**25 August 2026 revision:** the owner approved a successor text-only implementation, not a cut-over.
The graph now owns one initial generation and at most two repairs; the model service makes no hidden
repair for Agent runs. A future evaluator acquires once, freezes both packets and runs three samples
per lane through the same retry controller, alternating order and retaining failures as zero. This
isolates packet content from synthesis orchestration. Because the full run costs 30–90 synthesis
calls, paid execution remains separately budget-gated. Claim review, genuine diversity review,
targeted section editing and filmmaker coaching follow in that order; clip work is deferred.

**25 August 2026 revised outcome:** after separate budget approval, both lanes completed 15/15 and
Agent mean quality exceeded fixed by 0.63 points. Two Agent-owned retries recovered invalid initial
generations, but raised P50/P95 ratios to `1.100404/1.993109`, failing both frozen latency limits. The
authorisation is consumed, no human packet review occurred and later text stages remain blocked.

**25 August 2026 latency revision:** continue T01 without paid calls, but preserve the failed result
and thresholds. A parseable invalid response may remain in process memory long enough for the graph
to request at most four exact field updates with an 800-token cap. Deterministic code merges the
patch and revalidates the whole study; safe telemetry records category and strategy only. Agent
initial temperature becomes `0`, while fixed production remains `0.2`. This is not evidence of a
latency improvement.

**25 August 2026 validation budget:** the owner approved one complete structural-repair comparison:
30–90 synthesis calls, at most ten planner calls and at most ten provider calls. The confirmation is
distinct from the consumed historical budget and does not authorise T02 or production routing.

### Alternatives considered

| Option | Assessment |
|---|---|
| Immediate Agent cut-over | Fast demonstration, no trustworthy comparison |
| Never use an Agent | Simpler, cannot adapt research actions to evidence gaps |
| Feature-gated measured adoption | More work, evidence-based decision |

### Consequences

- The repository contains an Agent core that is not falsely described as the public execution path.
- Production adapters, durable checkpoint ownership and Agent evaluation remain required.
- Model-proposed tools never bypass deterministic authorisation.

## ADR-012: Keep clip analysis local in the public beta

**Status:** Accepted  
**Date:** 15 August 2026

### Context

Clip analysis uses large computer-vision dependencies, user-supplied media and potentially long CPU
or GPU work. The hosted Container App has an ephemeral filesystem and deliberately bounded compute.

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

Keep Wikidata film identity independent of criticism. Represent provider readiness and failure in
the UI, cache each bundle separately and let Deep Study proceed with available evidence or report
insufficiency.

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

**Status:** Partially superseded by ADR-017; Azure hosting decision remains accepted
**Date:** 20 August 2026

### Context

The frontend already ran on Azure Static Web Apps while FastAPI ran on Render. This introduced two
deployment control planes, a backend cold start and an API address tied to a hosting provider.
Supabase magic-link authentication also does not match the desired public email-and-password
account experience. The current Azure login belongs to an NUS workforce tenant and cannot be used
as the public customer directory.

### Decision

Run FastAPI on Azure Container Apps behind `api.firstroll.app`, retain the static frontend at
`firstroll.app`, and manage both Azure services with Terraform. Keep Spaceship as DNS and preserve
Render temporarily as a rollback target.

Stage Microsoft Entra External ID as a second, explicitly selected authentication provider. The
target requires a customer tenant, separate SPA and API registrations, an email/password user flow
and the delegated `access_as_user` scope. Keep Supabase active until the customer tenant exists and
quota persistence no longer relies on a visitor's Supabase token.

### Options considered

| Option | Assessment |
|---|---|
| Keep Azure frontend, Render API and Supabase Auth | Lowest immediate effort, but retains two cloud control planes, the old API domain and magic-link UX |
| Move API to Azure but keep Supabase indefinitely | Improves hosting and removes cold start; does not meet the requested account experience |
| Move hosting to Azure and stage External ID separately | Gives a stable Azure topology while preserving a safe, independently reversible identity migration |
| Use the NUS workforce tenant | Rejected: it is not controlled as a public customer directory and current account lacks tenant administration permission |

### Consequences

- `firstroll.app` and `api.firstroll.app` are stable product domains independent of a Render service
  name.
- Azure Container Registry stores immutable API images; a managed identity pulls them without an
  ACR password.
- One warm Container App replica removes the former free-tier wake delay but incurs ongoing cost.
- Entra access-token validation is implemented but inactive, so the current Supabase login keeps
  working throughout the migration.
- An External ID customer tenant and a replacement quota persistence boundary are mandatory before
  activation.
- The browser and API provider switches must be deployed together; no client secret belongs in the
  SPA.

### Revisit when

Entra External ID becomes materially necessary for the product rather than merely useful as a
learning exercise. Any future activation must rerun the authentication, persistence and quota
acceptance suite before replacing Supabase Auth.

## ADR-016: Decouple quota persistence from browser identity tokens

**Status:** Accepted; deployment staged
**Date:** 20 August 2026

### Context

The original quota RPC derived `auth.uid()` from a Supabase bearer token. That was least-privilege
for the first beta, but it coupled paid-operation accounting to one identity product. An Entra
access token cannot authorise a Supabase authenticated-only RPC, and forwarding visitor tokens into
persistence expands the trust boundary.

### Decision

Introduce an identity-neutral PostgreSQL quota function and a backend-owned connection. FastAPI
first verifies the access token, then passes only a normalised identity provider and immutable
subject to `deep_study_quota_decision`. Keep the three-per-account and thirty-global UTC limits and
the transaction-scoped advisory lock.

Run the schema on Supabase PostgreSQL initially if that avoids a new database charge. The same
migration can later run on Azure Database for PostgreSQL. Select persistence explicitly with
`FIRSTROLL_QUOTA_PROVIDER`; retain the old Supabase RPC only for a bounded rollback period.

### Options considered

| Option | Assessment |
|---|---|
| Keep the visitor-token Supabase RPC | Cheapest short term, but blocks an Entra migration and couples identity to quota storage |
| Use a Supabase service-role REST key | Identity-neutral, but grants a broad backend credential and retains a provider-specific API |
| Use generic PostgreSQL with a restricted login | Portable and narrow at the SQL boundary; introduces a backend secret and connection management |
| Store counters in Container Apps memory | No database cost, but loses state and breaks under restart or multiple replicas |

### Consequences

- Supabase and Entra identities share one quota contract without sharing identifier namespaces.
- Quota rows use `(usage_day, identity_provider, subject)` rather than a foreign key to
  `auth.users`.
- The database sees no bearer token, email, prompt, film, evidence or generated study.
- A dedicated login needs only schema usage and function execute permission; the security-definer
  function owns table access.
- The database URL becomes a protected backend credential. It is stored as a Container Apps secret
  and, during this stage, in encrypted remote Terraform state; Azure Key Vault is the next
  hardening step.
- Daily counters need no historical account migration. The cut-over should begin at a UTC boundary
  or accept that the first transition day can reset a small demo allowance.

### Action items

1. Install `database/migrations/202608200001_identity_neutral_deep_study_quotas.sql`.
2. Create the restricted `firstroll_backend` login and store its URL securely.
3. Switch quota storage while Supabase Auth remains active and test status, concurrency and 429s.
4. Observe a full UTC day, then activate Entra separately.
5. Remove the legacy RPC after its rollback window and move the database secret to Key Vault.

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

This retains a second managed platform alongside Azure, but avoids inventing an authentication
system and gives the browser a well-defined data-isolation mechanism. Provider-neutral quota code
from ADR-016 remains valuable for later database portability; it does not require an immediate
identity migration. The staged Entra implementation remains an optional architecture exercise,
not a production dependency.

### Consequences

- A user can create an account, sign in with a password, recover access and keep a durable saved
  film list across devices.
- Account deletion cascades application rows from the referenced `auth.users(id)` primary key.
- A policy mistake would be a cross-account data risk, so migration tests and RLS acceptance tests
  are release requirements.
- Saved films are durable; studies, evidence and personal provider keys are deliberately not.
- Supabase remains an operational dependency even though the frontend and API run on Azure.

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

## How to Add or Change a Decision

1. Add a numbered entry to the index with `Proposed` status.
2. State the constraint and at least two credible alternatives.
3. Record privacy, cost, reliability and maintenance consequences.
4. Link the implementation and acceptance evidence in `docs/PROGRESS.md`.
5. Mark the old ADR `Superseded` rather than rewriting its historical decision.
