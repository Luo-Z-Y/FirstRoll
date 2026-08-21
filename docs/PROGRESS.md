# FirstRoll Project Progress

### 21 August 2026 — Always-available native director shelf

Delivered:

1. Replaced the Three.js/WebGL room and Blender GLB with a native HTML/CSS filmography shelf that
   requires no graphics capability, module graph or model download.
2. Rendered the selected film synchronously with five designed loading cases, then replaced those
   placeholders in place with up to twelve verified directing works from one bounded fast request.
3. Made native poster images optional over title-and-year fallback covers, retained case selection
   and kept the responsive shelf at six columns on wide panels and three on narrow screens. A slower,
   best-effort request can upgrade additional posters without returning the shelf to loading.
4. Changed fast-provider failure from a missing or unavailable shelf into a stable one-film state:
   loading cases are removed, the selected edition remains and a visible retry can restart the request.
5. Added a separate shelf request identity so cancelled, retried or stale fast and poster-enrichment
   work cannot overwrite the latest film; enrichment failure leaves the ready shelf unchanged.
6. Removed the obsolete 3D runtime, vendored Three.js files, GLB and Blender build tool from the web
   package; the hosted build is now approximately 748 KB rather than 1.5 MB.

Acceptance evidence:

- all 174 automated tests, frontend JavaScript syntax, npm audit and repository whitespace checks
  pass;
- live local browser verification for *Interstellar* shows one selected case and five placeholders
  immediately, then twelve selectable cases with no console errors or horizontal overflow;
- the same browser run passes at 1,440-pixel desktop and 390-pixel mobile widths, while a synthetic
  provider failure leaves one selected case, no loading cases and a visible retry;
- the production build contains no 3D model, Three.js module or shelf-specific runtime file.

Known constraint:

- the expanded filmography still depends on Wikidata relationship coverage and availability; on a
  sparse or failed response the native shelf deliberately remains useful with the selected film only;
- optional poster enrichment may continue for up to sixty seconds after the shelf is ready, but it is
  cancellable and cannot restore loading or hide the native cases.

Next actionable work:

1. Observe the lighter shelf on the hosted CDN and retain the one-film fallback contract when the
   related-film provider is changed or cached more aggressively.

### 21 August 2026 — Hardened frontend CI/CD trust boundary

Delivered:

1. Made pull-request CI explicitly read-only, stopped checkout from persisting its token and pinned
   every GitHub, HashiCorp and Azure action to an immutable full commit SHA.
2. Replaced credentialled pull-request preview deployments with a production-only workflow that
   accepts a successful same-repository `master` push, checks out its exact approved SHA and refuses
   to deploy if a newer revision has reached `master`.
3. Isolated the frontend build, high-severity npm audit and bounded `dist` validation in an
   uncredentialled job that seals its output as an immutable, run-scoped artifact. A separate runner
   checks out no repository code and gives the token only to Azure's build-disabled upload step.
4. Rotated the Azure token out of repository-wide secrets and into a `master`-restricted GitHub
   `production` environment. Reduced the repository's default workflow token to read-only and
   enforced full-SHA action references with a narrow external-action allow-list.
5. Added workflow contract tests, cancellation and timeout bounds, weekly npm and Actions Dependabot
   checks, and operator documentation for the new deployment gate.

Acceptance evidence:

- the 175-test suite, action-workflow and YAML validation, JavaScript syntax, npm audit and repository
  whitespace checks pass locally;
- GitHub reports read-only default workflow permissions, mandatory action SHA pinning, the restricted
  `production` environment secret and no repository-wide Azure deployment secret;
- a successful `master` CI run triggers the production workflow, which uploads only the pre-built
  `dist` directory before `https://firstroll.app` is checked for the approved build.

Known constraint:

- the Azure action is SHA-pinned, but its pinned Dockerfile delegates to Microsoft's maintained
  `staticappsclient:stable` image; the remaining transitive image update boundary is controlled by
  Azure rather than this repository.

Next actionable work:

1. Review weekly Dependabot action and npm updates, retaining full-SHA pins and re-running the
   production smoke check before merging a supply-chain change.

### 21 August 2026 — Interruptible recent-film switching

Delivered:

1. Added an abort controller and monotonically increasing request identity to discovery search.
2. Made every new query abort the preceding title request and all active fast or enriched shelf
   requests before presenting its own progress state.
3. Suppressed abort errors and guarded every late response, so a provider that ignores cancellation
   still cannot replace the newest search results.
4. Kept the search control interactive while loading, allowing recent chips, edited queries or a
   repeated search to interrupt immediately.

Acceptance evidence:

- the 171-test suite, frontend JavaScript syntax and repository whitespace checks pass;
- a live rapid sequence of *The Thing* → *Crash* → *Interstellar* ends only on the *Interstellar*
  identity choices, with no stale progress panel, unavailable error or lingering busy state.

Concurrency contract:

- discovery is deliberately latest-request-wins; cancelled provider work may finish server-side, but
  its browser response is ignored and cannot mutate the active film interface.

### 21 August 2026 — Progressive director shelf loading

Delivered:

1. Split the director shelf into a bounded fast identity request and a non-blocking enriched-poster
   request, with separate browser caches and time budgets.
2. Rendered the fast director film list immediately with available artwork or designed fallbacks,
   then upgraded the live cases when enriched poster data arrived.
3. Prevented slow poster providers from replacing the entire shelf with an error after 28 seconds.
4. Collapsed the shelf column when even the fast identity request fails, retaining the selected film
   card without redundant failure copy or a full-height empty panel.

Acceptance evidence:

- the 170-test suite, frontend JavaScript syntax and repository whitespace checks pass;
- live *Interstellar* verification renders 12 director cases, upgrades 11 poster covers and exposes no
  “full shelf unavailable” text.

Resilience boundary:

- background poster enrichment is best-effort; film identity and designed cover fallbacks remain usable
  when an artwork provider is slow or unavailable.

### 21 August 2026 — Clearable local search history

Delivered:

1. Added an independent close control to every recent-search chip without nesting interactive
   buttons or changing the chip's search-again behaviour.
2. Added a compact clear-all action and removed the local-storage key when the history becomes empty.
3. Kept individual removal, complete clearing and later search additions synchronised between the
   rendered list, in-memory discovery state and browser-local persistence.
4. Updated the README to document the browser-only history controls and the director-only,
   front-facing poster shelf.

Acceptance evidence:

- frontend JavaScript syntax, the 170-test automated suite and repository whitespace checks pass;
- live browser inspection confirms five independently labelled dismiss controls, one clear-all control,
  no nested buttons and the intended compact visual treatment.

Privacy boundary:

- recent searches remain in the current browser's local storage and are not saved to a FirstRoll
  account or sent to the backend as history records.

### 20 August 2026 — README dual-runtime architecture graph

Delivered:

1. Replaced the README's older five-layer local pipeline diagram with the current dual-runtime
   topology: Azure Static Web Apps, Azure Container Apps, Supabase identity and RLS-owned account
   data, backend quota PostgreSQL, transient hosted study results and the local private edition.
2. Drew the hosted request path and private-runtime path in one Mermaid graph, including public
   provider acquisition, typed evidence assembly, DeepSeek structured synthesis, deterministic
   validation and the planned clip-to-study evidence bridge.
3. Updated the adjacent architecture explanation and stack table so they no longer describe the
   API as a Render service or imply that private books, vectors, secrets and clips enter the hosted
   runtime.

Acceptance evidence:

- the compact README graph agrees with `docs/ARCHITECTURE.md` on hosting, identity, persistence,
  quota and privacy boundaries;
- Mermaid node labels containing punctuation are quoted and every edge target is declared;
- Markdown whitespace and local-link validation pass.

Known constraint:

- the graph deliberately summarises the system; field-level persistence, API contracts and decision
  history remain in the linked architecture, data-model, API-reference and ADR documents.

Next actionable work:

1. Keep the README graph and `docs/ARCHITECTURE.md` in the same checkpoint whenever a deployment or
   trust boundary changes.

### 20 August 2026 — Persistent Supabase accounts

Delivered:

1. Kept Supabase as the production identity provider and replaced the magic-link-only interface
   with password sign-up, password sign-in, confirmation-aware account creation and password
   recovery. Supabase continues to persist and refresh the browser session.
2. Added a production migration for user profiles, preferences and saved films. Every record
   references `auth.users(id)` with cascading deletion; all exposed tables enable RLS and limit
   operations to `(select auth.uid()) = user_id`.
3. Added “Save to account” to film dossiers and a persistent saved-film collection in Settings,
   including removal and cross-device reload through the signed-in Supabase client.
4. Recorded ADR-017: Entra remains staged for learning or a later enterprise requirement, but is
   no longer on the public-beta critical path.

Acceptance evidence:

- static tests reject a regression to `signInWithOtp()` and require password sign-up/sign-in,
  session persistence and recovery;
- migration tests require all three RLS boundaries, Auth foreign keys, `anon` revocation and the
  new-user trigger;
- the production migration reports three RLS-enabled tables, ten policies, profile and preference
  backfills for both existing Auth users, and the new-user trigger;
- local PostgreSQL acceptance testing proves Account B sees only its own saved film, a cross-account
  insert is blocked, and Auth deletion cascades all three user-owned record types;
- frontend deployment, refresh-session and password-recovery browser acceptance remain.

### 20 August 2026 — Azure API cut-over and account-authentication staging

Delivered:

1. Published FastAPI through Azure Container Apps at `https://api.firstroll.app`, verified managed
   TLS, health, discovery and exact-origin CORS, and rebuilt the Azure Static Web Apps frontend with
   the stable API origin.
2. Imported the live API custom-domain association into Terraform. The production plan now reports
   no drift and protects both frontend and API domains from accidental destruction.
3. Staged a provider-selectable Microsoft Entra External ID implementation: MSAL in the browser,
   strict JWT issuer/audience/signature/scope validation in FastAPI and corresponding Terraform
   variables. Supabase remains the only active provider.
4. Chose email-and-password customer accounts rather than email OTP. Activation is blocked until an
   administrable External ID customer tenant exists.
5. Added an identity-neutral PostgreSQL quota adapter and migration. FastAPI now has a provider plus
   immutable-subject persistence contract, a dedicated backend connection path and a guarded legacy
   Supabase rollback adapter; Entra cannot be configured with the visitor-token quota RPC.

Acceptance evidence:

- `https://api.firstroll.app/api/health` returns HTTP 200;
- production discovery returns the expected canonical film for an exact title/year query;
- the deployed frontend runtime configuration points to `https://api.firstroll.app`;
- Terraform validates and reports `No changes` against the live Azure state;
- provider-selection and Entra-token tests pass while the production Supabase path remains intact.
- quota tests prove that the PostgreSQL boundary does not receive the browser bearer token and that
  the migration retains the atomic daily advisory lock.

### 19 August 2026 — Hosted architecture and technical reference pack

Delivered:

1. Corrected the product description from a merely local or deployment-ready application to a
   local-first system with an active Azure frontend and Render API. The documentation now treats
   “local-first” as a privacy and data-placement decision while describing the hosted browser/API
   boundary separately.
2. Split detailed technical material into linked, maintainable references: current architecture,
   complete HTTP/SSE API dictionary, Supabase/SQLite/JSON/in-memory data model, architectural
   decision register and evaluation contract.
3. Added field-level table designs for the Supabase quota schema and local retrieval index,
   including keys, constraints, RLS/RPC ownership, atomic reservation behaviour and persistence
   boundaries.
4. Added an endpoint-by-endpoint access, request, response and failure dictionary, plus the safe SSE
   event and header contracts. Local-only, bearer-protected, conditionally authenticated and
   feature-gated operations are now distinguished explicitly.
5. Recorded fourteen major product and architecture decisions with context, alternatives,
   consequences and revisit conditions. These cover lineage, dual runtime, Render topology, film
   identity, provider adapters, evidence types, local RAG, quality policy, Supabase, progress
   streaming, the gated Agent, clip locality, provider degradation and temporary result storage.
6. Removed the mutable baseline table from the README and made the newest reviewed JSON under
   `evals/results/` canonical. Added metric definitions, case-level results, limitations and a
   replacement procedure that prevents screenshots or copied prose from silently becoming a new
   baseline.

Acceptance evidence:

- every README documentation-map target exists and the repository tree lists the new references;
- the API dictionary covers every FastAPI route currently declared in `app/backend/main.py`;
- the data tables reconcile with the checked-in Supabase migration and local SQLite/index models;
- the Render deployment is documented as active without inventing service origins that are not
  versioned in the repository;
- the latest available raw evaluation artefact remains
  `evals/results/baseline-2026-08-18.json`; its recorded metrics are reproduced in
  `docs/EVALUATION.md` and no newer values were inferred from an image.

Known constraints:

- if a newer baseline has been run outside this repository, its complete redacted JSON report must
  still be added before it can replace the versioned 18 August baseline;
- the exact Render frontend and API origins are dashboard configuration and are not currently
  recorded in the repository;
- the decision register captures consequential architecture/product choices, not every visual or
  parser implementation detail.

Next actionable work:

1. Commit the next complete evaluation artefact and update only the canonical evaluation document.
2. Record the exact public origins in hosting documentation if stable publication of those URLs is
   desired.
3. Continue the production Agent comparison and clip-to-study evidence bridge under the documented
   decision and evaluation contracts.

### 19 August 2026 — README architecture and status reconciliation

Delivered:

1. Reconciled the README status with the implemented hosted boundary: Supabase authentication,
   atomic quota reservation and redacted SSE progress now appear as delivered capabilities rather
   than future prerequisites.
2. Updated the Agent boundary to distinguish completed fixed-workflow streaming and baseline work
   from the still-pending production graph adapter and like-for-like Agent evaluation.
3. Added an authenticated Deep Study sequence diagram covering bearer verification, the fixed
   workflow, public event projection, transient owner-scoped result storage and the separate result
   request.
4. Made the roadmap and known limitations explicitly retain the outstanding interactive browser
   observation and the process-local ten-minute run-store constraint.

Acceptance evidence:

- README architecture, API and roadmap statements now agree with the implementation and this
  progress log;
- Markdown whitespace validation passes and no runtime behaviour changed in this documentation
  checkpoint.

Next actionable work:

1. Complete the synthetic privacy observation in a human-opened localhost browser tab.
2. Replace the transient run store before multi-instance or resumable research execution.
3. Implement the production graph service adapter and compare it against the frozen baseline.

### 18 August 2026 — Authenticated, redacted browser research progress

Delivered:

1. Added an authenticated `POST /api/discovery/films/{film_id}/study/stream` endpoint for hosted
   Deep Study. Supabase bearer validation and hosted availability checks complete before an SSE
   response is created.
2. Added a strict public event projector with an allow-list for lifecycle kinds, bounded public
   messages, monotonic sequence numbers, elapsed time and four non-sensitive aggregate counts.
   Prompts, credentials, retrieved passages, review bodies, model output and hidden reasoning have no
   field in this contract.
3. Mapped provider and application exceptions to fixed public failure messages. Raw exception text
   cannot enter the stream even when it contains request credentials or private source material.
4. Kept the full result outside SSE. The browser retrieves it through
   `GET /api/research/runs/{run_id}`, which authenticates again, enforces run ownership and gives
   unknown and cross-account callers the same 404 response.
5. Updated the hosted browser to consume the POST response as a readable stream, show only each
   public progress message, require ordered events and fetch the final study separately. The local
   edition retains its existing synchronous route.
6. Kept the transport independent of the production Agent decision: it currently projects the
   deterministic Deep Study workflow and can later receive the bounded graph's safe lifecycle
   events without exposing graph state.

Acceptance evidence:

- authenticated integration coverage injects a synthetic personal DeepSeek key, private prompt,
  private book passage and synthetic hidden-reasoning field, then proves none appears anywhere in
  the SSE response while the separately authenticated result retains the private study payload;
- ownership coverage proves a second authenticated account receives 404 for the run, and failure
  coverage proves provider exceptions are redacted;
- public-contract coverage rejects arbitrary messages, event kinds and token-like counts, while frontend
  contract coverage verifies the streamed request, ordered parser and separate result request;
- all 142 automated tests pass; scoped Ruff, JavaScript syntax and whitespace checks pass.

Known constraints:

- the final result store is process-local, bounded to 50 runs and expires entries after ten minutes;
  durable, owner-scoped storage is required before multi-instance or resumable execution;
- this progress transport does not switch the public Deep Study route to the LangGraph Agent;
- the in-app browser automation client blocked programmatic localhost navigation during acceptance.
  A human-opened localhost tab is still required for the final interactive browser observation.

### 18 August 2026 — Bounded LangGraph research Agent core

Delivered:

1. Added LangGraph 1.2 to local and hosted dependency sets and locked version 1.2.11.
2. Preserved the framework-neutral research contract as the deterministic policy boundary around
   the graph rather than duplicating authentication, budget and tool-authorisation rules.
3. Implemented typed graph state, bounded reducers, safe public progress events, runtime-injected
   service interfaces, named nodes, conditional routing and explicit terminal states.
4. Split model-proposed tool choice from deterministic application authorisation and provider
   execution. Retrieved evidence remains untrusted data and cannot authorise an action.
5. Added bounded recovery for an unavailable provider, empty evidence, invalid planning and one
   failed quality pass. A repair can run only once.
6. Added optional LangGraph checkpoint compilation and verified that a completed thread is
   checkpointed without placing credentials or service clients in graph state.
7. Kept the current fixed Deep Study route unchanged as the production comparison and fallback.

Acceptance evidence:

- 18 focused contract-and-graph tests pass, covering existing evidence, ambiguous film identity,
  empty research, provider timeout recovery, malicious retrieved instructions, one-shot repair,
  repeated quality failure, invalid or out-of-policy planner output, final-budget authorisation,
  reducers, graph structure and checkpoint state;
- all 137 automated tests pass;
- the new graph, contract and tests pass Ruff, and the graph plus contract pass MyPy;
- the graph compiles with named nodes and runs entirely with deterministic fake services in CI.

Known constraints:

- the graph does not yet replace `POST /api/discovery/films/{film_id}/study`;
- production criticism, retrieval and DeepSeek adapters still need to implement the graph service
  protocol behind a feature flag;
- authenticated checkpoint ownership and durable production checkpoint storage remain pending;
- the Agent must run the frozen five-case evaluation before any public cut-over.

Next actionable work:

1. Implement a production `ResearchGraphServices` adapter over the existing discovery, evidence,
   criticism and study services.
2. Add a feature-flagged authenticated endpoint and safe SSE event projection.
3. Run the fixed workflow and Agent on the same golden cases, then retain the Agent only if its
   quality and recovery gains justify its latency, cost and operational complexity.

### 18 August 2026 — Fixed-workflow baseline for future Agent evaluation

Delivered:

1. Froze five representative film-study cases covering formal specificity without a clip,
   abundant secondary interpretation, multilingual identity, ambiguous-title resolution and
   sparse-evidence limitation.
2. Added a reproducible evaluator for the current fixed workflow. It records film identity,
   per-stage and end-to-end latency, operational failures, deterministic quality acceptance,
   repair use, citation validity, evidence coverage, DeepSeek call count and token usage.
3. Stored a non-secret configuration fingerprint with the result: DeepSeek Pro and YouTube were
   configured; Douban and official Letterboxd credentials were absent; the local index contained
   seven documents, 4,381 chunks and multilingual MiniLM embeddings.
4. Reclassified `generic_language`, `central_argument_generic` and `mechanism_not_causal` as scored
   quality defects rather than hard rejections. An accepted study receives the gate's 25 points in
   proportion to its raw score; unsupported central assertions and absent mechanisms remain blocking.
5. Kept operational and quality failure rates separate and documented that the automated score
   does not establish factual correctness for film form that has not been observed from a clip.
6. Reran the same five live cases after the policy change and preserved central and per-section
   gate diagnostics in the baseline artefact.

Baseline results:

| Measure | Result |
|---|---:|
| Cases completed | 4 / 5 |
| Operational failure rate | 20% |
| Quality-gate pass rate | 100% of completed studies |
| Quality acceptance failure rate | 0% of completed studies |
| Mean / median quality score | 98.94 / 99.5 |
| Mean end-to-end latency | 65.798 s |
| P50 / P95 end-to-end latency | 66.409 s / 96.451 s |
| Repair rate | 0% of completed studies |
| Model calls / total tokens | 4 / 46,950 |

Case results:

| Case | Quality | Gate | End-to-end latency |
|---|---:|---|---:|
| *Syndromes and a Century* — cinematography | 100 | passed | 77.212 s |
| *In the Mood for Love* — constrained space | 96.75 | passed | 31.080 s |
| *Memoria* — sound perspective | — | DeepSeek timeout | 101.261 s |
| *The Thing* — ambiguous identity | 99 | passed | 53.029 s |
| *We Are All Strangers* — sparse evidence | 100 | passed | 66.409 s |

Interpretation:

- the fixed workflow is operationally reliable on this small case set and resolved the deliberately
  ambiguous *The Thing* query to the 1982 John Carpenter film;
- all four completed studies passed; weak causal signalling remained visible as a deduction for
  *In the Mood for Love* and *The Thing* rather than triggering repair or rejection;
- *Memoria* received no quality decision because DeepSeek timed out after 91.759 seconds at the study
  stage; this is recorded as an operational failure, not a quality failure;
- quality scores, gate rates and repair rates now use completed studies as their denominator, while
  end-to-end latency and operational failure continue to include every attempted case;
- the five-case run is a functional baseline, not a statistically stable provider failure estimate.
  Any Agent comparison must reuse the case file and report its run count, configuration fingerprint
  and both failure rates.

Acceptance evidence:

- all 124 automated tests pass and the modified Python files pass Ruff;
- the live result is stored in `evals/results/baseline-2026-08-18.json` without credentials or private
  source excerpts;
- all five cases used the same fixed workflow and acceptance rubric intended for later Agent runs.

### 15 August 2026 — Ambiguous film identity confirmation

Delivered:

1. Replaced automatic first-result selection with an explicit confirmation step whenever discovery
   returns more than one possible film.
2. Added accessible candidate cards showing the poster, release year, director and original title so
   similarly named works can be distinguished before any dossier or related-film indexing begins.
3. Kept single-result searches immediate and prevented rejected same-title candidates from being
   treated as related films on the selected film's shelf.

Acceptance evidence:

- frontend contract coverage verifies that ambiguous searches cannot bypass the selection gate;
- browser acceptance with *The Thing* exposed four attributed candidates, selected the 1982 John
  Carpenter film and confirmed that the chooser was removed before the shelf opened;
- the narrow responsive check reported no horizontal overflow, and all 105 automated tests pass.

### 15 August 2026 — Non-blocking shelf loading

Delivered:

1. Decoupled the Blender/Three.js room from related-film indexing, so the first interactive frame
   appears while Wikidata relationships continue loading in the background.
2. Added a bounded fast path for shelf summaries: twelve results per relationship group, at most
   sixty hydrated candidate entities, no secondary labels, award descriptions, Wikipedia summaries
   or sequential Letterboxd poster fallbacks on the critical path.
3. Added backend related-film caching and a browser-session cache, with a fifteen-second request
   boundary and at most one retry instead of three unbounded attempts.
4. Made case construction synchronous and streamed poster textures onto existing cases, preventing
   a slow or unavailable image host from blocking the scene-ready state.
5. Preserved the full enrichment route for callers that explicitly need it; the fast shelf summaries
   are not written into the canonical film-detail cache, so opening a dossier still retrieves complete
   metadata.

Acceptance evidence:

- the previous cold related-film request exceeded thirty seconds; the bounded cold request measured
  10.24 seconds and the cached request measured 2.1 milliseconds;
- browser instrumentation showed the interactive room in 2.8 seconds, with twenty-six real cases
  completing in the background at 14.3 seconds and no console errors;
- all 104 automated tests pass, including fast-path caching, canonical-detail isolation and
  non-blocking poster regressions.

### 15 August 2026 — Hosted Douban MCP runtime

Delivered:

1. Added a Node 22 build stage to the production image and pinned `moria97/douban-mcp` to commit
   `1adc26d39532db893616ceb7ea851733948ae69e` for reproducible builds.
2. Copied only the built connector, production dependencies and Node runtime into the Python image.
3. Made authenticated Settings report the live hosted connector state while deliberately providing
   no Douban cookie or visitor-credential field.
4. Retained anonymous provider access and graceful degradation when Douban blocks or rate-limits the
   unofficial connector.

Acceptance evidence:

- the complete production image builds with zero reported npm production vulnerabilities;
- its cookie-free MCP handshake exposes `search-movie` and `list-movie-reviews`;
- an anonymous container lookup matched *In the Mood for Love* to Douban subject `1291557` and
  returned its live community score;
- the full application suite passes with 103 tests.

### 15 August 2026 — Authenticated public Settings and session integrations

Delivered:

1. Added a responsive hosted Settings view with verified Supabase account identity, live Deep Study
   quota status and explicit sign-in, refresh and sign-out controls.
2. Added optional personal DeepSeek and YouTube keys held only in JavaScript memory for one browser
   tab. They are cleared on refresh or sign-out, never persisted and sent only with the matching
   authenticated request.
3. Preserved the three-study daily account boundary for personal DeepSeek requests and added strict
   key syntax, length, CORS and authentication checks at the API edge.
4. Added Douban MCP as a visible local-edition integration with direct setup guidance while refusing
   Douban cookies on the hosted server.
5. Kept the private local Settings, library and clip-analysis routes unpublished.

Acceptance evidence:

- desktop and mobile production-build visual QA passed without horizontal overflow;
- request-scoped DeepSeek and YouTube keys, unauthenticated rejection, account status and quota
  reporting are covered by backend and frontend contract tests;
- Python lint, JavaScript syntax, production static build and the full suite pass with 102 tests.

### 15 August 2026 — Authenticated Deep Study quotas

Delivered:

1. Added an idempotent Supabase migration with private RLS-enabled daily counters, authenticated-only
   status and reservation RPCs, a fixed three-per-account limit and a thirty-per-demo global limit.
2. Serialised reservations per UTC day inside PostgreSQL, preventing concurrent requests from
   exceeding either limit without requiring a service-role key.
3. Added bounded FastAPI quota validation, HTTP 429 responses with reset timing and an explicit
   hosted feature switch that remains closed unless authentication, quotas and DeepSeek are all
   configured.
4. Replaced the hosted edition's unavailable private PDF index with four transparent, first-party
   formal-analysis frameworks; all generated film-form claims remain viewing hypotheses.
5. Added remaining account/global allowance to successful study results and retained the local
   private-library workflow unchanged.

Acceptance evidence:

- focused authentication and quota tests pass across reservation, account denial, malformed RPC
  response, public evidence and HTTP 429 paths;
- the full suite passes with 95 tests, together with Python lint, JavaScript syntax and whitespace
  checks;
- the paid feature remains fail-closed until the live Supabase migration and Render-only DeepSeek
  environment settings are verified.

### 15 August 2026 — Zoom-safe selected edition

Delivered:

1. Replaced the selected-edition card's viewport-only responsive assumption with a component-width
   container query, so the artwork and film copy collapse to one column before either reaches the
   inner frame.
2. Allowed the collection header, long film titles and dossier action to wrap without increasing
   their grid track or crossing the border at high browser zoom.
3. Bumped the hosted stylesheet asset version so Render visitors receive the corrected layout
   immediately after deployment.

Acceptance evidence:

- measured medium- and high-zoom-equivalent layouts keep the header, title, copy and button within
  the selected-edition panel;
- all 89 automated tests pass, including a regression for the component-width breakpoint.

### 15 August 2026 — Supabase authentication boundary

Delivered:

1. Added passwordless email sign-in and sign-out to the hosted frontend using a bundled Supabase
   browser client with PKCE and persisted user sessions.
2. Added a public `/api/auth/me` endpoint and a bounded FastAPI bearer-token verifier that resolves
   identities through Supabase Auth without accepting client-supplied user details.
3. Protected hosted Deep Study with authentication while retaining a second explicit quota gate;
   no paid model request can run until durable usage limits are enabled.
4. Kept the Supabase secret and service-role keys out of the design. Only the project URL and
   `sb_publishable_...` key may enter the static bundle or backend environment.
5. Extended the atomic hosted build and CI job to install and bundle the pinned authentication
   client, with validation for the public Supabase configuration.

Acceptance evidence:

- all 88 automated tests pass, including valid, missing, malformed and wrong-role token paths;
- hosted-mode tests confirm the public runtime config exposes only a publishable key;
- Deep Study returns HTTP 401 without a session and reaches the HTTP 503 quota gate only after a
  verified account is present.

Known constraint:

- authentication is ready, but hosted Deep Study remains disabled until the per-user and global
  quota tables are installed and enforced.

### 15 August 2026 — Public deployment acceptance fixes

Delivered:

1. Removed the brittle 50-title shelf gate: the 3D shelf now renders every distinct verified film
   returned by Wikidata instead of hiding the whole scene when one row contains fewer than ten.
2. Added stricter Bilibili identity checks so short translated-title collisions such as music
   albums, audio dramas and dance videos are not presented as film resources.
3. Added an explicit hosted YouTube configuration state, replaced the unavailable clip-analysis
   action with its **coming soon** state, and hid the local-only Settings link in public mode.
4. Preserved local Settings and clip analysis unchanged; connector secrets remain server-side and
   are not exposed through the unauthenticated public site.

Acceptance evidence:

- the live related-film endpoint returns real Wong Kar-wai, shared-cast, country and genre matches;
- the hosted API correctly reports YouTube as `credentials_required` and Douban as `not_installed`;
- all 83 automated tests pass, including regressions for partial shelf rows and short-title video
  collisions.

### 15 August 2026 — Deployment-ready public-beta shell

Delivered:

1. Added a Python 3.11 production Docker image and a bounded hosted dependency set that excludes
   TensorFlow, Torchvision, OpenCV, EasyOCR, TransNetV2 and the local embedding model.
2. Added an atomic static-site build that packages the existing HTML, CSS, JavaScript, Three.js,
   Blender GLB and runtime API configuration into a 1.5 MB `dist` directory.
3. Added explicit public-mode gates: remote settings and private-library routes return 404, while
   clip analysis and unauthenticated Deep Study return 503 before loading expensive code or keys.
4. Added exact-origin CORS configuration for the future Render Static Site without permitting a
   wildcard origin.
5. Added a public **Video analysis is coming soon** state while preserving the complete local
   analysis interface by default.
6. Reworked CI to install the same lightweight dependency manifest used by the production image and
   added hosted-mode regressions.
7. Added a click-by-click Render deployment guide that keeps the DeepSeek key absent until Supabase
   JWT verification and quotas are complete.
8. Added an uncached runtime-config endpoint, so hosted delivery reports public mode and
   **Video analysis is coming soon** while the local interface retains its complete analysis
   workflow.
9. Restored the explicit split requested for publication: the CDN-hosted frontend and sleeping API
   use separate origins, and the public API root returns service metadata rather than a duplicate
   website; the combined interface remains available only in local mode.

Acceptance evidence:

- the static production build completes and contains the app, local Three.js runtime and Blender
  model in a 1.5 MB output;
- a clean temporary Python environment installs only `requirements-hosted.txt`, imports the API and
  returns `{"status":"ok"}`;
- the Docker image builds successfully from `python:3.11-slim` and starts Uvicorn on Render's port;
- live container checks return HTTP 200 for health, HTTP 404 for the private library and HTTP 503 for
  unauthenticated Deep Study in public mode;
- all 80 automated tests pass, including 21 focused hosted, discovery and settings checks, together
  with backend compilation, scoped Ruff and both JavaScript syntax checks.

Known constraint:

- authenticated hosted Deep Study remains deliberately disabled until the Supabase milestone; the
  public deployment must not receive a DeepSeek key before that work is complete.

### 14 August 2026 — Compact archive refinement

Delivered:

1. Narrowed the physical Blender room from a wall-spanning archive to an intimate Criterion-style
   bay sized for 10–15 jewel cases across, with matching camera bounds, labels and live-case spacing.
2. Limited every curated live row to 15 cases and moved side-wall collections deeper into the aisle,
   leaving a calm doorway threshold instead of oversized foreground cases intersecting the camera.
3. Reworked the synthetic-looking block palette into translucent jewel shells with muted paper
   inserts, packed smoked-oak, plaster and carpet textures, softer brass and warmer controlled light.
4. Kept sparse data honest while fixing the one-case presentation bug: genuine titles appear first,
   then neutral non-selectable FirstRoll archive cases complete a minimum 12-case centre row.
5. Moved thinner brass plaques below and in front of all case geometry so title, collection and count
   text cannot be covered by a disc case or shelf edge.
6. Removed case collisions by deriving live-case width from a fixed 0.06-metre gap, keeping ambient
   cases upright with wider spacing and reserving an empty joint where side and rear shelves meet.
7. Corrected the remaining oblique-view overlap by reducing case depth from 0.34 to 0.13 metres,
   making Blender inserts paper-thin, removing the duplicate selection-outline mesh and replacing
   hover scaling with a smaller forward-only pull.

Acceptance evidence:

- the Anthony Chen / *Ilo Ilo* reproduction now renders 12 cases instead of one while retaining one
  genuine selectable film and 11 explicitly non-selectable archive fillers;
- the label reads `Anthony Chen · director & related`, sits below the case line and remains visible;
- the compact model loads as a 4.1 MB self-contained GLB, down from 6.1 MB;
- live browser validation confirms the rebuilt scene loads, reports 12 cases and has zero page-level
  horizontal overflow;
- close rear-wall and angled-corner checks show separated case silhouettes, clear hover expansion and
  no side/rear collection intersection;
- an exact *The Third Man* / Carol Reed close-up at the back-wall angle shows separate shallow cases,
  and the hovered case remains clear of both neighbours without a duplicate outline;
- 76 automated tests, JavaScript syntax and repository whitespace checks pass.

### 14 August 2026 — Blender WebGL film shelf

Delivered:

1. Replaced the simulated CSS room with a real GLB generated by a deterministic Blender
   script, including a gallery shell, one fitted shelf wall, smoked-oak boards, blackened steel,
   brass rails, carpet, ceiling lights, entrance framing and populated ambient archive rows.
2. Added a pinned, locally served Three.js WebGL runtime and GLTF loader; the shelf has no CDN or
   external-rendering dependency and the checked-in GLB requires no Blender installation at runtime.
3. Added a bounded first-person camera with pointer-look, mouse-wheel and W/S walking, A/D strafing,
   reset and visible walk controls, plus a live room-position indicator and radar.
4. Created film-specific transparent jewel cases in the browser so director, shared-cast, production-
   country and relevant-film collections stay connected to live discovery data rather than being baked
   into the model.
5. Added generated paper spines, physical brass shelf plaques, hover pull-out animation, ray-cast case
   picking and selected-film highlighting; selecting a 3D case rebuilds both the edition and shelf.
6. Added a Blender regeneration tool, local Three.js licence, static-asset regression tests, responsive
   WebGL sizing, reduced-motion handling and a visible loading/error fallback.
7. Reframed the experience as a single film shelf: all titled, selectable collections now occupy
   separate horizontal rows on the rear wall, while side-wall shelving was removed. This eliminates
   the cross-wall perspective overlap that remained even after the cases were physically separated.
8. Mounted each collection label on its own shelf fascia so labels no longer cover cases on the row
   below, including at the closest permitted camera position.
9. Prevented partial shelf flashes: the viewer now waits for related-film indexing before mounting,
   renders a complete hidden frame, waits for two browser paint frames and keeps the loading panel in
   place until the canvas fade has finished.
10. Replaced the two remaining decorative GLB rows and all generated placeholders with five live,
    selectable rows of real related-film records. Increased relationship retrieval to 18 per category,
    omitted unresolved Q-ID captions, widened cases to twelve per row and upgraded spine and plaque
    typography for clear close-view reading. Removed the redundant in-scene control hint so it cannot
    cross the bottom shelf caption; hovering a case now exposes its full title, year and director in
    the shelf header without compressing the text onto a narrow spine.
11. Wrapped live cases in their available film-poster artwork with a centre crop and translucent title
    treatment. Poster requests are deduplicated, bounded by a six-second fallback and included in the
    ready gate so artwork does not pop in after the shelf appears.
12. Removed the sparse-response fallback that could reveal one repeated case on every row. Related-film
    retrieval now retries transient failures, requires ten distinct verified records before reveal,
    reports a clear unavailable state instead of inventing fullness, and hydrates the existing archive
    in place so late data no longer causes an unexplained full-panel refresh.
13. Replaced per-row pool reuse with a shelf-wide film and title/year ledger, preventing any edition
    from appearing on more than one row. Expanded each relationship category to sixty candidates and
    standardised the final rows at ten cases, so five complete rows can remain genuinely distinct while
    respecting the requested 10–15-case width. Matched both spine and fascia texture aspect ratios to
    their physical meshes so captions render at natural proportions.
14. Moved the default and reset camera from the distant doorway to close reading distance, while
    retaining the existing step-back and free-walk controls. Added an eight-request, IMDb-verified
    Letterboxd fallback budget for related films that have neither a Wikidata image nor a usable
    Wikipedia poster, with cached artwork reused on later shelf builds.
15. Derived the walking and strafing basis from the rendered Three.js camera's world direction,
    rather than duplicating its yaw maths. W/S now follow the direction actually on screen and A/D
    remain perpendicular to it at every viewing angle.

Acceptance evidence:

- the production GLB loaded successfully from FastAPI into the WebGL canvas;
- visible browser checks confirmed distant and close views of the single fitted shelf wall;
- three Move closer actions moved from `DISTANT VIEW` towards the shelf while retaining the full
  horizontal separation between every case;
- a real pointer hover activated the case pull-out state, and clicking it changed the selected edition
  from *In the Mood for Love* to *Happy Together* before reloading the 3D collection;
- compact validation retained the live scene and produced no page-level horizontal overflow;
- a populated close-view check for *In the Mood for Love* confirmed three parallel rows, unobstructed
  spines and labels mounted clear of the cases;
- loading-state validation confirmed that the shelf stays covered until its live cases and first full
  WebGL frame are ready;
- shelf allocation regression checks confirm that row filling shares one ID and title/year ledger,
  and 3D texture checks preserve the physical aspect ratio of spine and shelf captions;
- a live *We Are All Strangers* audit rendered 50 cases across five full rows and reported 50 unique
  title/year editions; close-view inspection confirmed naturally proportioned fascia and spine text;
- related-film regression coverage confirms that an IMDb identity can supply a source-attributed
  Letterboxd poster when the primary Wikimedia paths are empty;
- live *We Are All Strangers* validation opened directly in `MID VIEW`, returned Reset view to the
  same close position and loaded its real Letterboxd poster through the verified IMDb match; the 3D
  shelf completed with 50 cases and no artwork-loading errors;
- movement-vector regression checks require the basis to come from the rendered camera direction;
  live four-heading validation confirmed W follows front, right, left and rear-facing views, while
  a 90-degree side view confirmed D and A move to the camera's right and left respectively;
- 3D asset tests, the full automated suite, JavaScript syntax and repository whitespace checks pass.

Operational note:

- removing the redundant side shelving reduced the generated GLB from roughly 3.7 MB to about 0.8 MB;
  the asset remains browser-cached and requires no Blender installation at runtime.

### 13 August 2026 — Walkable CSS 3D closet

Delivered:

1. Converted the archive from a panoramic composition into a layered CSS 3D scene with a recessed
   back wall, sharply angled side walls, floor and ceiling planes, and a foreground doorway.
2. Added a bounded camera depth that can move from the entrance to close shelf-reading distance.
3. Mapped vertical pointer dragging, mouse-wheel movement, W/S and Up/Down keys, and visible Walk
   in/Walk out controls to the same camera model; horizontal dragging continues to turn between
   aisles.
4. Added a live depth gauge and entrance/mid-room/close-shelf position labels, with Reset view
   returning both direction and distance to centre.
5. Preserved transformed case hit targets so a film remains selectable at close range, while drag
   completion still suppresses accidental selection.

Acceptance evidence:

- live browser checks moved the camera from `-360` at the entrance to `360` close to the shelves;
- vertical pointer drag reached depth `396`, mouse-wheel movement returned towards the entrance,
  and the W key advanced the same camera by one bounded step;
- a real pointer click selected *Ashes of Time* while the case was on a transformed 3D shelf;
- compact layout retains visible walk controls and no page-level horizontal overflow;
- 73 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Draggable walk-in film closet

Delivered:

1. Replaced the flat related-title shelves with a panoramic three-wall archive room modelled on
   the physical browsing experience of the Criterion Closet.
2. Placed the director's complete available filmography on one uninterrupted, physically labelled
   front row while retaining poster-art jewel cases among non-interactive archive filler cases.
3. Added verified relationship shelves for shared cast, production country and genre/metadata
   affinity, with the matched actor and country names printed on physical shelf labels.
4. Added mouse and touch dragging, native trackpad scrolling, arrow-key navigation, a live aisle
   indicator and a re-centre control.
5. Prevented a completed drag from accidentally selecting the case beneath the pointer and kept
   deliberate case selection connected to the main edition display.
6. Added responsive framing, reduced-motion compatibility and horizontal-page-overflow guards.

Acceptance evidence:

- live *In the Mood for Love* validation populated 19 films on the Wong Kar-wai row, 10 shared-cast
  matches, 12 production-country matches and 12 metadata-affinity recommendations;
- a real pointer drag moved from the centre to the Director aisle without changing the selected
  film, while arrow-key navigation moved the same viewport independently;
- selecting *Ashes of Time* from the closet changed the main edition title, cover and dossier
  target;
- desktop, dark-theme and compact viewport checks show no page-level horizontal overflow;
- 73 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Dossier reception and awards

Delivered:

1. Added attributed Douban and Letterboxd platform scores to the dossier opening panel.
2. Normalised both providers to 100 and added a combined score weighted 50% per source only
   when both ratings are available.
3. Added up to three prominent Wikidata awards with linked names and concise introductions.
4. Omitted missing ratings and awards rather than rendering disabled or empty controls.

Acceptance evidence:

- live *Parasite* validation displays Douban 8.8/10, Letterboxd 4.5/5 and a 89.2/100
  equal-weight aggregate;
- the same dossier displays the Palme d'Or and two Academy Awards with source-linked context;
- browser checks confirm desktop and compact layouts without overflow or console errors;
- 69 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Exact-title Bilibili full-film discovery

Delivered:

1. Retained attributed multilingual Wikidata labels as provider-search aliases.
2. Reordered Bilibili acquisition to search exact CJK titles before qualified topical queries.
3. Expanded complete-film markers and allowed an exact alias plus explicit completeness language
   to trigger bounded detail validation when an upload uses a later distribution year.
4. Preserved year/director safeguards for weak or ambiguous matches and content-type exclusions
   for interviews, criticism, trailers, clips, games and music.
5. Added final revalidation for fresh and persisted Full film cards, rejecting unrelated long
   results and reclassifying long reactions as video essays.

Acceptance evidence:

- a regression reproduces *The World of Love* (2025), exact alias `世界的主人`, upload year 2026,
  BV ID `BV1iHZcBgEzm` and the public 10,294-second duration;
- the supplied result is classified as `full_film` and placed under the Full film tab;
- a live search returned `BV1iHZcBgEzm` as a 10,294-second Full film;
- all 64 automated tests pass;
- scoped Ruff and repository whitespace checks pass.

### 13 August 2026 — Crew-value display validation

Delivered:

1. Prevented embedded MediaWiki style and script content from entering parsed infobox values.
2. Added backend plausibility validation for crew names, rejecting CSS, markup machinery,
   malformed punctuation and unreasonable lengths.
3. Added an independent browser-side crew guard before values are joined and displayed.
4. Added a regression fixture reproducing the leaked `.mw-parser-output` value while retaining
   the legitimate producer names that follow it.

Acceptance evidence:

- the malformed CSS fixture yields only `Kim Se-hun` and `Jenna Ku`;
- all 61 automated tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Attributed review and video text in Deep Study

Delivered:

1. Added bounded raw review bodies from every cached criticism provider to the typed Deep Study
   evidence packet alongside structured critical claims.
2. Added uploader descriptions from relevant interviews, video essays, lectures and production
   material while excluding complete films, trailers and scene extracts from prompt text.
3. Added best-effort public YouTube caption discovery, manual/automatic track labelling, event
   normalisation and private catalogue persistence.
4. Added `E*` attributed-text citations, strict citation validation and expandable source text
   with canonical links in the generated-study interface.
5. Preserved evidence boundaries between criticism, uploader context, fallible captions, verified
   creator statements and direct film observation.

Acceptance evidence:

- focused tests cover review text, video descriptions, caption parsing, prompt inclusion and
  attributed-source citation validation;
- all 60 automated tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Multi-source crew reconciliation

Delivered:

1. Retained Wikidata as the canonical film identity while enriching factual credits from the
   matched English Wikipedia film infobox.
2. Added director, writer/screenplay, producer, cinematographer and editor extraction using a
   bounded standard-library HTML parser.
3. Merged identity-normalised names, filled only missing runtime values and retained field-level
   Wikidata/Wikipedia provenance.
4. Added producer and editor facts plus linked crew sources to the dossier.
5. Included the expanded crew and provenance in the Deep Study evidence packet.

Acceptance evidence:

- live *We Are All Strangers* reconciliation returns Anthony Chen as director, writer and
  producer; Teoh Gay Hian as cinematographer; Hoping Chen as editor; and a 157-minute runtime;
- the dossier visibly links both Wikidata and the Wikipedia infobox as crew sources;
- 57 automated tests pass, including infobox reconciliation and evidence-packet coverage.

### 13 August 2026 — Minimal interface copy

Delivered:

1. Removed decorative header and footer copy from the public interface.
2. Removed repeated section labels, readiness text, connector descriptions and instructional
   empty states across discovery, analysis and Settings.
3. Retained action labels, error messages, source attribution, privacy boundaries and live status
   only where they affect a decision or explain system state.

Acceptance evidence:

- browser checks confirm the simplified public and Settings pages in wide and compact layouts;
- no footer chrome, normal-operation readiness copy or horizontal overflow remains;
- 55 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Stable cumulative video discovery

Delivered:

1. Added a private `.firstroll/videos` catalogue that survives backend and browser refreshes.
2. Changed **Refresh videos** to **Find more videos**: each search merges rather than replaces.
3. Deduplicated by platform and provider video ID while preserving the relative order of
   previously accepted videos within each content type.
4. Expanded Bilibili retrieval into focused complete-film, criticism, interview, production
   material and extract queries; increased the per-provider candidate allowance.
5. Capped each film catalogue at 48 accepted items and returned the number added by each search.

Acceptance evidence:

- two live *Memoria* searches expanded the catalogue from 20 to 25 videos;
- all 20 initial videos remained present in the same relative order;
- the expanded result covered seven content types;
- 55 automated tests pass, including cumulative merge and duplicate-ID regression tests.

### 13 August 2026 — Typed video classification

Delivered:

1. Added one content type to every YouTube and Bilibili result: full film, interview,
   video essay/review, lecture, trailer, scene/extract, behind the scenes or other.
2. Treated a complete feature as one **Full film** category without rights subcategories.
3. Added official YouTube duration lookup plus Bilibili search-record duration parsing and
   bounded public-page metadata fallback.
4. Added a second compact Bilibili query for complete films and cross-provider ordering that
   surfaces full films first.
5. Made textual content markers override duration so long interviews and ceremonies are not
   misclassified as films.
6. Added criticism-style category tabs that filter the fetched cards locally, showing only
   categories present in the current result set.

Acceptance evidence:

- a live *Memoria* search classifies the complete film, Cannes press conference, video essays,
  scene extracts and festival ceremony separately;
- browser checks confirm that All, Full film and Trailer tabs expose 12, two and four matching
  cards respectively, without another network request;
- six focused classification and provider tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Persistent dark mode

Delivered:

1. Added an accessible light/dark toggle to the main interface and local Settings.
2. Used the operating-system preference for first load and saved explicit choices locally.
3. Added a dark palette for surfaces, typography, controls, evidence panels and the animated logo.
4. Kept the selected theme consistent while navigating between discovery and Settings.
5. Refined the switch and button system with restrained depth, rounded controls, tactile press
   feedback and spring-like motion while retaining FirstRoll's editorial identity.

Acceptance evidence:

- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm both themes, navigation persistence and narrow-width layouts;
- toggle labels and pressed state remain synchronised with the active theme;
- the animated thumb passes through an intermediate position before settling, and reduced-motion
  preferences suppress non-essential transitions.

### 13 August 2026 — Film viewing resources

Delivered:

1. Added a **Watch & study** dossier section with local progress feedback and embedded
   public-video cards.
2. Added official YouTube Data API search with a write-only API-key entry in Settings and
   privacy-enhanced YouTube embeds.
3. Added key-free Bilibili retrieval through its server-rendered public search page after its
   anonymous JSON endpoint returned HTTP 412 risk control.
4. Added film-title, original-title, year, director and film-context relevance checks to
   reject ambiguous namesakes, music and games.
5. Restricted provider requests, redirects, thumbnails and embed URLs to known HTTPS hosts,
   with timeouts, response limits and bounded result counts.
6. Kept videos as attributed viewing resources rather than automatically treating their
   contents as verified evidence or sending them to DeepSeek.

Acceptance evidence:

- live *Memoria* Bilibili check returns three film-specific results after rejecting unrelated
  uses of the title;
- targeted video, settings and discovery tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

This file is the durable implementation ledger for FirstRoll. Update it whenever a
milestone changes state, a meaningful feature is completed, or verification evidence
changes.

Status vocabulary:

- **Complete** — implemented and verified against its current acceptance criteria.
- **In progress** — active implementation exists, but required work remains.
- **Planned** — accepted scope, not yet implemented.
- **Blocked** — cannot progress without a named decision, dependency or permission.

## Current Snapshot

**Last updated:** 14 August 2026

**Release stage:** local working prototype

**Primary development URL:** `http://127.0.0.1:8000`
**Automated verification:** 76 tests passing

| Area | Status | Current evidence |
|---|---|---|
| Film discovery | Complete | Wikidata identity search, attributed dossier enrichment and a real Blender/Three.js related-film shelf |
| Public video resources | Complete | Persistent cumulative catalogue; typed tabs; bounded uploader-description and public YouTube-caption extraction |
| Product navigation | Complete | Discover and Analyse modes; Study consolidated into Discover |
| Theme support | Complete | System-aware light/dark themes with a locally persisted accessible toggle |
| Local settings | Complete | Write-only connector credentials plus local add, remove and index controls for the private library |
| Private library catalogue | Complete | Seven existing film-study PDFs retained; managed uploads and non-destructive removal; paths and content withheld from public APIs |
| PDF ingestion | Complete | Token-aware page chunks, overlap, section hints, language and stable IDs |
| Local embeddings | Complete | 4,381 of 4,381 chunks embedded with a local multilingual 384-dimension model |
| Hybrid retrieval | Complete | FTS5 + vector candidates, reciprocal-rank fusion and diversity selection |
| Query planning | Complete | User focus, craft taxonomy and attributed criticism generate subqueries |
| Douban adapter | Complete | Optional local MCP connection, title matching, review links and private cache |
| Research adapter | Complete | Crossref abstracts with local identity relevance checks and DOI attribution |
| Letterboxd adapter | Complete | Public-web IMDb identity resolution plus optional official OAuth retrieval |
| Guardian adapter | Complete | Public content-index matching and attributed article-body retrieval |
| Criticism structuring | Complete | Pydantic critic claims with missing-field preservation and evidence labels |
| Criticism source controls | Complete | Tabbed provider switcher; first selection fetches and later selections reuse the cached bundle |
| Evidence packet | Complete | Film record, theory, critic claims, raw review text and attributed video text separated by explicit permitted uses |
| Deep Study schema | Complete | Critic, theory, hypothesis, mechanism, alternative, verification and confidence fields |
| Quality control | Complete | Deterministic gate, citation checks and at most one bounded repair call |
| Evidence-layered UI | Complete | Quality status, validated `S*`/`C*`/`E*` citations, retrieval rationale and expandable excerpts |
| Clip analysis | Complete | Scene/shot metrics, shot scale, colour, objects and JSON/CSV export |
| Clip evidence in Deep Study | Planned | Current study generation does not consume measured clip observations or timecodes |
| Creator primary sources | Partial | Relevant video descriptions and available public captions enter Deep Study; verified speaker attribution remains planned |
| Persistent projects | Planned | Film, clip, study and note sessions are not retained as reusable projects |

## Latest Completed Milestone

### 11 August 2026 — Architecture map with implementation stack

Delivered:

1. Reworked the system diagram into five explicit responsibility layers.
2. Added the shared runtime and specialised technologies to each architectural component.
3. Separated public inputs, private inputs, local processing and external synthesis visually.
4. Added a compact layer-to-stack reference beneath the diagram.

Acceptance evidence:

- every named technology maps to the current project configuration or implementation;
- Mermaid uses GitHub-compatible flowchart, subgraph, class and labelled-edge syntax;
- the local/private boundary and planned clip-evidence bridge remain explicit.

### 11 August 2026 — Simplified discovery landing page

Delivered:

1. Removed the research-principle card from the discovery hero.
2. Removed the empty-state film-dossier explainer and its three descriptive panels.
3. Removed the redundant hero guidance sentence and tightened the surrounding layout.

Acceptance evidence:

- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm clean initial, search-results and narrow-width layouts.

### 11 August 2026 — Douban translated-title identity repair

Delivered:

1. Reproduced the apparent MCP failure for *Memoria* and traced the nested task-group error
   to FirstRoll's film identity guard, not to Douban review availability.
2. Prefer Wikidata's IMDb identifier for Douban film search, with exact-year validation of
   the unique provider result.
3. Retained the stricter title/year scorer when no stable external identifier is available
   or the provider returns ambiguous candidates.
4. Flatten nested MCP exception groups so future failures expose the actionable underlying
   diagnostic.
5. Added regression coverage for translated-title acceptance, same-year ambiguity and
   task-group error unwrapping.

Acceptance evidence:

- live *Memoria* check resolves Douban subject `30137576` and retrieves eight attributed
  long-form reviews;
- scoped criticism tests: 23 passed;
- scoped Ruff checks pass.

### 11 August 2026 — Secondary-evidence technical documentation

Delivered:

1. Documented the complete Crossref, Douban, Letterboxd and Guardian acquisition pipelines.
2. Recorded provider-specific identity resolution, confidence thresholds, result limits,
   attribution fields, response-size limits, redirect restrictions and failure behaviour.
3. Added the *Memoria* translated-title diagnosis as a concrete explanation of IMDb-based
   Douban resolution and MCP task-group error unwrapping.
4. Distinguished Letterboxd public-page acquisition from its official OAuth API without a
   hidden fallback between them.
5. Documented the raw-evidence cache, stable source-ID relationship and Pydantic boundary
   that precede optional DeepSeek claim structuring.

### 11 August 2026 — Source documentation and Letterboxd identity repair

Delivered:

1. Documented the Wikidata, Wikipedia, Crossref, Douban, Letterboxd and Guardian
   acquisition paths in the README.
2. Recorded the raw-retrieval, private-cache and separate DeepSeek-structuring boundary.
3. Replaced ambiguous Letterboxd slug-first matching with verified IMDb-ID resolution when
   Wikidata supplies an IMDb identifier.
4. Added a JSON-LD director guard for title/year fallback pages.
5. Added regressions for same-title, same-year films with different directors.

Acceptance evidence:

- live *An Unfinished Film* check resolves Lou Ye's canonical Letterboxd slug and retrieves
  four attributed reviews;
- automated tests: 43 passed;
- scoped Ruff, frontend JavaScript syntax and repository whitespace checks pass.

### 11 August 2026 — Animated monochrome identity

Delivered:

1. Replaced the framed reel symbol with a minimal black-and-white film-roll mark.
2. Animated the film strip once from its short resting tab to its fully extended state.
3. Applied the same identity to the discovery and local Settings headers.
4. Added a compact SVG favicon and a static reduced-motion state.
5. Slimmed the cylinder and left a short film tab visible in the resting state.

Acceptance evidence:

- SVG validity, frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm the animation cycle, favicon response, Settings header and narrow layout;
- the stylesheet provides a static, fully extended mark when reduced motion is preferred.

### 11 August 2026 — Local recent-search history

Delivered:

1. Removed example values from the film title, year and director fields.
2. Replaced the three suggested films with the five most recent searches.
3. Stored recent searches locally, deduplicated them and kept the newest search first.
4. Made each recent item restore the full title, year and director query and search again.

Acceptance evidence:

- automated tests: 43 passed;
- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm empty, persisted, deduplicated and narrow-width states.

### 11 August 2026 — Criticism source switcher

Delivered:

1. Replaced the separate provider actions with a compact, accessible source tab switcher.
2. Made the first selection of an unloaded source initialise its fetch and structuring flow.
3. Made later selections switch instantly to the cached provider bundle without refetching.
4. Moved refresh controls into the active source panel and marked active and loaded states.
5. Prevented slower background requests from replacing a source selected in the meantime.

Acceptance evidence:

- automated tests: 40 passed;
- frontend JavaScript syntax, scoped Ruff checks and repository whitespace checks pass;
- browser checks confirm cached Douban and Letterboxd switching sends no new request;
- desktop and narrow-width layouts have no horizontal overflow or console errors.

### 11 August 2026 — Settings-based private library management

Delivered:

1. Added a Study library panel to Settings with the current private catalogue and index state.
2. Added local catalogue uploads for PDF, EPUB, Markdown and text documents with a 500 MB
   limit, while clearly identifying PDF as the current indexed format.
3. Added non-destructive removal that unregisters a document without deleting its source file.
4. Added an explicit local search-index rebuild action and visible rebuild recommendation.
5. Preserved all seven books already registered on the development machine.
6. Kept file paths, document contents, uploaded copies and derived index data outside public
   responses and source control.
7. Reduced Settings guidance copy to essential labels, privacy cues and index limitations.

Acceptance evidence:

- automated tests: 40 passed, including add, remove, validation and rebuild flows;
- frontend JavaScript syntax, scoped Ruff checks and repository whitespace checks pass;
- live catalogue metadata still reports seven registered books after the change;
- desktop and narrow-width browser checks show the complete catalogue with no console errors.

### 11 August 2026 — Layered README architecture map

Delivered:

1. Reorganised the system map into five readable layers from user experience to outputs.
2. Simplified service labels while retaining the implemented discovery, criticism,
   retrieval, synthesis, quality-control and clip-analysis flows.
3. Strengthened the visual distinction between local/private processing, provenance-bearing
   evidence and external services.
4. Kept the clip-to-study connection visibly marked as planned work.

Acceptance evidence:

- Mermaid block uses GitHub-compatible flowchart, subgraph and class syntax;
- every architecture node maps to an implemented service, evidence type or documented plan;
- the privacy and external-transmission boundary is stated directly beneath the graph.

### 9 August 2026 — Official Letterboxd API adapter

Delivered:

1. Added write-only Client ID and Client Secret fields to the local Settings registry.
2. Implemented official OAuth client-credentials authentication with clear rejection errors.
3. Added official film search and popularity-ranked public review retrieval.
4. Preserved member attribution, log-entry ID, rating, language and source links.
5. Stored criticism bundles per provider so Letterboxd and Douban claims can coexist.
6. Added a Letterboxd action to film dossiers and combined both providers in Deep Study.
7. Added transport-isolated tests with no scraping or unofficial fallback.

Acceptance evidence:

- automated tests: 29 passed;
- scoped Ruff checks: passed;
- frontend JavaScript syntax and repository whitespace checks: passed;
- live Settings API: Letterboxd exposes separate masked Client ID and Client Secret fields;
- live unconfigured request: returns a specific incomplete-credentials response without making
  an unofficial fallback request.

### 7 August 2026 — README architecture map

Delivered:

1. Expanded the README Mermaid diagram into a boundary-aware system architecture map.
2. Distinguished external services from local/private processing and storage.
3. Documented the film-discovery, criticism, hybrid-retrieval, evidence-packet,
   quality-repair and clip-analysis data flows.
4. Marked the clip-to-study connection as planned rather than implemented.

Acceptance evidence:

- Mermaid block uses GitHub-compatible flowchart and subgraph syntax;
- every implemented data flow corresponds to a current FirstRoll service;
- privacy and external-transmission boundaries are explained directly below the graph.

### 7 August 2026 — Continuous essay presentation

Delivered:

1. Kept the structured evidence sections as an internal generation and validation model.
2. Replaced the visible two-column evidence cards with one continuous critical essay.
3. Joined critic reports, theory, hypotheses, mechanisms and alternative readings into
   successive prose paragraphs with compact inline citations.
4. Moved viewing verification into a collapsed post-essay checklist and retained
   expandable retrieval and source evidence.
5. Tuned the generation prompt so internal sections advance one argument without
   repeating the same thesis.
6. Switched the default synthesis model from `deepseek-v4-flash` to
   `deepseek-v4-pro`; Flash remains available through `DEEPSEEK_MODEL`.

Acceptance criteria:

- [x] continuous article renders without visible evidence-card segmentation;
- [x] theory and critic citations remain visible within the relevant paragraph;
- [x] quality status, creator-intent boundary and source evidence remain inspectable;
- [x] automated tests and frontend syntax checks pass;
- [x] live browser generation uses `deepseek-v4-pro` and renders as one article.

### 6 August 2026 — Deep Study display compatibility fix

Delivered:

1. Added versioned frontend asset URLs so an updated stylesheet cannot load with stale
   study-rendering JavaScript.
2. Disabled HTML shell caching for the local application entry point.
3. Added a backward-compatible renderer for legacy sections that contain `analysis`
   instead of the newer layered evidence fields.
4. Restored explicit text styling for legacy study paragraphs.

Acceptance evidence:

- legacy and layered section fixtures both display substantive analysis text;
- frontend JavaScript syntax check: passed;
- local browser check: study analysis layers render above verification tasks.

### 6 August 2026 — Hybrid retrieval and evidence-quality pipeline

Delivered:

1. Replaced character-count PDF chunks with token-aware, overlapping page chunks.
2. Added stable content IDs and index schema metadata.
3. Added local multilingual embeddings and private SQLite vector storage.
4. Added focus- and criticism-aware query planning.
5. Added FTS/vector reciprocal-rank fusion and diversity constraints.
6. Added typed evidence packets that constrain permitted claim types.
7. Expanded Deep Study into explicit evidence and inference layers.
8. Added deterministic specificity, calibration and citation checks.
9. Added one bounded DeepSeek audit/repair attempt.
10. Added visible quality state, source rationale and full evidence excerpts to the UI.

Acceptance evidence:

- private index: 7 documents, 4,381 cited chunks and 4,381 local vectors;
- automated tests: 22 passed;
- scoped Ruff checks: passed;
- frontend JavaScript syntax check: passed;
- `git diff --check`: passed;
- live API test: hybrid retrieval used film focus and cached criticism;
- live browser test: evidence layers, quality status and citations rendered correctly;
- safety test: an overconfident study remained labelled insufficient evidence after its
  single repair pass.

### 7 August 2026 — Actionable Douban diagnostics

Delivered:

1. Replaced the ambiguous empty-review error with separate authentication, genuinely empty,
   incomplete-row and connector-schema diagnostics.
2. Added safe, length-limited provider-response previews for otherwise unknown formats.
3. Redacted credential-like values and links from diagnostic previews.
4. Added regression tests for each diagnostic path.

Acceptance evidence:

- automated tests: 26 passed;
- scoped Ruff checks: passed;
- `git diff --check`: passed;
- live connector test for *Syndromes and a Century*: correct Douban film match, one
  attributed review summary and four structured critical claims returned.

### 7 August 2026 — Multiline Douban review parsing

Delivered:

1. Reconstructed logical review rows when Douban summaries contain physical line breaks.
2. Preserved multiline review prose rather than rejecting partial Markdown-table lines.
3. Tolerated unescaped pipe characters inside summary text while retaining the final review ID.
4. Added a regression fixture based on the malformed *Kaili Blues* response shape.

Acceptance evidence:

- live *Kaili Blues* response: eight reviews reconstructed from a 280-line table and eight
  attributed critical claims returned;
- focused parser tests and Ruff checks: passed.

## Next Milestone

### Clip-to-study evidence bridge — Planned

Objective: allow Deep Study to make bounded, timecoded formal observations from a
user-provided clip while preserving the current evidence taxonomy.

Proposed acceptance criteria:

- [ ] Define typed `film_observed` evidence for scenes, shots and time ranges.
- [ ] Persist scene and shot identifiers throughout the analysis response.
- [ ] Expose deterministic tools for scene metrics and comparisons.
- [ ] Select relevant clip evidence from the user's study focus.
- [ ] Permit observed claims only when supported by a scene or timecode citation.
- [ ] Keep whole-film extrapolations separate from clip-supported observations.
- [ ] Display book, critic and clip citations as distinct evidence classes.
- [ ] Add tests for citation validity, unsupported extrapolation and missing clip data.
- [ ] Add a browser workflow from Analyse results back into the film dossier.

## Subsequent Priorities

1. **Creator primary-source layer** — ingest attributed interviews, commentaries and
   production records; distinguish direct quotation, paraphrase and inference.
2. **Persistent film projects** — retain discovery records, private clips, analyses,
   notes, criticism and generated studies under a local project ID.
3. **Evaluation suite** — measure retrieval relevance, citation accuracy, unsupported
   claims, appropriate abstention, repair effectiveness, latency and DeepSeek cost.
4. **Retrieval performance** — keep the embedding model warm or load it outside the
   request path so the first dossier opens faster.
5. **Legacy algorithm hardening** — remove inherited lint debt, reduce fallback ambiguity
   and add representative video fixtures.

## Known Risks and Constraints

- Douban MCP is unofficial and depends on an external page structure and access policy.
- Review summaries are secondary copyrighted material; retain attribution and source links.
- User-supplied books and clips must remain local and should not be committed to Git.
- DeepSeek sees only the selected evidence packet, but this still transmits excerpt text to
  an external model provider after the user chooses Generate study.
- A strong formal reading cannot be confirmed without viewing evidence.
- Creator intention must not be inferred from style, criticism or theory alone.
- The local multilingual model adds a first-load delay and a sizeable local download.
- Inherited computer-vision dependencies may behave differently across operating systems.

## Maintenance Rule

For each meaningful implementation change:

1. update the relevant row in **Current Snapshot**;
2. add a dated milestone entry when a coherent feature set completes;
3. record automated and live acceptance evidence;
4. move the next actionable milestone into **Next Milestone**;
5. keep limitations explicit rather than silently removing unfinished scope.
