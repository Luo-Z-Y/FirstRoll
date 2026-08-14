# FirstRoll Public Beta Hosting

FirstRoll's first public beta uses two Render services from the same `master` branch:

```text
Browser  ->  Render Static Site  ->  Render FastAPI Web Service  ->  public film sources
                 frontend                     API
```

The hosted edition deliberately publishes discovery, the 3D shelf and Supabase email sign-in.
Private-library settings, local documents, clip uploads, computer-vision analysis and
unauthenticated Deep Study are blocked by the backend. Authenticated Deep Study remains quota-gated
until its durable Supabase usage tables are installed.
The separate origins keep the public boundary explicit and allow the frontend shell to load while
the free API service wakes.

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

## 1. Create the backend Web Service

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

Record the complete backend URL. It is required when building the static site.

Open the root service URL. In public mode it identifies itself as the FirstRoll API; it is not the
visitor-facing website.

## 2. Create the separate Static Site

1. In Render, select **New** and then **Static Site**.
2. Select the same GitHub repository and enter:

   | Setting | Value |
   |---|---|
   | Name | `firstroll-web-luo` or another available name |
   | Branch | `master` |
   | Root directory | leave empty |
   | Build command | `./tools/build_web.sh` |
   | Publish directory | `dist` |
   | Auto-deploy | After CI checks pass |

3. Add this public build-time environment variable:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_API_BASE` | the complete backend `https://...onrender.com` URL |

4. Select **Create Static Site** and wait for it to report **Live**.
5. Record its complete URL.

The frontend should appear immediately even when the backend is asleep. Search will remain
unavailable until the API has woken.

## 3. Connect Supabase authentication

The Supabase project URL and publishable key are designed to be public. Use the same two values on
both Render services; never use the secret or service-role key for these settings.

1. In Supabase, open **Project Settings → API** and copy **Project URL** and the
   `sb_publishable_...` key.
2. In the Render **Static Site**, open **Environment** and add:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_SUPABASE_URL` | the Supabase Project URL |
   | `FIRSTROLL_SUPABASE_PUBLISHABLE_KEY` | the `sb_publishable_...` key |

3. Save the changes and choose **Manual Deploy → Deploy latest commit**. These are build-time
   values, so a fresh static build is required.
4. In the Render **backend Web Service**, open **Environment** and add:

   | Key | Value |
   |---|---|
   | `SUPABASE_URL` | the same Supabase Project URL |
   | `SUPABASE_PUBLISHABLE_KEY` | the same `sb_publishable_...` key |

5. Save and redeploy the backend.
6. Keep Supabase **Authentication → URL Configuration → Site URL** set to the exact frontend URL,
   `https://firstroll-web.onrender.com`, and include that same URL in **Redirect URLs**.
7. Open the frontend in a private window, select **Sign in**, request an email link, follow it and
   confirm the header displays the account email. `/api/auth/me` should then return that account's
   Supabase user ID and email when called with its bearer token.

The browser stores only Supabase's short-lived user session. FastAPI validates each bearer token
against Supabase Auth before allowing an authenticated operation. No provider secret is included in
the static bundle.

## 4. Allow the Static Site to call the API

1. Return to the backend Web Service.
2. Select **Environment**.
3. Add:

   | Key | Value |
   |---|---|
   | `FIRSTROLL_CORS_ALLOWED_ORIGINS` | the complete static-site `https://...onrender.com` URL |

4. Choose **Save, rebuild, and deploy**.
5. Open the static site in a private browser window and perform a film search.

Do not use `*` as the allowed origin. The exact frontend origin will later carry Supabase bearer
tokens to the API.

## Optional public video provider

YouTube search requires a server-side YouTube Data API v3 key. Add `YOUTUBE_API_KEY` to the
backend Web Service's **Environment** page and redeploy; never add it to the Static Site. Restrict
the key to the YouTube Data API in Google Cloud and set a conservative quota alert.

Douban is not bundled into the hosted image. Its current integration is an unofficial Node-based
MCP connector and may require a user cookie, so it must not be exposed through unauthenticated
public Settings. Review and pin the connector, then protect its use with Supabase authentication
before enabling it on the shared server.

## 5. Current public-beta acceptance checks

- `/api/health` returns HTTP 200.
- The Static Site URL serves the interface and 3D assets without waiting for the backend.
- The backend root identifies itself as the FirstRoll API.
- Search begins working after the backend wakes.
- `/api/settings` and `/api/library/status` return HTTP 404 in public mode.
- `/api/analyze` returns HTTP 503 in public mode.
- `/api/auth/me` returns HTTP 401 without a session and the signed-in account with a valid session.
- Deep Study returns HTTP 401 without a session and HTTP 503 at the quota gate when signed in.
- No `.firstroll` data, uploaded clips, API keys or private library files appear in the image,
  repository, frontend source or network responses.

## 6. Next security milestone

Create durable Supabase usage tables, add per-user and global Deep Study quotas, and only then add
the DeepSeek API key to Render. Video analysis remains a local feature and is presented as
**Coming soon** in the public interface.

## Free-tier limitations

The Render backend sleeps after an idle period and its filesystem is ephemeral. Any durable account,
quota or study data must live in Supabase. The static site is CDN-served and does not depend on the
backend process to display the interface.
