# Backend Release Threat Model

This model describes the implemented GitHub Actions → Azure Container Registry → Azure Container
Apps release path. It does not claim that a separate approval broker, HMAC capability service or
append-only audit database exists.

## Assets and trust boundaries

Protected assets are the production API, its configuration, the ACR image set, the human approval
decision and the evidence showing what was released.

```text
Pull-request code
    │ read-only CI; no Azure identity
    ▼
protected master + successful CI
    │ branch-bound GitHub OIDC token
    ▼
build runner ── AcrPush + app Reader ── ACR candidate + sealed manifest
    │
    ▼
GitHub production environment ── required human owner review
    │ environment-bound GitHub OIDC token
    ▼
fresh deploy runner (no checkout) ── Contributor on one Container App
    │
    ▼
exact Azure revision ── health, identity, API, docs and CORS checks
                         └─ failure restores previous image
```

GitHub and Azure are external trusted platforms. Retrieved application evidence and visitor input
are unrelated to deployment authority and cannot approve a release.

## Threats and controls

| Threat | Implemented control | Residual risk |
|---|---|---|
| Pull-request code steals production credentials | PR CI receives no Azure token. OIDC subjects use GitHub's identity-bound owner/repository prefix and match `master` or the `production` environment. | A malicious change merged to `master` can affect later workflow behaviour; owner review and branch protection remain important. |
| Build identity changes production | Build identity has only `AcrPush` on one registry and `Reader` on one app. | It can upload a malicious image, but cannot select it for production. |
| Deploy identity changes unrelated Azure resources | `Contributor` is scoped to the exact FirstRoll Container App, not the resource group or subscription. | Contributor can change any setting on that app after approval. |
| Long-lived Azure or registry secret leaks | GitHub exchanges a signed OIDC assertion for a short-lived Azure token; ACR admin access stays disabled. | GitHub/Azure platform compromise is out of scope. |
| A different commit or image is deployed | Manifest binds repository, run ID, branch, full SHA, image repository/tag/digest and its own canonical digest. Deployment uses `repository@sha256:…`. | Pattern-based risk classification may miss a novel semantic risk. |
| Manifest is edited after build | Deploy job recomputes its SHA-256 content digest before requesting Azure credentials. | GitHub artefact service integrity is still trusted. |
| Old approved run overwrites newer `master` | Current remote `master` is checked before build and again after approval; concurrency does not cancel an approval in progress. Manual dispatch also requires successful push CI for the exact SHA. | A force-push by an administrator can invalidate governance assumptions. |
| Repository code runs with deploy access | Deploy runner checks out no source and uses only platform tools plus inline validation. | Workflow YAML itself came from the approved commit, so workflow changes are classified high risk. |
| Misleading release summary | Facts and risk minimum come from deterministic Git/digest/test inputs; unknown scan/SBOM states are shown as unconfigured. | Human-readable change descriptions are coarse file-area descriptions. |
| Human approves the wrong run | GitHub shows the exact run and environment; manifest summary includes full technical bindings. | Human error remains possible; compare SHA and digest before approval. |
| New revision is unhealthy or misidentified | Workflow waits for that exact revision, requires `Healthy` and `Running`, requires the baked SHA from `/api/health`, and compares Azure's configured image with the approved digest. | A shallow health endpoint cannot prove every user path works. |
| Public API boundary regresses | Post-deploy checks cover representative endpoints, exact CORS origin and disabled API documentation. | Provider-specific failures may occur after smoke checks. |
| Failed release leaves production broken | The previous image is captured before deployment and restored after a failed post-deploy check. Its commit identity is baked into that image. | Azure-wide outage or a broken previous image can make automated rollback fail. |
| Approval is bypassed | Deploy job names the branch-restricted `production` environment with a required human reviewer. The deploy OIDC subject also names that environment. | Repository administrators can alter environment policy; GitHub audit history must be reviewed for such changes. |
| Workflow starts before setup is complete | Entire release path requires `BACKEND_RELEASE_ENABLED=true`; preflight rejects missing variables/secrets. | A partially configured enabled workflow fails noisily but does not receive a valid Azure token. |

## Deterministic release policy

The release tool assigns the highest applicable minimum:

- `blocked`: CI, container test or configured scan failed;
- `high`: destructive migration, cloud identity/permission change, or release-authority change;
- `medium`: non-destructive migration, auth/quota/secret/CORS/API/base-image/infrastructure change;
- `low`: no detected sensitive category and required checks passed.

The model cannot lower this classification. High risk still requires informed human review; it is
not an automated approval.

## Evidence and auditability

GitHub retains the workflow run, protected-environment review, job logs, manifest artefact and job
summary for the configured retention period. Azure retains activity and revision logs. This is a
platform audit trail, not an application-owned append-only ledger.

The release manifest deliberately contains no access token, client secret, Supabase secret, API key
or application evidence. The deploy client ID is stored in the protected environment, and no
production credential is uploaded as an artefact.

## Not yet implemented

- container vulnerability scanning;
- software bill of materials generation;
- signed container attestations;
- durable export of GitHub/Azure deployment audit events;
- synthetic checks beyond the current representative HTTP boundary.

These gaps must remain visible in release summaries and must not be described as passing controls.
