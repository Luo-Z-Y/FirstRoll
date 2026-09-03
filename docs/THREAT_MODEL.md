# Backend Release Approval — Threat Model

This document identifies the threats to the FirstRoll backend production
approval system and records the mitigation for each threat.

## Trust boundaries

```
┌─────────────────────────────────────────────┐
│ Repository-controlled code                  │
│ (CI, build scripts, workflow definitions)   │
│ Trust level: contributor                    │
├─────────────────────────────────────────────┤
│ GitHub Actions runner                       │
│ Trust level: ephemeral, sandboxed           │
├─────────────────────────────────────────────┤
│ GitHub platform                             │
│ (environment protection, pending reviews)   │
│ Trust level: platform                       │
├─────────────────────────────────────────────┤
│ Approval broker service                     │
│ Trust level: trusted service identity       │
├─────────────────────────────────────────────┤
│ Azure Container Registry                    │
│ Trust level: cloud infrastructure           │
├─────────────────────────────────────────────┤
│ Azure Container Apps (production)           │
│ Trust level: production                     │
├─────────────────────────────────────────────┤
│ Agent runtime                               │
│ Trust level: delegated, no standing access  │
└─────────────────────────────────────────────┘
```

---

## Threat catalogue

### T01 — Permanent agent authority

| Field | Value |
|---|---|
| Asset | Production deployment gate |
| Actor | Agent with standing credentials |
| Precondition | Agent holds a reusable PAT or App key |
| Trust boundary | Agent → GitHub production environment |
| Mitigation | Agent never receives signing keys, PATs, App private keys, or reusable deployment tokens. Single-use HMAC capabilities expire in 15 minutes and are consumed after first use. |
| Residual risk | If the signing key leaks, an attacker could mint capabilities until the key is rotated. |
| Verification test | `test_agent_cannot_approve_without_signing_key` |

### T02 — Stolen reusable GitHub token

| Field | Value |
|---|---|
| Asset | GitHub deployment approval |
| Actor | Attacker with a leaked PAT |
| Precondition | A long-lived PAT exists |
| Trust boundary | External → GitHub API |
| Mitigation | No PATs are used. The approval broker uses short-lived GitHub App installation tokens (max 1 hour). The `GITHUB_TOKEN` in workflows cannot approve its own pending deployment. |
| Residual risk | GitHub App private key compromise (see T16). |
| Verification test | Workflow does not reference `secrets.GITHUB_TOKEN` for approval. |

### T03 — Replayed approval capability

| Field | Value |
|---|---|
| Asset | Production deployment |
| Actor | Attacker who intercepts a valid capability |
| Precondition | Capability token intercepted |
| Trust boundary | Agent/UI → Approval broker |
| Mitigation | Single-use nonce consumed atomically. Expired capabilities (15-minute TTL) are rejected. HMAC signature prevents forgery. |
| Residual risk | Race condition if nonce store is non-atomic (mitigated by thread lock; production should use Redis SETNX). |
| Verification test | `test_reused_authorization_rejected` |

### T04 — Approval for one candidate applied to another

| Field | Value |
|---|---|
| Asset | Deployment integrity |
| Actor | Attacker or confused agent |
| Precondition | Valid capability exists for candidate A |
| Trust boundary | Approval broker verification |
| Mitigation | Capability is bound to commit SHA, image digest, workflow run ID, manifest digest. Verification rejects any mismatch. |
| Residual risk | None if all binding fields are checked. |
| Verification test | `test_approval_for_one_candidate_cannot_approve_another`, `test_wrong_commit_sha_rejected`, `test_wrong_image_digest_rejected` |

### T05 — Candidate changed after user review

| Field | Value |
|---|---|
| Asset | User's informed consent |
| Actor | Concurrent merge or image rebuild |
| Precondition | User reviews candidate, then candidate changes |
| Trust boundary | Manifest integrity |
| Mitigation | Capability binds to manifest digest. If the candidate changes, the manifest digest changes, and the capability is rejected. Stale-revision check in the build job aborts if master has moved. |
| Residual risk | None if manifest digest is verified. |
| Verification test | `test_wrong_manifest_digest_rejected` |

### T06 — Stale release overwriting a newer release

| Field | Value |
|---|---|
| Asset | Production currency |
| Actor | Delayed approval of an older candidate |
| Precondition | Newer master commit exists |
| Trust boundary | Build job stale-revision check |
| Mitigation | Strict latest-only policy: build job verifies `HEAD` of `origin/master` matches the triggering SHA. Concurrency group cancels older runs. |
| Residual risk | Brief race window between stale check and image push. |
| Verification test | Workflow YAML inspection (`test_branch_must_be_master`) |

### T07 — Compromised repository code reaching approval credentials

| Field | Value |
|---|---|
| Asset | Approval broker credentials |
| Actor | Malicious PR author |
| Precondition | PR merges code that exfiltrates secrets |
| Trust boundary | Repository code → Approval service |
| Mitigation | Build job does not have approval credentials. Deploy job runs on a fresh runner with no code checkout. Approval broker runs as a separate service with its own credentials. GitHub App private key is never in repository secrets. |
| Residual risk | If the broker service itself is compromised (see T16). |
| Verification test | `test_no_checkout_step` (deploy job) |

### T08 — Prompt injection causing deployment

| Field | Value |
|---|---|
| Asset | Production deployment |
| Actor | Attacker injecting instructions via PR title/description |
| Precondition | Agent processes untrusted text |
| Trust boundary | Agent → Approval system |
| Mitigation | LLM-generated prose is separate from the structured manifest. The approval binds to the manifest, not to the natural-language summary. Explicit approval action required; vague text ("go ahead") does not trigger approval. |
| Residual risk | Agent could be confused about which candidate to present, but cannot mint a valid capability without the signing key. |
| Verification test | `test_agent_cannot_approve_without_signing_key` |

### T09 — Fabricated release summary

| Field | Value |
|---|---|
| Asset | User's informed decision |
| Actor | Compromised or hallucinating LLM |
| Precondition | LLM generates the approval summary |
| Trust boundary | Manifest → Summary |
| Mitigation | Critical facts (CI status, digest, migration, scan) come from the structured manifest, not from LLM generation. The LLM may rephrase but cannot invent or alter test results, digests, migration presence, or risk classification. Summary tests verify unavailable facts are never fabricated. |
| Residual risk | LLM could downplay non-deterministic risk reasons (mitigated by deterministic minimum risk level). |
| Verification test | `test_never_fabricates_unavailable_facts` |

### T10 — Misleading risk classification

| Field | Value |
|---|---|
| Asset | User's risk perception |
| Actor | Bug or LLM override |
| Precondition | Risk level is incorrectly lowered |
| Trust boundary | Risk engine |
| Mitigation | Deterministic minimum risk level cannot be lowered. Migration presence forces ≥ medium. Destructive migration forces high. Failed checks force blocked. The `minimum_deterministic_level` field is recorded and compared. |
| Residual risk | Novel risk factors not covered by pattern detection. |
| Verification test | `test_deterministic_minimum_is_preserved` |

### T11 — GitHub webhook spoofing

| Field | Value |
|---|---|
| Asset | Workflow trigger integrity |
| Actor | External attacker |
| Precondition | Attacker sends fake webhook |
| Trust boundary | GitHub platform |
| Mitigation | GitHub Actions `workflow_run` events are platform-generated and cannot be spoofed via external webhooks. The build job additionally verifies `head_repository.full_name == github.repository`. |
| Residual risk | GitHub platform compromise (out of scope). |
| Verification test | `test_repository_must_match` |

### T12 — CSRF against approval UI

| Field | Value |
|---|---|
| Asset | Approval decision |
| Actor | Attacker with cross-origin request |
| Precondition | User is authenticated to approval UI |
| Trust boundary | Browser → Approval broker |
| Mitigation | If a browser-based approval UI is added, it must include CSRF tokens and SameSite cookies. Current implementation uses HMAC-signed capabilities which are inherently CSRF-resistant (the attacker cannot forge a valid token). GitHub's built-in review UI has its own CSRF protection. |
| Residual risk | None for the current HMAC-based design. |
| Verification test | N/A (no browser approval UI currently deployed) |

### T13 — Race between approval and deployment

| Field | Value |
|---|---|
| Asset | Deployment consistency |
| Actor | Concurrent approvals |
| Precondition | Two approval attempts for the same candidate |
| Trust boundary | Nonce store |
| Mitigation | Atomic nonce consumption (thread lock for in-memory; Redis SETNX for production). GitHub's pending deployment API is idempotent for the same run/environment. Concurrency group prevents parallel deploy jobs. |
| Residual risk | In-memory nonce store is not durable across process restarts. |
| Verification test | `test_reused_authorization_rejected` |

### T14 — Audit-log tampering

| Field | Value |
|---|---|
| Asset | Audit trail integrity |
| Actor | Attacker with file system access |
| Precondition | Audit log stored on mutable file system |
| Trust boundary | Broker → Audit storage |
| Mitigation | Production audit log should use an append-only service (Azure Monitor, CloudWatch). Current file-based log is for development. Audit events contain identifiers but no secrets. |
| Residual risk | File-based log is mutable in development. |
| Verification test | `test_audit_event_contains_no_secrets` |

### T15 — Secret leakage

| Field | Value |
|---|---|
| Asset | Credentials and tokens |
| Actor | Build job, audit log, or error message |
| Precondition | Secret appears in logs or artifacts |
| Trust boundary | All boundaries |
| Mitigation | Audit events never contain signing keys, tokens, or private keys. Workflow uses `persist-credentials: false`. Terraform state uses encrypted remote backend. Production secrets are environment-scoped. `.gitignore` and `.dockerignore` exclude sensitive paths. |
| Residual risk | Docker layer caching could expose intermediate secrets (mitigated by multi-stage build). |
| Verification test | `test_audit_event_contains_no_secrets` |

### T16 — Approval broker compromise

| Field | Value |
|---|---|
| Asset | GitHub App identity |
| Actor | Attacker who compromises the broker service |
| Precondition | Broker service is compromised |
| Trust boundary | Broker → GitHub API |
| Mitigation | GitHub App has minimal permissions (`deployments: write`, `actions: read`). Installation tokens are short-lived (1 hour). The App can only approve pending deployments for repositories where it is installed. Credential rotation and monitoring are operational controls. |
| Residual risk | Until detection, attacker could approve pending deployments. |
| Verification test | Operational: monitor GitHub audit log for unexpected approvals. |

### T17 — Rollback to an unsafe revision

| Field | Value |
|---|---|
| Asset | Production integrity |
| Actor | Operator or automated rollback |
| Precondition | Previous revision has a known vulnerability |
| Trust boundary | Operational |
| Mitigation | Rollback restores the immediately previous known-good revision. If that revision is also unsafe, manual intervention is required. Destructive rollback actions require explicit authorisation. |
| Residual risk | No automated rollback-safety validation. |
| Verification test | Manual: verify rollback target before executing. |

---

## Summary

| Threat | Severity | Mitigated | Test coverage |
|---|---|---|---|
| T01 Permanent agent authority | Critical | ✅ | ✅ |
| T02 Stolen reusable token | Critical | ✅ | ✅ |
| T03 Replayed capability | High | ✅ | ✅ |
| T04 Cross-candidate approval | High | ✅ | ✅ |
| T05 Changed candidate | High | ✅ | ✅ |
| T06 Stale release | Medium | ✅ | ✅ |
| T07 Compromised code → credentials | Critical | ✅ | ✅ |
| T08 Prompt injection | High | ✅ | ✅ |
| T09 Fabricated summary | Medium | ✅ | ✅ |
| T10 Misleading risk | Medium | ✅ | ✅ |
| T11 Webhook spoofing | Low | ✅ | ✅ |
| T12 CSRF | Medium | ✅ | N/A |
| T13 Race condition | Low | ✅ | ✅ |
| T14 Audit tampering | Medium | Partial | ✅ |
| T15 Secret leakage | Critical | ✅ | ✅ |
| T16 Broker compromise | Critical | Partial | Operational |
| T17 Unsafe rollback | Medium | Partial | Manual |
