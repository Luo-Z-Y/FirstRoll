# Finding your way around FirstRoll

This is a source-code map, not a new architecture. Runtime behaviour, API routes and the
production approval gate are unchanged. Start with the task you want to perform below;
you do not need to understand every file first.

## Repository layout

```text
app/
  backend/             Python API, provider adapters and study services
    algorithms/        Inherited local clip-analysis code and its data files
  web/
    src/               Feature-oriented TypeScript application modules
    *.ts               Browser startup and account/settings entry points
    index.html         Page structure
    styles.css         Shared visual styles and responsive breakpoints
    generated/         Compiled local scripts — generated, not committed
tests/
  test_*.py            API, services, security, build and release contracts
  web/                 Frontend unit/controller tests and TypeScript contracts
  fixtures/            Small synthetic test data, not private source material
tools/
  frontend/            Compiler, static build, preview and optional diagnostic
  release/             Release receipts and VPS validation/activation tooling
infra/vps/             Caddy, Docker Compose and server administration scripts
supabase/migrations/   Versioned database schema and account/quota policies
docs/                  Architecture, setup, operations, data and progress guides
models/                Local analysis model assets; not required by the hosted image
dist/                  Generated hosted frontend — never edit or commit
```

Root-level files are intentionally limited to package/dependency configuration, the Docker
entry point, repository policies, licence/attribution and the README. Keep `.firstroll/`,
`.env`, model downloads, generated output and private credentials out of commits. A local
`.claude/` folder is not part of this reorganisation; it is not uploaded or deleted.

## Where should I make a change?

| Task | Start here | Check here |
|---|---|---|
| Page layout or styling | `app/web/index.html`, `styles.css` | Browser at phone/desktop widths, `tests/test_web_assets.py` |
| Festival map | `app/web/src/festivals/` | `tests/web/festivals.test.cjs` |
| Search, shelf and dossier | `app/web/src/discovery/`, `dossier/` | Frontend application/race tests; `tests/test_discovery.py` |
| API routes and feature boundaries | `app/backend/main.py` | Hosted-mode, auth and API contract tests |
| Film catalogue providers | `discovery.py`, `tmdb_discovery.py` in the backend | Discovery/TMDb tests |
| Reviews and public video context | Backend `criticism.py`, `video_sources.py`; frontend `criticism/`, `videos/` | Criticism/video-source tests |
| Deep Study generation and checks | Backend `study_service.py`, `evidence.py`, `packet_quality.py`, `public_study.py` | Study/evidence/quality tests |
| Streamed progress | Backend `research_stream.py`, `study_observability.py`; frontend `study/` | Stream/observability and frontend progress tests |
| Accounts, settings and quotas | Backend `auth.py`, `settings.py`, `quota.py`; browser account adapters | Auth/settings/quota tests and SQL migrations |
| Private library retrieval | Backend `library.py`, `library_index.py` | Library/index tests |
| Local clip analysis | Backend `analysis_pipeline.py`, `algorithms/`; frontend `analysis/` | Analysis frontend tests; local clip acceptance |
| Local or hosted frontend build | `tools/frontend/` | Bundle, developer-tool and frontend-CI tests |
| Production release | `tools/release/`, `infra/vps/`, `.github/workflows/vps-release.yml` | Release-protocol/VPS tests; [Operations](OPERATIONS.md) |

The backend files remain at their existing import paths. Their names above are relative to
`app/backend/`; frontend feature folders are relative to `app/web/src/`.

## Daily commands

Run these from the repository root after following [Setup](SETUP.md):

| Need | Command |
|---|---|
| Install locked frontend dependencies | `npm ci --include=dev --ignore-scripts` |
| Check TypeScript | `npm run typecheck` |
| Compile scripts for the local API server | `npm run build:local` |
| Open a hosted-style local preview | `npm run preview` then visit `http://127.0.0.1:4173/` |
| Use another preview port | `PORT=4199 npm run preview` |
| Run the full local edition instead | `npm run build:local` then `uv run firstroll` |
| Test the frontend | `npm run test:web` |
| Test Python code | `uv run pytest -q` (defaults to `tests/`) |
| Build the static frontend | `FIRSTROLL_API_BASE=https://api.firstroll.app npm run build` |
| Test that minified build | `FIRSTROLL_TEST_APP=dist/assets/app.js npm run test:web` |

`npm run preview` compiles first, then explicitly enables frontend serving and binds only to
loopback. If the port is already occupied, it fails: identify the old process before stopping
it. An API health response alone does not prove the frontend is running. No command above
approves a production release. Real provider calls may cost money if configured and invoked.

## Frontend tools

- `tools/frontend/build.cjs`: the shared TypeScript compiler/bundler for local, Docker and hosted
  builds. It calculates the repository root independently of the caller's working directory.
- `tools/frontend/build.sh`: locked dependencies, hosted configuration and `dist/` assembly.
- `tools/frontend/preview.sh`: hosted-mode loopback launch; prefer `npm run preview` so assets
  are compiled first. It requires the Python environment described in Setup.
- `tools/frontend/check-responsiveness.cjs`: optional historical synthetic benchmark. It expects
  a pre-migration baseline with committed JavaScript assets and a separately provisioned browser
  toolchain; it is not part of everyday tests or a general mobile visual test.

These replace the former `tools/frontend-build.cjs`, `tools/build_web.sh`,
`tools/preview_hosted_web.sh` and `tools/check_web_responsiveness.cjs` paths. Prefer the stable
npm commands in personal scripts. CI, Docker, tests and current documentation use the new paths.

## Rules for future work

1. Keep a feature's controller, types, rendering and focused tests together in the existing
   feature structure. Share a helper only when it has more than one real consumer.
2. Change source, not `generated/` or `dist/`. Do not move legacy algorithm data independently
   of the code that loads it; those relative paths need a separate tested migration.
3. Keep Python tests under `tests/`, browser tests under `tests/web/` and fixtures synthetic.
4. Add development tooling to `tools/frontend/` or `tools/release/` according to responsibility.
5. Use a short-lived branch and a reviewed, green PR. Merging and production approval are
   separate steps; never use a cleanup task to bypass the release gate.

## Deliberately deferred

The largest remaining structural issue is `app/backend/main.py`: it combines route definitions,
service wiring and boundary checks. Extracting routers with explicit dependencies would help,
but moving security-sensitive routes alongside this tooling change would make verification
harder. Split it in a dedicated follow-up with route/auth contract tests. Likewise, keep
legacy algorithm modernisation and the separate mobile/monochrome PRs outside this change.

For a deeper frontend walkthrough see [Frontend guide](FRONTEND_GUIDE.md); for runtime topology
see [Architecture](ARCHITECTURE.md). This guide is a map of the code, not a claim that all
technical debt is resolved.
