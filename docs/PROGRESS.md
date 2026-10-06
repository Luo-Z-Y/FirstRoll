# FirstRoll Project Progress

This file is the durable implementation ledger for FirstRoll. Update it whenever a
milestone changes state, a meaningful feature is completed, or verification evidence
changes.

Status vocabulary:

- **Complete** — implemented and verified against its current acceptance criteria.
- **In progress** — active implementation exists, but required work remains.
- **Planned** — accepted scope, not yet implemented.
- **Partial** — part of the accepted scope works; the remainder is planned.
- **Blocked** — cannot progress without a named decision, dependency or permission.
- **Parked** — removed by a recorded decision; recoverable from a named archive tag.
- **Live** — running on the public beta; a qualifier names any acceptance still pending.

## Current Snapshot

### 6 October 2026 — CI trigger simplification (local branch)

Restricted push-triggered CI to `master` while retaining pull-request CI. Feature branches
need an open PR (draft is sufficient) for remote checks. All existing checks remain unconditional.
Removed the unfinished change-scope wiring and live-revision lookup from the workflows;
the Python classifier and tests remain local learning exercises, not active CI policy.
Documentation-only filtering and pending-release reuse are deferred. Production release
creation, freshness checks and owner approval are unchanged. This is not deployed or merged.
Verification: 76 focused CI, VPS release and release-protocol tests pass, including new
trigger-policy and unconditional-check regression tests. Whitespace checks pass.

**Last updated:** 5 October 2026. Agent/Azure retirement, codebase organisation
and the film-duration rounding fix are merged into master. Mobile festival polish
is prepared in PR #57. Previous mobile browser acceptance passed; physical-touch
testing remains pending. Merging does not confirm production deployment.

### Codebase organisation checkpoint

Frontend development tooling is grouped under `tools/frontend/`: `build.cjs`,
`build.sh`, `preview.sh` and the optional historical `check-responsiveness.cjs`
diagnostic. Repository-root resolution, Docker's nested build-context allow-list,
workflow invocations, tests and documentation have been updated together.

Existing `npm run build` and `build:local` commands remain stable.
`npm run preview` compiles before launching the hosted-style loopback UI.
Pytest defaults to `tests/` instead of scanning unrelated workspace directories.

The [Codebase guide](CODEBASE.md) maps folders, features, tests and daily commands.
Backend router extraction remains a separate future change. This reorganisation
does not change Python service imports, HTTP routes, feature flags, database
schema or production approval policy. Private and untracked files are excluded.

### Verification evidence

These results describe separate verification checkpoints, not a completed
verification of the newly combined PR branch:

- Original tooling checkpoint: 304 Python tests and 80 frontend tests passed
  against source and minified hosted bundles. Strict TypeScript, local and hosted
  builds, focused Ruff checks, shell syntax and whitespace checks passed.
- Tooling PR tested with the duration fix on master: 304 Python tests and
  81 frontend tests passed, including source and minified hosted bundles.
- Mobile PR tested with the duration fix on master: 301 Python tests and
  84 frontend tests passed, including source and minified hosted bundles.
- Earlier mobile browser checks passed at 320, 390 and 430 CSS pixels and
  1280 pixels on desktop. These do not establish physical-device pinch/pan
  behaviour.
- Fresh CI must pass after combining the mobile and tooling changes.
  Record its results separately rather than treating earlier runs as proof
  of the combined branch.

The optional historical browser benchmark was not rerun. It requires its
documented baseline and browser toolchain. A previous broad Ruff scan reported
23 findings in unchanged legacy `app/backend/algorithms` files.

The reduced Python test count follows the removal of Agent/Azure-only tests,
not the removal of live festival or account tests. VPS tests simulate activation
and recovery failures; they do not replace browser acceptance or a real
recovery drill.

### Production checkpoint

**Last verified release:** VPS public beta v232 (`cf43ba57`), deployed through
owner-approved run `37213215944` on 5 October 2026.

Pipeline and independent checks passed for file fingerprints, API identity,
API contracts, CORS and hidden documentation routes. Live desktop checks covered
festival navigation, November filtering, SGIFF details and zoom/reset.
Earlier v230 browser checks covered search, shelf, dossier, Settings and the
sign-in dialogue.

Authenticated account/quota acceptance remains unverified. At that verified
checkpoint, paid Deep Study and video analysis were disabled, and v230 was
retained for application rollback. No recovery drill was performed.

A merge or documentation update does not establish a newer live release.
Deployment requires approval of the exact release run, followed by successful
deployment and live verification. This PR does not change secrets or authorise
production deployment.

**Primary development URL:** `http://127.0.0.1:8000`

**Public beta URL:** `https://firstroll.app`

Hosting and recovery procedures:
[Operations](OPERATIONS.md) and [VPS stack](../infra/vps/README.md).

| Area | Status | Current evidence |
|---|---|---|
| Film discovery | Complete | TMDb primary catalogue with open Wikidata/Wikipedia failover, explicit ambiguity confirmation, attributed dossier enrichment and the always-available native director shelf |
| Public video resources | Complete | Persistent cumulative catalogue; typed tabs; bounded uploader-description and public YouTube-caption extraction |
| Product navigation | Complete | Discover, Analyse, Festivals and Settings preserve per-tab view content and scroll; versioned session storage makes Discover refresh-safe |
| Festival atlas | Live in v232 | 32 festivals and the Oscars; inline map, month filter and calendar; typical windows, not confirmed edition dates; typed module/build integration preserved |
| Frontend TypeScript | Complete | Strict composition root, controllers/views, decoders and adapters; shared compiler for local, Docker and hosted assets; 80 frontend tests |
| Theme support | Complete | System-aware light/dark themes with a locally persisted accessible toggle |
| Local settings | Complete | Write-only connector credentials plus local add, remove and index controls for the private library |
| Hosted public beta | Live — authenticated acceptance pending | v232 on Tencent with exact-run approval; live file/API and festival desktop checks passed; authenticated account/quota checks remain |
| Accounts and quotas | Complete — hosted quota check pending | Supabase email-and-password authentication (the only provider), atomic daily Deep Study quotas through the Supabase RPC (portable PostgreSQL adapter staged, not active) and a launch-independent localhost test account; authenticated quota verification on the server is outstanding |
| Authenticated research progress | Complete — browser observation pending | Allow-listed SSE lifecycle events, owner-scoped result retrieval and secret/evidence redaction tests; final interactive browser observation remains pending |
| Private library catalogue | Complete | Seven existing film-study PDFs retained; managed uploads and non-destructive removal; paths and content withheld from public APIs |
| PDF ingestion | Complete | Token-aware page chunks, overlap, section hints, language and stable IDs |
| Local embeddings | Complete | 4,381 of 4,381 chunks embedded with a local multilingual 384-dimension model; background prewarm removes the cold packet stall |
| Hybrid retrieval | Complete | FTS5 + vector candidates, reciprocal-rank fusion and diversity selection |
| Query planning | Complete | User focus, craft taxonomy and attributed criticism generate subqueries |
| Douban adapter | Complete | Optional local or hosted MCP connection, title matching, review links and private cache |
| Research adapter | Complete | Crossref abstracts with local identity relevance checks and DOI attribution |
| Letterboxd adapter | Complete | Public-web IMDb identity resolution plus optional official OAuth retrieval |
| Guardian adapter | Complete | Public content-index matching and attributed article-body retrieval |
| Criticism structuring | Complete | Pydantic critic claims with missing-field preservation and evidence labels |
| Criticism source controls | Complete | Tabbed provider switcher; first selection fetches and later selections reuse the cached bundle |
| Evidence packet | Complete | Film record, theory, critic claims, raw review text and attributed video text separated by explicit permitted uses; focus-ranked bounded packet selection |
| Deep Study schema | Complete | Critic, theory, hypothesis, mechanism, alternative, verification and confidence fields |
| Quality control | Complete | Deterministic gate, citation checks and at most one bounded repair call (schema or quality), so no more than two model calls per study |
| Packet-quality assessment | Complete | `app/backend/packet_quality.py` scores the evidence packet of each completed study for the UI; synthetic six-case fixture in `tests/fixtures/packet_quality_cases.json`. The frozen fixed-workflow evaluation baseline and its results are archived at tag `archive/agent-programme` |
| Evidence-layered UI | Complete | Inspectable progress, packet and citations; quality status, validated `S*`/`C*`/`E*` citations, retrieval rationale and expandable excerpts; WCAG-audited keyboard flow |
| Autonomous research Agent | Parked | Removed on 1 October 2026 (commit `9d29263`) after no paid comparison cleared its gate; recoverable from tag `archive/agent-programme`; revival conditions in [ADR-026](DECISIONS.md#adr-026-park-the-autonomous-research-agent-programme) |
| Release delivery | Live release verified — recovery drill pending | `VPS Release`: protected `master`, exact-run owner approval in `production`, sealed receipt, image-digest deployment over pinned SSH, external live checks and rollback on failed verification; Azure delivery retired (tag `archive/azure`) |
| Web responsiveness | In progress | Blocking API work offloaded to the worker pool, dossier-lifetime fetch cancellation, pre-authentication Deep Study cancel controls and minified assets, measured synthetically on 12 September; live profiling of search → shelf → dossier → reception is still required |
| Clip analysis | Complete | Scene/shot metrics, shot scale, colour, objects and JSON/CSV export (local edition only); still runs on the API event loop |
| Clip evidence in Deep Study | Planned (deferred) | Study generation does not consume measured clip observations or timecodes |
| Creator primary sources | Partial | Relevant video descriptions and available public captions enter Deep Study; verified speaker attribution remains planned |
| Persistent projects | Planned | Film, clip, study and note sessions are not retained as reusable projects; a completed study lives for ten minutes in API process memory |

## 5 October 2026 — Mobile festival atlas polish and narrow-header repair

Follow-up: the localhost obstruction is resolved. Port 4182 held an older API-only process;
restarting it with `FIRSTROLL_SERVE_HOSTED_FRONTEND=true` served the actual interface. Browser
checks passed at **320, 390 and 430 CSS px and 1280 px desktop**, measured from the browser
rather than assuming its zoom-adjusted viewport override matched CSS pixels. November filtering
returns six festivals; calendar selection focuses/reveals SGIFF details, map-pin selection
works, and zoom/reset preserve screen-sized pins. Light/dark modes were checked.

The 320 px check exposed header overflow: intrinsic minimum widths pushed the navigation and
theme control outside the screen. Mobile grid/flex tracks now explicitly shrink, navigation
buttons remain 44 px tall, and the version badge sits below the logo at widths up to 380 px.
After the fix, document scroll width equals client width at all four tested sizes, with no
clipped header children. A source/hosted CSS regression check protects cascade ordering and
shrinkable tracks. These are browser checks, not physical-device pinch/pan evidence.
Production remains v232; the repair is part of PR #57 and does not authorise deployment.

- PR #50 merged at its verified head after both CI runs passed and GitHub reported no conflicts,
  no unresolved conversations and zero commits behind master. Merged-master CI `37248750628`
  passed. This retires experimental Agent/Azure code while retaining the typed atlas and fixed
  Deep Study workflow. The cleanup release must not be approved separately by automation.
- At widths up to 640 px, month controls scroll horizontally with 44 px touch height; zoom
  controls sit above the map rather than covering it. The intro is more compact and long names
  wrap. The calendar becomes a readable date-labelled list instead of a squashed annual chart.
- Pins now use actual CSS-pixel dimensions with 24 px hit circles, recalculated on zoom and
  resize. Zero-sized hidden views use a finite fallback. Closely located festivals can still
  overlap at world scale: zoom or use the calendar for precise selection.
- Mobile calendar selection focuses and reveals the detail card. Pin selection and desktop
  calendar selection do not force scrolling. Tests cover these boundaries and pin sizing.
- 301 Python tests and 82 frontend cases pass, including the minified application; strict typing,
  both builds and whitespace checks pass. An initial minified-test invocation named `web.js`
  incorrectly; rerunning against the actual `dist/assets/app.js` passed.
- Initial browser acceptance was blocked by the preview setup; the follow-up above resolves it.
  Real-device pinch/pan is still unverified.
- Production stays v232. No secrets, account settings, database, feature flags or DNS changed.
  Prepare one combined release after acceptance, then obtain approval for its exact run.

## Next Milestone

### Public-beta acceptance on the server — In progress

Objective: finish authenticated acceptance of live v232 before enabling paid Deep Study. The single-server
cut-over itself is complete (stack, bootstrap, `VPS Release`, DNS and TLS, exact-run approval and
external live checks; see the 28–29 September entries).

Acceptance criteria:

- [ ] Browser acceptance of the live release (receipt, sign-in, saved films, search, shelf, dossier
  and reception) against the checklist in [Operations](OPERATIONS.md).
- [ ] Authenticated quota readiness verified on the server (status, concurrency and refusal once a
  limit is reached) before paid Deep Study is enabled.
- [ ] A separately approved rollback drill on the server, once a second release exists to roll back
  to.
- [ ] A Supabase keep-alive or monitor, so the Free-plan seven-day pause cannot silently break
  sign-in.
- [ ] Owner removes the Azure-era GitHub settings that no workflow reads. A names-only listing on
  1 October showed repository variables `ACR_LOGIN_SERVER`, `AZURE_CONTAINER_APP_NAME`,
  `AZURE_RESOURCE_GROUP`, `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID` and `BACKEND_RELEASE_ENABLED`,
  repository secret `AZURE_BUILD_CLIENT_ID`, and `production` secrets `AZURE_DEPLOY_CLIENT_ID` and
  `AZURE_STATIC_WEB_APPS_API_TOKEN_*`, a deployment token that should also be reset in Azure if the
  Static Web App still exists. The owner also decides on any remaining Azure resources and the
  gitignored local Terraform state.

Boundary: the v232 approval does not approve another run, a database migration or paid calls. The
next owner-approved release will be the first built after the trim.

### 5 October 2026 — Film-duration rounding fix (local, not deployed)

Round total minutes before splitting hours and minutes, preventing `1h 60m`.
Added regression coverage for hour boundaries, numeric strings and invalid values.
TypeScript and all 81 frontend tests passed; whitespace check passed.

### 5 October 2026 — Refresh PR #50 without reverting the live frontend

Integrated the existing trim branch with current `master` (`cf43ba57`) in an isolated worktree,
preserving its history for a normal fast-forward push. Resolved conflicts in CI, HTML, assets,
builds and documentation. Retired the renamed `entra-auth.ts`, its loader branch, globals,
compiler entry and API asset allow-list entry; kept the Supabase and loopback-only adapters.
CI still checks strict TypeScript and all 80 frontend cases. The festival catalogue/controller,
navigation and shared build remain intact. No generated bundles or user-private files are tracked.

Kept the compact documentation structure and carried forward the TypeScript learning guide and
v230/v232 release evidence. The superseded Azure docs/tests and Entra adapter are removed only
from this branch; original contents remain in Git and the archive tags. The original user checkout
and its untracked files are untouched. Current-master/CI checklist completion requires remote
CI to pass for the new head; merging and deployment are separate actions.

### 4–5 October 2026 — Live TypeScript and festival checkpoints

- v230 / `ec9975c8`, run `37208179152`: TypeScript migration, 653 Python and 73 frontend tests;
  signed-out search/shelf/dossier/Settings/sign-in-dialogue browser checks passed.
- v232 / `cf43ba57`, run `37213215944`: festival integration, 655 Python and 80 frontend tests;
  live festival navigation/filtering/SGIFF/zoom/reset checks passed after exact-run approval.
- v232 receipt `vps-cf43ba57-37213215944-1`, SHA-256
  `212dec21a570e13f4f683e5919a78fd0e03fcce1246040de072a0b85d17733fe`;
  image SHA-256 `eb0f9f92e000336f64cffdc48755932e8b8c0be8ef9c6a09d6aa2c752875e556`.
- API healthy; v230 retained for rollback. No database/secret/feature-flag changes or paid calls.
  Authenticated account/quota, mobile/pinch and sustained monitoring are not claimed as verified.

### Live responsiveness profiling and API-loop isolation — Planned

- Authorised live search → shelf → dossier → reception profiling. Investigate repeated Wikidata
  enrichment, redundant TMDb shelf work, video captions delaying cards and unnecessary shelf/player
  DOM replacement before introducing new cache or provider-flow contracts.
- Remove the authentication wait on initial account-data hydration (saved films and settings).
- Move local clip analysis off the API event loop onto a bounded serial worker, after a separate
  review of shared output paths and model state.

## Subsequent Priorities

1. **Persistent film projects** — owner-scoped retention of film, clip, study and note sessions,
   meeting ADR-014's revisit conditions: RLS, deletion, export and a migration with tests.
2. **Cost telemetry and an operator kill switch** — required before raising either daily Deep Study
   limit.
3. **Clip-to-study evidence bridge** — let measured clip observations and timecodes enter the evidence
   packet in the local edition.
4. **Creator primary-source layer** — ingest attributed interviews, commentaries and production
   records; distinguish direct quotation, paraphrase and inference.
5. **Release hardening** — image scanning, SBOMs and signed provenance for the `VPS Release` path.

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
- The public beta runs on one rented server: a single point of failure with a long-lived deploy key,
  no CDN and a brief API restart on every release. The server's private configuration and TLS state
  are not in the repository and need an owner-held off-host backup.
- The Supabase Free plan pauses the project after seven idle days, which breaks sign-in until it is
  resumed in the dashboard.
- Parked Agent and retired Azure code exist only at their archive tags and will drift from `master`.

## Milestone Ledger

Dated entries, newest first. Entries dated 6–31 August 2026 were moved unchanged into
[PROGRESS_ARCHIVE_2026-08.md](PROGRESS_ARCHIVE_2026-08.md) on 27 September 2026.

### 1 October 2026 — Agent programme parked, Azure path retired and documentation consolidated

Commit `9d29263` on `chore/trim-and-crystallise` removed the unused Agent and Azure paths; the same
branch then consolidated the documentation. The change is confined to repository files: it made no
provider, database, DNS, GitHub-setting, cloud-resource or production-deployment change, and live
v219 predates it.

| Removed | Recover from |
|---|---|
| Autonomous research Agent: six backend modules, `app/backend/research_graph/`, the Agent-only DeepSeek methods, `FIRSTROLL_LOCAL_AGENT_ENABLED` and the `langgraph` dependency | `archive/agent-programme` |
| Evaluation harness: `tools/evaluate_*.py`, `tools/review_*.py`, the benchmark audit, gate, packet and smoke tools, the whole `evals/` directory and eight Agent/evaluation documents | `archive/agent-programme` |
| Azure delivery: `infra/terraform`, the Static Web Apps and backend-release workflows, `tools/release/{cli,manifest,risk,summary,frontend}.py`, the Azure receipt functions and CLI in `tools/release/protocol.py` (now only the shared helpers `vps.py` imports) and `app/web/staticwebapp.config.json` | `archive/azure` |
| Entra External ID: `EntraAuthVerifier`, `app/web/entra-auth.js`, `@azure/msal-browser`, the `ENTRA_*`/`FIRSTROLL_ENTRA_*` variables, browser `authProvider`/`entra*` fields and the PyJWT dependency | `archive/azure` |

Kept: the fixed Deep Study workflow; packet-quality assessment, whose fixture moved to
`tests/fixtures/packet_quality_cases.json`; Supabase Auth as the only accepted
`FIRSTROLL_AUTH_PROVIDER`; the Supabase quota RPC by default, with `PostgresQuotaClient` selectable
through `FIRSTROLL_QUOTA_PROVIDER=postgres`; the `infra/vps` stack and `VPS Release` with
`tools/release/protocol.py` and `vps.py`; CI, minus its Terraform step; local clip analysis.

Decisions: [ADR-026](DECISIONS.md#adr-026-park-the-autonomous-research-agent-programme) parks the
Agent programme with revival conditions, and
[ADR-027](DECISIONS.md#adr-027-retire-azure-and-host-the-public-beta-on-one-vps) records the VPS
hosting and Azure retirement. ADR-003, 004, 011, 015 and 020–025 are condensed and marked
superseded or parked. ADR-009's status is corrected: the Supabase RPC is the active quota default,
and ADR-016's PostgreSQL adapter is staged, not active.

Documentation: the readme was cut to an overview, and eight topic documents were folded into a set
in which each topic has one owner (scopes in the readme's Documentation Map):

| Former document | Now in |
|---|---|
| `API_REFERENCE`, `DATA_MODEL`, `DATA_SOURCES` | [Data](DATA.md) |
| `HOSTING`, `RELEASE` | [Operations](OPERATIONS.md) and [infra/vps/README.md](../infra/vps/README.md) |
| `LOCAL_SETUP` | [Setup](SETUP.md) |
| `THREAT_MODEL`, `WEB_RESPONSIVENESS` | [Architecture](ARCHITECTURE.md) |

Acceptance evidence:

- `.venv/bin/python -m pytest -q tests`: 289 passed, including 54 single-server release checks,
  16 shared release-primitive checks, 34 same-ASGI-loop concurrency checks and the test that runs
  the 27 Node request/race checks (`node --test tests/web/responsiveness.test.cjs`). The fall from
  642 tests on `058c747` reflects the removed Agent, evaluation and Azure release code.
- `ruff check app/backend --exclude app/backend/algorithms`: clean.
- Production frontend build (`tools/frontend/build.sh`, live channel): passes.

Constraints:

- Restoring the Agent requires ADR-026's revival conditions; its frozen evaluation results,
  including the fixed-workflow baseline, are readable only from `archive/agent-programme`.
- Azure-era GitHub settings, any remaining Azure resources and local Terraform state are untouched
  and await the owner decision listed in **Next Milestone**.

Next actionable work: the public-beta acceptance milestone above, starting with browser acceptance
and authenticated quota verification; then live responsiveness profiling.

### 1 October 2026 — Explain the deployed architecture and correct stale documentation

Read-only checks of the normal public URLs returned the v219 receipt, exact `b678e52e` API SHA and
healthy status. Discovery status confirms public mode, Supabase configured, open catalogue fallback
and hosted Deep Study/video analysis off. These checks do not constitute a signed-in quota test,
browser acceptance or a continuous post-deployment observation window.

Reworked the README's opening status and added a beginner-oriented component guide, request paths,
storage lifetimes, release process and single-server limitations. Corrected the stale server-purchase
roadmap, Azure API wording and the claim that the staged generic PostgreSQL quota adapter was already
the active path. Code selects Supabase by default; personal DeepSeek keys still require the hosted
enablement boundary and quota reservation. Detailed architecture, hosting and Obsidian notes are
aligned; historical Azure diagrams remain explicitly historical rather than newly validated.

Documentation only: no application code, provider settings, database schema, DNS or production
deployment changed. The existing launch documentation PR #49 is reused because its base still
matches current protected master; a documentation merge would not authorise another deployment.

### 29 September 2026 — v219 deployed to Tencent with owner approval

After the owner explicitly confirmed the named v219 launch, changed only Spaceship's `@` and `api`
CNAME records to A records for `119.28.111.192`. Reloaded the dashboard to confirm persistence;
both existing TXT records and nameservers are unchanged. Public DNS-over-HTTPS and the VPS resolver
confirm the new address. The local resolver/browser still caches Azure for the root domain; that
temporary Azure 404 is not a VPS application response.

Started Caddy without the API, verified trusted HTTPS for both exact hostnames, then approved only
production run `36534759362` for commit `b678e52e14deb84cdf7d2d1653e2c44405e0d988`. The gate and
branch policy were not weakened. The run completed successfully at 07:22 UTC, including receipt and
archive checks before credentials, current-master checks, pinned SSH, release activation, external
checks of every static asset, exact API identity, hidden documentation and CORS.

- Image: `ghcr.io/luo-z-y/firstroll-api@sha256:9b7993d4fbe5abde15ade85cfa53d38d394636911bf192ff7f2118e89dc8a7a8`.
- Live release: `vps-b678e52e-36534759362-1`, frontend version `v219`.
- Health returns 200 with the approved SHA; docs/redoc/OpenAPI and private settings return 404;
  account identity without a token returns 401. Public mode is on; Deep Study/video analysis are off.
- Both containers have zero restarts in the initial inspection; the API is healthy. Initial memory
  use was approximately 67 MiB for the API and 59 MiB for Caddy, not a sustained-load benchmark.
- Public search returned the intended *In the Mood for Love* (2000) record in approximately eight
  seconds using Wikidata/Wikipedia; TMDb remains unconfigured.
- Its dossier returned the correct identity in 2.71 seconds; the director-only shelf endpoint
  returned 12 films in 4.61 seconds. These are individual API samples, not browser/load benchmarks.

Browser sign-in and interactive shelf/dossier acceptance, a full observation window and a real
recovery drill are outstanding. No account/password change, database migration or paid model call
was performed. No earlier VPS application release exists to roll back to. Documentation is kept on
a separate branch; no further production run is approved by this launch.

### 29 September 2026 — First candidate held; deployment failure handling corrected

Readiness PR #47 merged after green checks; exact-master CI at `f1192476` passed 621 tests.
Enabled `VPS_RELEASE_ENABLED`. Candidate run `36532955695` passed frontend/container build, npm
audit and container smoke checks, uploaded its sealed package and stopped at the human gate.
It was cancelled without approval when a read-only review reproduced a shell error-propagation bug.

- Bash suppresses `set -e` inside conditionally called functions: failed digest writes, image pulls,
  site switches or Caddy reloads could reach a success-state write. Activation and multi-command
  helpers now propagate failures explicitly; environment and current-release writes are atomic.
- A failed local activation restores the pre-release site and digest. With a real previous release
  it checks that API again; on first deployment it stops the candidate API and restores the bootstrap
  site, never attempting to pull the all-zero placeholder digest. Failed recovery retains files and
  explicitly requires manual intervention.
- Each attempt uses a unique site directory, so same-commit retries cannot delete the active site.
- A failed rollback-record write recovers the previous state; housekeeping failures are warnings
  so an already active release still reaches the runner's live verification.
- GitHub performs post-deployment rollback only after a successful rollout whose live check fails,
  avoiding a second rollback after local recovery. A first successful release still has no previous
  application target for post-verification rollback. Stack/configuration and database rollback are
  not claimed.

Verification: 642 tests pass, including 54 focused VPS checks; Ruff, shell syntax and diff checks
pass. No DNS change, application deployment, production approval or paid model call occurred.
Build fingerprints for the cancelled candidate remain in its GitHub artefact; it must not be deployed.

### 29 September 2026 — Provider configuration and HTTPS ingress verified

After the owner reported completing the setup, a pinned SSH check confirmed non-placeholder
DeepSeek and YouTube keys in the server's resolved Compose configuration, `.env` mode 0600 and
valid configuration. Only presence/boolean results were displayed; no credential values were
retrieved into the conversation. TMDb remains unconfigured, so open catalogue fallback is expected.
Public mode is on; paid Deep Study and video analysis stay off. These checks prove configuration
presence, not provider-key validity or authenticated quota readiness.

The refreshed Tencent console shows a TCP 443 allow rule alongside TCP 22/80 and ICMP. DNS still
points to Azure, so HTTPS end-to-end acceptance remains outstanding. The owner authorised candidate
preparation and deployment if possible; the existing exact-run human approval gate remains in force.
The candidate must pass build/smoke checks and image-pull verification before DNS cut-over, and
DNS/TLS must be ready before the waiting production job is approved. The first VPS release has no
previous VPS release for automatic rollback. No production deployment is claimed by this checkpoint.

### 29 September 2026 — Protected VPS access configured; activation held

- Reviewed and merged the passing private-key ignore PR #45. Updated preparation PR #46 against
  that master, waited for fresh checks and merged it; merged `master` CI passed at `1a8e2b6`.
- Verified GitHub `production` still requires the human owner and permits deployments only from
  `master`. Stored only the dedicated VPS deployment private key as `VPS_SSH_PRIVATE_KEY` in that
  environment; the personal administrator key stays local. Configured `VPS_HOST`, `VPS_USER` and
  the previously verified Ed25519 `VPS_SSH_HOST_KEY` as repository variables.
- Set `BACKEND_RELEASE_ENABLED=false`, disabled both legacy Azure release workflows and cancelled
  their obsolete waiting candidates `36367718705` and `36367718612`. No production gate was approved
  or weakened. Kept `VPS_RELEASE_ENABLED` unset while configuration is incomplete.
- Saved the owner-confirmed HTTPS certificate contact privately on the server. Verified `.env`
  remains `0600`, owned by `firstroll`, and Compose's quiet validation passes. No application
  containers run.
- A names/presence-only check found existing local DeepSeek and YouTube keys, but no local TMDb key.
  The security review blocked their transfer without explicit payload/destination consent; requested
  that consent and did not retry or copy the keys. Paid Deep Study remains disabled.
- Read Tencent's cloud firewall in the console: TCP 22, TCP 80 and ICMP are allowed; TCP 443 is
  missing. Requested approval for that specific HTTPS rule; did not change the cloud firewall.
- DNS still points to Azure. A read-only Azure account check now reports `Enabled`, but the API
  resource reports failed provisioning with no container environment or secrets to recover; this
  is not evidence that the former hosting has recovered, and no Azure resource was changed.

Outstanding: the two explicit consents, provider/quota readiness, HTTPS ingress, candidate/package
verification, DNS/TLS, the exact-run owner approval, browser acceptance and a recovery drill.
No API-key transfer, database migration, production deployment or paid model request occurred.
Verification: 33 focused VPS tests pass again; documentation diff checks, protected-environment
read-back, cancelled-candidate status and the live quiet Compose/permissions checks pass.

### 29 September 2026 — Tencent VPS prepared and verified after reboot

The owner purchased Tencent Lighthouse Starter in Singapore Zone 2 (2 vCPUs, 2 GB RAM, 40 GB SSD),
bound the administrator key to `ubuntu`, supplied the host fingerprint through Tencent's browser
terminal, and explicitly authorised preparation and a subsequent reboot.

- Verified Ubuntu 24.04.4 LTS / x86-64 with pinned Ed25519 host checking. Created a separate local
  deployment key outside Git and installed only its public half for `firstroll`; Docker group access
  is explicitly root-equivalent. The administrator key remains local and ignored.
- Applied the reviewed bootstrap: Ubuntu updates, Docker 29.1.3, Compose 2.40.3, rotated logs,
  `/opt/firstroll` configuration, owner-only `.env`, unattended updates and UFW allowing only TCP
  22/80/443 and UDP 443. Preserved the existing approximately 2 GB swap.
- Found a real Ubuntu socket-activation edge case: the OpenSSH upgrade stopped `ssh.service` while
  leaving `ssh.socket` active, so standalone `sshd -t` failed because systemd's `/run/sshd` was absent.
  Starting the service recreated the runtime directory and allowed validation/reload. The bootstrap
  now starts it before the standalone check; three shell-fake regression cases verify success and
  fail-closed behaviour on start/validation failure.
- Verified new SSH connections for both accounts before and after the owner-approved reboot into
  kernel `6.8.0-142-generic`. Docker, SSH, unattended updates and UFW survived; `dpkg --audit` is clean
  and no reboot-required marker remains. Approximately 31 GB disk space remains free.
- `docker compose config --quiet` passes. Caddy 2.11.4 validates in a temporary, network-disabled
  container with no published ports; that container was removed and no application containers run.
- Updated the hosting runbook for Tencent's `ubuntu` account, explicit public-key-only uploads,
  host verification, traffic limits, private-key storage and the distinction between host preparation
  and production activation.

Verification: 33 focused VPS tests, Ruff lint/format, Bash syntax and diff checks; live server checks
above. Tencent's separate cloud-firewall rules and end-to-end HTTPS have not yet been verified.

Not done: provider secrets or certificate-contact configuration, DNS changes, certificate issuance,
GitHub deployment-secret/variable changes, an application release, database migration, paid model
calls or a rollback drill. The public beta remains offline. The private deployment key has not been
uploaded to GitHub.

### 28 September 2026 — Single-server hosting path prepared after the Azure suspension

Context: the Azure Free Trial subscription (`FreeTrial` offer, spending limit on) was found `Disabled`
on 27 September 2026. The Container Apps environment was suspended, `api.firstroll.app` timed out and
`firstroll.app` returned 404, while the Supabase project remained active. The owner chose to move the
public beta to a rented server rather than upgrade Azure to pay-as-you-go.

1. Added `infra/vps`: `docker-compose.yml` (Caddy 2.11.4 plus the API container deployed by immutable
   GitHub Container Registry digest, capabilities dropped, memory-limited, rotated logs), `Caddyfile`
   (both hostnames, the former Static Web Apps cache policy, SSE-safe proxy), `.env.example`,
   `bootstrap.sh` (Ubuntu 24.04: Docker, service account, firewall, swap, unattended security
   updates, key-only SSH) and `deploy.sh` (release, rollback and status; the site switches only after
   the API reports the baked commit).
2. Added `tools/release/vps.py`, which seals a `vps` receipt binding the site inventory and the image
   digest to the commit, verifies the receipt and archive on the deploy runner before any credential
   exists, and checks the live receipt, every static file, API identity, hidden documentation routes
   and the exact CORS origin.
3. Added the `VPS Release` workflow with the same CI-gated candidate selection and human `production`
   approval: a build job without production credentials pushes the image to GitHub Container Registry;
   the deploy job verifies first, pins the server host key, installs the reviewed stack files, releases
   by digest and rolls back on failed verification. It is fail-closed on `VPS_RELEASE_ENABLED`.
4. CI validates the stack with `shellcheck`, `docker compose config` and `caddy validate`; Dependabot
   watches the Caddy image pin.
5. Reconciled `readme.md`, `HOSTING.md` (server purchase, deploy key, bootstrap, DNS, certificates,
   GitHub configuration, first release, operations, cost and risks; Azure sections marked legacy),
   `RELEASE.md`, `ARCHITECTURE.md` and `THREAT_MODEL.md`.

Verification: 618 tests pass locally, including 30 new checks in `tests/test_vps_release.py`;
`shellcheck`, `docker compose config` and `caddy validate` pass locally against the pinned images.
No server exists yet, so certificate issuance, a live release and a rollback have not been exercised.

Not done: server purchase, DNS change, bootstrap, GitHub configuration, first approved release,
rollback drill, GitHub package visibility check and removal of the legacy Azure workflows and Terraform.

### 27 September 2026 — Progress ledger reconciled and repository housekeeping

Documentation and repository hygiene only; no application code, test, provider or model call changed:

1. Restored this file's intended structure. The intro, status vocabulary, **Current Snapshot** and
   **Next Milestone** now lead the file; dated entries follow newest-first under **Milestone Ledger**.
   A month of prepended entries had buried the intro at line 3,092 and left the snapshot stale.
2. Refreshed **Current Snapshot** (last updated 14 August, 76 tests) against `master` at `6028a98`:
   588 tests, the deployed public beta, accounts and quotas, research progress, the evaluation
   baseline, the blocked Agent programme, release delivery and web responsiveness are now recorded.
3. Recorded the two owner-gated items already described in the 10 and 12 September entries as
   explicit **Blocked** milestones so the pending human decisions are visible in one place.
4. Moved the 6–31 August 2026 entries unchanged into
   [PROGRESS_ARCHIVE_2026-08.md](PROGRESS_ARCHIVE_2026-08.md) and added an archiving step to the
   maintenance rule, keeping the live ledger readable.
5. Working-copy housekeeping outside Git: fast-forwarded local `master` to `origin/master`, deleted
   the merged `fix/web-responsiveness` and empty `gogocho` local branches, moved four untracked
   book-conversion scratch files into the ignored `.agents/` directory and removed the stale
   `.venv-pycinemetrics-stale` environment. `docs/archify-architecture-atlas` remains unmerged on
   `origin` pending an owner decision.

Verification: Markdown anchors and line counts checked programmatically; no tests exercise this file.

### 12 September 2026 — First web/backend responsiveness pass

Implemented on `fix/web-responsiveness`, without a production approval or provider/model call:

1. Offloaded synchronous catalogue/status/cache work in async reception and criticism handlers,
   library upload/rebuild response metadata, and SSE authentication/platform-key checks to the
   existing Starlette worker pool. Authentication, ownership, evidence, quota and model order remain
   unchanged; no cache, executor, acquisition stage or call budget was added.
2. Made dossier/evidence browser work follow the selected dossier's lifetime. Closing a loading
   dossier, changing film or searching again aborts obsolete fetches; late results, errors and focus
   callbacks cannot replace the current film or attach another film's criticism.
3. Established Deep Study busy/cancel controls before token retrieval, prevented overlapping clicks
   and blocked obsolete study POSTs after cancellation during authentication. Provider work already
   started can still consume quota; no backend cancellation/refund guarantee is claimed.
4. Minified application JavaScript and CSS with the existing locked esbuild dependency, preserving
   globals, release filenames and cache policy. The pair is 21.5% smaller than the baseline shipped
   files (249,828 → 196,202 bytes), or 12.0% smaller with local deterministic gzip.
5. Added dependency-free executable JavaScript race tests to the existing Python CI gate and an
   optional, pinned-tool Chrome diagnostic that starts no backend, fulfils/blocks page HTTP traffic
   and removes speculative connection hints. This is not an OS-level network sandbox.
6. Reconciled README, architecture/API/hosting prose and the web-responsiveness note (since folded
   into [Architecture](ARCHITECTURE.md#7-web-responsiveness)) with the implementation, measurements
   and remaining work.

Acceptance evidence, recorded separately:

- **Deterministic:** all 588 repository tests passed in a temporary tracked-source copy with no private
  runtime. Included 34 same-ASGI-loop concurrency checks and 27 Node request/race checks; the same
  27 Node checks also pass against the minified build. Locked production-style build, scoped Ruff,
  JavaScript/shell syntax and whitespace checks pass. Global Ruff was unavailable; `.venv/bin/ruff`
  supplied the passing lint check.
- **Browser:** Chrome 152, 4× CPU throttle, 390px/1440px, twenty interactions per variant/viewport.
  With a synthetic 500 ms token delay, median click-to-busy mutation improved from about 502 ms to
  0.4–0.8 ms. The next-frame paint proxy improved from about 511 ms to 27–28 ms; it is not INP. Forty
  candidate cancellations before token readiness sent zero mocked study POSTs. Both widths had zero
  uncaught page errors and no horizontal overflow. The hash-bound synthetic report
  `evals/results/web-responsiveness-2026-09-12.json` is retained (at tag `archive/agent-programme`
  since 1 October 2026); no live latency or model-speed result is claimed.
- **Review:** fixed the reviewer's cached-criticism-tab busy-state regression and added both fetch and
  structuring transition tests. Also removed speculative connection hints from the browser fixture
  and narrowed its network-isolation claim.
- **Perceptual:** inspected both synthetic full-page screenshots; progress and cancellation controls
  are visible. Long titles still wrap tightly in the existing desktop edition card. Real fonts,
  complete accessibility and other browsers remain outside this acceptance run.
- **Architecture:** reviewed as an internal scheduling/ownership refactor preserving documented
  contracts. No Archify source changed: the baseline has no typed architecture sources/atlas and
  Archify is unavailable. No validate, deliver or visual-check result is claimed; existing Markdown
  architecture documentation is reconciled.

Known constraints and next actionable work:

- Authorised live search → shelf → dossier → reception profiling is still required. Investigate
  repeated Wikidata enrichment, redundant TMDb shelf work, video captions delaying cards, and
  unnecessary shelf/player DOM replacement before introducing new cache or provider-flow contracts.
- Authentication still waits for initial account-data hydration. The shared worker pool can saturate;
  local clip analysis still blocks the API loop and renders hidden analysis panels eagerly. A bounded
  serial analysis worker needs a separate review of shared output paths and model state.
- Publish through a green protected-master pull request; any resulting production deployment must
  remain pending for the human owner's approval of that exact run.

### 10 September 2026 — Standardised frontend/backend release contract

Implemented on a short-lived feature branch; owner production approval remains required:

1. Added shared, dependency-free release receipts bound to component, commit, run, build attempt,
   payload fingerprint and a seven-day approval expiry. Build-job outputs independently bind the
   expected receipt fingerprint; retained evidence lasts 90 days without extending old approvals.
2. Added frontend post-approval stale-master refusal, candidate file hashing, live receipt/public-file
   verification and API smoke checks. The Azure-consumed configuration file is verified in the
   package, not fetched as a public asset. Version metadata is served without caching.
3. Added a verified previous-package baseline and recovery upload on frontend upload/verification
   failure. Recovery checks the restored exact files and does not depend on an unrelated API outage.
   The run stays failed after recovery. Initial bootstrap explicitly acknowledges no legacy backup.
4. Both workflows fetch only reviewed release-control modules from the CI-approved commit, retain
   independent credentials/approvals and preserve active deployments. Neither applies Terraform,
   migrates databases, installs deployment-time dependencies or executes artefact-provided scripts.
5. Backend change selection now includes accumulated changes since the deployed source SHA, with a
   conservative full-tree fallback for legacy/unknown versions. Corrected the summary's misleading
   suggestion that an application release also applies changed Terraform files.
6. Updated README, architecture, hosting and release runbooks, ADR-025 and Obsidian project notes.

Verification at the implementation checkpoint:

- All 553 repository tests passed after the final review pass; added executable
  receipt, rollback, live-failure and workflow-parity cases rather than relying only on YAML strings.
- The production-style frontend build passed with locked dependencies and lifecycle scripts disabled.
- Ruff, Terraform formatting and the official checksum-verified actionlint 1.7.12 validator pass.
  Docker is not running locally, so the protected GitHub CI build remains the container-build check.
- The current live `/release.json` returns HTTP 404, confirming that bootstrap is genuinely required.
- No production approval, deployment, Terraform apply, account change or paid model call occurred.

Operational proof still required: owner-approved initial frontend release, backend release, browser
acceptance and a separately approved live recovery drill. Image scans, SBOMs, signed provenance,
permanent backups and coordinated/atomic cross-service deployment remain out of scope.

### 04 September 2026 — Passwordless backend delivery activated and live-validated

Delivered without approving or changing the production API image:

1. Merged PR #39 after both required CI checks passed and removed its short-lived branch locally and
   remotely.
2. Applied the reviewed Terraform plan exactly: two managed identities, two federated credentials
   and three narrow role assignments were added; no existing resource changed or was destroyed.
3. Configured the GitHub repository and protected `production` environment with separate build and
   deploy client IDs, Azure resource variables and the fail-closed release switch.
4. Preserved the selected-Actions policy and mandatory full-SHA pinning while allowing only the
   pinned `azure/login` integration required by the release workflow.
5. Ran a real proof build. Revision binding, Docker build and public-boundary smoke tests passed; the
   first Azure token exchange then failed closed before registry access because GitHub's live OIDC
   subject includes immutable owner and repository IDs.
6. Corrected Terraform to trust the exact identity-bound prefix reported by GitHub and replaced the
   AzureRM provider's deprecated federated-identity argument.

Verification at this checkpoint:

- the merged master CI run for `1dac6de7b3642d492cd2abd067d0e3fe079ba4d1` passed;
- the post-apply Terraform plan reported no drift;
- the proof image built and passed its container smoke test before the deliberately rejected OIDC
  exchange;
- the correction plan contains only two in-place federated-subject updates, with no additions or
  destroys and no application/runtime changes;
- all 480 repository tests pass; focused release tests, Terraform formatting/validation and
  repository checks cover the corrected subject construction.

Status: the production API still runs its previous image. The next proof run may build and seal a
candidate, but deployment must remain paused at GitHub's protected `production` environment until
the owner reviews and approves that exact run.

### 04 September 2026 — Backend release design simplified and hardened before activation

Delivered without changing the live production environment:

1. Replaced the unfinished HMAC/Approval Broker design with the already configured GitHub
   `production` environment as the single required human approval authority.
2. Added Terraform definitions for two passwordless GitHub OIDC identities. The branch-bound build
   identity can push to one ACR and read one app; the approval-bound deploy identity can update only
   the FirstRoll Container App.
3. Removed Azure JSON credentials, ACR usernames and ACR passwords from the backend workflow design.
4. Integrated the deterministic risk classifier and canonical release manifest into the actual build
   path. Release-authority changes and cloud permission/identity changes now force high risk.
5. Bound the manifest to repository, workflow run, current `master`, full commit SHA, image tag,
   immutable image digest and its own canonical digest. The deploy runner recomputes and verifies
   those facts before requesting an Azure token.
6. Kept the deploy runner source-free, baked the commit SHA into the image, made either a live SHA or
   Azure-configured image-digest mismatch fatal, added exact revision/API/docs/CORS checks, and added
   automatic restoration of the prior image after failed post-deployment verification.
7. Added `BACKEND_RELEASE_ENABLED` as a fail-closed activation switch so merging the design cannot
   start building or deploying before Terraform and GitHub configuration are complete.
8. Reconciled the architecture, threat model, hosting guide, release runbook, README, ADR and
   Obsidian project log with the implemented design and its honest gaps.
9. Split resource ownership explicitly: Terraform owns the Container App and all configuration but
   ignores its post-bootstrap image field; the approved release workflow owns that field alone.

Verification at this checkpoint:

- 98 focused manifest, risk, summary, workflow, CLI and Terraform-structure tests pass;
- all 479 repository tests, Python lint, JavaScript syntax, frontend production build and npm audit
  pass; npm reports zero vulnerabilities;
- Terraform formatting and static validation pass; the live-state plan is exactly seven additions,
  zero changes and zero destroys (two identities, two federated credentials and three roles);
- local Docker validation reached the build boundary, but Docker Hub timed out twice while resolving
  the pinned base-image metadata. CI remains responsible for the final production-image build proof.

Status: code is under review on PR #39. Terraform has not been applied, GitHub OIDC values have not
been configured, `BACKEND_RELEASE_ENABLED` remains absent/false and no production deployment was
approved or attempted. Scanning, SBOMs, attestations and an application-owned audit ledger remain
future controls rather than claimed capabilities.

## Maintenance Rule

For each meaningful implementation change:

1. update the relevant row in **Current Snapshot**;
2. add a dated milestone entry when a coherent feature set completes;
3. record automated and live acceptance evidence;
4. move the next actionable milestone into **Next Milestone**;
5. keep limitations explicit rather than silently removing unfinished scope;
6. when the ledger grows past roughly one month or one thousand lines, move older dated entries
   unchanged into a dated `PROGRESS_ARCHIVE_<year>-<month>.md` file and link it from the ledger
   heading.
