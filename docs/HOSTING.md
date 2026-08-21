# FirstRoll Public Beta Hosting

**Deployment status:** Active Azure frontend and Azure API

**Visitor URL:** `https://firstroll.app`

**API URL:** `https://api.firstroll.app`

**Last reconciled:** 21 August 2026

FirstRoll is not merely a local application. Its active public beta uses Azure Static Web Apps for
the frontend and Azure Container Apps for the Docker API, while private-library and clip-analysis
capabilities remain local by design:

```text
Browser  ->  Azure Static Web Apps  ->  Azure Container Apps  ->  public film sources
              firstroll.app             api.firstroll.app
```

The hosted edition publishes discovery, the 3D shelf, Supabase email-and-password accounts with
saved films, and an authenticated Integration Centre. Private-library settings, local documents, clip uploads, computer-vision
analysis and unauthenticated Deep Study are blocked by the backend. Authenticated Deep Study is
protected by durable Supabase usage counters.
The separate origins keep the public boundary explicit and allow either service to be deployed or
rolled back independently.

The frontend and API origins are deployment configuration. `FIRSTROLL_API_BASE` points to
`https://api.firstroll.app`, while `FIRSTROLL_CORS_ALLOWED_ORIGINS` must include the exact
`https://firstroll.app` origin. See
[Architecture](ARCHITECTURE.md), [API Reference](API_REFERENCE.md), [Data Model](DATA_MODEL.md) and
[Architecture Decisions](DECISIONS.md) for the corresponding runtime contracts.

Terraform under `infra/terraform` manages the imported Static Web App, both custom-domain
associations, Azure Container Registry, Log Analytics, the Container Apps environment and the
FastAPI Container App. Spaceship remains the DNS provider.

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

## 1. Render rollback procedure

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

## 2. Operate the Azure Static Web Apps frontend

The active Static Web App deploys through
`.github/workflows/azure-static-web-apps-salmon-field-03695a010.yml`. The production workflow accepts
only a successful `CI` run caused by a push to this repository's `master` branch. Pull requests run
the same frontend audit, syntax checks, contract tests and build without receiving a deployment
credential; FirstRoll deliberately does not create Azure preview deployments from pull-request code.
Use `./tools/preview_hosted_web.sh` for a local hosted-mode preview.

| Setting | Value |
|---|---|
| Trigger | successful `CI` push run on `master` |
| Checked-out revision | exact CI-approved SHA, verified as the current `master` head |
| App location | `dist`; pre-built before the deployment credential is used |
| API location | empty; FastAPI is a separate service |
| Output location | empty because Azure's application build is skipped |
| Build script | `./tools/build_web.sh` with lockfile-controlled, lifecycle-script-disabled installation |
| Visitor domain | `https://firstroll.app` |

The workflow supplies these public build values:

| Key | Purpose |
|---|---|
| `FIRSTROLL_API_BASE` | complete backend origin; `https://api.firstroll.app` |
| `FIRSTROLL_SUPABASE_URL` | Supabase project URL |
| `FIRSTROLL_SUPABASE_PUBLISHABLE_KEY` | browser-safe Supabase publishable key |

The Azure deployment token is rotated into the branch-restricted GitHub `production` environment as
`AZURE_STATIC_WEB_APPS_API_TOKEN_SALMON_FIELD_03695A010`; it is not a repository-wide secret. Never
place that token in source code or a public build variable. The uncredentialled build job validates
`dist` and seals it in an immutable, one-day GitHub Actions artifact. A separate deployment runner
checks out no repository code, downloads that artifact by its run-scoped ID and gives the token only
to the final pinned Azure action. `skip_app_build` prevents that action from running repository build
code while credentialled.

Both workflows grant `GITHUB_TOKEN` only read access to repository contents, do not persist checkout
credentials and pin every external action to a full commit SHA. Repository Actions policy enforces
SHA pinning and permits only GitHub-owned actions plus the explicitly allow-listed HashiCorp and
Azure actions. Dependabot checks the npm lock and action pins weekly; production dependency audit
failures at high severity block CI and deployment.

Every push to `master` runs CI first. A successful current revision starts one serialised production
job; a failed, cancelled, pull-request, foreign-repository or stale run cannot deploy. After a
production job succeeds, verify `https://firstroll.app` because custom-domain DNS and CDN caching are
separate from the build job. The frontend should appear independently of the API's deployment state.

## 3. Connect Supabase authentication

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
4. Configure the matching Container App values through Terraform and Azure's secret boundary:

   | Key | Value |
   |---|---|
   | `SUPABASE_URL` | the same Supabase Project URL |
   | `SUPABASE_PUBLISHABLE_KEY` | the same `sb_publishable_...` key |

5. Deploy a new immutable Container App revision.
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

## 4. Enable quota-controlled Deep Study

The public demo permits three Deep Studies per account per UTC day and thirty across all accounts.
It stores only the Supabase user UUID, UTC day and counters; prompts and generated studies are not
stored in Supabase.

1. In Supabase, open **SQL Editor → New query**.
2. Paste the complete contents of
   `supabase/migrations/202608150001_deep_study_quotas.sql` and select **Run**.
3. Confirm the result reports success. The migration creates two RLS-enabled tables in the
   non-exposed `firstroll_private` schema and two authenticated-only functions:
   `deep_study_quota_status()` and `reserve_deep_study_quota()`.
4. Add these values to the Azure Container App—not the Static Web App—and deploy a new revision:

   | Key | Value |
   |---|---|
   | `DEEPSEEK_API_KEY` | the private DeepSeek API key |
   | `DEEPSEEK_MODEL` | `deepseek-v4-flash` |
   | `FIRSTROLL_DEEP_STUDY_ENABLED` | `true` |

5. Never add `DEEPSEEK_API_KEY` to the Static Site or repository. No Supabase secret or
   service-role key is required.
6. Save and redeploy the backend. The explicit feature switch must remain absent or false until the
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
3. Store its `postgresql://...?...sslmode=require` connection URL in macOS Keychain and provide it
   to Terraform through `TF_VAR_database_url`; never commit or print it.
4. Set `quota_provider = "postgres"`, review the plan, deploy a new API image and test quota status,
   reservation, the fourth-request 429 and concurrent reservations.
5. Observe one complete UTC quota day before removing the legacy Supabase RPC.

The API passes PostgreSQL only the verified identity-provider name and immutable subject. It does
not forward the browser bearer token, email, study question or generated result.

## 5. Allow the Azure frontend to call the API

1. Set this Container App environment value through Terraform:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_CORS_ALLOWED_ORIGINS` | `https://firstroll.app` |

2. Review and apply the Terraform plan.
3. Open `https://firstroll.app` in a private browser window and perform a film search.

Do not use `*` as the allowed origin. The exact frontend origin will later carry Supabase bearer
tokens to the API. Add the Azure-generated hostname only if it intentionally remains a supported
visitor origin.

## Optional public video provider

YouTube search can use a server-side YouTube Data API v3 key. Add `YOUTUBE_API_KEY` to the Container
App's secret boundary and deploy a new revision; never add it to the Azure static build.
Alternatively, a
signed-in visitor can supply a personal key for one browser tab through Settings. The browser holds
that key only in memory and sends it only with an authenticated video-search request. Restrict keys
to the YouTube Data API in Google Cloud and set a conservative quota alert.

The production image builds and bundles the unofficial Douban MCP connector at the exact revision
declared by `DOUBAN_MCP_REF` in `Dockerfile`. It uses anonymous provider access by default. Public
Settings reports whether that hosted runtime is ready but provides no Douban credential field, and
the API never accepts or stores a visitor's Douban cookie. Provider page changes, access controls or
rate limits can still make this optional source temporarily unavailable.

## 6. Current public-beta acceptance checks

- `/api/health` returns HTTP 200.
- `https://firstroll.app` serves the interface and 3D assets without waiting for the backend.
- The backend root identifies itself as the FirstRoll API.
- Search begins working after the backend wakes.
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

## 7. Azure Container Apps production state

The API migration is complete:

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

## 8. Optional Entra External ID learning path

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

## 9. Next security milestone

Add cost telemetry and an operator-visible kill switch before raising either daily limit. Video
analysis remains a local feature and is presented as **Coming soon** in the public interface.

## Cost and availability notes

The Container App filesystem is ephemeral. Durable account, quota or study data must live in a
database rather than the container. Azure Static Web Apps is CDN-served and does not depend on the
backend process to display the interface.

The Container App defaults to one minimum replica to address cold starts. Lowering it to
zero reduces compute cost but reintroduces a wake-up delay. Azure Container Registry Basic and Log
Analytics can incur charges even before application traffic arrives.
