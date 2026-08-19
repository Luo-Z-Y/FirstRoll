# FirstRoll Public Beta Hosting

**Deployment status:** Active Azure frontend with Render API

**Visitor URL:** `https://firstroll.app`

**API URL:** `https://firstroll.onrender.com`

**Last reconciled:** 19 August 2026

FirstRoll is not merely a local application. Its active public beta uses Azure Static Web Apps for
the frontend and Render for the Docker API, while private-library and clip-analysis capabilities
remain local by design:

```text
Browser  ->  Azure Static Web Apps  ->  Render FastAPI Web Service  ->  public film sources
              firstroll.app                  API
```

The hosted edition publishes discovery, the 3D shelf, Supabase email sign-in and an authenticated
Integration Centre. Private-library settings, local documents, clip uploads, computer-vision
analysis and unauthenticated Deep Study are blocked by the backend. Authenticated Deep Study is
protected by durable Supabase usage counters.
The separate origins keep the public boundary explicit and allow the Azure-hosted frontend shell to
load while the free Render API wakes.

The frontend and API origins are deployment configuration. `FIRSTROLL_API_BASE` currently points to
the Render API, while `FIRSTROLL_CORS_ALLOWED_ORIGINS` must include the exact
`https://firstroll.app` origin. See
[Architecture](ARCHITECTURE.md), [API Reference](API_REFERENCE.md), [Data Model](DATA_MODEL.md) and
[Architecture Decisions](DECISIONS.md) for the corresponding runtime contracts.

Terraform under `infra/terraform` defines the foundation for moving FastAPI to Azure Container
Apps. It intentionally does not manage or import the existing Static Web App.

## Local production checks

Build the static site with a temporary API address:

```bash
FIRSTROLL_API_BASE=https://firstroll-api-example.onrender.com ./tools/build_web.sh
```

Build and start the backend container:

```bash
docker build -t firstroll:render .
docker run --rm --name firstroll-render-test \
  -e FIRSTROLL_PUBLIC_MODE=true \
  -p 127.0.0.1:18000:10000 \
  firstroll:render
```

In another terminal, verify:

```bash
curl http://127.0.0.1:18000/api/health
curl http://127.0.0.1:18000/api/discovery/status
```

Stop the test container with `docker stop firstroll-render-test`.

## 1. Current Render API recovery procedure

The active API is already deployed. Use these steps only to recreate it during recovery:

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

The active Static Web App deploys from `master` through
`.github/workflows/azure-static-web-apps-salmon-field-03695a010.yml`.

| Setting | Value |
|---|---|
| App location | `/` |
| API location | empty; FastAPI is a separate service |
| Output location | `dist` |
| Build script | `./tools/build_web.sh` |
| Visitor domain | `https://firstroll.app` |

The workflow supplies these public build values:

| Key | Purpose |
|---|---|
| `FIRSTROLL_API_BASE` | complete backend origin; currently `https://firstroll.onrender.com` |
| `FIRSTROLL_SUPABASE_URL` | Supabase project URL |
| `FIRSTROLL_SUPABASE_PUBLISHABLE_KEY` | browser-safe Supabase publishable key |

The Azure deployment token remains in the GitHub Actions secret
`AZURE_STATIC_WEB_APPS_API_TOKEN_SALMON_FIELD_03695A010`. Never place that token in source code or a
public build variable.

Every push to `master` runs CI and the Azure deployment. After it succeeds, verify
`https://firstroll.app` because custom-domain DNS and CDN caching are separate from the build job.
The frontend should appear immediately even when the Render backend is asleep.

## 3. Connect Supabase authentication

The Supabase project URL and publishable key are designed to be public. Use the same two values in
the Azure frontend build and Render backend; never use the secret or service-role key for these
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
4. In the Render **backend Web Service**, open **Environment** and add:

   | Key | Value |
   |---|---|
   | `SUPABASE_URL` | the same Supabase Project URL |
   | `SUPABASE_PUBLISHABLE_KEY` | the same `sb_publishable_...` key |

5. Save and redeploy the backend.
6. Keep Supabase **Authentication → URL Configuration → Site URL** set to
   `https://firstroll.app`, and include `https://firstroll.app/**` in **Redirect URLs**. Retain the
   Azure-generated hostname only when it remains an intentional test entry point; remove obsolete
   Render frontend URLs.
7. Open the frontend in a private window, select **Sign in**, request an email link, follow it and
   confirm the header displays the account email. `/api/auth/me` should then return that account's
   Supabase user ID and email when called with its bearer token.

The browser stores only Supabase's short-lived user session. FastAPI validates each bearer token
against Supabase Auth before allowing an authenticated operation. No provider secret is included in
the static bundle.

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
4. In the Render backend Web Service—not the Static Site—open **Environment** and add:

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

## 5. Allow the Azure frontend to call the API

1. Return to the backend Web Service.
2. Select **Environment**.
3. Add:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_CORS_ALLOWED_ORIGINS` | `https://firstroll.app` |

4. Choose **Save, rebuild, and deploy**.
5. Open `https://firstroll.app` in a private browser window and perform a film search.

Do not use `*` as the allowed origin. The exact frontend origin will later carry Supabase bearer
tokens to the API. Add the Azure-generated hostname only if it intentionally remains a supported
visitor origin.

## Optional public video provider

YouTube search can use a server-side YouTube Data API v3 key. Add `YOUTUBE_API_KEY` to the backend
Web Service's **Environment** page and redeploy; never add it to the Azure static build.
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

## 7. Azure Container Apps migration

The next infrastructure milestone replaces only the Render API:

```text
firstroll.app     -> Azure Static Web Apps
api.firstroll.app -> Azure Container Apps
Supabase          -> authentication and quota, unchanged
```

The migration sequence is deliberately reversible:

1. Use `infra/terraform` to create Azure Container Registry, Log Analytics and a Container Apps
   environment in the existing `firstroll-production` resource group.
2. Build the current Dockerfile into Azure Container Registry.
3. Enable the gated Container App resource and verify its Azure hostname.
4. Copy backend configuration and secrets through Azure's secret boundary.
5. Test health, discovery, authentication, quota and Deep Study.
6. Bind `api.firstroll.app` and allow Azure to issue TLS.
7. Rebuild the static frontend with the new API origin.
8. Keep Render available as a rollback target for at least 48 hours.
9. Remove Render only after logs and acceptance checks remain healthy.

Do not migrate authentication or introduce PostgreSQL in the same change. Those are separate
milestones with independent rollback and data-migration plans.

## 8. Next security milestone

Add cost telemetry and an operator-visible kill switch before raising either daily limit. Video
analysis remains a local feature and is presented as **Coming soon** in the public interface.

## Cost and availability notes

The Render backend sleeps after an idle period and its filesystem is ephemeral. Any durable account,
quota or study data must live in Supabase. Azure Static Web Apps is CDN-served and does not depend on
the backend process to display the interface.

The planned Container App defaults to one minimum replica to address cold starts. Lowering it to
zero reduces compute cost but reintroduces a wake-up delay. Azure Container Registry Basic and Log
Analytics can incur charges even before application traffic arrives.
