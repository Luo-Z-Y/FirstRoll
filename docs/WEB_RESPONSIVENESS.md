# Web Responsiveness

**Checkpoint:** 12 September 2026 — local candidate, not a live deployment measurement.

This first latency pass removes avoidable blocking and obsolete UI work without shortening evidence
collection or changing model budgets. It does not claim faster provider responses or faster essays.

## Changes

- Async reception and criticism handlers dispatch synchronous catalogue, status and cache reads
  through Starlette's existing worker pool. Library upload/rebuild response metadata does the same.
- Hosted SSE token verification and platform-key configuration checks also use that pool. Verification
  still precedes run creation, evidence preparation, quota reservation and generation. No successful
  authentication decision is cached, and the result request still authenticates independently.
- A dossier's browser requests share its lifetime. Closing it, choosing another film or starting a
  search aborts its detail, reception, video and criticism fetches. Identity/reference checks also
  reject responses already received before cancellation, including delayed errors and focus changes.
- Deep Study establishes its busy state and **Stop waiting** action before awaiting authentication.
  Repeated clicks cannot start overlapping studies. Cancellation during authentication prevents a
  later study POST; authentication failures use the existing actionable error UI.
- The static build minifies `app.js` and `styles.css` with the already-locked esbuild dependency.
  Classic-script globals, fixed release filenames, cache revalidation and auth bundles are retained.
  The local source-served edition remains readable and unminified.

These are implementation-level scheduling and ownership fixes to the existing latest-selection,
authentication, evidence and release contracts. They introduce no new cache, persistent schema,
service boundary, provider acquisition stage or Agent lifecycle. The dossier controller is browser
request bookkeeping only and never enters the session snapshot or backend result store.

## Acceptance evidence

### Deterministic checks

- 588 repository tests passed in an isolated copy of tracked source, without the developer's private
  runtime. This includes 34 same-ASGI-loop concurrency tests and a Python wrapper for 27 executable
  JavaScript request/race tests.
- Each concurrency test keeps a synthetic blocking call held by a thread event until `/api/health`
  completes on the **same event loop**. A separate watchdog makes an event-loop stall fail rather than
  disguising it as a slow but successful request. These are ordering/concurrency checks, not load SLOs.
- The 27 JavaScript tests also passed against the minified production build. Their fake transport
  deliberately ignores abort signals to exercise stale-response protection independently of fetch
  cancellation. Unrelated DOM startup/rendering is stubbed in these unit tests.
- Locked, lifecycle-script-disabled frontend build, scoped Ruff, JavaScript/shell syntax and
  `git diff --check` passed. The shell's globally selected Ruff command was unavailable; the installed
  `.venv/bin/ruff` passed instead.

Measured asset bytes against baseline `40577ca534a4eade0df07c9da015e21b6c2ad06b`:

| Asset | Baseline shipped bytes | Candidate bytes | Baseline gzip | Candidate gzip |
|---|---:|---:|---:|---:|
| `app.js` | 154,709 | 115,716 | 36,319 | 31,176 |
| `styles.css` | 95,119 | 80,486 | 17,000 | 15,733 |

Together these assets are 21.5% smaller uncompressed and 12.0% smaller with local deterministic gzip.
These are file-size comparisons, not measurements of Azure transfer encoding or time-to-interactive.

### Browser evidence

`tools/check_web_responsiveness.cjs` exercises the real page and generated candidate assets in a fresh
Chrome context. It fulfils synthetic API responses locally, blocks external page HTTP requests
(including fonts) and removes speculative preconnect/DNS hints from served HTML. This is not an
OS-level network sandbox. It starts no backend and reads no existing browser profile, book, credential
or study cache.

Chrome 152 with four-times CPU throttling was tested at 390px and 1440px, with twenty interactions per
variant/viewport. Under a deliberately injected 500 ms authentication delay, median click-to-busy
mutation fell from approximately **502 ms to 0.4–0.8 ms**. The candidate's two-animation-frame paint
proxy was approximately **27–28 ms**, compared with **511 ms** before. The proxy is not INP or a real paint
instrumentation result. All forty candidate interactions could cancel before authentication resolved
and sent **zero mocked study POSTs**; the baseline had already sent forty by the time busy appeared.

Both viewports had zero uncaught page errors or horizontal overflow. The diagnostic records the
baseline revision, candidate asset SHA-256 values, browser version, timing summaries and its explicit
synthetic limitation in the [retained report](../evals/results/web-responsiveness-2026-09-12.json).
No authenticated live session, real provider or model was contacted.

### Perceptual review and architecture gate

The candidate's full-page 390px and 1440px screenshots were inspected separately from the assertions.
The busy message and cancellation control remain visible in both layouts; long catalogue titles
still wrap tightly in the existing desktop selected-edition card. This is not a full accessibility,
real-font, cross-browser or real-content visual acceptance run.

Architecture was reviewed against `docs/ARCHITECTURE.md`; the documented topology, evidence and
request contracts are preserved. No Archify source changed. The baseline repository contains neither
typed `docs/architecture/` sources nor `docs/ARCHITECTURE_ATLAS.md`, and no Archify executable is
available here. No Archify validate, deliver or visual-check result is claimed. Existing Markdown
architecture prose is reconciled; introducing typed diagrams is not part of this internal refactor.

## Reproduce without paid calls

The focused regression suite needs the existing Python development environment and Node 22:

```bash
uv run pytest -q tests/test_api_responsiveness.py tests/test_web_responsiveness.py
node --test tests/web/responsiveness.test.cjs
FIRSTROLL_API_BASE=https://firstroll.example.com npm run build
FIRSTROLL_TEST_APP=dist/assets/app.js node --test tests/web/responsiveness.test.cjs
```

For the optional browser diagnostic, install the pinned development-only tool into a temporary
folder, not the application dependency graph. Google Chrome must already be installed. Installation
contacts npm; the diagnostic itself fulfils or blocks every page HTTP request:

```bash
browser_tools=$(mktemp -d)
npm --prefix "$browser_tools" install --ignore-scripts --no-audit --no-fund \
  --package-lock=false playwright@1.58.2
NODE_PATH="$browser_tools/node_modules" node tools/check_web_responsiveness.cjs \
  40577ca534a4eade0df07c9da015e21b6c2ad06b
```

The diagnostic requires the preceding `dist` build and baseline Git object. It writes synthetic
screenshots and a hash-bound JSON report into a fresh temporary directory, printed at completion.
Run the complete Python suite from a clean temporary source copy when the working tree contains a
populated private runtime; the focused fixtures above replace all services with fakes.

## Limits and next work

1. Real discovery, authentication, caption acquisition and model transport can still be slow. Supabase
   token readiness still waits for initial account-data hydration; this change makes that wait visible
   and cancellable rather than changing authentication/account sequencing.
2. Browser abort cannot reliably stop an already-started synchronous backend/provider call. Quota may
   still be consumed. No automatic retry, refund, new call budget or backend cancellation guarantee
   has been added.
3. Starlette's worker pool is finite and shared. These tests do not prove responsiveness under pool
   saturation. Admission control would require a separately reviewed design, not just more workers:
   hosted research results are still process-local.
4. Local clip analysis still runs synchronously on the API loop, and its hidden browser analysis
   panels still render eagerly. Moving analysis to a bounded serial worker must account for shared
   output filenames/model state before enabling concurrent work.
5. Next, profile public search → shelf → dossier → reception with representative identities and
   authorised provider access. Prioritise repeated Wikidata detail enrichment, redundant TMDb shelf
   work, captions delaying video-card display, and unnecessary shelf/player DOM replacement. Any
   cache, provider-flow or material request-sequence change must first satisfy the architecture gate.
6. Live rollout and any real-provider/model timing or load test remain separate, owner-approved work.
