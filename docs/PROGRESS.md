# FirstRoll Project Progress

### 13 August 2026 — Film viewing resources

Delivered:

1. Added a **Watch & study** dossier section with local progress feedback and embedded
   public-video cards.
2. Added official YouTube Data API search with a write-only API-key entry in Settings and
   privacy-enhanced YouTube embeds.
3. Added key-free Bilibili retrieval through its server-rendered public search page after its
   anonymous JSON endpoint returned HTTP 412 risk control.
4. Added film-title, original-title, year, director and film-context relevance checks to
   reject ambiguous namesakes, music and games.
5. Restricted provider requests, redirects, thumbnails and embed URLs to known HTTPS hosts,
   with timeouts, response limits and bounded result counts.
6. Kept videos as attributed viewing resources rather than automatically treating their
   contents as verified evidence or sending them to DeepSeek.

Acceptance evidence:

- live *Memoria* Bilibili check returns three film-specific results after rejecting unrelated
  uses of the title;
- targeted video, settings and discovery tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

This file is the durable implementation ledger for FirstRoll. Update it whenever a
milestone changes state, a meaningful feature is completed, or verification evidence
changes.

Status vocabulary:

- **Complete** — implemented and verified against its current acceptance criteria.
- **In progress** — active implementation exists, but required work remains.
- **Planned** — accepted scope, not yet implemented.
- **Blocked** — cannot progress without a named decision, dependency or permission.

## Current Snapshot

**Last updated:** 13 August 2026

**Release stage:** local working prototype

**Primary development URL:** `http://127.0.0.1:8000`
**Automated verification:** 50 tests passing

| Area | Status | Current evidence |
|---|---|---|
| Film discovery | Complete | Wikidata search by title, year and director; Wikipedia context and source links |
| Public video resources | Complete | Film-matched Bilibili embeds plus optional official YouTube Data API search |
| Product navigation | Complete | Discover and Analyse modes; Study consolidated into Discover |
| Local settings | Complete | Write-only connector credentials plus local add, remove and index controls for the private library |
| Private library catalogue | Complete | Seven existing film-study PDFs retained; managed uploads and non-destructive removal; paths and content withheld from public APIs |
| PDF ingestion | Complete | Token-aware page chunks, overlap, section hints, language and stable IDs |
| Local embeddings | Complete | 4,381 of 4,381 chunks embedded with a local multilingual 384-dimension model |
| Hybrid retrieval | Complete | FTS5 + vector candidates, reciprocal-rank fusion and diversity selection |
| Query planning | Complete | User focus, craft taxonomy and attributed criticism generate subqueries |
| Douban adapter | Complete | Optional local MCP connection, title matching, review links and private cache |
| Research adapter | Complete | Crossref abstracts with local identity relevance checks and DOI attribution |
| Letterboxd adapter | Complete | Public-web IMDb identity resolution plus optional official OAuth retrieval |
| Guardian adapter | Complete | Public content-index matching and attributed article-body retrieval |
| Criticism structuring | Complete | Pydantic critic claims with missing-field preservation and evidence labels |
| Criticism source controls | Complete | Tabbed provider switcher; first selection fetches and later selections reuse the cached bundle |
| Evidence packet | Complete | Film record, theory and critic claims separated by explicit permitted uses |
| Deep Study schema | Complete | Critic, theory, hypothesis, mechanism, alternative, verification and confidence fields |
| Quality control | Complete | Deterministic gate, citation checks and at most one bounded repair call |
| Evidence-layered UI | Complete | Quality status, layered sections, retrieval rationale and expandable excerpts |
| Clip analysis | Complete | Scene/shot metrics, shot scale, colour, objects and JSON/CSV export |
| Clip evidence in Deep Study | Planned | Current study generation does not consume measured clip observations or timecodes |
| Creator primary sources | Planned | No automated interview or production-record ingestion yet |
| Persistent projects | Planned | Film, clip, study and note sessions are not retained as reusable projects |

## Latest Completed Milestone

### 11 August 2026 — Architecture map with implementation stack

Delivered:

1. Reworked the system diagram into five explicit responsibility layers.
2. Added the shared runtime and specialised technologies to each architectural component.
3. Separated public inputs, private inputs, local processing and external synthesis visually.
4. Added a compact layer-to-stack reference beneath the diagram.

Acceptance evidence:

- every named technology maps to the current project configuration or implementation;
- Mermaid uses GitHub-compatible flowchart, subgraph, class and labelled-edge syntax;
- the local/private boundary and planned clip-evidence bridge remain explicit.

### 11 August 2026 — Simplified discovery landing page

Delivered:

1. Removed the research-principle card from the discovery hero.
2. Removed the empty-state film-dossier explainer and its three descriptive panels.
3. Removed the redundant hero guidance sentence and tightened the surrounding layout.

Acceptance evidence:

- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm clean initial, search-results and narrow-width layouts.

### 11 August 2026 — Douban translated-title identity repair

Delivered:

1. Reproduced the apparent MCP failure for *Memoria* and traced the nested task-group error
   to FirstRoll's film identity guard, not to Douban review availability.
2. Prefer Wikidata's IMDb identifier for Douban film search, with exact-year validation of
   the unique provider result.
3. Retained the stricter title/year scorer when no stable external identifier is available
   or the provider returns ambiguous candidates.
4. Flatten nested MCP exception groups so future failures expose the actionable underlying
   diagnostic.
5. Added regression coverage for translated-title acceptance, same-year ambiguity and
   task-group error unwrapping.

Acceptance evidence:

- live *Memoria* check resolves Douban subject `30137576` and retrieves eight attributed
  long-form reviews;
- scoped criticism tests: 23 passed;
- scoped Ruff checks pass.

### 11 August 2026 — Secondary-evidence technical documentation

Delivered:

1. Documented the complete Crossref, Douban, Letterboxd and Guardian acquisition pipelines.
2. Recorded provider-specific identity resolution, confidence thresholds, result limits,
   attribution fields, response-size limits, redirect restrictions and failure behaviour.
3. Added the *Memoria* translated-title diagnosis as a concrete explanation of IMDb-based
   Douban resolution and MCP task-group error unwrapping.
4. Distinguished Letterboxd public-page acquisition from its official OAuth API without a
   hidden fallback between them.
5. Documented the raw-evidence cache, stable source-ID relationship and Pydantic boundary
   that precede optional DeepSeek claim structuring.

### 11 August 2026 — Source documentation and Letterboxd identity repair

Delivered:

1. Documented the Wikidata, Wikipedia, Crossref, Douban, Letterboxd and Guardian
   acquisition paths in the README.
2. Recorded the raw-retrieval, private-cache and separate DeepSeek-structuring boundary.
3. Replaced ambiguous Letterboxd slug-first matching with verified IMDb-ID resolution when
   Wikidata supplies an IMDb identifier.
4. Added a JSON-LD director guard for title/year fallback pages.
5. Added regressions for same-title, same-year films with different directors.

Acceptance evidence:

- live *An Unfinished Film* check resolves Lou Ye's canonical Letterboxd slug and retrieves
  four attributed reviews;
- automated tests: 43 passed;
- scoped Ruff, frontend JavaScript syntax and repository whitespace checks pass.

### 11 August 2026 — Animated monochrome identity

Delivered:

1. Replaced the framed reel symbol with a minimal black-and-white film-roll mark.
2. Animated the film strip to extend from the roll, pause and retract.
3. Applied the same identity to the discovery and local Settings headers.
4. Added a compact SVG favicon and a static reduced-motion state.
5. Slimmed the cylinder and left a short film tab visible in the resting state.

Acceptance evidence:

- SVG validity, frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm the animation cycle, favicon response, Settings header and narrow layout;
- the stylesheet provides a static, fully extended mark when reduced motion is preferred.

### 11 August 2026 — Local recent-search history

Delivered:

1. Removed example values from the film title, year and director fields.
2. Replaced the three suggested films with the five most recent searches.
3. Stored recent searches locally, deduplicated them and kept the newest search first.
4. Made each recent item restore the full title, year and director query and search again.

Acceptance evidence:

- automated tests: 43 passed;
- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm empty, persisted, deduplicated and narrow-width states.

### 11 August 2026 — Criticism source switcher

Delivered:

1. Replaced the separate provider actions with a compact, accessible source tab switcher.
2. Made the first selection of an unloaded source initialise its fetch and structuring flow.
3. Made later selections switch instantly to the cached provider bundle without refetching.
4. Moved refresh controls into the active source panel and marked active and loaded states.
5. Prevented slower background requests from replacing a source selected in the meantime.

Acceptance evidence:

- automated tests: 40 passed;
- frontend JavaScript syntax, scoped Ruff checks and repository whitespace checks pass;
- browser checks confirm cached Douban and Letterboxd switching sends no new request;
- desktop and narrow-width layouts have no horizontal overflow or console errors.

### 11 August 2026 — Settings-based private library management

Delivered:

1. Added a Study library panel to Settings with the current private catalogue and index state.
2. Added local catalogue uploads for PDF, EPUB, Markdown and text documents with a 500 MB
   limit, while clearly identifying PDF as the current indexed format.
3. Added non-destructive removal that unregisters a document without deleting its source file.
4. Added an explicit local search-index rebuild action and visible rebuild recommendation.
5. Preserved all seven books already registered on the development machine.
6. Kept file paths, document contents, uploaded copies and derived index data outside public
   responses and source control.
7. Reduced Settings guidance copy to essential labels, privacy cues and index limitations.

Acceptance evidence:

- automated tests: 40 passed, including add, remove, validation and rebuild flows;
- frontend JavaScript syntax, scoped Ruff checks and repository whitespace checks pass;
- live catalogue metadata still reports seven registered books after the change;
- desktop and narrow-width browser checks show the complete catalogue with no console errors.

### 11 August 2026 — Layered README architecture map

Delivered:

1. Reorganised the system map into five readable layers from user experience to outputs.
2. Simplified service labels while retaining the implemented discovery, criticism,
   retrieval, synthesis, quality-control and clip-analysis flows.
3. Strengthened the visual distinction between local/private processing, provenance-bearing
   evidence and external services.
4. Kept the clip-to-study connection visibly marked as planned work.

Acceptance evidence:

- Mermaid block uses GitHub-compatible flowchart, subgraph and class syntax;
- every architecture node maps to an implemented service, evidence type or documented plan;
- the privacy and external-transmission boundary is stated directly beneath the graph.

### 9 August 2026 — Official Letterboxd API adapter

Delivered:

1. Added write-only Client ID and Client Secret fields to the local Settings registry.
2. Implemented official OAuth client-credentials authentication with clear rejection errors.
3. Added official film search and popularity-ranked public review retrieval.
4. Preserved member attribution, log-entry ID, rating, language and source links.
5. Stored criticism bundles per provider so Letterboxd and Douban claims can coexist.
6. Added a Letterboxd action to film dossiers and combined both providers in Deep Study.
7. Added transport-isolated tests with no scraping or unofficial fallback.

Acceptance evidence:

- automated tests: 29 passed;
- scoped Ruff checks: passed;
- frontend JavaScript syntax and repository whitespace checks: passed;
- live Settings API: Letterboxd exposes separate masked Client ID and Client Secret fields;
- live unconfigured request: returns a specific incomplete-credentials response without making
  an unofficial fallback request.

### 7 August 2026 — README architecture map

Delivered:

1. Expanded the README Mermaid diagram into a boundary-aware system architecture map.
2. Distinguished external services from local/private processing and storage.
3. Documented the film-discovery, criticism, hybrid-retrieval, evidence-packet,
   quality-repair and clip-analysis data flows.
4. Marked the clip-to-study connection as planned rather than implemented.

Acceptance evidence:

- Mermaid block uses GitHub-compatible flowchart and subgraph syntax;
- every implemented data flow corresponds to a current FirstRoll service;
- privacy and external-transmission boundaries are explained directly below the graph.

### 7 August 2026 — Continuous essay presentation

Delivered:

1. Kept the structured evidence sections as an internal generation and validation model.
2. Replaced the visible two-column evidence cards with one continuous critical essay.
3. Joined critic reports, theory, hypotheses, mechanisms and alternative readings into
   successive prose paragraphs with compact inline citations.
4. Moved viewing verification into a collapsed post-essay checklist and retained
   expandable retrieval and source evidence.
5. Tuned the generation prompt so internal sections advance one argument without
   repeating the same thesis.
6. Switched the default synthesis model from `deepseek-v4-flash` to
   `deepseek-v4-pro`; Flash remains available through `DEEPSEEK_MODEL`.

Acceptance criteria:

- [x] continuous article renders without visible evidence-card segmentation;
- [x] theory and critic citations remain visible within the relevant paragraph;
- [x] quality status, creator-intent boundary and source evidence remain inspectable;
- [x] automated tests and frontend syntax checks pass;
- [x] live browser generation uses `deepseek-v4-pro` and renders as one article.

### 6 August 2026 — Deep Study display compatibility fix

Delivered:

1. Added versioned frontend asset URLs so an updated stylesheet cannot load with stale
   study-rendering JavaScript.
2. Disabled HTML shell caching for the local application entry point.
3. Added a backward-compatible renderer for legacy sections that contain `analysis`
   instead of the newer layered evidence fields.
4. Restored explicit text styling for legacy study paragraphs.

Acceptance evidence:

- legacy and layered section fixtures both display substantive analysis text;
- frontend JavaScript syntax check: passed;
- local browser check: study analysis layers render above verification tasks.

### 6 August 2026 — Hybrid retrieval and evidence-quality pipeline

Delivered:

1. Replaced character-count PDF chunks with token-aware, overlapping page chunks.
2. Added stable content IDs and index schema metadata.
3. Added local multilingual embeddings and private SQLite vector storage.
4. Added focus- and criticism-aware query planning.
5. Added FTS/vector reciprocal-rank fusion and diversity constraints.
6. Added typed evidence packets that constrain permitted claim types.
7. Expanded Deep Study into explicit evidence and inference layers.
8. Added deterministic specificity, calibration and citation checks.
9. Added one bounded DeepSeek audit/repair attempt.
10. Added visible quality state, source rationale and full evidence excerpts to the UI.

Acceptance evidence:

- private index: 7 documents, 4,381 cited chunks and 4,381 local vectors;
- automated tests: 22 passed;
- scoped Ruff checks: passed;
- frontend JavaScript syntax check: passed;
- `git diff --check`: passed;
- live API test: hybrid retrieval used film focus and cached criticism;
- live browser test: evidence layers, quality status and citations rendered correctly;
- safety test: an overconfident study remained labelled insufficient evidence after its
  single repair pass.

### 7 August 2026 — Actionable Douban diagnostics

Delivered:

1. Replaced the ambiguous empty-review error with separate authentication, genuinely empty,
   incomplete-row and connector-schema diagnostics.
2. Added safe, length-limited provider-response previews for otherwise unknown formats.
3. Redacted credential-like values and links from diagnostic previews.
4. Added regression tests for each diagnostic path.

Acceptance evidence:

- automated tests: 26 passed;
- scoped Ruff checks: passed;
- `git diff --check`: passed;
- live connector test for *Syndromes and a Century*: correct Douban film match, one
  attributed review summary and four structured critical claims returned.

### 7 August 2026 — Multiline Douban review parsing

Delivered:

1. Reconstructed logical review rows when Douban summaries contain physical line breaks.
2. Preserved multiline review prose rather than rejecting partial Markdown-table lines.
3. Tolerated unescaped pipe characters inside summary text while retaining the final review ID.
4. Added a regression fixture based on the malformed *Kaili Blues* response shape.

Acceptance evidence:

- live *Kaili Blues* response: eight reviews reconstructed from a 280-line table and eight
  attributed critical claims returned;
- focused parser tests and Ruff checks: passed.

## Next Milestone

### Clip-to-study evidence bridge — Planned

Objective: allow Deep Study to make bounded, timecoded formal observations from a
user-provided clip while preserving the current evidence taxonomy.

Proposed acceptance criteria:

- [ ] Define typed `film_observed` evidence for scenes, shots and time ranges.
- [ ] Persist scene and shot identifiers throughout the analysis response.
- [ ] Expose deterministic tools for scene metrics and comparisons.
- [ ] Select relevant clip evidence from the user's study focus.
- [ ] Permit observed claims only when supported by a scene or timecode citation.
- [ ] Keep whole-film extrapolations separate from clip-supported observations.
- [ ] Display book, critic and clip citations as distinct evidence classes.
- [ ] Add tests for citation validity, unsupported extrapolation and missing clip data.
- [ ] Add a browser workflow from Analyse results back into the film dossier.

## Subsequent Priorities

1. **Creator primary-source layer** — ingest attributed interviews, commentaries and
   production records; distinguish direct quotation, paraphrase and inference.
2. **Persistent film projects** — retain discovery records, private clips, analyses,
   notes, criticism and generated studies under a local project ID.
3. **Evaluation suite** — measure retrieval relevance, citation accuracy, unsupported
   claims, appropriate abstention, repair effectiveness, latency and DeepSeek cost.
4. **Retrieval performance** — keep the embedding model warm or load it outside the
   request path so the first dossier opens faster.
5. **Legacy algorithm hardening** — remove inherited lint debt, reduce fallback ambiguity
   and add representative video fixtures.

## Known Risks and Constraints

- Douban MCP is unofficial and depends on an external page structure and access policy.
- Review summaries are secondary copyrighted material; retain attribution and source links.
- User-supplied books and clips must remain local and should not be committed to Git.
- DeepSeek sees only the selected evidence packet, but this still transmits excerpt text to
  an external model provider after the user chooses Generate study.
- A strong formal reading cannot be confirmed without viewing evidence.
- Creator intention must not be inferred from style, criticism or theory alone.
- The local multilingual model adds a first-load delay and a sizeable local download.
- Inherited computer-vision dependencies may behave differently across operating systems.

## Maintenance Rule

For each meaningful implementation change:

1. update the relevant row in **Current Snapshot**;
2. add a dated milestone entry when a coherent feature set completes;
3. record automated and live acceptance evidence;
4. move the next actionable milestone into **Next Milestone**;
5. keep limitations explicit rather than silently removing unfinished scope.
