# FirstRoll Public Beta Hosting

**Deployment status:** Offline. The Azure Free Trial subscription was disabled when its credit
expired (observed 27 September 2026), which suspended both the Static Web App and the Container
Apps environment. The public beta is being moved to one rented Linux server.

**Visitor URL:** `https://firstroll.app`

**API URL:** `https://api.firstroll.app`

**Last reconciled:** 29 September 2026

**Preparation checkpoint:** Tencent VPS purchased and bootstrapped. Separate administrator and
deployment logins, Docker/Compose, UFW and unattended updates pass after the owner-approved reboot.
Caddy configuration validates, but its public service and the API have not been started. GitHub's
dedicated deployment secret and pinned-host variables are configured behind the existing owner
review; both Azure release workflows are disabled. The certificate contact is saved privately.
Provider-key transfer awaits explicit consent, and Tencent's cloud firewall still lacks TCP 443.
DNS/TLS, package preparation and the first exact-run production approval remain; `VPS_RELEASE_ENABLED`
is deliberately unset. See [configuration evidence](PROGRESS.md#29-september-2026--protected-vps-access-configured-activation-held).

FirstRoll is not merely a local application. Its public beta serves the static browser bundle and the
Docker API from separate origins, while private-library and clip-analysis capabilities remain local
by design. The current target is a single self-managed server on which Caddy terminates TLS for both
hostnames, serves the static release and proxies the API container:

```text
Browser  ->  Caddy on the rented server  ->  FastAPI container  ->  public film sources
              firstroll.app (static files)   api.firstroll.app
```

The hosted edition publishes discovery, the native director shelf, Supabase email-and-password
accounts with saved films, and an authenticated Integration Centre. Private-library settings, local
documents, clip uploads, computer-vision analysis and unauthenticated Deep Study are blocked by the
backend. Authenticated Deep Study is protected by durable Supabase usage counters. The separate
origins keep the public boundary explicit even though both are now served by one host.

The frontend and API origins are deployment configuration. `FIRSTROLL_API_BASE` points to
`https://api.firstroll.app`, while `FIRSTROLL_CORS_ALLOWED_ORIGINS` must include the exact
`https://firstroll.app` origin. See
[Architecture](ARCHITECTURE.md), [API Reference](API_REFERENCE.md), [Data Model](DATA_MODEL.md) and
[Architecture Decisions](DECISIONS.md) for the corresponding runtime contracts.

The server stack lives under `infra/vps`; the `VPS Release` workflow and
[Release Runbook](RELEASE.md) deliver it. Terraform under `infra/terraform` still describes the
legacy Azure resources, which remain in the disabled subscription and could be reactivated by
upgrading it to pay-as-you-go. Spaceship remains the DNS provider. The Azure sections later in this
document are kept as legacy reference until that path is removed.

## Single-server hosting

Accounts, saved films and quotas stay in Supabase, and study results remain transient in the API
process. A replacement server can be bootstrapped from this repository, but keep encrypted off-host
backups of private configuration and a recovery plan for Supabase; the repository does not contain
the server's secrets or TLS state.

### 1. Confirm the purchased server

| Setting | Purchased instance, verified 29 September 2026 |
|---|---|
| Provider and region | Tencent Lighthouse Starter, Singapore Zone 2 |
| Size | 2 vCPUs, 2 GB memory, 40 GB SSD; approximately 2 GB swap already configured |
| Image | Ubuntu 24.04.4 LTS, x86-64 |
| Access | Personal SSH key bound to `ubuntu`; use `sudo` for administration, not direct root login |
| Transfer | Console reports 512 GB/month and 20 Mbps; check excess-traffic and renewal charges separately |
| Expiry | 29 September 2027; renewal pricing has not been verified |

Before first SSH authentication, compare the server's Ed25519 fingerprint against
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` in Tencent's trusted browser terminal. Only then
trust that host key locally. Never disable host-key checking. `SERVER_IP` below is the verified
public IPv4 address. Replace the example personal-key path with the actual local filename.

### 2. Create a dedicated deploy key

GitHub Actions connects with its own key, never with your personal one:

```bash
ssh-keygen -t ed25519 -N '' -C firstroll-vps-github-actions -f ~/.ssh/firstroll-vps-deploy
```

Do not overwrite an existing key. The public half (`~/.ssh/firstroll-vps-deploy.pub`) goes to the
server in the next step. Keep the private half owner-readable only and outside the repository; it
will later become the `VPS_SSH_PRIVATE_KEY` secret of the protected `production` environment.
Creating the local key does not configure GitHub or authorise a release.

### 3. Bootstrap the server

On a fresh server, copy only the setup files and deployment **public** key. Do not recursively
upload `infra/`, which may contain a downloaded administrator key. These examples assume a personal
key at `~/.ssh/firstroll-admin.pem` and a host key already verified and recorded locally:

```bash
ssh -i ~/.ssh/firstroll-admin.pem -o StrictHostKeyChecking=yes ubuntu@SERVER_IP \
  'mkdir -p /home/ubuntu/firstroll-vps'
scp -i ~/.ssh/firstroll-admin.pem -o StrictHostKeyChecking=yes \
  infra/vps/bootstrap.sh infra/vps/deploy.sh infra/vps/docker-compose.yml \
  infra/vps/Caddyfile infra/vps/.env.example ~/.ssh/firstroll-vps-deploy.pub \
  ubuntu@SERVER_IP:/home/ubuntu/firstroll-vps/
ssh -i ~/.ssh/firstroll-admin.pem -o StrictHostKeyChecking=yes ubuntu@SERVER_IP
# On the server; keep this session open until new administrator/deployment logins pass:
sudo env NEEDRESTART_MODE=a \
  FIRSTROLL_DEPLOY_PUBLIC_KEY="$(cat /home/ubuntu/firstroll-vps/firstroll-vps-deploy.pub)" \
  bash /home/ubuntu/firstroll-vps/bootstrap.sh
```

`bootstrap.sh` upgrades packages, installs Docker and Compose from Ubuntu, rotates container logs,
creates the `firstroll` service account with the supplied deployment public key, installs the stack
under `/opt/firstroll` with a placeholder site, adds swap only on qualifying small servers without
existing swap, enables `ufw` (TCP 22/80/443 and UDP 443), turns on unattended security updates and
restricts SSH to key authentication. It also copies root's authorised keys if present; it does not
copy `ubuntu`'s personal key into the deployment account. The Docker group is root-equivalent.

Reruns preserve `.env` and published releases but refresh stack files, upgrade packages and restart
Docker, so review any existing workloads first. At the end the script prints the server's public
Ed25519 host key line for step 6. Verify new logins for both `ubuntu` and `firstroll`, effective
`sshd -T` settings, firewall rules and `docker compose config --quiet` before closing the original
administrator session. Package updates may require a separately scheduled reboot.

On Ubuntu's socket-activated SSH setup, an OpenSSH upgrade can leave `ssh.socket` active but
`ssh.service` stopped, with `/run/sshd` absent. The bootstrap starts `ssh.service` before its final
standalone `sshd -t`, letting systemd create that runtime directory. It then validates and reloads;
failure must not be worked around by weakening SSH authentication.

Tencent's cloud firewall is separate from `ufw`: verify it allows the intended SSH/deployment and
web traffic too. Do not expose the API's internal port 10000. Preparing files does not start Caddy,
obtain certificates, change DNS or deploy the application.

The console inspection on 29 September found only TCP 22, TCP 80 and ICMP allowed from all IPv4
addresses. Add an explicit TCP 443 allow rule, with the owner's approval, before HTTPS cut-over.
UDP 443 is optional for HTTP/3; TCP 443 is sufficient for ordinary HTTPS. Do not select **Allow all**.

Then edit the private environment file on the server:

```bash
ssh -i ~/.ssh/firstroll-vps-deploy -o StrictHostKeyChecking=yes firstroll@SERVER_IP
nano /opt/firstroll/.env     # set CADDY_ACME_EMAIL; leave FIRSTROLL_IMAGE_DIGEST as printed
```

For a migration, get explicit consent before copying existing provider credentials to a new host.
Transfer only the named keys over host-verified SSH, never through chat, Git, build arguments or
frontend files. Keep the destination owner-readable only (0600) and validate with
`docker compose --project-directory /opt/firstroll config --quiet`; ordinary `config` prints resolved
values and must not be used in shared logs. An unavailable optional TMDb key means discovery falls
back to the open catalogue, not that a working TMDb integration has been verified. Keep paid Deep
Study disabled until its provider key and authenticated quota boundary are verified.

The file already carries the public Supabase values and the public-mode switches from
`infra/vps/.env.example`. Keep Deep Study disabled until section
[Enable quota-controlled Deep Study](#enable-quota-controlled-deep-study) is complete.

### 4. Point DNS at the server

In Spaceship, replace the Azure records with the server address:

| Record | Type | Value |
|---|---|---|
| `firstroll.app` | A | `SERVER_IP` (replaces the Static Web Apps records) |
| `api.firstroll.app` | A | `SERVER_IP` (replaces the `*.azurecontainerapps.io` CNAME) |
| `asuid.api.firstroll.app` | TXT | Leave in place during cut-over; remove later only if no longer needed |

Save the previous records first. Replace only conflicting website/API records, check for stale AAAA
records, and preserve unrelated mail and verification records.

Wait until `dig +short firstroll.app` and `dig +short api.firstroll.app` both return the server
address before continuing, otherwise certificate issuance fails and is rate-limited by Let's Encrypt.

### 5. Start Caddy and obtain certificates

```bash
ssh -i ~/.ssh/firstroll-vps-deploy -o StrictHostKeyChecking=yes firstroll@SERVER_IP
docker compose --project-directory /opt/firstroll up -d --no-deps caddy
docker compose --project-directory /opt/firstroll logs -f caddy
```

The log should report a certificate obtained for each hostname. `https://firstroll.app` then shows
the placeholder page and `https://api.firstroll.app` returns `502` until the first release. Starting
only Caddy is deliberate: the API image is published by the release workflow, not built on the server.

### 6. Configure GitHub

| Location | Name | Value |
|---|---|---|
| `production` environment secret | `VPS_SSH_PRIVATE_KEY` | contents of `~/.ssh/firstroll-vps-deploy` |
| Repository variable | `VPS_HOST` | the server IP address (or a hostname that resolves to it) |
| Repository variable | `VPS_SSH_HOST_KEY` | the `ssh-ed25519 AAAA...` line printed by `bootstrap.sh` |
| Repository variable | `VPS_USER` | `firstroll` (optional; this is the default) |
| Repository variable | `VPS_RELEASE_ENABLED` | `true` only after every other value is in place |

Also keep the legacy Azure workflows inert: leave `BACKEND_RELEASE_ENABLED` unset or `false`, and
disable `Frontend Release` from **Actions → Frontend Release → ⋯ → Disable workflow**, because it
would otherwise build a candidate on every `master` push and fail at the Azure token.
Disable `Backend Release` too when the Azure path is no longer being used, and cancel obsolete
waiting Azure candidates instead of approving them. Preserve the existing environment reviewers
and the master-only deployment branch policy. Saving a VPS key is not permission to approve a run.

After the first build, open your GitHub **Packages** list, select `firstroll-api` and confirm its
visibility is **Public** only after inspecting the build inputs for secrets and private data. The
server currently pulls anonymously; a public repository alone does not prove an image is safe to
publish. Confirm that `production` has a required human reviewer before enabling releases.

### 7. Run the first release

A merge to `master` with green CI starts `VPS Release`, or start it from **Actions → VPS Release →
Run workflow** on `master`. The build job audits dependencies, builds the frontend and the image,
smoke-tests the container, pushes the image to GitHub Container Registry, seals `release.json` and
uploads the package. The run then waits at the protected `production` environment.

Read the step summary, then choose **Review deployments → production → Approve and deploy**. The
deploy job verifies the receipt, archive and current `master`, connects with the pinned host key,
uploads the package, runs `/opt/firstroll/deploy.sh release`, and verifies the live receipt, every
static file, the API's baked commit, hidden documentation routes and the exact CORS origin.

Confirm in a browser: `https://firstroll.app/release.json` names the merged commit, the header shows
`vN · LIVE`, sign-in works, a search fills the shelf and a dossier opens.

### 8. Operate the server

```bash
/opt/firstroll/deploy.sh status                                        # releases and containers
docker compose --project-directory /opt/firstroll logs --tail 200 api  # API log
/opt/firstroll/deploy.sh rollback                                      # previous release
docker compose --project-directory /opt/firstroll up -d api            # apply a .env change
# Reboot through the administrator's ubuntu account, not the deployment account:
# sudo reboot
```

Enable Deep Study by setting `FIRSTROLL_DEEP_STUDY_ENABLED=true` and `DEEPSEEK_API_KEY` in
`/opt/firstroll/.env`, then re-run the `up -d api` command. Never edit `deploy.sh`, `Caddyfile` or
`docker-compose.yml` on the server by hand: the workflow overwrites them from the approved commit on
each release, so change them in the repository instead.

Rotate the deploy key by generating a new pair, appending the public key to
`/home/firstroll/.ssh/authorized_keys`, replacing the `production` secret and removing the old line.

### 9. Cost, limits and risks

- The purchased instance has a prepaid server term and a finite traffic allowance. Excess traffic,
  optional services and renewal may cost extra; check the account's actual rates and alerts. Paid
  model/API usage is a separate cost.
- One server is a single point of failure with no autoscaling and no CDN; static assets are served
  from one region. Each release restarts the API container, so the API is unavailable for a few
  seconds while Caddy keeps serving the static shell.
- The deploy key is a long-lived credential, unlike the Azure OIDC exchange. Its private half stays
  on the operator's Mac and, once configured, in the approval-bound `production` environment. The
  workflow pins the server identity; this does not itself restrict where a stolen key could be
  used. Rotate the key if exposed. Membership of the `docker` group is equivalent to root.
- Rollback needs the previous image in GitHub Container Registry and the previous site directory on
  the server; the very first release has nothing to roll back to.
- Public criticism and video sources may treat the new IP address differently from Azure's. Their
  absence degrades evidence coverage rather than availability.
- The Supabase Free plan pauses a project after seven idle days; a paused project breaks sign-in until
  it is resumed in the Supabase dashboard.

## Local production checks

For day-to-day UI work, run the hosted frontend mode rather than the private
local edition:

```bash
./tools/preview_hosted_web.sh
```

Open `http://127.0.0.1:4173`. This uses the same public-mode feature boundary
and the same `app/web` source as `firstroll.app`, but serves the browser and API
from one localhost origin. To test account features too, provide `SUPABASE_URL`
and `SUPABASE_PUBLISHABLE_KEY` before starting the script.

The header carries a comparable build identity:

- `vN · LIVE` is the Git commit count deployed by Azure;
- `vN+1 · LOCAL` is the next development candidate on localhost;
- hovering the label shows the short Git commit.

`tools/build_web.sh` generates this metadata in `assets/config.js`; FastAPI
generates the same fields for local previews. Do not edit a generated `dist`
file to change the label. A normal commit and Azure deployment advances the
live build number automatically.

Build the static site with a temporary API address:

```bash
FIRSTROLL_API_BASE=https://api.firstroll.app ./tools/build_web.sh
```

Build and start the backend container:

```bash
docker build -t firstroll:azure .
docker run --rm --name firstroll-azure-test \
  -e FIRSTROLL_PUBLIC_MODE=true \
  -p 127.0.0.1:18000:10000 \
  firstroll:azure
```

In another terminal, verify:

```bash
curl http://127.0.0.1:18000/api/health
curl http://127.0.0.1:18000/api/discovery/status
```

Stop the test container with `docker stop firstroll-azure-test`.

## Legacy: Render rollback procedure

Render is no longer the production API. Use these steps only if an Azure rollback cannot be
completed by selecting the last healthy immutable Container App revision:

1. Sign in to the Render dashboard.
2. Select **New** and then **Web Service**.
3. Connect the GitHub repository containing FirstRoll. Grant access only to this repository when
   Render offers that choice.
4. Enter these settings:

   | Setting | Value |
   |---|---|
   | Name | `firstroll-api-luo` or another available name |
   | Region | Singapore |
   | Branch | `master` |
   | Root directory | leave empty |
   | Runtime | Docker |
   | Dockerfile path | `./Dockerfile` |
   | Docker build context | `.` |
   | Instance type | Free |
   | Health check path | `/api/health` |
   | Auto-deploy | After CI checks pass |

5. Add this environment variable before the first deployment:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_PUBLIC_MODE` | `true` |

6. Do not add a DeepSeek key, Supabase service-role key or local connector secret yet.
7. Select **Create Web Service**.
8. Wait for the deployment to report **Live**.
9. Open `https://YOUR-BACKEND.onrender.com/api/health` and confirm that it returns
   `{"status":"ok"}`.

Record the complete backend URL. It is required when building the Azure frontend.

Open the root service URL. In public mode it identifies itself as the FirstRoll API; it is not the
visitor-facing website.

## Legacy Azure: operate the Static Web Apps frontend

The active Static Web App deploys through
`.github/workflows/azure-static-web-apps-salmon-field-03695a010.yml`. Protected `master` is the
production source: development happens on short-lived branches, required CI runs without deployment
credentials and only a current, green pull request may merge. FirstRoll deliberately has no permanent
`local` or `develop` branch and creates no Azure preview deployment from pull-request code. Use
`./tools/preview_hosted_web.sh` for a local hosted-mode preview.

A successful CI run for the merge commit may build a production candidate, but it cannot deploy
immediately. The credentialled job waits at the protected GitHub `production` environment until the
repository owner manually approves that exact run.

| Setting | Value |
|---|---|
| Trigger | successful push CI on protected `master`, or manual dispatch validated against exact-SHA CI |
| Checked-out revision | exact CI-approved SHA, verified as the current `master` head |
| App location | `dist`; pre-built before the deployment credential is used |
| API location | empty; FastAPI is a separate service |
| Output location | empty because Azure's application build is skipped |
| Build script | `./tools/build_web.sh` with lockfile-controlled, lifecycle-script-disabled installation |
| Visitor domain | `https://firstroll.app` |

The build minifies `app.js` and `styles.css` with the locked esbuild dependency, keeping classic-script
globals, release inventory filenames and cache revalidation unchanged. Local source-served previews
remain unminified. See [Web Responsiveness](WEB_RESPONSIVENESS.md) for synthetic byte/timing evidence
and the distinction between worker dispatch and guaranteed responsiveness under load.

The workflow supplies these public build values:

| Key | Purpose |
|---|---|
| `FIRSTROLL_API_BASE` | complete backend origin; `https://api.firstroll.app` |
| `FIRSTROLL_SUPABASE_URL` | Supabase project URL |
| `FIRSTROLL_SUPABASE_PUBLISHABLE_KEY` | browser-safe Supabase publishable key |

The Azure deployment token is rotated into the branch-restricted GitHub `production` environment as
`AZURE_STATIC_WEB_APPS_API_TOKEN_SALMON_FIELD_03695A010`; it is not a repository-wide secret. Never
place that token in source code or a public build variable. The uncredentialled build job validates
`dist`, inventories its file hashes and seals a shared `release.json` receipt. Artefacts are retained
for 90 days but new approvals expire after seven days. A separate deployment runner waits for the
owner, downloads the artefact by ID, fetches only exact-commit release-control modules, then verifies
the receipt, current `master`, complete file inventory and known-good rollback package. It has no
application checkout or dependency installation. `skip_app_build` prevents rebuilding while the
Azure token is used. After upload, exact live files and API reachability are checked; a failed update
attempts to restore the verified previous static package. The first standardised release explicitly
acknowledges no legacy rollback baseline. See [Release Runbook](RELEASE.md) for bootstrap and recovery.

Frontend release jobs grant `GITHUB_TOKEN` read-only contents/actions access; CI retains read-only
contents access. Neither persists checkout
credentials and pin every external action to a full commit SHA. Repository Actions policy enforces
SHA pinning and permits only GitHub-owned actions plus the explicitly allow-listed HashiCorp and
Azure actions. Dependabot checks the npm lock and action pins weekly; production dependency audit
failures at high severity block CI and deployment.

The protected delivery sequence is:

1. create a short-lived branch from current `origin/master` and test locally;
2. push the branch, open a pull request and wait for the required `checks` job;
3. merge only when the branch is current, checks pass and conversations are resolved;
4. inspect the sealed production candidate in GitHub Actions and manually approve the `production`
   environment deployment;
5. wait for automatic live file and API checks, then verify sign-in, search, the shelf and study in a
   browser. `https://firstroll.app/release.json` identifies the deployed component and source commit.

Failed, cancelled, pull-request, foreign-repository and already-stale CI runs cannot reach the
approval gate. Agents may create and merge a green pull request, but must stop and report the pending
production run rather than approving or bypassing it. Custom-domain DNS and CDN caching remain
separate from the build job, and the frontend should appear independently of the API's deployment
state.

### Backend release automation

The backend has a separate, explicitly enabled `Backend Release` workflow. It uses Azure OIDC
rather than the Static Web Apps token or long-lived service-principal/registry passwords.

| GitHub location | Name | Purpose |
|---|---|---|
| Repository secret | `AZURE_BUILD_CLIENT_ID` | Branch-bound managed identity that pushes ACR images and reads current app metadata |
| `production` environment secret | `AZURE_DEPLOY_CLIENT_ID` | Approval-bound managed identity that updates only the FirstRoll Container App |
| Repository variable | `AZURE_TENANT_ID` | Azure tenant used for both OIDC exchanges |
| Repository variable | `AZURE_SUBSCRIPTION_ID` | Subscription containing FirstRoll resources |
| Repository variable | `ACR_LOGIN_SERVER` | Terraform registry login-server output |
| Repository variable | `AZURE_RESOURCE_GROUP` | `firstroll-production` |
| Repository variable | `AZURE_CONTAINER_APP_NAME` | `firstroll-api` |
| Repository variable | `BACKEND_RELEASE_ENABLED` | Must equal `true` only after every other item is configured |

Terraform declares both identities, their GitHub federated subjects and least-privilege role
assignments. The build identity cannot deploy; the deploy identity cannot push images or manage the
resource group. The deploy job has no source checkout and receives a short-lived token only after
the existing required owner review. It refuses stale `master`, altered manifests, mutable tags and
live baked-SHA or Azure image-digest mismatches, and restores the previous image when verification
fails after rollout. Terraform ignores only the running image after bootstrap so an infrastructure
apply cannot roll back a newer approved release; it still owns the app's other configuration.

Follow [Backend Release Runbook](RELEASE.md) for the exact setup, first proof run and operating rules.
The implementation does not include an approval broker, HMAC token or GitHub App. GitHub's protected
environment is the approval system and GitHub/Azure retain the current audit evidence.

## Connect Supabase authentication

The Supabase project URL and publishable key are designed to be public. Use the same two values in
the Azure frontend build and Container App; never use the secret or service-role key for these
settings.

1. In Supabase, open **Project Settings → API** and copy **Project URL** and the
   `sb_publishable_...` key.
2. Confirm the Azure workflow supplies:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_SUPABASE_URL` | the Supabase Project URL |
   | `FIRSTROLL_SUPABASE_PUBLISHABLE_KEY` | the `sb_publishable_...` key |

3. Trigger a new Azure Static Web Apps build after changing either value; they are compiled into
   `dist/assets/config.js`.
4. Configure the matching API values in `/opt/firstroll/.env` on the server (formerly the Azure
   Container App secret boundary):

   | Key | Value |
   |---|---|
   | `SUPABASE_URL` | the same Supabase Project URL |
   | `SUPABASE_PUBLISHABLE_KEY` | the same `sb_publishable_...` key |

5. Apply them with `docker compose --project-directory /opt/firstroll up -d api`.
6. Keep Supabase **Authentication → URL Configuration → Site URL** set to
   `https://firstroll.app`, and include `https://firstroll.app/**` in **Redirect URLs**. Retain the
   Azure-generated hostname only when it remains an intentional test entry point; remove obsolete
   Render frontend URLs.
7. In Supabase **Authentication → Providers → Email**, keep email/password enabled. Decide whether
   email confirmation is required for the public beta; the browser handles both an immediate
   session and a confirmation-first sign-up.
8. Open the frontend in a private window, select **Sign in**, create a password account and confirm
   the header displays its name or email. Sign out and use the same credentials to sign in again.
   `/api/auth/me` should return that account's Supabase user ID and email when called with its bearer
   token.

The Supabase browser client persists the session and refresh token in browser storage, with automatic
token refresh. FastAPI validates each bearer token against Supabase Auth before allowing an
authenticated API operation. The browser contains no password after form submission and no
provider secret is included in the static bundle.

### Install persistent account data

1. In Supabase, open **SQL Editor → New query**.
2. Paste the complete contents of
   `supabase/migrations/202608200002_persistent_accounts.sql` and select **Run**.
3. In **Table Editor**, confirm `firstroll_profiles`, `firstroll_preferences` and
   `firstroll_saved_films` exist and show RLS as enabled.
4. Create or sign into Account A, save a film and refresh the page. Confirm the film remains in
   **Settings → Saved films**.
5. Sign out, create Account B and confirm Account A's film is absent. Save a different film, then
   return to Account A and confirm each account still sees only its own row.
6. Test **Forgot password?** and confirm the recovery link returns to `https://firstroll.app`.

The account migration backfills profile and preference rows for existing Auth users. It grants no
table access to `anon`, needs no service-role key and stores no password, provider API key, study
prompt, evidence or generated result.

## Enable quota-controlled Deep Study

The public demo permits three Deep Studies per account per UTC day and thirty across all accounts.
It stores only the Supabase user UUID, UTC day and counters; prompts and generated studies are not
stored in Supabase.

1. In Supabase, open **SQL Editor → New query**.
2. Paste the complete contents of
   `supabase/migrations/202608150001_deep_study_quotas.sql` and select **Run**.
3. Confirm the result reports success. The migration creates two RLS-enabled tables in the
   non-exposed `firstroll_private` schema and two authenticated-only functions:
   `deep_study_quota_status()` and `reserve_deep_study_quota()`.
4. Add these values to `/opt/firstroll/.env` on the server—never to the static build—and restart
   the API container:

   | Key | Value |
   |---|---|
   | `DEEPSEEK_API_KEY` | the private DeepSeek API key |
   | `DEEPSEEK_MODEL` | `deepseek-v4-flash` |
   | `FIRSTROLL_DEEP_STUDY_ENABLED` | `true` |

5. Never add `DEEPSEEK_API_KEY` to the static site or repository. No Supabase secret or
   service-role key is required.
6. Run `docker compose --project-directory /opt/firstroll up -d api` and confirm `/api/health`. The explicit feature switch must remain absent or false until the
   SQL migration and key are both ready.
7. Sign in on the frontend, open a dossier and generate a study. The result displays the remaining
   account and global allowance. A fourth account request on the same UTC day returns HTTP 429.

Quota reservation occurs immediately before the paid model call. A request that reaches DeepSeek
counts against the allowance even if the provider later fails, preventing retries from becoming an
unbounded cost path. The hosted edition uses a four-part, first-party formal-analysis protocol and
labels all film-form claims as viewing hypotheses; it does not claim to have watched the film.

### Move quota to the identity-neutral PostgreSQL boundary

The replacement migration is
`database/migrations/202608200001_identity_neutral_deep_study_quotas.sql`. It can be installed on
Supabase PostgreSQL first and moved unchanged to Azure PostgreSQL later.

1. Run the migration with a database administrator.
2. Create a dedicated `firstroll_backend` login and grant only schema usage and execute permission
   on `firstroll_private.deep_study_quota_decision(text, text, boolean)`, as shown at the end of the
   migration. Do not grant direct table access.
3. Store its `postgresql://...?...sslmode=require` connection URL as `FIRSTROLL_DATABASE_URL` in
   `/opt/firstroll/.env` (legacy Azure: `TF_VAR_database_url`); never commit or print it.
4. Set `FIRSTROLL_QUOTA_PROVIDER=postgres`, restart the API container and test quota status,
   reservation, the fourth-request 429 and concurrent reservations.
5. Observe one complete UTC quota day before removing the legacy Supabase RPC.

The API passes PostgreSQL only the verified identity-provider name and immutable subject. It does
not forward the browser bearer token, email, study question or generated result.

## Legacy Azure: allow the frontend to call the API

1. Set this Container App environment value through Terraform:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_CORS_ALLOWED_ORIGINS` | `https://firstroll.app` |

2. Review and apply the Terraform plan.
3. Open `https://firstroll.app` in a private browser window and perform a film search.

Do not use `*` as the allowed origin. The exact frontend origin will later carry Supabase bearer
tokens to the API. Add the Azure-generated hostname only if it intentionally remains a supported
visitor origin.

## Optional primary film catalogue

Set `TMDB_BEARER_TOKEN` on the backend container to use the official TMDb catalogue for discovery,
posters and structured crew data. Do not expose it through the static frontend build. With no token,
the deployed API continues to use Wikidata/Wikipedia. A configured TMDb timeout fails over to that
open path and reports degraded provider state.

TMDb requires attribution, including the non-endorsement notice displayed by FirstRoll, and its free
API terms are for non-commercial use. Review and obtain appropriate commercial permission before a
revenue-generating deployment.

## Optional public video provider

YouTube search can use a server-side YouTube Data API v3 key. Add `YOUTUBE_API_KEY` to the server's
`/opt/firstroll/.env` and restart the API container; never add it to the static build.
Alternatively, a
signed-in visitor can supply a personal key for one browser tab through Settings. The browser holds
that key only in memory and sends it only with an authenticated video-search request. Restrict keys
to the YouTube Data API in Google Cloud and set a conservative quota alert.

The production image builds and bundles the unofficial Douban MCP connector at the exact revision
declared by `DOUBAN_MCP_REF` in `Dockerfile`. It uses anonymous provider access by default. Public
Settings reports whether that hosted runtime is ready but provides no Douban credential field, and
the API never accepts or stores a visitor's Douban cookie. Provider page changes, access controls or
rate limits can still make this optional source temporarily unavailable.

## Current public-beta acceptance checks

- `/api/health` returns HTTP 200.
- `/docs`, `/redoc` and `/openapi.json` return HTTP 404 in public mode; generated API documentation
  remains available only in the local development edition.
- `https://firstroll.app` serves the interface and native shelf assets without waiting for the backend.
- The backend root identifies itself as the FirstRoll API.
- Search begins working after the backend wakes.
- A completed Discover shelf survives refresh and switching among Discover, Analyse and Settings
  through bounded per-tab session storage without repeating completed provider requests.
- `/api/settings` and `/api/library/status` return HTTP 404 in public mode.
- `/api/analyze` returns HTTP 503 in public mode.
- `/api/auth/me` returns HTTP 401 without a session and the signed-in account with a valid session.
- `/api/account/integrations` returns quota and provider capability status only for a valid session.
- The production image reports Douban MCP as installed without exposing a visitor-cookie input.
- Deep Study returns HTTP 401 without a session, generates only after an atomic quota reservation,
  and returns HTTP 429 when either daily limit is exhausted.
- Personal DeepSeek and YouTube keys remain in tab memory, are cleared on refresh or sign-out and
  are accepted only on their matching authenticated request.
- No `.firstroll` data, uploaded clips, API keys or private library files appear in the image,
  repository, frontend source or network responses.

## Legacy Azure: Container Apps production state (suspended)

**Suspended since 27 September 2026.** The disabled Free Trial subscription stopped these resources;
they are retained for reference and possible reactivation only. Before the suspension the API
migration was complete:

```text
firstroll.app     -> Azure Static Web Apps
api.firstroll.app -> Azure Container Apps
Supabase Auth     -> production password accounts and persistent sessions
Supabase Postgres -> RLS-owned profiles, preferences and saved films
PostgreSQL        -> provider-neutral quota store (deployment staged)
```

`api.firstroll.app` has a CNAME to the Azure-generated Container Apps hostname and `asuid.api` has
the Azure verification TXT record. Azure owns the managed certificate. Terraform has imported the
live association and reports no infrastructure drift.

Render may remain available briefly as a rollback target, but it is not the active API. Prefer
rolling the Container App back to the last healthy immutable image before changing DNS.

## Legacy: optional Entra External ID learning path

ADR-017 keeps Supabase as production authentication because it already supplies password accounts,
session management and user-scoped PostgreSQL on the appropriate cost tier. Entra External ID is no
longer required to launch persistent FirstRoll accounts.

The code and Terraform provider switch remain staged but inactive as an architecture-learning or
future enterprise path. Before ever selecting
`FIRSTROLL_AUTH_PROVIDER=entra`, create an External ID customer tenant, an email/password user
flow, separate `FirstRoll Web` and `FirstRoll API` registrations, and expose the delegated
`access_as_user` scope. The browser and API must switch together.

The backend-owned PostgreSQL quota adapter and migration are implemented. It stores provider plus
immutable subject and never forwards browser tokens. Before enabling Entra, install that migration,
configure the dedicated database login and set `FIRSTROLL_QUOTA_PROVIDER=postgres`. Terraform
rejects an Entra deployment that still selects the legacy Supabase quota RPC.

## Next security milestone

Add cost telemetry and an operator-visible kill switch before raising either daily limit. Video
analysis remains a local feature and is presented as **Coming soon** in the public interface.

## Cost and availability notes

The API container's filesystem is ephemeral and the server holds no durable product data. Durable
account, quota or study data must live in a database rather than on the host. Fast and
poster-enriched filmography responses are bounded process-memory caches and are rebuilt after every
release. The static site is served by Caddy from `/opt/firstroll/releases/current`, so it does not
depend on the API process.

The server runs one API container continuously for a flat monthly price: no cold starts, no
autoscaling and no per-request billing. The suspended Azure resources incur no charge while the
subscription is disabled; reactivating them would restore Container Apps, Container Registry and Log
Analytics charges.
