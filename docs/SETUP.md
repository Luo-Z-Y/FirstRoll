# Set Up FirstRoll

This guide installs and runs the private **local edition** on one computer, configures its optional
connectors and private study library, and lists the checks a contributor runs before opening a pull
request. The public server is covered in [Operations](OPERATIONS.md) and
[infra/vps/README.md](../infra/vps/README.md), the system design in [Architecture](ARCHITECTURE.md),
and sources, storage and the HTTP API in [Data](DATA.md).

```text
Browser → http://127.0.0.1:8000 → one FastAPI process (uv run firstroll)
            ├── web interface, Settings console and API
            ├── TMDb (optional) → Wikidata/Wikipedia → bundled offline records
            ├── DeepSeek plus criticism and video sources (key-free or optional keys)
            ├── private study library and index under .firstroll/
            └── local clip analysis (FFmpeg + computer-vision models)
```

`uv run firstroll` binds to `127.0.0.1:8000` only, so the app is not reachable from the local network
or the internet. Do not start a separate frontend server.

## Requirements

| Requirement | Needed for | Notes |
|---|---|---|
| macOS, Windows or Linux | Everything | |
| Git | Install and updates | |
| Python 3.11 or 3.12 | Everything | `pyproject.toml` requires `>=3.11,<3.13`; `.python-version`, CI and the production image use 3.11 |
| [`uv`](https://docs.astral.sh/uv/getting-started/installation/) | Environment and dependencies | Installs the locked dependency set from `uv.lock` |
| FFmpeg | Clip analysis only | Discovery and Deep Study work without it |
| Node.js 22 or later | Douban MCP, tests and frontend build | Not needed just to run the local edition |
| Internet connection | Live catalogue search and connectors | A small bundled catalogue covers a complete outage |
| Disk space | Computer-vision stack and models | The first `uv sync` downloads large packages; the first library index build downloads the embedding model |

## Install

### 1. System tools

| Platform | Commands |
|---|---|
| macOS ([Homebrew](https://brew.sh/)) | `brew install git ffmpeg uv` |
| Windows (PowerShell) | `winget install --id Git.Git -e`, `winget install --id Gyan.FFmpeg -e`, `winget install --id astral-sh.uv -e`, then reopen PowerShell |
| Ubuntu or Debian | `sudo apt update && sudo apt install git ffmpeg curl`, then `curl -LsSf https://astral.sh/uv/install.sh \| sh` and open a new terminal |

### 2. FirstRoll

```bash
git clone https://github.com/Luo-Z-Y/FirstRoll.git
cd FirstRoll
uv sync                 # runtime only
uv sync --extra dev     # contributors: adds pytest, ruff and mypy
```

`uv sync` is exact: running it later without `--extra dev` removes the development tools again.

## Run the Local Edition

| Task | Command |
|---|---|
| Start | `uv run firstroll`, then open <http://127.0.0.1:8000> |
| Stop | `Ctrl+C` in the same terminal |
| Update | `git pull`, `uv sync`, `uv run firstroll` |
| Run on another port | `uv run uvicorn app.backend.main:app --host 127.0.0.1 --port 8001` |

Keep `--host 127.0.0.1` on any manual launch. The local edition also serves interactive API
documentation at <http://127.0.0.1:8000/docs>; the hosted mode does not publish it.

## Confirm It Works

1. Open <http://127.0.0.1:8000/api/health>; it returns `{"status": "ok"}`.
2. Choose **Sign in** and use the local test account (below) with any password of at least eight
   characters. Reload and confirm that the session persists.
3. Open **Settings → System settings** and confirm the unlimited local allowance.
4. Search for a film by title, year and optionally director. Discovery reports TMDb as ready when a
   token is configured, otherwise it reports that TMDb credentials are required and uses Wikidata.
5. Open a film dossier and inspect its source link and evidence boundary.
6. Open **Analyse**, choose a short video clip and generate an analysis.

### Local test account

| Property | Behaviour |
|---|---|
| Identity | `luo_zhiyang@outlook.com`, any password of eight or more characters |
| Where it works | Any port, but only when both the browser URL host and the connecting client are loopback (`localhost`, `127.0.0.1` or `::1`); every other host rejects its token |
| Launchers | `uv run firstroll` and the hosted preview (`tools/frontend/preview.sh`) expose the same account |
| Storage | Profile, preferences and saved films live in that browser's local storage, not in Supabase |
| Allowance | Bypasses only FirstRoll's own Deep Study counters; DeepSeek, YouTube and other provider limits and billing still apply |

On a loopback address the header shows **Discover / Analyse / Settings**. The in-app **Settings**
view covers profile, appearance and allowance; the separate **Settings console**, opened directly at
<http://127.0.0.1:8000/settings> (called "the console" below), holds connector credentials and the
private library.

## Configuration

Each connector reads its credential from an environment variable first, then from the write-only
store `.firstroll/settings.json` (mode `0600`, Git-ignored) that the console writes. The browser only
ever receives a masked hint. When every credential of a connector comes from the environment, the
console disables **Save locally** for it.

FirstRoll does **not** load `.env` files. Export variables before starting the process, or use the
console, and restart after changing any. [.env.example](../.env.example) is a reference list. It
includes three hosted variables (`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
`FIRSTROLL_DEEP_STUDY_ENABLED`) that stay empty or off locally.

### Connectors

| Connector | Variable(s) | What it adds | Without it |
|---|---|---|---|
| TMDb catalogue | `TMDB_BEARER_TOKEN` (API Read Access Token) | Faster title matching, posters, credits, IMDb/Wikidata identity links | Key-free Wikidata/Wikipedia, then bundled offline records |
| DeepSeek | `DEEPSEEK_API_KEY`, optional `DEEPSEEK_MODEL` | Deep Study synthesis and structuring of attributed critic claims | Discovery, evidence and criticism retrieval still work; no generated study |
| YouTube Data API | `YOUTUBE_API_KEY` | Public, embeddable YouTube film videos | Bilibili public search only |
| Douban MCP | `DOUBAN_COOKIE` (only if anonymous access fails), `FIRSTROLL_DOUBAN_MCP_PATH` | Chinese-language review summaries | Douban tab unavailable |
| Letterboxd API | `LETTERBOXD_CLIENT_ID` and `LETTERBOXD_CLIENT_SECRET` | Official OAuth search and popularity-ranked public reviews | The key-free public-web **Letterboxd** tab still works |
| Not yet used | `NYT_API_KEY`, `GUARDIAN_API_KEY` | Shown as *planned* in the console; no adapter uses them | — |

Key-free sources need no configuration: Wikidata/Wikipedia, Crossref scholarship (**Research** tab),
the Guardian public Content API index (**Guardian** tab), Letterboxd public web pages and Bilibili.
Provider terms, copyright boundaries and permitted model use are in [Data](DATA.md).

### DeepSeek

Paste the key into the DeepSeek card in the console and choose **Save locally**, or export
`DEEPSEEK_API_KEY`. **Generate study** in a film dossier then sends DeepSeek a selected, attributed
evidence packet, never a whole PDF, an embedding or a local file path ([Data](DATA.md) lists what it
contains). A local study needs at least one indexed library passage, so build the
[private study library](#private-study-library) first. The fixed workflow makes at most two model
calls per study: the draft, plus either one bounded schema retry or one quality repair.

| `DEEPSEEK_MODEL` | Use |
|---|---|
| `deepseek-v4-pro` (default) | More coherent long-form study writing |
| `deepseek-v4-flash` | Lower latency and cost; identical evidence, schema and quality gate |

### TMDb

Create a TMDb application, copy its **API Read Access Token** and paste it into the console's
**TMDb catalogue** card (or export `TMDB_BEARER_TOKEN`), then run **Test connection**. Clearing the
token returns discovery to the open fallback. TMDb requires attribution, which the dossier shows, and
separate review for commercial use. On a server the token belongs only in the backend environment,
never in static frontend configuration.

### Douban MCP

Douban MCP is an unofficial adapter and may break when Douban changes its pages or access controls.
Install it only inside the Git-ignored connector directory, at the revision the production image pins
in `Dockerfile`:

```bash
mkdir -p .firstroll/connectors
git clone https://github.com/moria97/douban-mcp.git .firstroll/connectors/douban-mcp
cd .firstroll/connectors/douban-mcp
git checkout --detach 1adc26d39532db893616ceb7ea851733948ae69e
npm ci --ignore-scripts
npm run build
cd ../../..
```

After the build, the production image also applies pinned dependency overrides and an `npm audit`
gate; repeat those `Dockerfile` steps if you want the same dependency set locally.

FirstRoll runs `node` on `.firstroll/connectors/douban-mcp/dist/index.js` over stdio, or on the file
named by `FIRSTROLL_DOUBAN_MCP_PATH`, and uses only its `search-movie` and `list-movie-reviews`
tools. Once that file exists, the **Douban** tab becomes available in film dossiers and requests are
anonymous. Only if they fail, save a personal cookie in the console, which also enables its **Test
connection** button. Never share or commit a cookie.

Review summaries are copyrighted secondary criticism: FirstRoll keeps a link to each original review,
caches the bundle and any DeepSeek-structured claims under `.firstroll/criticism`, and leaves missing
scenes, techniques and timecodes empty rather than inferring them.

### Letterboxd

| Tab | Mechanism | Credentials |
|---|---|---|
| **Letterboxd** | Bounded reader of public film and review pages; may break when Letterboxd changes its pages | None |
| **Letterboxd API** | Official OAuth client credentials; `/search` and `/log-entries` | Client ID and Client Secret granted by Letterboxd |

The two adapters are independent: the API tab is enabled only when both credentials are present and
never falls back to page reading, and the public-web tab never uses OAuth credentials.

### Other local variables

| Variable | Default | Effect |
|---|---|---|
| `FIRSTROLL_SETTINGS_PATH` | `.firstroll/settings.json` | Location of the write-only credential store |
| `FIRSTROLL_LIBRARY_PATH` | `.firstroll/library` | Managed library folder |
| `FIRSTROLL_LIBRARY_MANIFEST` | `.firstroll/library.json` | Registered external paths and removal list |
| `FIRSTROLL_LIBRARY_INDEX` | `.firstroll/library.sqlite3` | Private search index |
| `FIRSTROLL_EMBEDDINGS` | `1` | `0` builds a lexical-only (FTS5) index |
| `FIRSTROLL_PREWARM_EMBEDDINGS` | `1` | `0` defers loading the query encoder until the first semantic query |
| `FIRSTROLL_EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Local embedding model; rebuild the index after changing it |
| `FIRSTROLL_VIDEO_ANALYSIS_ENABLED` | on locally, off in public mode | `false` disables clip analysis |
| `FIRSTROLL_WORDCLOUD_FONT` | a system CJK font | Word-cloud font file for clip analysis; the original `PYCINEMETRICS_WORDCLOUD_FONT` is still read |

Hosted-only variables (`FIRSTROLL_PUBLIC_MODE`, `SUPABASE_*`, `FIRSTROLL_DEEP_STUDY_ENABLED`,
`FIRSTROLL_AUTH_PROVIDER`, `FIRSTROLL_QUOTA_PROVIDER`, `FIRSTROLL_DATABASE_URL` and
`FIRSTROLL_CORS_ALLOWED_ORIGINS`) are set on the server, and `FIRSTROLL_RELEASE_SHA` is baked into
the production image; see [Operations](OPERATIONS.md) and
[infra/vps/README.md](../infra/vps/README.md). Leave them unset for the local edition.

## Private Study Library

The library supplies page-cited passages to Deep Study. Manage it from **Study library** in the
console at <http://127.0.0.1:8000/settings>.

| Action | How | Result |
|---|---|---|
| Add | Upload a PDF, EPUB, Markdown or text file (up to 500 MB) | Copied into the managed library folder with mode `0600` |
| Add manually | List absolute paths in `.firstroll/library.json` (example below), or place files in `.firstroll/library` | Catalogued in place, without copying |
| Remove | **Remove** in the console | Drops the registration; never deletes the source file |
| Index | **Rebuild search index**, or `uv run firstroll-index` | Rebuilds `.firstroll/library.sqlite3` |
| Check | Console, or <http://127.0.0.1:8000/api/library/status> | Titles, formats, sizes, topics and index state; never paths |

```json
{
  "documents": [
    "/absolute/path/to/a-film-book.pdf",
    "/absolute/path/to/research-notes.md"
  ]
}
```

Rebuild the index whenever documents are added, removed or replaced; film dossiers then show the
selected passages with book title and PDF page. Only PDFs are indexed; EPUB, Markdown and text files
are catalogue-only for now. FirstRoll does not run OCR, so a scanned PDF without a text layer yields
no passages. The first build downloads the embedding model; retrieval then runs on-device and falls
back to lexical (FTS5) search when vectors are disabled or unavailable. Index structure and retrieval
parameters are in [Data](DATA.md).

On start, the local edition loads the query encoder once in a background thread (unless
`FIRSTROLL_PREWARM_EMBEDDINGS=0`) while the API stays responsive. `/api/discovery/status` reports the
warm-up as `idle`, `warming`, `ready`, `failed` or `unavailable`; a failed warm-up still leaves
lexical retrieval available.

**Privacy and copyright.** Uploads, registrations, chunks, vectors, criticism and video caches and
credentials all stay under `.firstroll/`, which Git ignores, and the library APIs never return file
paths or document contents. Clip analysis writes frames and charts to the Git-ignored `img/<clip>/`
folder and deletes its temporary copy of the uploaded clip. Only add, analyse or index material you
are entitled to use, and never publish copyrighted books, films or clips because they sit in a
private research library.

## Development and Verification

Install the development extra (`uv sync --extra dev`) and Node.js 22, then run
`npm ci --include=dev --ignore-scripts` before the checks:

| Check | Command | Expected |
|---|---|---|
| Python suite (also runs the Node race checks) | `uv run pytest -q tests` | All pass |
| Frontend contracts, module and race checks | `npm run test:web` | All pass |
| Lint | `uv run ruff check app/backend tests tools --exclude app/backend/algorithms` | Clean |
| Strict frontend types | `npm run typecheck` | All pass |
| Local frontend bundles | `npm run build:local` | Generated scripts under `app/web/generated/` |
| Whitespace | `git diff --check` | No output |

Pytest defaults to `tests/`; an explicit path still works for focused checks. The inherited modules under
`app/backend/algorithms` still carry historical lint findings and are excluded from the lint gate.
CI (`.github/workflows/ci.yml`) runs the pytest suite (against `requirements-hosted.txt`) and the
strict frontend build and Node suite, audits the npm lock, validates the VPS stack, builds the production image and
checks its Douban MCP handshake, and builds the static frontend. CI does not run Ruff or
`git diff --check`, so run those locally.

### Static frontend build

`tools/frontend/build.sh` (also `npm run build`) runs `npm ci`, minifies the app with esbuild and writes
the hosted site to the Git-ignored `dist/` with a generated `assets/config.js`.

| Variable | Required | Rule |
|---|---|---|
| `FIRSTROLL_API_BASE` | Yes | Backend `https://` URL |
| `FIRSTROLL_SUPABASE_URL` | With the key | `https://*.supabase.co` |
| `FIRSTROLL_SUPABASE_PUBLISHABLE_KEY` | With the URL | Must begin `sb_publishable_` |
| `FIRSTROLL_BUILD_CHANNEL` | No | `local`, `live` or `preview`; defaults to `live` in CI, otherwise `local` |
| `FIRSTROLL_BUILD_NUMBER`, `FIRSTROLL_BUILD_COMMIT` | No | Default to the Git commit count (plus one for `local`) and short SHA |

```bash
FIRSTROLL_API_BASE=https://firstroll.example.com ./tools/frontend/build.sh
FIRSTROLL_TEST_APP=dist/assets/app.js npm run test:web
```

The second command reruns the frontend suite against the minified application build.

### Hosted-mode preview

Run `npm run preview` to compile the frontend, then launch `tools/frontend/preview.sh`.
The launcher serves the hosted interface and API from one loopback origin, by default
<http://127.0.0.1:4173> (set `PORT` to change it). It sets `FIRSTROLL_PUBLIC_MODE=true`,
`FIRSTROLL_SERVE_HOSTED_FRONTEND=true`, `FIRSTROLL_VIDEO_ANALYSIS_ENABLED=false` and
`FIRSTROLL_BUILD_CHANNEL=local`. Export `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` to exercise real
accounts; otherwise use the local test account. As on the live site, clip analysis is disabled, the
console at `/settings` returns `404` and Deep Study uses the hosted first-party framework passages
instead of the private library. The local test account skips the hosted enablement switch and quota
but still needs a DeepSeek key from the environment or the local store.

### Optional browser diagnostic

`tools/frontend/check-responsiveness.cjs` measures immediate study feedback in Chrome against synthetic
fixtures, without starting the backend or contacting providers. It needs a prior `dist` build, an
installed Google Chrome, Playwright 1.58.2 kept outside the project's dependencies, and the full
SHA of a baseline commit present in this clone:

```bash
browser_tools=$(mktemp -d)
npm --prefix "$browser_tools" install --ignore-scripts --no-audit --no-fund \
  --package-lock=false playwright@1.58.2
NODE_PATH="$browser_tools/node_modules" node tools/frontend/check-responsiveness.cjs <baseline-full-sha>
```

It writes screenshots and a hash-bound JSON report to a fresh temporary directory. Synthetic timings
are not live-site or model-speed claims.

### Branches, agents and releases

Work on short-lived `feat/`, `fix/`, `docs/` or `chore/` branches and merge through a green pull
request into protected `master`, as set out in [AGENTS.md](../AGENTS.md). Optional Pi subagents are
described in [.pi/README.md](../.pi/README.md); production release and approval are in
[Operations](OPERATIONS.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `uv: command not found` | Open a new terminal; if it persists, reinstall `uv` from the official instructions |
| Port 8000 already in use | Stop the other service, or start on another port with the `uvicorn` command above |
| Discovery says Wikidata is unavailable | Check the connection; supported sample films still resolve from the bundled offline catalogue |
| Clip analysis fails while discovery works | Confirm `ffmpeg -version` in a new terminal; start with a short MP4, since large files and model inference need substantial memory |
| Console at `/settings` returns `403` | Open it from the same machine via `127.0.0.1`, `localhost` or `::1` |
| Console at `/settings` returns `404` | `FIRSTROLL_PUBLIC_MODE` is set (for example by the hosted preview); unset it and restart |
| **Save locally** is disabled for a connector | Its environment variables are set and take precedence; unset them and restart to manage it from the console |
| Douban tab unavailable or reports "not installed" | Build the connector so `dist/index.js` exists, or point `FIRSTROLL_DOUBAN_MCP_PATH` at it |
| **Letterboxd API** tab disabled | Configure both the Client ID and the Client Secret |
| Study fails with "Add a DeepSeek API key in FirstRoll Settings first." | Save a DeepSeek key in the console, or export `DEEPSEEK_API_KEY` and restart |
| Study fails with "No cited local passages are available…" | Add at least one text-layer PDF to the library and rebuild the index |
| Startup fails with `FIRSTROLL_AUTH_PROVIDER must be 'supabase'` | Unset a stale value left from the retired Azure set-up (tag `archive/azure`); Supabase is the only provider |
| An old command uses `tools/evaluate_*`, `evals/` or `FIRSTROLL_LOCAL_AGENT_ENABLED` | Removed with the parked research Agent programme; recover it from tag `archive/agent-programme` if needed |
