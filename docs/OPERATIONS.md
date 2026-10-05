# FirstRoll Operations

The operator guide for the hosted public beta: the production server, its release path, recovery,
Supabase configuration and acceptance. Local development, CI and the hosted-mode preview are in
[Setup](SETUP.md); components, state lifetimes and release-path threats are in
[Architecture](ARCHITECTURE.md); schemas and the HTTP API are in [Data](DATA.md); rationale is in
[Decisions](DECISIONS.md); dated evidence is in [Progress](PROGRESS.md). The stack files are listed
in [infra/vps/README.md](../infra/vps/README.md).

**Last reconciled:** 5 October 2026; removal code in this branch is not yet deployed.

| Item | Current state |
|---|---|
| Live release | v232: commit `cf43ba57`, run `37213215944`, deployed on 5 October 2026 after exact-run owner approval |
| URLs | Visitor site `https://firstroll.app`; API `https://api.firstroll.app` |
| Automated live checks | Pipeline and independent static-file/API/contract/CORS/hidden-doc checks passed on 5 October; desktop festival filtering/details/zoom passed; earlier v230 search/shelf/dossier/Settings checks passed |
| Not yet verified | Authenticated sign-in and saved-film/password actions, authenticated quota, a rollback drill, sustained performance monitoring |
| Disabled | Paid Deep Study and hosted video analysis. TMDb is unconfigured, so the open catalogue is in use |
| Rollback target | v230 / `ec9975c8`, retained site and immutable API image; excludes databases, secrets and infrastructure |

The Azure path (Static Web Apps, Container Apps, Terraform, Entra External ID) was retired in
`9d29263` and is preserved at tag `archive/azure`. No workflow reads its secrets or variables
(`AZURE_*`, `BACKEND_RELEASE_ENABLED`, the Static Web Apps token), so the owner can delete them.

## Rules for operators and agents

- `master` is protected. A merge may build a release candidate but is never production approval.
- Only a human repository owner approves the `production` environment, and only for one exact run.
  Never approve a run merely to clear a queue. Agents report a pending deployment and never approve,
  bypass or weaken the gate unless the owner explicitly instructs them to approve that specific run
  ([AGENTS.md](../AGENTS.md)).
- Each DNS change, database migration, paid model call, server reboot and rollback drill needs its
  own explicit owner approval. Approving a release approves none of them.
- Server secrets live only in `/opt/firstroll/.env` (mode 0600). The deploy key's private half lives
  only on the operator's machine and in the `production` environment secret. None of them goes in
  Git, chat, build arguments, logs or the static bundle.
- Deploy the API by immutable digest only, never by `latest` or another mutable tag.
- Never hand-edit `deploy.sh`, `Caddyfile` or `docker-compose.yml` on the server: every release
  reinstalls them from the approved commit. Change them in the repository.

## 1. Production topology

```text
Browser ─HTTPS─► Caddy (on the server, ports 80/443)
                   ├─ firstroll.app      ─► /opt/firstroll/releases/current   (static site)
                   └─ api.firstroll.app  ─► api container :10000 (FastAPI, internal only)
                                              └─► Supabase Auth/Postgres · DeepSeek · public film sources
```

| Component | Production setting |
|---|---|
| Server | Tencent Lighthouse Starter, Singapore Zone 2: 2 vCPUs, 2 GB memory, 40 GB SSD, about 2 GB swap, Ubuntu 24.04.4 LTS x86-64. Prepaid until 29 September 2027 |
| Accounts | `ubuntu` is the administrator (personal key, `sudo`). `firstroll` is the deployment account (Docker group, which is root-equivalent) |
| DNS | Spaceship. A records for `firstroll.app` and `api.firstroll.app` point at the server's IPv4 address |
| TLS and static files | Caddy `2.11.4`. Let's Encrypt certificates are kept in the `caddy_data` volume. `release.json` is sent with `no-store`; `/`, `index.html` and `/assets/*` must revalidate |
| API | `ghcr.io/luo-z-y/firstroll-api@<digest>`. Memory limit `768M`, all capabilities dropped, `no-new-privileges`, JSON logs rotated at 3 × 10 MB |
| Durable data | Supabase holds accounts, profiles, preferences, saved films and Deep Study counters. The server keeps no durable product data |
| Release | `.github/workflows/vps-release.yml`, gated by the protected GitHub `production` environment |
| Image registry | GitHub Container Registry package `firstroll-api`. It is public because the server pulls anonymously |

Server layout (created by `bootstrap.sh`, owned by `firstroll`):

| Path | Contents |
|---|---|
| `/opt/firstroll/.env` | Private configuration, mode 0600. `deploy.sh` rewrites only its `FIRSTROLL_IMAGE_DIGEST` line |
| `/opt/firstroll/{docker-compose.yml,Caddyfile,deploy.sh}` | Stack files from the most recently approved commit |
| `/opt/firstroll/releases/` | One directory per release attempt (`site-<sha>.XXXXXX`, plus `site-bootstrap`). `current` is a relative symlink to one of them |
| `/opt/firstroll/state/current-release`, `previous-release` | `<sha> <digest> <site-directory>` records |
| `/opt/firstroll/incoming/<sha>/` | The upload area for one release. The workflow deletes it afterwards |

The API's in-memory results and caches, and the caches it writes inside its container, are lost
whenever a release recreates the container; lifetimes are listed in [Architecture](ARCHITECTURE.md).

## 2. Bootstrap a server

Use this section for a new or replacement server. The commands assume a personal administrator key at
`~/.ssh/firstroll-admin.pem` (replace it with your actual filename), and `SERVER_IP` is the verified
public IPv4 address.

1. **Verify the host identity.** In the provider's trusted browser terminal, run
   `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Compare the result with the fingerprint shown
   on your first SSH connection before you trust it. Never disable host-key checking.
2. **Create a dedicated deploy key.** GitHub Actions must never use your personal key. Do not
   overwrite an existing key:

   ```bash
   ssh-keygen -t ed25519 -N '' -C firstroll-vps-github-actions -f ~/.ssh/firstroll-vps-deploy
   ```

   Keep the private half owner-readable and outside the repository; it later becomes
   `VPS_SSH_PRIVATE_KEY` ([section 4](#4-github-configuration)). Creating the key does not configure
   GitHub or authorise a release.
3. **Copy only the setup files and the public key**, then run the bootstrap. Do not recursively
   upload `infra/`, because it may contain a downloaded administrator key:

   ```bash
   ssh -i ~/.ssh/firstroll-admin.pem -o StrictHostKeyChecking=yes ubuntu@SERVER_IP \
     'mkdir -p /home/ubuntu/firstroll-vps'
   scp -i ~/.ssh/firstroll-admin.pem -o StrictHostKeyChecking=yes \
     infra/vps/bootstrap.sh infra/vps/deploy.sh infra/vps/docker-compose.yml \
     infra/vps/Caddyfile infra/vps/.env.example ~/.ssh/firstroll-vps-deploy.pub \
     ubuntu@SERVER_IP:/home/ubuntu/firstroll-vps/
   ssh -i ~/.ssh/firstroll-admin.pem -o StrictHostKeyChecking=yes ubuntu@SERVER_IP
   # On the server. Keep this session open until new logins succeed:
   sudo env NEEDRESTART_MODE=a \
     FIRSTROLL_DEPLOY_PUBLIC_KEY="$(cat /home/ubuntu/firstroll-vps/firstroll-vps-deploy.pub)" \
     bash /home/ubuntu/firstroll-vps/bootstrap.sh
   ```

`bootstrap.sh` (run as root) upgrades packages; installs Docker and Compose from Ubuntu; caps
container logs at 3 × 10 MB; creates `firstroll` with the supplied deploy key (plus root's authorised
keys, if any, never `ubuntu`'s); installs the stack under `/opt/firstroll` with a placeholder site and
creates `.env` from the template only if it is missing; adds a 1 GB swap file only below about 1.9 GB
of memory with no existing swap; enables `ufw` for SSH, TCP 80/443 and UDP 443; turns on unattended
security upgrades; and, once any key is installed, restricts SSH to keys
(`PermitRootLogin prohibit-password`). Finally it prints the `ssh-ed25519 …` host-key line for
`VPS_SSH_HOST_KEY`. Reruns keep `.env` and published releases but refresh the stack files, upgrade
packages and restart Docker, so review any running workloads first.

Before you close the administrator session, check that new logins work for both `ubuntu` and
`firstroll`, that `sudo sshd -T` reports key-only authentication, that `sudo ufw status` shows the
expected rules and that, as `firstroll`, `docker compose --project-directory /opt/firstroll config
--quiet` passes. Never run plain `config`, because it prints resolved secrets. The provider's cloud
firewall is separate from `ufw`. Allow TCP 22, 80 and 443 there; UDP 443 is optional and only needed
for HTTP/3. Never choose **Allow all**, and never expose port 10000.

**Edit `/opt/firstroll/.env`** as `firstroll`. The template is `infra/vps/.env.example`:

| Key | Production value |
|---|---|
| `FIRSTROLL_IMAGE_DIGEST` | Leave the all-zero placeholder. `deploy.sh` writes the real digest |
| `FIRSTROLL_SITE_DOMAIN`, `FIRSTROLL_API_DOMAIN` | `firstroll.app`, `api.firstroll.app` |
| `CADDY_ACME_EMAIL` | The owner's Let's Encrypt contact address |
| `FIRSTROLL_PUBLIC_MODE` / `FIRSTROLL_VIDEO_ANALYSIS_ENABLED` | `true` / `false` |
| `FIRSTROLL_CORS_ALLOWED_ORIGINS` | Exactly `https://firstroll.app`. Never `*` |
| `FIRSTROLL_AUTH_PROVIDER` | `supabase`, the only accepted value |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | The project URL and `sb_publishable_…` key. Both are public; never use a secret or service-role key |
| `FIRSTROLL_DEEP_STUDY_ENABLED` | `false` until [section 9](#9-supabase-accounts-deep-study-quota-and-enablement) is complete |
| `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` | The platform key (may be present while the flag is off) and `deepseek-v4-flash`. If `DEEPSEEK_MODEL` is unset, the code falls back to `deepseek-v4-pro` |
| `TMDB_BEARER_TOKEN`, `YOUTUBE_API_KEY` | Optional server-side keys ([section 10](#10-optional-providers)) |
| `FIRSTROLL_API_MEMORY_LIMIT` | `768M` (`640M` on a 1 GB server) |
| `FIRSTROLL_QUOTA_PROVIDER`, `FIRSTROLL_DATABASE_URL` | Not in the template. Add them only for the optional PostgreSQL quota provider ([section 9](#optional-identity-neutral-postgresql-quota-provider)) |

Never set `FIRSTROLL_RELEASE_SHA` in `.env`: it would override the commit baked into the image, so
the identity checks of later releases would fail. When migrating to a new server, get explicit
consent before copying provider credentials. Transfer only the named keys over host-verified SSH,
then keep the file at 0600 and validate it with `config --quiet`.

## 3. DNS and HTTPS

For a cut-over, build and inspect a candidate ([section 6](#6-the-vps-release-flow)) before you change
DNS, then make sure HTTPS works before approving the waiting production job.

| Record (Spaceship) | Type | Value |
|---|---|---|
| `@` (`firstroll.app`) | A | `SERVER_IP` |
| `api` (`api.firstroll.app`) | A | `SERVER_IP` |

1. Save the existing records first. Replace only the website and API records, remove stale AAAA
   records, and keep mail, nameserver and unrelated TXT records. The `asuid.api` TXT verification
   record belonged to the retired Azure host and is no longer used.
2. Wait until `dig +short firstroll.app` and `dig +short api.firstroll.app` both return the server.
   Certificate attempts made earlier fail, and Let's Encrypt rate-limits failures.
3. Start Caddy without the API. It obtains a certificate for each hostname:

   ```bash
   ssh -i ~/.ssh/firstroll-vps-deploy -o StrictHostKeyChecking=yes firstroll@SERVER_IP
   docker compose --project-directory /opt/firstroll up -d --no-deps caddy
   docker compose --project-directory /opt/firstroll logs -f caddy
   ```

Until the first release, `https://firstroll.app` shows the placeholder page and
`https://api.firstroll.app` returns 502. The API image is never built on the server. Caddy access
logging is off because it would record visitor IP addresses; if you need it for debugging, add a
`log` block in the repository.

## 4. GitHub configuration

| Location | Name | Value |
|---|---|---|
| `production` environment secret | `VPS_SSH_PRIVATE_KEY` | Contents of `~/.ssh/firstroll-vps-deploy` |
| Repository variable | `VPS_HOST` | Server IP address, or a hostname that resolves to it |
| Repository variable | `VPS_SSH_HOST_KEY` | The `ssh-ed25519 AAAA…` line printed by `bootstrap.sh`. The workflow also accepts `ecdsa-sha2-*` and `ssh-rsa` keys |
| Repository variable | `VPS_USER` | Optional; defaults to `firstroll` |
| Repository variable | `VPS_RELEASE_ENABLED` | Set to `true` only after everything else is in place. Any other value stops new candidates; the running server is unaffected |

The `production` environment must keep the repository owner as a required reviewer, allow
deployments only from `master` and have no administrator bypass. Saving a key or variable does not
approve a run.

- Before you make or keep the `firstroll-api` package **Public**, inspect the image's build inputs for
  secrets and private data; a public repository does not prove that an image is safe to publish.
- Every external action in both workflows is pinned to a full commit SHA. `.github/dependabot.yml`
  checks GitHub Actions and the npm lock weekly, and has a weekly `docker` entry for `infra/vps`.
- The browser bundle's public Supabase values are set in the **Build the production frontend** step
  of `vps-release.yml`, so a new Supabase project means changing that workflow as well as `.env`.

## 5. Release contract

**CI → build and seal → owner approval → re-verify → deploy by digest → live verification →
automatic recovery on failure.**

| Rule | Detail |
|---|---|
| Candidate source | A successful push run of `CI` (`.github/workflows/ci.yml`) on current `master` from this repository, or a manual dispatch on `master` whose exact SHA already has a successful push CI run. Pull-request, failed, cancelled, foreign and stale runs never reach the gate |
| Receipt | `release.json` (schema 1, component `vps`). It binds the repository, environment `production`, branch `master`, commit, run, attempt, `release_id` (`vps-<sha8>-<run>-<attempt>`), artefact name, creation and expiry times, image reference and digest, a SHA-256 inventory of every site file except `release.json`, the inventory's fingerprint (`payload_digest`) and a `receipt_digest` over all of it |
| Site limits | At most 100 files and 64 MiB. `index.html`, `assets/config.js`, `assets/app.js`, `assets/auth.js` and `assets/styles.css` are required. Symbolic links and hidden or unsafe paths are refused |
| Approval window | Seven days from sealing. Re-running only the deploy job does not renew it |
| Artefact retention | 90 days, subject to repository limits. This is not permanent storage |
| Code the deploy runner executes | Only `tools/release/protocol.py` and `tools/release/vps.py`, fetched from the exact approved commit, plus the workflow itself. There is no application checkout or dependency installation. On the server it runs the artefact's `deploy.sh` ([section 12](#12-cost-availability-and-known-constraints)) |
| Expected values | Taken from build-job outputs, never from the downloaded receipt |
| Concurrency | Group `vps-release-production`, never cancelled in progress. GitHub may replace an excess pending run, so this is not a queue. Reject obsolete waiting runs; the freshness checks refuse superseded code anyway |

Receipt hashes detect alteration but are **not** signed provenance, and approval is a single-owner
gate, not two-person review. Green checks do not prove the application correct, so browser
acceptance ([section 11](#11-public-beta-acceptance-checks)) stays manual.

## 6. The VPS release flow

**Build job: "Build, test and publish the release candidate".** It runs only when
`VPS_RELEASE_ENABLED == 'true'`. It has `packages: write` but no production credential.

| Step | What it does |
|---|---|
| Check out the CI-approved revision | Full history (for the build number), without persisted credentials |
| Bind the release to current master | Fails if the checkout or remote `master` differs from the CI SHA. A manual run also needs successful push CI for that SHA |
| Audit frontend dependency lock | `npm audit --audit-level=high` |
| Build the production frontend | `./tools/frontend/build.sh` with the API base `https://api.firstroll.app`, channel `live` and the public Supabase values |
| Validate the bounded site directory | Checks the entry files, rejects symbolic links, runs `node --check` and confirms the API base and channel |
| Build the backend image | `docker build --build-arg FIRSTROLL_RELEASE_SHA=<commit>` |
| Smoke-test the container and its public boundary | Public mode with Deep Study and video analysis off. `/api/health` must report `ok` and the commit; `/docs`, `/redoc` and `/openapi.json` must return 404 |
| Publish the immutable candidate to GitHub Container Registry | Pushes `ghcr.io/luo-z-y/firstroll-api:<commit>` and resolves its `sha256` digest |
| Seal the release receipt | `python3 -m tools.release.vps prepare …` writes `dist/release.json` and the step summary |
| Package the site and server stack | `site.tar.gz`, `release.json` and `stack/{docker-compose.yml,Caddyfile,deploy.sh}` |
| Upload the sealed release package | Artefact `vps-release-<run>-<attempt>` |

**Human approval.** Read the step summary: release ID, commit, image digest, site fingerprint and
expiry. If you intend this exact release, choose **Review deployments → production → Approve and
deploy**. If `master` has moved, reject the run and let a fresh candidate build.

**Deploy job: "Deploy the approved candidate to the server"** (environment `production`).

| Step | What it does |
|---|---|
| Download only the sealed release package | Downloads by artefact ID |
| Fetch approved release control modules | Fetches `protocol.py` and `vps.py` at the exact SHA through the GitHub contents API |
| Verify the receipt, site archive and approval expiry | `vps verify` checks the receipt against the commit, run, attempt, receipt digest and image digest. The archive must contain exactly the sealed inventory and receipt |
| Refuse a stale revision after approval | Fails if `master` moved while approval was pending |
| Check required production configuration | Confirms `VPS_SSH_PRIVATE_KEY`, `VPS_HOST` and a well-formed `VPS_SSH_HOST_KEY` |
| Prepare the pinned SSH identity | Writes the key only now, with `known_hosts` pinned to `VPS_SSH_HOST_KEY`, `StrictHostKeyChecking yes`, `IdentitiesOnly` and `BatchMode`, then tests the connection |
| Record the rollback target | Runs `deploy.sh status` and records the current release |
| Upload the release package to the server | Copies the site archive and stack files to `incoming/<sha>/`, then installs `deploy.sh`, `docker-compose.yml` and `Caddyfile` into `/opt/firstroll` |
| Release on the server | `deploy.sh release <sha> <digest> <archive>` |
| Verify the live site and API identity | `vps live` (see below) |
| Roll back after failed post-deployment verification | Runs only if the rollout succeeded and a later step failed: `deploy.sh rollback`, then `vps health` |
| Remove the uploaded package | Always runs once SSH is configured |
| Record the deployment result | Writes the result, commit, digest, previous release, targets and UTC time to the summary |

**On the server, `deploy.sh release`** checks its arguments and `.env`, unpacks the archive into a
new, unique `site-<sha>.XXXXXX` directory (which must contain `index.html` and `release.json`), then:
writes the digest atomically → pulls the API image and runs `up -d` → waits up to about two minutes
for `/api/health` to report the expected commit → switches `releases/current` atomically and reloads
Caddy → writes `current-release`. Only after all of that succeeds does it record the previous
release, prune old site directories (always keeping the current and previous ones) and prune unused
images. Every step propagates errors explicitly, even inside Bash conditionals.

**Live verification (`vps live`)** retries for up to 180 seconds, contacts only the two production
origins and follows no redirects. It requires that `/release.json` equals the receipt, every
inventoried file matches its fingerprint, `/api/health` reports `ok` and the commit, `/api/contract`
and `/api/discovery/status` respond, `/docs`, `/redoc` and `/openapi.json` return 404, and a CORS
preflight allows exactly `https://firstroll.app`. `vps health`, used after a rollback, runs the same
API checks without requiring a particular commit.

## 7. Day-to-day operation

Connect as `firstroll` using the deploy key and pinned host checking:

```bash
/opt/firstroll/deploy.sh status                                        # releases, digest, site, containers
docker compose --project-directory /opt/firstroll logs --tail 200 api  # API log
docker compose --project-directory /opt/firstroll up -d api            # apply a .env change
curl -s https://api.firstroll.app/api/health                           # from anywhere: status and release_sha
curl -s https://firstroll.app/release.json                             # live receipt
```

- **Reboot** only through `ubuntu` (`sudo reboot`) and only with owner approval. Unattended upgrades
  may require one. Docker starts at boot and both containers use `restart: unless-stopped`.
- **Stop automated candidates** by setting `VPS_RELEASE_ENABLED` to anything other than `true`.
- **Rotate the deploy key** if it may be exposed: generate a new pair, append the public half to
  `/home/firstroll/.ssh/authorized_keys`, replace `VPS_SSH_PRIVATE_KEY`, then delete the old line.
- **Change the stack** only in the repository. CI checks it with `shellcheck`, `docker compose config`
  and `caddy validate`; the rest of CI and the local hosted-mode preview are in [Setup](SETUP.md).
- **Audit trail:** GitHub deployment history and job summaries, the `state/` records and `releases/`
  directories on the server, and the rotated container logs. No other audit export exists.

## 8. Rollback and recovery

| Failure point | Automatic result |
|---|---|
| Any step before **Release on the server** | Nothing on the server changes, except that the stack files are reinstalled once the upload step has run |
| `deploy.sh release` fails with a previous release | Restores the previous site and digest, restarts and re-verifies the previous API, then deletes the candidate site. The job fails |
| `deploy.sh release` fails on a server's first release | Restores the bootstrap page and stops the API. The all-zero placeholder digest is never pulled |
| Recovery itself fails | Reports that manual recovery is required and keeps the candidate files |
| Rollout succeeds but live verification fails | The workflow runs `deploy.sh rollback` and `vps health`. The job stays failed so the incident remains visible. On a server's first release there is nothing to roll back to, so fix forward |
| Job cancelled or timed out | No automatic recovery is guaranteed. Never assume production is unchanged: run `deploy.sh status` and check `/api/health` and `/release.json` |

Recovery restores **only the image digest and the static site**. It never restores the stack files,
other `.env` values, Caddy state or Supabase data. If the rollout fails, the workflow does not run a
second rollback.

**Manual rollback** (with owner approval):

```bash
/opt/firstroll/deploy.sh status     # note Current and Previous release
/opt/firstroll/deploy.sh rollback   # previous digest becomes current, site switches back
/opt/firstroll/deploy.sh status
```

Then confirm from outside that `/api/health` reports the previous `release_sha` and that
`/release.json` names the same commit. Rollback swaps the current and previous records, so a second
rollback rolls forward. It needs a recorded previous release, that release's site directory on the
server and its image in GHCR. Each release prunes unused images on the server, so rollback depends
on pulling the previous image from GHCR: never delete package versions that might be rollback
targets. Going further back than one release means reverting on `master` and releasing again.

**When rollback fails:** `rollback` has no recovery of its own. If the previous image cannot be
pulled or never becomes healthy, `.env` may already name the previous digest while the site still
serves the newer release. Run `deploy.sh status` and compare **Configured digest** and **Served
site** with **Current release**. Then either fix forward with a new approved release, or restore the
digest line in `.env` to the value in `state/current-release` and run `up -d api`.

**Recovery drill (outstanding; needs a second VPS release and owner approval).** Record
`deploy.sh status`, `/api/health` and `/release.json`; run `deploy.sh rollback` and verify the
previous identity externally, plus sign-in and search in a browser; roll forward with a second
`rollback` and verify again; record the timings and evidence in [Progress](PROGRESS.md).

**Replacing a lost server:** bootstrap a new one ([section 2](#2-bootstrap-a-server)); restore `.env`
from an encrypted off-host copy (none is automated, and the repository holds no server secrets);
update `VPS_HOST` and `VPS_SSH_HOST_KEY`; move DNS ([section 3](#3-dns-and-https)); let Caddy obtain
new certificates; then approve a fresh release. Supabase data is unaffected because it does not live
on the server.

## 9. Supabase accounts, Deep Study quota and enablement

Table, function and RLS definitions are in [Data](DATA.md); this section is the procedure.

### Authentication and account data

1. Copy the Supabase **Project URL** and `sb_publishable_…` key from the project's API settings. Put
   them in the build step ([section 4](#4-github-configuration)) and in `.env` as `SUPABASE_URL` and
   `SUPABASE_PUBLISHABLE_KEY`, then run `up -d api`. No secret or service-role key is used anywhere.
2. Under **Authentication → URL Configuration**, set the Site URL to `https://firstroll.app` and add
   `https://firstroll.app/**` to the Redirect URLs. Remove obsolete hosts.
3. Under **Authentication → Providers → Email**, keep email and password enabled, and decide whether
   sign-up needs email confirmation. The browser handles both cases.
4. In **SQL Editor**, run `supabase/migrations/202608200002_persistent_accounts.sql`, then confirm in
   **Table Editor** that `firstroll_profiles`, `firstroll_preferences` and `firstroll_saved_films`
   exist with RLS enabled. The migration backfills existing users and needs no service-role key.
5. Check account isolation with two test accounts. A film saved by Account A must survive a refresh
   and must not appear for Account B. **Forgot password?** must return to `https://firstroll.app`.

### Deep Study quota (default: Supabase RPC)

The public demo allows **3 Deep Studies per account and 30 across all accounts per UTC day**. The
reservation happens immediately before the paid model call, so a request that reaches DeepSeek
counts even if the provider then fails, and studies made with a visitor's personal DeepSeek key
count too.

1. In **SQL Editor**, run `supabase/migrations/202608150001_deep_study_quotas.sql`. It creates the
   private counters and the authenticated-only functions `deep_study_quota_status()` and
   `reserve_deep_study_quota()`.
2. **Verify readiness without a paid call.** Sign in and open **Settings**, or call
   `/api/account/integrations` with that session. The response shows the quota status without
   reserving anything. A 503 means the quota store is unconfigured or its migration is missing. A
   502 means the store could not return a decision.

### Enabling Deep Study

Hosted Deep Study needs public mode, `FIRSTROLL_DEEP_STUDY_ENABLED=true`, configured Supabase auth,
a configured quota store, and either `DEEPSEEK_API_KEY` or a visitor's personal key. Otherwise the
study routes return 503. With owner approval for the paid calls:

1. set or confirm `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL=deepseek-v4-flash` and
   `FIRSTROLL_DEEP_STUDY_ENABLED=true` in `.env`, then run `up -d api`
2. check that `/api/discovery/status` reports `features.deep_study: true` (this needs the platform
   key)
3. sign in, open a dossier and generate one study. The result shows the remaining allowance. A
   fourth study from the same account that day ends in a `quota_exhausted` `run_failed` event on the
   stream; only the synchronous route returns 429 with `Retry-After`
   ([DATA.md](DATA.md#deep-study))

To switch it off, set the flag to `false` and run `up -d api`.

### Optional: identity-neutral PostgreSQL quota provider

`PostgresQuotaClient` is retained and staged, but it is not the production path. It sends PostgreSQL
only the verified provider name and subject. The migration is ordinary, portable PostgreSQL and can
run on Supabase's database or any other PostgreSQL server.

1. As a database administrator, run `database/migrations/202608200001_identity_neutral_deep_study_quotas.sql`.
2. Create the dedicated `firstroll_backend` login exactly as the comments at the end of the migration
   show: schema usage and execute on
   `firstroll_private.deep_study_quota_decision(text, text, boolean)` only, with no table access.
3. Put its `postgresql://…?sslmode=require` URL in `.env` as `FIRSTROLL_DATABASE_URL`. Never print it.
4. Set `FIRSTROLL_QUOTA_PROVIDER=postgres` and run `up -d api`. Then test the quota status, a
   reservation, the refusal of the fourth study and concurrent reservations.
5. Per-account counts start afresh in the new table, so switch at a UTC day boundary. Observe one
   full UTC day before you retire the Supabase RPC.

## 10. Optional providers

| Provider | Configuration | Behaviour when absent or failing |
|---|---|---|
| TMDb catalogue | `TMDB_BEARER_TOKEN` in `.env` | Wikidata/Wikipedia discovery. A TMDb timeout falls back to it and reports degraded status. TMDb needs attribution, and its free terms are non-commercial, so get permission before any revenue-generating use |
| YouTube Data API v3 | `YOUTUBE_API_KEY` in `.env`, restricted to that API, with a quota alert | Signed-in visitors can supply a personal key in Settings. It is held in tab memory and sent only with authenticated video-search requests |
| Douban MCP | Bundled in the image at `DOUBAN_MCP_REF` (Dockerfile), using anonymous access | Optional source that provider changes or rate limits can interrupt. The API never accepts or stores a visitor's Douban cookie |

## 11. Public-beta acceptance checks

| Check | Expected | Status (1 Oct 2026) |
|---|---|---|
| `/api/health` | 200, `ok`, approved `release_sha` | Verified |
| `/release.json` and the header | Receipt names the deployed commit; the header shows `vN · LIVE` | Receipt verified; header not browser-checked |
| `/docs`, `/redoc`, `/openapi.json` | 404 | Verified |
| `/api/settings`, `/api/library/status` | 404 in public mode | Settings verified; library covered by tests |
| `/api/analyze` | 503 while video analysis is off (the public-mode default) | Covered by tests; status reports video analysis off |
| API root | Identifies itself as the FirstRoll API | Covered by tests |
| `/api/auth/me` | 401 without a session; the account with one | 401 verified; signed-in check outstanding |
| Search, shelf, dossier | Correct identity. The shelf survives refresh and tab switches | API samples only; browser check outstanding |
| Sign-in, saved films, password recovery | Persist across refresh, with accounts isolated | Outstanding |
| `/api/account/integrations` | Quota and provider status only with a valid session | Outstanding |
| Deep Study | 401 without a session, 503 while disabled, `quota_exhausted` once a limit is reached | Disabled; quota outstanding |
| Personal keys | Held in tab memory, cleared on refresh or sign-out | Outstanding |
| Douban MCP | Installed, with no cookie input | CI verifies the image handshake |
| Private material | No `.firstroll` data, clips, keys or private books in the image, bundle or responses | Process control at each review |

## 12. Cost, availability and known constraints

- **Server:** prepaid Tencent term until 29 September 2027. The console reports 512 GB of traffic a
  month at 20 Mbps. Excess traffic, optional services and renewal prices are unverified, so check
  the account's rates and alerts.
- **Paid APIs:** DeepSeek is billed per use. The daily quota limits the number of studies, not the
  tokens, and each study makes at most two model calls. Add cost telemetry and an operator-visible
  kill switch before raising either limit.
- **GitHub:** artefacts kept for 90 days count towards the repository's storage allowance.
- **Availability:** one server, with no CDN, autoscaling or failover. Each release recreates the API
  container, so the API is unavailable for a few seconds while Caddy keeps serving the static site.
  Until the site switches, the previous site talks to the new API.
- **Supabase Free pauses a project after seven days without activity.** A paused project breaks
  sign-in, saved films and quota until someone resumes it in the dashboard; discovery keeps working.
  No keep-alive is implemented. Before adding one, confirm what Supabase currently counts as activity.
- **Stack files are outside the receipt.** `deploy.sh`, `Caddyfile` and `docker-compose.yml` travel
  in the sealed artefact but are not hashed in `release.json` or checked by `vps verify`. They are
  installed before activation and stay installed after any recovery.
- **Long-lived deploy key.** It stays valid until rotated ([section 7](#7-day-to-day-operation)), and
  its holder has root-equivalent access through the Docker group. The host pin stops redirection,
  not misuse of a stolen key.
- **No monitoring or alerting.** The Compose health check marks the API unhealthy but does not
  restart it; only a process exit triggers a restart.
- **No image vulnerability scan, SBOM or off-host backup** of `.env` or Caddy state. The full list
  of unimplemented controls is in [Architecture](ARCHITECTURE.md).
- **Outbound reputation.** Public criticism and video sources may treat the server's IP address
  differently. That reduces evidence coverage but not availability.
