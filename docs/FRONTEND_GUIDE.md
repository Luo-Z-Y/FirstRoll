# Understanding the FirstRoll Frontend

This guide describes the incremental refactor through 2 October 2026. It changes how we
organise and build the source, not the product's layout. The public v219 deployment has
not been changed by this work.

## Start here

The original `app/web/app.js` was 3,843 lines. It is now 2,410 lines (2,597 after the first
checkpoint): still a transitional coordinator, but clip analysis, discovery views and shared
responsibilities have their own files.
Splitting code is useful when each file has a clear responsibility, not merely fewer lines.

| File under `app/web/` | Responsibility | Read when you want to… |
|---|---|---|
| `index.html` | Page structure and existing script URLs | Find a button or panel |
| `src/main.ts` | Build entry point | See where compilation starts |
| `app.js` | DOM references, navigation, discovery state and request ownership | Follow a search or dossier request |
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
| `src/analysis/controller.js` | Private clip state, upload, rendering and exports | Follow the Analyse feature |
| `auth.js`, `local-auth.js`, `integrations.js` | Existing account/settings adapters | Follow sign-in or settings |

Suggested reading order: `format.ts` → its tests → `types.ts` → `progress.ts` → `main.ts`
→ `app.js`'s `setup()` and one handler. Do not try to memorise the entire coordinator.

## Follow the discovery boundary

`renderFilmArchive()` still updates selection/session state in `app.js`, then asks
`filmArchiveMarkup()` for HTML. That pure view calls `directorShelfFilms()` to select the
first twelve distinct displayable records, then renders the shelf. No view reads global
state, fetches records, changes focus or writes storage. Existing `data-*` attributes keep
event delegation working; request IDs, timeouts, cancellation and poster enrichment remain
in the coordinator.

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

`strict: true` currently applies to `src/**/*.ts`, **not** the remaining JavaScript
controllers. A typed function called from unchecked JavaScript can still receive bad data.
Provider JSON is untrusted regardless of its declared interface. The progress module keeps
its allow-lists, run-ID checks, sequence checks and terminal-event checks at runtime.
TypeScript does not replace those checks, API authentication, tests or safe HTML escaping.
The existing clip heuristics are still proxies, not verified object recognition.

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
FIRSTROLL_TEST_APP=dist/assets/app.js node --test tests/web/responsiveness.test.cjs
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
- CI installs locked dependencies, checks/builds TypeScript, runs tests and builds Docker.

The current race harness overrides top-level handlers, so the compiler deliberately keeps
function identifiers stable. This is transitional test infrastructure, not a public module API.
Replace it with injected controllers before switching the whole entry to an isolated IIFE.

## Remaining work, in order

1. Split dossier/video/criticism controllers while preserving request ownership and abort rules.
2. Move Deep Study orchestration into a typed controller with the existing safety tests.
3. Type DOM references, account and settings adapters; shrink `app.js` to startup wiring.
4. Consider React/Next.js only as a separate architecture decision with a concrete need.

This milestone does not claim all frontend code is typed or every feature is fully modular.
Preserving a working application is more useful than renaming a large file to `.ts` and
suppressing its errors.
