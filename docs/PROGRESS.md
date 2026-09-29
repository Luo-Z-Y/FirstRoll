# FirstRoll Project Progress

This file is the durable implementation ledger for FirstRoll. Update it whenever a
milestone changes state, a meaningful feature is completed, or verification evidence
changes.

Status vocabulary:

- **Complete** — implemented and verified against its current acceptance criteria.
- **In progress** — active implementation exists, but required work remains.
- **Planned** — accepted scope, not yet implemented.
- **Blocked** — cannot progress without a named decision, dependency or permission.

## Current Snapshot

**Last updated:** 29 September 2026 (readiness PR #47 merged; `f1192476` CI passed; first candidate
cancelled before approval after failure-path review; activation recovery fixes pass 642 local tests)

**Release stage:** local working prototype; the public beta is offline. The Azure Free Trial
subscription was disabled when its credit expired (observed 27 September 2026), suspending the Static
Web App and the Container Apps environment. A single-server hosting path (`infra/vps` and the
`VPS Release` workflow) is implemented and tested locally. The purchased Tencent Lighthouse server
is bootstrapped and verified after reboot. Protected GitHub VPS access and the certificate contact
are configured. The owner has added the provider keys and cloud HTTPS rule; presence/permission
checks pass. The VPS workflow is enabled. Its first candidate built successfully but was cancelled
before approval after failure-path review. A replacement candidate, image-pull verification,
DNS/TLS, exact-run production approval and a recovery drill remain. Paid Deep Study stays disabled.

**Primary development URL:** `http://127.0.0.1:8000`
**Public beta URL:** `https://firstroll.app` (offline until the single-server cut-over)
**Automated verification:** 642 repository tests passing locally on 29 September 2026, including
54 single-server checks, 34 same-ASGI-loop concurrency checks and 27 Node request/race checks.
The new VPS cases simulate activation and recovery failures without touching a server. They do not
replace first-live-release acceptance or a real recovery drill.

| Area | Status | Current evidence |
|---|---|---|
| Film discovery | Complete | TMDb primary catalogue with open Wikidata/Wikipedia failover, explicit ambiguity confirmation, attributed dossier enrichment and the always-available native director shelf |
| Public video resources | Complete | Persistent cumulative catalogue; typed tabs; bounded uploader-description and public YouTube-caption extraction |
| Product navigation | Complete | Discover, Analyse and Settings preserve per-tab view content and scroll; a versioned `sessionStorage` snapshot makes the Discover workspace refresh-safe; Study remains consolidated into Discover |
| Theme support | Complete | System-aware light/dark themes with a locally persisted accessible toggle |
| Local settings | Complete | Write-only connector credentials plus local add, remove and index controls for the private library |
| Hosted public beta | In progress — offline | Tencent host, protected deployment access, provider-key presence and cloud TCP 443 verified. Preparing the candidate; image-pull checks, DNS/TLS and exact-run production approval remain |
| Accounts and quotas | Complete | Supabase email authentication, atomic daily Deep Study quotas and a launch-independent localhost test account |
| Authenticated research progress | Implemented | Allow-listed SSE lifecycle events, owner-scoped result retrieval and secret/evidence redaction tests; final interactive browser observation remains pending |
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
| Quality control | Complete | Deterministic gate, citation checks, bounded synthesis recovery and at most one bounded repair call |
| Evidence-layered UI | Complete | Inspectable progress, packet and citations; quality status, validated `S*`/`C*`/`E*` citations, retrieval rationale and expandable excerpts; WCAG-audited keyboard flow |
| Fixed-workflow evaluation baseline | Complete | Frozen, fingerprinted fixed/Agent/A01/A02 metrics; the entry gate passes all 17 targets and 11 required steps; GuideLLM/lm-eval tooling is mock-qualified only |
| Autonomous research Agent | Blocked | Local, default-off. A01R class-aware acquisition and A02R patch-reliability harnesses are implemented with native tool calls; every paid comparison so far failed at least one gate, production remains NO-GO and no evaluation budget has been released since 31 August |
| Release delivery | Complete — live proof pending | Protected `master`, human `production` gate, versioned receipts and rollback across all three workflows; `VPS Release` (digest deployment over a pinned SSH host key) is the current path and the Azure workflows are inert legacy paths |
| Web responsiveness | In progress | Blocking API work offloaded to the worker pool, dossier-lifetime fetch cancellation, pre-authentication Deep Study cancel controls and minified assets, measured synthetically; live profiling of search → shelf → dossier → reception is still required |
| Clip analysis | Complete | Scene/shot metrics, shot scale, colour, objects and JSON/CSV export (local edition only) |
| Clip evidence in Deep Study | Planned (deferred) | Deferred until the text Agent programme is accepted; study generation does not consume measured clip observations or timecodes |
| Creator primary sources | Partial | Relevant video descriptions and available public captions enter Deep Study; verified speaker attribution remains planned |
| Persistent projects | Planned | Film, clip, study and note sessions are not retained as reusable projects; the autonomous phase store is a private run checkpoint only |

## Next Milestone

### Single-server cut-over — In progress (server prepared; deployment not authorised)

Objective: bring `firstroll.app` and `api.firstroll.app` back online on one rented server without
weakening the human production gate.

Acceptance criteria:

- [x] Caddy + Docker Compose stack with the API deployed by immutable digest, the former static cache
  policy and rotated logs (`infra/vps`).
- [x] Idempotent Ubuntu 24.04 bootstrap: Docker, service account, firewall, swap, unattended
  security updates and key-only SSH.
- [x] Server-side release that switches the site only after the API reports the baked commit, with
  rollback and status commands.
- [x] `VPS Release` workflow: CI-gated candidate, credential-free build to GitHub Container Registry,
  sealed receipt, verification before the deploy key exists, pinned host key, live checks and rollback.
- [x] CI validation of the stack files and 30 structural/behavioural tests.
- [x] Server purchased, bootstrapped and reachable through separate administrator/deployment keys;
  approved reboot verified on the updated kernel.
- [x] GitHub `production` deployment secret and pinned VPS host/user variables configured; existing
  human reviewer and master-only deployment policy verified and preserved.
- [x] Legacy Azure release workflows disabled and their two obsolete waiting candidates cancelled.
- [x] Owner added DeepSeek/YouTube keys; presence and private configuration validated without values.
- [x] Cloud TCP 443 allow rule observed after the owner's setup.
- [ ] Authenticated quota readiness verified before enabling paid Deep Study.
- [ ] DNS moved from Azure; certificates issued.
- [ ] VPS release activation enabled; candidate built; image contents/visibility and server pull verified.
- [ ] First owner-approved release verified in a browser (receipt, sign-in, search, shelf, dossier).
- [ ] Rollback drill on the server.

Next boundary: prepare and verify the candidate, check its image can be pulled, then complete the
agreed DNS/TLS cut-over and obtain approval for the exact first `production` run. General permission
to prepare/deploy does not override the exact-run production gate or authorise database migration.

### Autonomous Agent causal ablations — Blocked (awaiting owner evaluation budget)

Objective: prove which autonomous components add value before integrating claim review, coaching or a
product route.

Acceptance criteria:

- [x] Define typed evidence gaps and require independent origins for recovered packets.
- [x] Add a deterministic acquisition baseline and Crossref Agent action.
- [x] Acquire each provider observation once and share it privately across fixed, deterministic and
  model-planned lanes.
- [x] Blind lane identity during owner packet review.
- [x] Provide a frozen field-patch versus regeneration harness with controlled schema/citation faults.
- [x] Require exact preservation of accepted fields and complete citation validation.
- [x] Freeze value, latency, token, privacy and human thresholds before any paid call.
- [ ] Reuse an accepted private packet for synthesis without reacquisition.
- [ ] Advance claim audit only if the preceding capability earns its cost against the baseline.

Blocking decision: A01R and A02R are implemented but no paid or human evaluation budget has been
released since 31 August 2026. The owner must either fund a bounded run or record the programme as
parked.

### Standardised production release bootstrap — Superseded while Azure is suspended

Carried from the 10 September 2026 entry. The single-server cut-over replaces this proof; it would
only become relevant again if the Azure subscription were reactivated:

- an owner-approved initial frontend release (`allow_initial_release` acknowledgement, then approval of
  the protected `production` environment), which establishes the first `/release.json` rollback
  baseline;
- an owner-approved backend release so the production API matches `master` (as recorded on
  4 September 2026 it still ran its previous image);
- browser acceptance of the released candidate and a separately approved live recovery drill.

### Live responsiveness profiling and API-loop isolation — Planned

Carried from the 12 September 2026 entry:

- authorised live search → shelf → dossier → reception profiling; investigate repeated Wikidata
  enrichment, redundant TMDb shelf work, video captions delaying cards and unnecessary shelf/player DOM
  replacement before introducing new cache or provider-flow contracts;
- remove the authentication wait on initial account-data hydration;
- move local clip analysis off the API loop onto a bounded serial worker, after a separate review of
  shared output paths and model state.

## Subsequent Priorities

1. **Claim audit and targeted editor** — classify evidential strength and patch only fields or
   sections named by deterministic validation.
2. **Evidence-grounded filmmaker coach** — turn accepted claims into traceable viewing and production
   exercises without adding film facts.
3. **Durable local Agent pilot** — add owner-scoped checkpointing, cancellation, resume and private
   project retention after reliability gates pass.
4. **Clip-to-study evidence bridge** — remain deferred until the complete text Agent is accepted.
5. **Creator primary-source layer** — ingest attributed interviews, commentaries and production
   records; distinguish direct quotation, paraphrase and inference.

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
- The public beta will run on one rented server: a single point of failure with a long-lived deploy
  key, no CDN and a brief API restart on every release.
- The Supabase Free plan pauses the project after seven idle days, which breaks sign-in until it is
  resumed in the dashboard.

## Milestone Ledger

Dated entries, newest first. Entries dated 6–31 August 2026 were moved unchanged into
[PROGRESS_ARCHIVE_2026-08.md](PROGRESS_ARCHIVE_2026-08.md) on 27 September 2026.

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
6. Reconciled README, architecture/API/hosting prose and [Web Responsiveness](WEB_RESPONSIVENESS.md)
   with the implementation, measurements and remaining work.

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
  uncaught page errors and no horizontal overflow. The hash-bound
  [synthetic report](../evals/results/web-responsiveness-2026-09-12.json) is retained; no live latency or
  model-speed result is claimed.
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
5. keep limitations explicit rather than silently removing unfinished scope.
6. when the ledger grows past roughly one month or one thousand lines, move older dated entries
   unchanged into a dated `PROGRESS_ARCHIVE_<year>-<month>.md` file and link it from the ledger
   heading.
