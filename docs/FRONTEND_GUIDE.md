# Understanding the FirstRoll Frontend

The modularisation milestone is complete as of 2 October 2026. It changes how we organise
and build the source, not the product's layout. The public deployment is unchanged.

## Start here

The original `app/web/app.js` was 3,843 lines. It is now **58 lines**: a composition root,
meaning the place that creates the feature modules and connects them. Every module under
`src/` is at most 500 lines.
Splitting code is useful when each file has a clear responsibility, not merely fewer lines.

| File under `app/web/` | Responsibility | Read when you want to… |
|---|---|---|
| `index.html` | Page structure and existing script URLs | Find a button or panel |
| `src/main.ts` | DOM-ready startup | See when the application starts |
| `app.js` | Composition root | See how feature factories connect |
| `src/context.js` | Per-application state, config and DOM references | Find a button reference or request state |
| `src/bootstrap.js` | Event registration | Follow a click into a controller |
| `src/navigation/controller.ts`, `types.ts` | Typed theme/product navigation and narrow state contract | Change navigation behaviour |
| `src/accounts/controller.js` | Account-facing UI and saved films | Trace account state into controls |
| `src/session/controller.js` | Bounded per-tab snapshots | Follow storage and restoration |
| `src/discovery/controller.js` | Search, selection and shelf requests | Follow cancellation and stale-response checks |
| `src/discovery/recent.ts`, `shelf.js` | Typed recent queries; shelf DOM state still JavaScript | Follow storage and shelf states |
| `src/dossier/controller.js`, `view.js` | Dossier requests/events and presentation | Follow a film dossier |
| `src/videos/controller.js`, `views.js` | Video requests/categories and cards | Follow video results |
| `src/criticism/controller.js`, `views.js` | Provider requests/tabs and rendering | Follow critical perspectives |
| `src/study/controller.js`, `views.js` | Study lifecycle and output | Follow authorisation, streaming and evidence |
| `src/discovery/types.ts` | Film summary shape used for display | Understand required IDs and optional metadata |
| `src/discovery/films.ts` | De-duplication, displayable titles and the twelve-film cap | Follow how records become shelf items |
| `src/discovery/views.ts` | Film choices, selected edition and shelf HTML | Change discovery markup without touching requests |
| `src/shared/crew.ts` | Crew-name filtering and display | Understand why raw IDs/scraped markup are hidden |
| `src/shared/format.ts` | Pure time, size and film-year formatting | Learn a small TypeScript function |
| `src/shared/html.ts` | HTML escaping and URL/embed allow-lists | Understand safe rendering of provider data |
| `src/api/errors.ts` | API error messages and HTTP fallback | Understand failed responses |
| `src/study/progress.ts` | Typed, runtime-validated progress events and their display | Follow streaming Deep Study progress |
| `src/analysis/types.ts` | RGB, frame, shot and scene shapes | Understand domain types |
| `src/analysis/math.ts` | Pure numerical helpers | Learn independently testable functions |
| `src/analysis/heuristics.ts` | Existing colour/texture/shot/scene heuristics | Understand local analysis calculations |
| `src/analysis/controller.ts`, `view.ts` | Typed private clip state/upload/export and rendering | Follow the Analyse feature |
| `src/analysis/dom.ts`, `response.ts` | DOM contract and runtime response validation | See the difference between types and validation |
| `src/shared/ui.ts` | Typed focus, progress markup and API-base helpers | Follow accessible focus scheduling |
| `auth.js`, `local-auth.js`, `integrations.js` | Existing account/settings adapters | Follow sign-in or settings |

For TypeScript basics, read `format.ts` → its tests → `types.ts` → `progress.ts`.
For the app, read `main.ts` → `app.js` → `context.js` → `bootstrap.js` → one handler.

## How the pieces connect

`createApplication()` creates a fresh context and constructs feature factories. A factory
is an ordinary function returning named handlers. Construction does not fetch data or register
feature listeners; `start()` performs setup once. Two applications get separate state/caches.
Features within one app intentionally share discovery state, preserving request IDs, abort
controllers and selected-film guards. Clip state remains private to its own controller.

The `services` object holds the assembled features. Controllers declare callbacks such as:

```js
const persistDiscoverySession = (...args) =>
  services.session.persistDiscoverySession(...args);
```

This **lazy delegate** looks up the session handler when called, after construction finishes.
It permits cross-feature calls without circular imports. Do not call these delegates during
construction before their target exists. This is dependency wiring, not a new framework.
Tests may inject named handler replacements through `createApplication({ overrides })`;
production passes none, and URL parameters/runtime config never control them.

## Follow the discovery boundary

`bootstrap.js` connects the search form to `discovery/controller.js`, which owns fetching,
cancellation and stale-response checks. In `discovery/shelf.js`, `renderFilmArchive()`
updates archive state and delegates session persistence, then asks
`filmArchiveMarkup()` for HTML. That pure view calls `directorShelfFilms()` to select the
first twelve distinct displayable records, then renders the shelf. No view reads global
state, fetches records, changes focus or writes storage. Existing `data-*` attributes keep
event delegation working; request IDs, timeouts, cancellation and poster enrichment remain
in the discovery controller. `session/controller.js` saves a bounded film projection,
not complete reviews or dossiers.

`FilmSummary.id` is required because selection and de-duplication use identity, not title.
Posters, years and original titles are optional because real catalogue records can be
incomplete. `readonly` array parameters mean helpers cannot rearrange the caller's list.
The generic `uniqueFilms<T>` keeps extra fields on the caller's record type instead of
discarding them. These types describe expected inputs; existing runtime checks still apply.

## What TypeScript adds

JavaScript performs the work in the browser. TypeScript adds checks **before** that code
is shipped. For example:

```ts
function formatTime(seconds: number): string {
  // A number goes in; text comes out.
  return `${Math.round(seconds)} seconds`;
}
```

Calling this with a string from another checked TypeScript file is a compiler error.
An `interface` describes a data shape; a union such as `"Long" | "Medium" | "Close-Up"`
restricts permitted values. `RGB` is a three-number tuple rather than an arbitrary array.
`import type` is erased during compilation; it does not add a runtime library.

An `export` makes a function available to other modules. An `import` declares that
dependency explicitly. Pure helpers do not read the DOM, modify storage or call providers;
this makes them simpler to understand and test.

`createAnalysisController(refs)` is a factory: it receives references to UI elements and
returns named event handlers. Its clip state lives inside the factory instead of in the
discovery state object. This is encapsulation, not an additional framework.

### What TypeScript does not guarantee

`strict: true` applies to `src/**/*.ts`, including the analysis, navigation and recent-search
controllers, **not** the remaining JavaScript controllers. `app.d.ts` describes only startup.
A typed function called from unchecked JavaScript can still receive bad data.
Provider JSON is untrusted regardless of its declared interface. The progress module keeps
its allow-lists, run-ID checks, sequence checks and terminal-event checks at runtime.
TypeScript does not replace those checks, API authentication, tests or safe HTML escaping.
The existing clip heuristics are still proxies, not verified object recognition.

### The second migration: state, DOM and network boundaries

The analysis feature now uses TypeScript end to end within its controller and view.
`ClipState.meta: VideoMeta | null` expresses the period before a file is ready. Code must
check for metadata before reading it. `AnalysisRefs` distinguishes an input, video, canvas,
button and textarea; using `currentTime` on the file input is a compiler error.

`parseAnalysisResponse(value: unknown, ...)` validates nested scenes, shots, metrics, RGB
triples and labels before creating an `AnalysisResult`. It accepts the backend's genuine
`Unknown` shot scale and optional legacy top-level shots/outputs. It rejects invalid numbers,
missing nested arrays and malformed metadata. It does not prove that detector observations
are scientifically accurate. Extra unconsumed fields are not part of the presentation model.

Filenames and object labels are escaped in HTML; correct string types alone do not prevent
injection. Missing canvas contexts are handled safely instead of assuming every browser can draw.
Navigation uses closed theme/product-view choices, with runtime guards for storage and DOM values.
Recent searches decode JSON as `unknown`; the normalised query has title/year/director strings.

The JavaScript composition root still passes dependencies into these typed features. Its entire
dependency graph is not compiler-verified yet. Narrow contracts improve each migrated module
without concealing that remaining boundary behind `any` or disabling strict checks.

## Source versus generated output

```text
src/main.ts → imports app.js → imports feature modules
                         ↓ shared compiler (esbuild)
Local:  app/web/generated/app.js → FastAPI /assets/app.js
Hosted: dist/assets/app.js      → Caddy /assets/app.js
```

`tsc` checks types without emitting files. esbuild then strips types and bundles imports.
The output has no unresolved module imports, so the existing classic script tag and public
filename remain valid. Hosted output is minified; localhost output is readable. Auth has
its own existing bundle. Neither source changes nor local builds deploy production.

Generated directories are ignored by Git. Always edit source, never a generated bundle.
Docker also builds from source, so a stale developer bundle cannot enter the image.

## Daily development

From the repository root, using Node.js 22+:

```bash
npm ci --include=dev --ignore-scripts
npm run build:local
uv run firstroll
```

Open `http://127.0.0.1:8000`. After source edits, run `npm run build:local` and refresh.
There is no watch mode yet. FastAPI returns a helpful 503 if the bundle is absent; it
never serves the import-bearing coordinator as the application entry.

Before publishing:

```bash
npm run typecheck
npm run test:web
uv run pytest -q tests
FIRSTROLL_API_BASE=https://api.firstroll.example.com npm run build
FIRSTROLL_TEST_APP=dist/assets/app.js npm run test:web
git diff --check
```

The example hostname is intentionally not production; building does not call it.
The hosted build needs the existing public account configuration for an actual release.
Never put provider API keys into browser configuration.

## How we guard behaviour

- Eighteen module tests cover escaping, embed allow-lists, formatting, error fallback, chunked
  UTF-8 progress, invalid/cross-run events, analysis maths and independent controller state,
  plus duplicate/missing film data, the twelve-film limit, crew filtering, accessible
  choices, selected versus clickable cards, loading placeholders and archive markup.
- The original 27 executable request/race cases run against compiled source and the
  minified release bundle. Stale responses, cancellations and authorisation races must
  remain safe.
- Python tests cover the local compiled-asset route, its missing-build error and the Docker
  build-context contract. Existing source-smoke checks point at the relocated modules.
- Ten application cases cover inert construction/independent state, idempotent startup,
  DOM-ready boot, cross-feature rendering, bounded snapshots, stale shelf selection and
  acyclic/size-bounded modules, navigation/storage fallback, recent searches and scheduled focus.
- Six analysis cases cover runtime parsing, invalid nested data, upload/render/export, failure,
  safe HTML and keyboard view guards. The controller cases also run on the release bundle.
- One compile-only test checks deliberately invalid TypeScript usages. An unused
  `@ts-expect-error` in these test fixtures fails the test, detecting weakened contracts.
- All **62 frontend cases** pass against both compiled source and the minified hosted bundle.
  The **645-test repository suite** passes, including the frontend test wrapper.
- CI installs locked dependencies, checks/builds TypeScript and nested JavaScript, runs all
  frontend tests on the hosted bundle and builds Docker.

The race harness now constructs the real application with injected handlers rather than
redefining hoisted functions. The compiler preserves the composition-root name for VM tests.
Interactive visual acceptance was blocked by the preview client; local Docker was unavailable.
Mocked-DOM integration tests do not constitute visual acceptance. Deployment requires the
human production approval gate.

## Milestone complete; optional next improvements

The application now has explicit feature boundaries, a small composition root and executable
integration coverage. No further monolithic-controller extraction is required for this milestone.
Analysis, navigation, recent searches and shared UI helpers are now typed. Next are shared
application state/wiring, session/discovery, dossier/video/criticism, Deep Study orchestration
and account/settings adapters. Consider React/Next.js only as a separate decision with a need.

This milestone does not claim all frontend code is typed.
Preserving a working application is more useful than renaming a large file to `.ts` and
suppressing its errors.
