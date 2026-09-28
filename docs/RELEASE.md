# FirstRoll Release Runbook — frontend and backend

FirstRoll uses the same release rules for two independently deployable components:

**Check → package → record → owner approval → recheck → deploy → verify → recover on failure.**

`VPS Release` is the current delivery path: it publishes the static site and the API container
together to the single rented server described in [Public Beta Hosting](HOSTING.md). `Frontend
Release` (Azure Static Web Apps) and `Backend Release` (Azure Container Apps) are the legacy Azure
paths; they stay in the repository while the disabled Azure subscription is retained, but should be
kept inert (see below). None of the workflows changes hosting, applies Terraform or runs database
migrations.

CI checks branches and pull requests without production deployment credentials. A successful push CI
run on current `master` allows candidate preparation. Manual runs require successful push CI for that
same SHA. Each component still needs its own human `production` environment approval.

## Common release contract

Both builds write `release.json`, a dependency-free, versioned receipt containing the component,
repository, environment, source commit, workflow run and build attempt, build time, approval expiry,
payload fingerprint and verification results. The frontend receipt also inventories every static
file and identifies its recovery package. The backend receipt binds its existing detailed risk
manifest and container digest. GitHub job outputs independently bind the expected receipt hash.

- New approval windows last **seven days**. Re-running only a deployment does not renew them.
- Artefacts are requested for **90 days** of recovery retention, subject to repository limits and
  deletion. This is not permanent storage and may consume GitHub artefact-storage allowance.
- The deploy runner downloads data, not build scripts. It fetches only the two reviewed Python
  control modules from the exact approved Git commit, without an application checkout or dependency
  installation. Repository administrators and reviewed workflow/control code remain trusted.
- Before cloud access is used, each deploy job checks receipt integrity, run/attempt/commit bindings,
  expiry and current `master`. The frontend also hashes the complete downloaded file inventory and
  rechecks that its planned previous live release has not changed.
- Active deployments are not cancelled by newer candidates. GitHub may replace an excess pending
  concurrency entry; this is not a FIFO release queue. Reject obsolete waiting approvals to free the
  component's release slot. The pre-deployment freshness check rejects superseded code.
- Deployment summaries record the commit, result and UTC completion-record time. A build timestamp
  is not falsely presented as a deployment timestamp. GitHub deployment history remains the audit log.

Receipt hashes detect alteration; they are **not independently signed provenance**. Green checks
do not prove application correctness. Browser-level acceptance still includes sign-in, film search,
the shelf and Deep Study, without exposing user credentials or making paid calls automatically.

## Single-server release (`VPS Release`)

Preconditions: the server was prepared with `infra/vps/bootstrap.sh`, DNS points at it, Caddy holds
certificates, and the GitHub values in [Public Beta Hosting](HOSTING.md#6-configure-github) exist.
`VPS_RELEASE_ENABLED=true` is the fail-closed switch; without it no job starts.

**Build job (no production credential).** After a successful push CI run on current `master`, or a
manual run validated against exact-SHA CI, the job audits the npm lock, builds the frontend with the
production API origin, removes the Static Web Apps routing file, builds the API image with the commit
baked in, smoke-tests the container's health, identity and hidden documentation routes, and pushes
the image to GitHub Container Registry as `ghcr.io/luo-z-y/firstroll-api:<commit>`. It then seals
`release.json` through `tools/release/vps.py`: component `vps`, the commit, run and attempt, the
image reference and its immutable digest, and a SHA-256 inventory of every site file. The site
archive, receipt and the three server stack files are uploaded as one 90-day artefact and the run
waits at the protected `production` environment.

**Deploy job (after human approval).** A fresh runner downloads only that artefact and fetches the two
reviewed control modules from the exact commit. Before any credential exists it verifies the receipt
against the build job's outputs (commit, run, attempt, receipt digest and image digest), confirms the
archive contains exactly the sealed inventory and receipt, checks the seven-day approval window and
refuses a `master` that moved. Only then is the deploy key written, together with a `known_hosts`
entry pinned to `VPS_SSH_HOST_KEY`, and used with `StrictHostKeyChecking yes`. The job records the
server's current release, uploads the package, installs the stack files from the approved commit and
runs `deploy.sh release <commit> <digest> <archive>`.

On the server, `deploy.sh` pulls the image by digest, starts it and waits until `/api/health`
reports the expected baked commit; only then does it switch `releases/current` to the new site and
reload Caddy. The runner then verifies from outside that `/release.json` equals the receipt, every
inventoried file matches its fingerprint, `/api/health` reports the commit, `/api/contract` and
`/api/discovery/status` respond, `/docs`, `/redoc` and `/openapi.json` return 404, and CORS allows
exactly `https://firstroll.app`. A failure after rollout runs `deploy.sh rollback`, which restores
the previous digest and site, and the job stays failed so the incident is visible.

Operating rules specific to this path:

- Stop automated candidates with `VPS_RELEASE_ENABLED=false`; the running server is unaffected.
- Rollback needs the previous image in GitHub Container Registry and the previous site directory on
  the server. The first release has no rollback target; recovering from it means fixing forward.
  Rolling back to an older commit than the previous release means reverting on `master`.
- Do not edit `deploy.sh`, `Caddyfile` or `docker-compose.yml` on the server; each release overwrites
  them from the approved commit.
- Rotate `VPS_SSH_PRIVATE_KEY` if it is exposed: generate a new pair, add the public key to the
  service account, replace the secret and remove the old line. The key is a long-lived credential,
  unlike the Azure OIDC exchange, and its holder has root-equivalent access to that host.
- Keep the legacy Azure workflows inert while the subscription is disabled: leave
  `BACKEND_RELEASE_ENABLED` unset and disable `Frontend Release` in the Actions UI, otherwise it builds
  a candidate on every push and fails at the Azure token.

Live proof of this path (first approved release and a rollback drill) is still pending; the
structure is covered by `tests/test_vps_release.py`, and CI validates the stack files with
`shellcheck`, `docker compose config` and `caddy validate`.

## Frontend: first standardised release

The existing legacy site has no verified `release.json` or retained known-good package. An automatic
first build therefore refuses to invent a rollback baseline. This is an expected bootstrap stop.

1. Merge the verified release-standardisation PR through protected `master` and wait for its CI.
2. Open **Actions → Frontend Release → Run workflow**. Select **master** and tick
   **allow_initial_release**. This acknowledges that this first frontend release has no automatic
   rollback baseline; it does not approve production deployment.
3. Read the generated summary, including the **INITIAL RELEASE** warning and expiry time.
4. If acceptable, select **Review deployments → production → Approve and deploy** for that exact run.
5. Wait for the upload and live checks to pass. Confirm `/release.json` identifies the expected
   commit, and check the public website's main user flows. A first-run failure requires owner
   recovery; the workflow cannot reconstruct an unrecorded legacy package.

The successful first release establishes the baseline. Future releases do not need the checkbox.
Setting it cannot bypass a malformed live receipt, a provider outage, a changed baseline, or a
missing/expired package for an already-standardised site.

## Frontend: routine releases and recovery

The build reads the current live receipt and verifies that its exact package belongs to a successful
same-repository frontend release on `master`. The new receipt binds that previous package. After
approval the deploy runner rechecks the live baseline, downloads the previous artefact by ID,
verifies its receipt and all files, then uploads the approved new package without rebuilding it.

Live verification retries within a three-minute deadline and checks:

- the exact published receipt and every public file's SHA-256 hash;
- API health, contract and discovery-status endpoints;
- no cached substitute for the new receipt (`release.json` is configured `no-store`).

Azure consumes `staticwebapp.config.json`; it is hashed in the package but not expected as a public
URL. Server-to-server API smoke checks do not replace authenticated browser or CORS acceptance.

If upload or verification fails after an upload attempt, the workflow reuploads the already-verified
previous static package and verifies its exact receipt and files. It does not rebuild old source.
Recovery verification does not require a separately failing API to recover: a frontend rollback
cannot repair a backend outage. The overall workflow remains **failed**, even after recovery.

For a failure:

1. Inspect **Verify the live frontend and API**, **Restore the verified previous frontend** and
   **Verify restored frontend identity and files** in the same run.
2. If recovery passed, confirm the previous version is live. Fix the cause on a new branch and
   prepare a fresh candidate; do not approve a stale run or erase the failed result.
3. If recovery failed, or execution was cancelled/timed out, stop releasing and inspect the current
   public receipt and retained package. Do not assume an upload failure left production unchanged.
4. Missing/expired recovery packages require an owner-reviewed recovery procedure or replacement
   baseline. Never silently substitute an unrelated successful build or disable the integrity gate.

Automatic restoration and their failure paths are tested with local fixtures. A real Azure rollout,
deliberately failed rollout and recovery still need owner-approved operational verification. There
is no new staging service, cross-service atomic release or frontend Azure OIDC migration in this change.

The workflow is **fail-closed by default**. Production now sets
`BACKEND_RELEASE_ENABLED=true` because the one-time identity and GitHub setup below is complete; a
fresh installation must not enable it before completing those steps.

## Mental model

| Item | Meaning |
|---|---|
| Azure Container Registry (ACR) | Private storage for versioned Docker images; it does not run them. |
| Azure Container App | The service that runs one selected image as `api.firstroll.app`. |
| Managed identity | An Azure account for software, with no password to store. |
| OIDC federation | Azure trusts a short-lived, GitHub-signed identity token for one matching workflow context. |
| Build identity | Can push to FirstRoll ACR and read the current app; cannot deploy. |
| Deploy identity | Can update only the FirstRoll Container App; its token is requested after approval. |
| `production` environment | GitHub's human approval gate and storage boundary for the deploy client ID. |

## Backend: one-time setup (already completed for FirstRoll)

### 1. Review the infrastructure plan

From `infra/terraform`, initialise the existing remote state and review the plan. Supply the existing
backend configuration and sensitive values through the established local mechanism; never commit
them.

```bash
terraform init -backend-config=backend.hcl
terraform fmt -check
terraform validate
terraform plan
```

The plan should add two managed identities, two federated credentials and three narrow role
assignments. It must not replace the live Container App, registry, custom domain or Static Web App.
Before applying, verify that Terraform's subject prefix matches GitHub's live value:

```bash
gh api repos/Luo-Z-Y/FirstRoll/actions/oidc/customization/sub --jq .sub_claim_prefix
```

The current prefix includes the immutable owner and repository IDs. A legacy
`repo:Luo-Z-Y/FirstRoll` subject will be rejected by Azure before any registry or deployment access
is issued.

Apply only after reviewing that exact plan:

```bash
terraform apply
```

Record the values printed by:

```bash
terraform output -raw github_build_client_id
terraform output -raw github_deploy_client_id
terraform output -raw container_registry_login_server
```

### 2. Configure GitHub repository values

Open **Repository → Settings → Secrets and variables → Actions**.

Add the repository secret:

| Secret | Value |
|---|---|
| `AZURE_BUILD_CLIENT_ID` | `terraform output -raw github_build_client_id` |

Add these repository variables:

| Variable | Value |
|---|---|
| `AZURE_TENANT_ID` | Azure tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `ACR_LOGIN_SERVER` | `terraform output -raw container_registry_login_server` |
| `AZURE_RESOURCE_GROUP` | `firstroll-production` |
| `AZURE_CONTAINER_APP_NAME` | `firstroll-api` |

Do not add an Azure JSON credential, ACR username or ACR password. OIDC replaces them.

### 3. Configure the protected production environment

Open **Repository → Settings → Environments → production**.

1. Keep `master` as the only deployment branch.
2. Keep the repository owner as a required reviewer.
3. Add environment secret `AZURE_DEPLOY_CLIENT_ID` using
   `terraform output -raw github_deploy_client_id`.
4. Do not enable administrator bypass or remove the reviewer to make a run continue.

The existing frontend deployment token may remain in this environment; it is unrelated to backend
OIDC.

### 4. Enable and prove the workflow

Only after steps 1–3, add repository variable `BACKEND_RELEASE_ENABLED` with value `true`. Open
**Actions → Backend Release → Run workflow**, select `master`, and start one release.
The manual path first proves that this exact `master` SHA already has a successful push-triggered CI
run; it cannot relabel an untested revision as passed.

The build job should:

1. bind itself to current `master`;
2. build and locally smoke-test the container;
3. obtain a short-lived build token from Azure;
4. bake the full commit SHA into the image and push it under that tag;
5. resolve its immutable digest;
6. generate a deterministic risk manifest and readable summary.

The deploy job then pauses at `production`. Review the summary, commit and image digest in that run.
Approve only when they match what you intend to release.

## What happens after approval

The fresh deploy runner downloads the sealed evidence and approved control modules; it does not
check out the application. Before Azure sign-in it verifies the shared receipt's seven-day validity
and independent fingerprint, recomputes the detailed manifest digest, verifies every run/commit/image binding and
checks that `master` has not moved. It then obtains a short-lived deploy token, saves the current
image as the rollback target, deploys the candidate digest and verifies:

- the exact Azure revision is healthy and running;
- `/api/health` reports the commit SHA baked into the image;
- Azure reports that the app is configured with the exact approved image digest;
- `/api/contract` and `/api/discovery/status` respond;
- `/docs`, `/redoc` and `/openapi.json` stay unavailable publicly;
- CORS allows `https://firstroll.app` exactly.

If a check fails after rollout starts, the workflow restores the previous image (which carries its
own baked release identity).
The job remains failed so the incident is visible even if rollback succeeds.

Backend scope/risk analysis compares the candidate with the deployed `release_sha`, not just its
immediate parent. If production has no usable ancestor SHA, it conservatively reviews the whole
tree. Runtime requirements, shared release tools, CI policy and migration source changes trigger a
candidate review. Migration and Terraform files are review evidence only: this workflow applies neither.
Container images must remain available in ACR for recovery; GitHub's 90-day evidence retention does
not control registry deletion.

## Safe operating rules

- Never approve a run merely to clear a queue.
- Never replace digest deployment with `latest` or another mutable tag.
- Never put production secrets in repository variables, logs, manifests or the frontend bundle.
- A high-risk result is reviewable, not automatically safe. A `blocked` result cannot deploy.
- If `master` moves while approval is pending, reject the old run and start a new one.
- To stop automated candidates, set `BACKEND_RELEASE_ENABLED` to `false` or remove it. Existing
  production traffic is unaffected.

## Current limitation

Image vulnerability scanning and SBOM generation are not configured yet, so the summary states that
honestly. Their absence is not silently presented as a pass. Adding either control is a separate,
testable hardening change.

GitHub approval is a human release-intent gate, not independent two-person review. Workflow YAML and
the exact-commit control modules remain repository-controlled. Cancelled jobs, exhausted timeouts or
platform outages can prevent automatic rollback. The initial frontend bootstrap has no legacy
rollback guarantee; subsequent recovery is bounded by retained, verified artefact availability.
