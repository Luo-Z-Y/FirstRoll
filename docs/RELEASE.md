# Backend Release Runbook

FirstRoll builds a backend candidate after successful CI on `master`, but a human owner must approve
the exact GitHub Actions deployment before Azure credentials become available. The workflow deploys
an immutable image digest and rolls back if the new revision fails its checks.

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

## One-time setup

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

The fresh deploy runner downloads only the sealed manifest; it does not check out repository code.
Before Azure sign-in it recomputes the manifest digest, verifies every run/commit/image binding and
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
