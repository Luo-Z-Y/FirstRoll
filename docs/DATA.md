# FirstRoll Data: Sources, Storage and HTTP API

**Last reconciled:** 1 October 2026 against commit `9d29263` · **API version:** `0.1.0`

This document owns three contracts: [data sources](#1-data-sources) (provider roles, selection
policy, attribution and licence boundaries), the [data model](#2-data-model) (every persisted or
transient record and its lifecycle) and the [HTTP API](#3-http-api-reference). The Deep Study
pipeline and evidence-packet budgets are in [Architecture](ARCHITECTURE.md), connector setup in
[Setup](SETUP.md), hosting and release in [Operations](OPERATIONS.md), and rationale in
[Decisions](DECISIONS.md).

---

## 1. Data sources

### Principles

- Identity, criticism and model input are separate layers. Technical access does not make a source
  reliable, redistributable or safe to send to a model; no model browses the web.
- Every provider has a bounded adapter: fixed HTTPS endpoints (Douban: a local stdio MCP process;
  public-page readers re-check the host after redirects), result limits, an identity check against
  the verified film and a normalised, attributed record. HTTP adapters set timeouts and most cap
  response size; Wikidata, Wikipedia and the Letterboxd API do not cap size.
- Providers fail independently; a failure never erases the film record or another provider's cache.
  Within a provider a malformed page is skipped, and the request fails only when nothing usable
  remains.
- Attribution and the canonical URL travel with every item. Where full-text reuse is not licensed,
  FirstRoll links to the source and quotes only within the applicable permission.
- Nothing reaches DeepSeek until the user requests claim structuring (local edition) or a Deep Study.
  Retrieved text is untrusted data, never instructions.

```text
verified film → provider search + identity match → attributed source + canonical URL
  → cached bundle, claim_status=pending (.firstroll/criticism)
  → optional DeepSeek structuring (local only) → Pydantic + source-ID check → claim_status=structured
```

### Source roles

| Source | Role | Credential | Edition | Licence and attribution boundary |
|---|---|---|---|---|
| TMDb API | Primary catalogue when configured: search, posters, synopsis, runtime, credits, IMDb/Wikidata IDs | `TMDB_BEARER_TOKEN` (Read Access Token) | Both | Shows "This product uses the TMDB API but is not endorsed or certified by TMDB."; free non-commercial use with attribution; commercial use needs separate TMDb review |
| Wikidata | Key-free fallback identity, crew, genre, country, IMDb ID, awards, related films | None | Both | CC0; labelled as an identity source, not evidence of intention |
| Wikipedia (English) | Fallback candidate search, overview, infobox crew reconciliation, poster | None | Both | CC BY-SA; article link and licence displayed; never merged into Wikidata or relabelled as FirstRoll analysis |
| Wikimedia Commons | Poster file named by Wikidata | None | Both | Check the individual file licence before any reuse |
| IMDb | Identity bridge only (title IDs from TMDb or Wikidata, used to reconcile Douban and Letterboxd) | None | Both | No IMDb API call and no IMDb page scraping; IMDb and OMDb rationale in [Decisions](DECISIONS.md) |
| Curated offline catalogue | Four demonstration films when Wikidata is unreachable | None | Both | First-party metadata; always labelled offline/degraded, never a live match |
| Crossref REST API | Matched scholarly abstracts with DOI links | None | Both | Abstract copyright may remain with publisher or author; bounded, attributed and linked |
| Douban MCP | Chinese-language review summaries and community score | Optional operator cookie (`DOUBAN_COOKIE`); never a visitor's | Both when installed | Unofficial; the connector's MIT licence covers its code, not the reviews |
| Letterboxd public web | Popular public reviews, aggregate score, poster fallback | None | Both | Unofficial public-page access; no login, session or member cookie |
| Letterboxd API | Popularity-ranked public reviews | `LETTERBOXD_CLIENT_ID`, `LETTERBOXD_CLIENT_SECRET` | Both when configured | Access and reuse governed by Letterboxd's approval and terms |
| The Guardian public web | Professional film reviews | None (search uses the Content API's public `test` key) | Both | Attributed professional criticism, linked to the article |
| YouTube Data API v3 | Embeddable public videos; captions (from public watch pages) for study categories | `YOUTUBE_API_KEY` or per-request personal key | Both | Privacy-enhanced `youtube-nocookie.com` embeds; uploads are not asserted to be authorised |
| Bilibili public search | Public videos without a key | None | Both | Unofficial public-page access; embeds via `player.bilibili.com` |
| Private library | Page-cited theory passages | None | Local only | User must hold the rights; documents and index never leave the device |
| FirstRoll public framework | Four first-party formal-analysis passages used as theory sources in hosted Deep Study | None | Hosted | First-party text (`app/backend/public_study.py`) |
| DeepSeek | Claim structuring and grounded synthesis | `DEEPSEEK_API_KEY` or per-request personal key | Both | Receives only the selected evidence after an explicit user action |

Server-side credentials come from the backend environment or, locally, the mode-`0600` settings
store; environment values take precedence. None is ever returned to the browser.

### Film identity and catalogue

Canonical film IDs are opaque and provider-qualified: `tmdb:{id}`, `wikidata:{QID}` (a bare QID is
accepted) or `demo:{slug}`; they key every cache, bundle and saved film. When several candidates
survive matching the user must choose; the model never selects an ambiguous film.

| `provider_policy` | When | Behaviour |
|---|---|---|
| `tmdb_primary` | TMDb token configured and search succeeds | TMDb search and hydration |
| `key_free_fallback` | No token | Wikidata/Wikipedia; a normal mode, not a fault |
| `wikidata_failover` | Token configured but TMDb search fails | Wikidata/Wikipedia with `mode=degraded` and the failure recorded in `sources` |

If Wikidata itself fails, search returns the curated offline catalogue with `mode=degraded`.

**TMDb.** One `/search/movie` request (`en-GB`, adult titles excluded), then at most eight candidates
hydrated through `/movie/{id}` with `credits`, `external_ids`, `alternative_titles` and
`release_dates`, four at a time. Year and director are re-checked locally; title similarity ranks the
survivors. Director shelves use `/person/{id}/movie_credits` for up to two verified directors, plus
`/movie/{id}/recommendations` unless `director_only` is set. 10 s timeout, 4 MB cap; no awards.

**Wikidata.** `wbsearchentities` (16 items), supplemented by QIDs from an English Wikipedia search
(12 pages; title, year, director and "film"), then `wbgetentities`; non-film items are rejected,
year and director filters are strict, and candidates are ranked by title similarity. Claims supply
release date, runtime, crew, genre, country, poster filename, up to three awards (ranked by
significance) and IMDb ID; related films use the SPARQL endpoint. Timeouts are 10 s (SPARQL 12 s,
Wikipedia 8 s).

**Wikipedia enrichment** runs only when Wikidata supplies an English sitelink. The REST summary
supplies the overview, URL and CC BY-SA attribution. The MediaWiki `parse` API supplies
`Infobox film`: director, writer/screenplay, producer, cinematography and editor values complete or
corroborate Wikidata without replacing the identity, and a Wikipedia runtime only fills a blank. The
parser ignores `style`, `script`, `template` and `noscript` nodes and rejects CSS or markup tokens;
the browser repeats the plausibility check.

**Posters**, in order: the Wikidata-named Commons file; an `a.ltrbxd.com` poster from the Letterboxd
page reached by IMDb ID, or from a title-derived page whose title, year and director match; then the
Wikipedia lead image, accepted only from `upload.wikimedia.org` (original before thumbnail, wide
images rejected).

### Criticism and research adapters

Each adapter returns attributed `ReviewSource` records (see [criticism bundle](#criticism-bundle)).
Source-ID prefixes keep records distinct across providers.

| Route | Identity match | Bounds | IDs |
|---|---|---|---|
| `crossref` | `query.bibliographic="<title>" <director> film cinema`, `filter=has-abstract:true`, `rows=24`; title or original title must occur in the work title or abstract; titles of two words or fewer also need the director's surname, or a film term in the work title | `api.crossref.org` only; 20 s; 3 MB; abstract ≥80 characters, ≤6,000 kept; up to 6 | `S1…` |
| `douban` | MCP `search-movie` by IMDb ID (else title); a single result with the matching release year is accepted, otherwise title similarity plus a year bonus must reach 0.55 | stdio child process given only `PATH` and an optional `COOKIE`; up to 8 summaries | `R1…` |
| `letterboxd-web` | `/imdb/{tt…}/` redirect first, then title and title-year slugs; Open Graph title (≥0.75 similarity) and year must match; JSON-LD director rejects namesakes | `letterboxd.com`/`www.letterboxd.com` HTTPS, including redirects; 20 s; 2 MB; up to 4 review pages; body ≥40 characters, ≤12,000 kept | `W1…` |
| `letterboxd` | OAuth client credentials; `/search` then title and year; `/log-entries` with `where=HasReview`, `filter=NoDuplicateMembers`, `sort=ReviewPopularity` | 20 s; moderated reviews skipped; up to 8; ≤6,000 characters | `L1…` |
| `guardian-web` | Content API search on headline, `section=film`, relevance order, 20 results; headline similarity ≥0.65 | Search host `content.guardianapis.com`; articles `theguardian.com` HTTPS, including redirects; 20 s; 3 MB; up to 4; body ≥80 characters, ≤12,000 kept | `G1…` |

- **Crossref** locates scholarship; an abstract is neither a description of the film nor a creator
  statement, and Crossref does not endorse the work. The named author and venue are the source.
- **Douban** (`moria97/douban-mcp`) stays optional: the listing is unvalidated, it needs a separate
  Node runtime, some functions may need a cookie, unofficial access can break and its licence does not
  cover reviews. FirstRoll calls only `search-movie` and `list-movie-reviews`, rebuilds Markdown
  table rows split by line breaks or unescaped pipes, and reports authentication blocks, empty
  tables, missing columns and schema drift distinctly; an empty table is not taken as proof that no
  reviews exist. No reviewer names are returned, so `author` stays empty. The hosted image bundles
  the connector at a pinned commit and never accepts a visitor cookie.
- **Letterboxd** public-web and API adapters are separate providers and never fall back to one
  another, so the access method stays explicit in provenance.
- **Guardian** headline and author come from JSON-LD, the rating from the star label, and text only
  from the article-body paragraphs (no navigation, recommendations or comments).

**Claim structuring** (`…/criticism/{provider}/structure`, local edition only) never fetches. It sends
cached reviews to DeepSeek in batches of three with one repair per batch. Each `CriticalClaim` is
Pydantic-validated (no extra fields, bounded lengths, `evidence_status=critic_reported`,
`extraction_confidence` `high`/`medium`/`low`, one to four lens tags, at most twelve per batch) and
must cite a `source_id` from its batch. Absent scene, observation, interpretation or
alternative-reading fields stay `null` (techniques stay empty) and are listed in `missing_fields`. A
refresh keeps claims only for unchanged review IDs.

**Reception.** `…/reception` normalises the Douban community score (scale 10) and the Letterboxd
public aggregate (scale 5) to 100; the 50/50 aggregate appears only when both exist. Awards come
only from Wikidata-backed records; TMDb records carry none.

### Public video resources

Videos are a viewing layer; only descriptions and captions of study-relevant categories become Deep
Study evidence.

| Aspect | YouTube | Bilibili |
|---|---|---|
| Access | Official Data API v3 `search` (`type=video`, `videoEmbeddable`, `videoSyndicated`, moderate SafeSearch) plus `videos?part=contentDetails,status` for ISO 8601 durations and a public, processed, embeddable status | Public server-rendered `search.bilibili.com` page (the anonymous JSON endpoint returns HTTP 412 risk control) |
| Queries | Verified title, year and director | Exact CJK aliases first (Wikidata `zh`, `zh-hans`, `zh-hant`, `ja`, `ko` labels and provider titles), then complete-film, criticism, interview/post-screening and production queries; at most ten |
| Validation | 11-character video IDs; channel attribution | `BV` IDs; the public video page for at most three plausible full-film candidates without a duration; every accepted result re-checked against its current page (four workers) |
| Limits | 20 s; 2 MB | 20 s search, 8 s video page; 4 MB (gzip handled) |
| Embed | `youtube-nocookie.com` | `player.bilibili.com` |

- Short or ambiguous titles must also match the year plus film context, or the director.
- Each result gets one type: `full_film`, `interview`, `video_essay`, `lecture`, `trailer`,
  `scene_extract`, `behind_the_scenes` or `other`. Title and description markers win (a reaction stays
  a video essay at any length); only then does a complete-film marker (`完整版`, `完整无删`, `无删减`,
  `未删减`, `全片`, `正片`, "full film") or ≥45 minutes yield `full_film`. An exact attributed localised
  title with such a marker may admit an upload year that differs from Wikidata's. Every merge
  reclassifies stored `full_film` cards and drops Bilibili results that no longer match the film.
- A search adds at most 12 results per platform; the catalogue is capped at 48 per film, deduplicated
  on `(platform, video_id)` and ordered by type (full films first), keeping existing order within a
  type. Entries expire six hours after `availability_checked_at` and are dropped from display and
  from the next merge.
- Captions (YouTube only; interviews, video essays, lectures and behind-the-scenes; at most six videos
  per pass, including a pass just before Deep Study) come from the watch page's `captionTracks`:
  manual before automatic, English first, at most two `json3` tracks of at least 40 characters,
  ≤12,000 kept. Signed caption URLs are never stored; `text_checked_at` prevents repeat attempts, and
  a missing or blocked track leaves the video usable.

### What reaches DeepSeek

| Material | Packet evidence type | Packet ID |
|---|---|---|
| Library passages (local) or the FirstRoll framework (hosted) | `theory_framework` | `S1…` |
| Structured critic claims | `critic_reported` claims | `C1…` |
| Douban, Letterboxd and Guardian review text | `critic_reported` | `E1…` |
| Crossref abstracts | `scholarly_abstract` | `E1…` |
| Video descriptions; captions without a verified speaker | `video_context` | `E1…` |
| Captions with `speaker_verified=true` | `creator_stated` | `E1…` |

Book passages are frameworks, not proof about the film; reviews and abstracts are attributed claims,
not observation. No adapter currently sets `speaker_verified`, so video text cannot yet establish
creator intention. Packet budgets and citation validation are in [Architecture](ARCHITECTURE.md).

**Private library.** Index only material you are entitled to use. Passages are cited by book title
and PDF page, never by file path; indexing is described in
[Setup](SETUP.md#private-study-library).

---

## 2. Data model

Hosted accounts, preferences, saved films and quota counters live in Supabase. Private books, derived
search data, connector secrets and acquired research live under the Git-ignored `.firstroll/`
directory, and clip-analysis output under the Git-ignored `img/`. Discovery caches and hosted study
results are process memory only.

### Storage inventory

| Store | Edition | Durability | Contains |
|---|---|---|---|
| Supabase Auth `auth.users` | Hosted | Durable | Identity, credentials and sessions, managed by Supabase |
| Supabase `public.firstroll_*` | Hosted | Durable | RLS-owned profile, preferences and saved films |
| Supabase `firstroll_private` quota tables | Hosted (default quota store) | Durable | Daily per-account and global Deep Study counters |
| PostgreSQL `firstroll_private` identity-neutral tables | Staged, opt-in | Durable | Daily provider/subject and global counters |
| `.firstroll/settings.json` | Local | Durable | Connector secrets not supplied by the environment |
| `.firstroll/library/` and `library.json` | Local | Durable | Managed private documents; registered paths and exclusions |
| `.firstroll/library.sqlite3` | Local | Durable, rebuildable | Chunks, FTS5 index, embeddings, index metadata |
| `.firstroll/criticism/*.json` | Both | Local: durable. Hosted: lost when the container is recreated | Attributed reviews and structured claims |
| `.firstroll/videos/*.json` | Both | As above | Video catalogue, descriptions and captions |
| `.firstroll/connectors/douban-mcp/` | Local | Durable | Optional connector install (code, not data); the hosted image uses `/opt/douban-mcp` |
| `img/<clip stem>/` | Local | Durable until deleted | Clip-analysis frames, `shotlen.csv`/`.png`, `objects.csv` and charts |
| Process memory | Both | Until restart | Study runs, discovery/related/reception caches, embedding warm-up state |
| Browser `sessionStorage` | Both | Per tab | Discover and product-view continuity |
| Browser `localStorage` | Both | Per browser | Theme, recent searches, Supabase session; loopback test-account records |
| Browser memory | Both | Per tab | Personal DeepSeek/YouTube keys |

In public mode the criticism and video caches are shared by every visitor for a film; they hold only
public attributed text.

### Supabase accounts

Migration `supabase/migrations/202608200002_persistent_accounts.sql`. Supabase Auth owns credentials
and email; FirstRoll's tables reference the Auth UUID and copy neither. The browser reads and writes
them directly with the publishable key and the user's session; the API never touches them.

| Table | Columns (type, constraint) |
|---|---|
| `firstroll_profiles` | `user_id` uuid PK → `auth.users(id)` cascade · `display_name` text null, 1–80 chars · `created_at`, `updated_at` timestamptz |
| `firstroll_preferences` | `user_id` uuid PK → `auth.users(id)` cascade · `theme` text default `system`, one of `system`/`light`/`dark` · `shelf_motion` boolean default true · timestamps |
| `firstroll_saved_films` | `id` uuid PK default `gen_random_uuid()` · `user_id` uuid → `auth.users(id)` cascade · `film_id` text 1–200 · `title` text 1–300 · `original_title` text null, 1–300 · `release_year` smallint null, 1888–2200 · `director` text null, 1–300 · `poster_url` text null, `https://` and ≤2,048 · timestamps · unique `(user_id, film_id)` · index `(user_id, created_at desc)` |

- RLS is enabled on all three; `public` and `anon` have no privileges. `authenticated` may select,
  insert and update all three and delete saved films; every policy requires
  `(select auth.uid()) = user_id` on old and new rows.
- `firstroll_touch_updated_at()` maintains `updated_at`. The security-definer
  `firstroll_handle_new_user()` trigger on `auth.users` creates profile (sign-up display name, ≤80)
  and preference rows; the migration backfills existing users.
- Personal keys, prompts, evidence and studies are excluded from every table.

### Supabase quota store (default)

Migration `supabase/migrations/202608150001_deep_study_quotas.sql`.

| Object | Definition |
|---|---|
| `firstroll_private.deep_study_user_daily` | `usage_day` date + `user_id` uuid (composite PK; `user_id` → `auth.users(id)` cascade) · `request_count` integer default 0, ≥0 · `updated_at` timestamptz |
| `firstroll_private.deep_study_global_daily` | `usage_day` date PK · `request_count` integer default 0, ≥0 · `updated_at` timestamptz |
| `public.deep_study_quota_status()` | `STABLE`; reads both counters for `auth.uid()`; consumes nothing |
| `public.reserve_deep_study_quota()` | `VOLATILE`; transaction-scoped advisory lock keyed on the UTC day, then increments both rows only when both limits allow |

Both functions return `allowed`, `reason` (`available`, `user_limit` or `global_limit`),
`user_limit`, `user_used`, `user_remaining`, `global_limit`, `global_used`, `global_remaining` and
`reset_at` (next UTC midnight). Limits are SQL constants: three per account and thirty in total per
UTC day. Schema and tables are revoked from `public`, `anon` and `authenticated`, with RLS enabled.
The functions are `SECURITY DEFINER` with an empty `search_path`, derive the user from `auth.uid()`
(error `42501` when absent) and are executable by `authenticated` only. The API calls them through
PostgREST with the visitor's bearer token and the publishable key; no service-role key is used.

### Identity-neutral PostgreSQL quota store (retained, staged)

Migration `database/migrations/202608200001_identity_neutral_deep_study_quotas.sql` is ordinary,
portable PostgreSQL (it can run on the existing Supabase database). Select it with
`FIRSTROLL_QUOTA_PROVIDER=postgres` plus `FIRSTROLL_DATABASE_URL`; it is not yet verified in
production.

| Object | Definition |
|---|---|
| `firstroll_private.deep_study_identity_daily` | `usage_day` date · `identity_provider` varchar(64), `^[a-z0-9_-]{1,64}$` · `subject` varchar(256), 1–256 chars · composite PK of all three · `request_count` integer default 0, ≥0 · `updated_at` timestamptz |
| `firstroll_private.deep_study_global_daily` | As in the Supabase migration (`create table if not exists`) |
| `firstroll_private.deep_study_quota_decision(p_identity_provider, p_subject, p_reserve default false)` | Validates inputs (error `22023`), locks only when reserving, returns the same JSON contract and 3/30 limits |

- `PostgresQuotaClient` re-validates provider and subject, connects with a 10 s timeout and sends only
  those two values and the reserve flag; the bearer token never reaches this database.
- The intended login is a dedicated `firstroll_backend` role (connection limit 5, 15 s statement and
  idle-in-transaction timeouts) with schema usage and function execute only; the SQL is in the
  migration's comments. The connection URL is a backend-only secret.
- Both migrations in one database share the global counter table. Rows have no foreign key to
  `auth.users`, so account deletion does not cascade. Per-account counts are not copied between
  stores, so switching mid-day restarts that day's per-account counts.

### Local SQLite retrieval index

Default `.firstroll/library.sqlite3` (override `FIRSTROLL_LIBRARY_INDEX`). A rebuild writes
`library.building.sqlite3`, sets mode `0600` and atomically renames it over the live file. Only PDFs
are extracted (with `pypdf`); other catalogue formats are listed but not indexed.

| Table | Columns |
|---|---|
| `chunk_records` | `chunk_id` TEXT PK (`ch_` + 24 hex of SHA-256 of document ID, page and normalised text) · `document_id` · `title` · `page` (one-based PDF page) · `section` · `topics` (pipe-separated) · `language` · `token_count` · `text` |
| `chunks` (FTS5) | Same identity fields, all `UNINDEXED`, plus indexed `text`; tokeniser `porter unicode61` |
| `embeddings` | `chunk_id` TEXT PK → `chunk_records` · `dimension` INTEGER · `vector` BLOB (`float32`) |
| `index_meta` | Key/value rows: `built_at`, `schema_version` (currently `2`), `chunking_version` (`token-v1`), `embedding_model` |

- Default encoder `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (override
  `FIRSTROLL_EMBEDDING_MODEL`); `FIRSTROLL_EMBEDDINGS=0` disables vectors, leaving lexical search.
- Retrieval fuses 25 BM25 and 25 vector candidates per planned query by reciprocal rank (k = 60), then
  keeps at most four passages per document and two per page, dropping near-duplicates.
- A `schema_version` mismatch reports `state: outdated` until rebuilt. Encoder warm-up status
  (`state` of `idle`, `warming`, `ready`, `failed` or `unavailable`; `duration_ms`; `background`) is
  process memory; it embeds one fixed phrase and reads no private chunk.

### Local JSON and file stores

All are written through a temporary file and atomic replace; directories are `0700`, files `0600`.

**Settings** — `.firstroll/settings.json` (override `FIRSTROLL_SETTINGS_PATH`): `tmdb_bearer_token`,
`deepseek_api_key`, `douban_cookie`, `letterboxd_client_id`, `letterboxd_client_secret`,
`youtube_api_key`, plus `nyt_api_key` and `guardian_api_key` for planned connectors. Environment
variables take precedence; the API exposes only configured state, source and the last four characters.

**Library** — managed uploads live in `.firstroll/library/` (override `FIRSTROLL_LIBRARY_PATH`): PDF,
EPUB, Markdown or text, ≤500 MB each, written via a hidden `.uploading` file, collisions numbered.
`.firstroll/library.json` (override `FIRSTROLL_LIBRARY_MANIFEST`) holds `documents` (registered
absolute paths) and `excluded_documents` (managed files hidden without deletion). Document IDs are 12
hex characters of the SHA-256 of the resolved path; the API never returns paths or contents.

#### Criticism bundle

`.firstroll/criticism/<film-id>--<provider>.json`, both parts sanitised to `[A-Za-z0-9_-]` and the
provider lower-cased (a legacy `<film-id>.json` is read as Douban). Pydantic models forbid extra
fields.

| Field | Meaning |
|---|---|
| `film_id` | Canonical FirstRoll ID |
| `provider` | `Douban`, `Letterboxd`, `Letterboxd public web`, `The Guardian public web` or `Crossref scholarship` |
| `provider_film_id`, `provider_film_title` | Matched provider identity, for human verification |
| `fetched_at` | ISO 8601 acquisition time |
| `reviews` | `ReviewSource[]`: `source_id`, `provider`, `review_id`, `title`, `summary`, `rating_label`, `author`, `url`, `language`, `content_scope=provider_summary` |
| `claims` | `CriticalClaim[]` structured from those reviews |
| `claim_status` | `pending` or `structured` |
| `notice` | Evidence boundary shown to the user |

#### Video bundle

`.firstroll/videos/<film-id>.json` (ID sanitised as above): `film_id`, `query`, `fetched_at`,
`videos` (≤48), `providers`, `notice`. Each `FilmVideo` has `platform`, `video_id`, `title`,
`creator`, `description`, `url`, `embed_url`, optional thumbnail, publication time and duration,
`category`, `relevance` (`title`, `director` or `title_and_director`), up to three `text_tracks`
(`kind` `captions`/`auto_captions`, `language`, ≤12,000-character `text`, `source_url`,
`speaker_verified`), `text_checked_at` and `availability_checked_at`.

### Browser storage

| Key | Storage | Contents and limits |
|---|---|---|
| `firstroll.discovery-session` | `sessionStorage` | Versioned snapshot ≤500 KB and ≤24 hours old: public query, up to 20 candidates, 12 director films and 10 nearby films, shelf state, optional dossier film ID |
| `firstroll.product-session` | `sessionStorage` | Active product view and three scroll offsets |
| `firstroll.theme` | `localStorage` | Theme choice |
| `firstroll.recent-searches` | `localStorage` | Up to five title/year/director searches |
| Supabase session | `localStorage` (supabase-js) | Access and refresh tokens; PKCE flow with automatic refresh |
| `firstroll.local-test.*` | `localStorage` | Sign-in flag, profile, preferences and saved films of the loopback-only test account |

Snapshots with the wrong schema, malformed identity, excessive age or size are discarded. Completed
shelves restore without provider requests; an in-flight search is reissued. Dossiers, criticism,
studies, credentials and account records never enter snapshots. Personal provider keys live only in
a JavaScript variable for the tab and are cleared on refresh or sign-out.

### Process-memory records

**`StudyRunStore`** keeps streamed Deep Study results out of the stream. Each entry holds the run UUID
(returned in `X-FirstRoll-Run-ID`), `owner_id` (`provider:subject`, required again to read),
monotonic `created_at`, `status` (`running`, `complete` or `failed`), the complete `result` and an
allow-listed `public_error`. Entries expire after ten minutes; at most 50 are kept and the oldest is
evicted on overflow. The store is per process and survives neither restart nor a second instance.

**Caches.** TMDb and Wikidata detail and related-film dictionaries and the reception dictionary
(stored only when scores or awards exist) last for the process lifetime with no size limit or
eviction. They are accelerators, not records of truth.

**Transient study objects.** `study.observability` (stage timings, aggregate counts) and
`study.packet_quality` (identity and citation checks, issue codes, ratios, labels) are aggregate-only
parts of the owner-visible result and accept no titles, questions, prompts, source text, URLs,
credentials, model output or exception messages. Observability is also logged. The synthetic
six-case packet-quality fixture, `tests/fixtures/packet_quality_cases.json`, uses invented films only.

### Lifecycle rules

1. Never commit `.firstroll`, `img/` output, private books, extracted text, embeddings, provider
   caches, cookies, API keys or uploaded clips.
2. Quota stores hold only an account identifier (Auth UUID, or provider plus subject), the UTC day and
   counters — never an email, bearer token, prompt, film, evidence or study.
3. The VPS API container has no data volume: anything it writes, including hosted criticism and video
   caches, disappears when a release recreates it. Durable hosted data belongs in Supabase or
   PostgreSQL (see [Operations](OPERATIONS.md)).
4. Deleting a Supabase Auth user cascades profile, preferences, saved films and Supabase per-account
   quota rows; global counters and identity-neutral rows are not linked to the Auth user.
5. A schema change needs a new migration under `supabase/migrations` or `database/migrations`, or a
   bumped local index `schema_version`.
6. A new persisted field must document its owner, retention, privacy class and deletion behaviour
   here before release.
7. Earlier local evaluation output (`.firstroll/autonomous-runs/`, `.firstroll/evaluations/`,
   `.firstroll/benchmarks/`) is no longer written; its code is parked at Git tag
   `archive/agent-programme`.

---

## 3. HTTP API reference

One FastAPI application serves both editions: locally at `http://127.0.0.1:8000` (API and web
interface); in the hosted beta at `https://api.firstroll.app` behind Caddy, with the static site on
`https://firstroll.app`. Paths below are relative; `{film_id}` may contain `:` and `/`.

- `FIRSTROLL_PUBLIC_MODE=true` selects the hosted boundary: local-only routes return 404 and `/docs`,
  `/redoc` and `/openapi.json` are not registered (404). Hiding them narrows discovery; it is not an
  authentication control.
- CORS is enabled only when `FIRSTROLL_CORS_ALLOWED_ORIGINS` lists exact origins: methods `GET`,
  `POST`, `OPTIONS`; request headers `Authorization`, `Content-Type`, `X-FirstRoll-DeepSeek-Key`,
  `X-FirstRoll-YouTube-Key`; exposed header `X-FirstRoll-Run-ID`; no credentials.

### Access classes

| Label | Meaning |
|---|---|
| Public | No account required |
| Local only | 404 in public mode; 403 unless the TCP client is `127.0.0.1` or `::1` |
| Local edition | 404 or unregistered in public mode; no loopback check |
| Bearer | `Authorization: Bearer <token>` verified by Supabase Auth (`GET /auth/v1/user`; UUID identity and role `authenticated`), or the loopback test account |
| Conditional bearer | Public, but a personal provider key requires a valid bearer in public mode |
| Feature gated | Requires explicit backend configuration |

`FIRSTROLL_AUTH_PROVIDER` accepts only `supabase`; authentication is never inferred from an email or
browser field. When both the request URL host and the TCP client are loopback, a fixed development
token in `app/backend/main.py` authenticates as provider `local` with an unlimited, non-persistent
quota; it cannot work through Caddy or any non-loopback host.

### Headers

| Header | Direction | Meaning |
|---|---|---|
| `Authorization: Bearer …` | Request | Supabase access token, at most 16,384 characters |
| `Content-Type` | Request | `application/json` for JSON bodies; browser-generated `multipart/form-data` for uploads |
| `X-FirstRoll-DeepSeek-Key` | Request | Optional personal DeepSeek key for one Deep Study request; 16–512 characters of `[A-Za-z0-9._-]`; never stored or returned |
| `X-FirstRoll-YouTube-Key` | Request | Optional personal YouTube key for one video search; same syntax |
| `X-FirstRoll-Run-ID` | Response | Run UUID on the Deep Study stream |
| `Retry-After` | Response | On 429: seconds until the next UTC reset, minimum 60 |
| `WWW-Authenticate: Bearer` | Response | On 401 |
| `Cache-Control` | Response | `no-store` on `/`, `/assets/config.js` and run results; `no-store, no-transform` on the stream |
| `Vary`, `X-Content-Type-Options: nosniff`, `X-Accel-Buffering: no` | Response | Stream (`Vary: Authorization, X-FirstRoll-DeepSeek-Key`; buffering disabled) and run results (`Vary: Authorization`) |

### Error contract

Errors use FastAPI's `{"detail": "Human-readable public error"}`; request-validation failures (422)
return a list of error objects in `detail`.

| Status | Meaning |
|---:|---|
| 400 | Invalid query, upload, connector field or personal-key syntax |
| 401 | Missing, malformed, expired or unauthorised session |
| 403 | Non-loopback caller on a local-only route |
| 404 | Unknown film, document, connector or provider; route unpublished in public mode; unknown, cross-owner or expired run |
| 409 | Value owned by the environment; no cached reviews to structure; run still in progress |
| 422 | Query, body or form constraint violated |
| 429 | Account or global Deep Study allowance exhausted (synchronous route) |
| 500 | Local index, filesystem or clip-analysis failure |
| 501 | Planned connector has no test |
| 502 | Provider, quota store or model returned no trustworthy result; failed run |
| 503 | Authentication, quota or Deep Study not configured; hosted clip analysis disabled |

### Service and account

| Route | Access | Response |
|---|---|---|
| `GET /` | Public | Local: `index.html`. Public mode: `{"service","status","health"}` unless `FIRSTROLL_SERVE_HOSTED_FRONTEND=true` |
| `GET /assets/config.js` | Public | `window.FIRSTROLL_CONFIG`: `apiBase`, `publicMode`, `videoAnalysisEnabled`, `supabaseUrl`, `supabasePublishableKey` (blank unless it starts `sb_publishable_`), `localTestAccountEmail` (loopback only), `buildId`, `buildNumber`, `buildChannel`, `buildCommit`. The hosted static site ships its own build-time copy |
| `GET /assets/{file}` | Public | Static files from `app/web` |
| `GET /api/health` | Public | `{"status":"ok"}`, plus `release_sha` and `release_digest` when set |
| `GET /api/contract` | Public | Compact, partial route list and clip-analysis form shape; this document is authoritative |
| `GET /api/discovery/status` | Public | Catalogue sources and `provider_policy`; `features` (`public_mode`, `video_analysis`, `deep_study`, `authentication`); local mode adds `local_library` with index and warm-up status |
| `GET /api/auth/me` | Bearer | `{"user":{"id","email","role","provider"}}` |
| `GET /api/account/integrations` | Bearer; public mode, or a loopback request in the local edition (otherwise 404) | `user`; `deep_study` (`platform_enabled`, `model`, non-consuming `quota`, `personal_session_key_supported`); `youtube`; `douban` (no personal credentials or cookie accepted); `privacy`. 502/503 on quota failure |

### Local settings and private library

All routes are **Local only** except `GET /api/library/status` (**Local edition**). Connector IDs are
`tmdb`, `deepseek`, `douban`, `letterboxd` and `youtube` (available) and `nyt` and `guardian`
(planned).

| Route | Request | Response and errors |
|---|---|---|
| `GET /settings` | — | Settings HTML |
| `GET /api/settings` | — | Masked connectors (`configured`, `credential_source` of `environment`, `local_store`, `mixed` or `none`, `credential_hint`) and storage description |
| `PUT /api/settings/connectors/{connector_id}` | `{"value":"…"}`, or `{"credentials":{"client_id":"…","client_secret":"…"}}` | `{"connector":…}`; 400 empty or unknown field; 404 connector; 409 environment owns the value |
| `DELETE /api/settings/connectors/{connector_id}` | — | `{"connector":…}`; 404 connector; 409 when only environment values remain |
| `POST /api/settings/connectors/{connector_id}/test` | — | Provider readiness; 404 connector; 501 planned connector; 502 provider failure |
| `GET /api/settings/library` | — | Catalogue, index status, `supported_formats`, `max_upload_mb`, `indexable_document_count`, `index_needs_rebuild` |
| `POST /api/settings/library` | Multipart `document` | `{"document","library"}`; 400 empty, oversized or unsupported |
| `DELETE /api/settings/library/{document_id}` | — | `{"document","library"}`; the source file is never deleted; 404 unknown; 500 manifest error |
| `POST /api/settings/library/rebuild` | — | Refreshed library settings; 500 redacted failure |
| `GET /api/library/status` | — | Public catalogue metadata and index status |

### Discovery, criticism and video

All routes are **Public** unless stated. Criticism routes take no body, return
`{"critical_research": bundle}`, and return 404 for an unknown film or 502 when the provider yields no
confident, attributed result (including a missing Douban install or Letterboxd credentials).

| Route | Parameters | Response |
|---|---|---|
| `GET /api/discovery/search` | `q` 1–160 chars; `year` 1888–2100; `director` ≤120 chars | `query` (`title`, `year`, `director`), `results` (`id`, titles, `year`, `directors`, poster, `match_score`, `source`; TMDb results add `external_ids`), `result_count`, `mode`, `sources`, `provider_policy`, `generated_at` |
| `GET /api/discovery/films/{film_id}` | — | `{"film":…}` with `critical_research` (provider status and cached bundles) and `video_sources` (status and fresh cached catalogue); local mode adds `local_library` and `study_reading` |
| `GET /api/discovery/films/{film_id}/related` | `limit` 1–60 (12); `fast` (true; `false` adds poster enrichment for Wikidata records); `director_only` (false) | `director`, `same_director`, `shared_cast`, `same_country`, `recommended`, `category_labels`, `state` |
| `GET /api/discovery/films/{film_id}/reception` | — | `scores`, `aggregate`, `providers`, `awards` |
| `POST /api/discovery/films/{film_id}/videos` | Conditional bearer; optional `X-FirstRoll-YouTube-Key` | `{"video_sources": bundle}`; 400 key syntax; 401 public mode with a key but no valid session; 502 nothing matched |
| `POST …/criticism/crossref` | — | Scholarly abstracts |
| `POST …/criticism/douban` | — | Douban review summaries |
| `POST …/criticism/letterboxd-web` | — | Public Letterboxd reviews |
| `POST …/criticism/guardian-web` | — | Guardian reviews |
| `POST …/criticism/letterboxd` | — | Official Letterboxd API reviews |
| `POST …/criticism/{provider}/structure` | **Local only**; `provider` is `crossref`, `douban`, `letterboxd`, `letterboxd-web` or `guardian-web` | Bundle with validated claims and `claim_status=structured`; 404 unknown provider; 409 no cached reviews; 502 missing DeepSeek key or failure |

Clients must require an explicit choice among several search candidates before opening a dossier or
starting Deep Study, ignore unknown response fields, and never treat provider summaries as direct
film observation.

### Deep Study

| Route | Access | Request | Response |
|---|---|---|---|
| `POST /api/discovery/films/{film_id}/study` | Local: Public. Public mode: Bearer + feature gate + quota | `{"question":"…"}` (optional); optional `X-FirstRoll-DeepSeek-Key` | `film_id`, `study`, `credential_source` (`personal_session` or `firstroll_platform`), and `quota` in public mode |
| `POST /api/discovery/films/{film_id}/study/stream` | Bearer in both modes; public mode adds feature gate + quota | As above | `text/event-stream` with `X-FirstRoll-Run-ID` |
| `GET /api/research/runs/{run_id}` | Bearer + run owner | — | The synchronous payload; 409 running; 502 failed (allow-listed message); 404 unknown, cross-owner or expired |

- **Feature gate.** In public mode Deep Study returns 503 unless `FIRSTROLL_DEEP_STUDY_ENABLED` is
  true, authentication and the quota store are configured, and a platform `DEEPSEEK_API_KEY` or a
  personal key is present. Production status is recorded in [Operations](OPERATIONS.md).
- **Clients.** The browser uses the stream and run routes in public mode and the synchronous route
  in the local edition.
- **Quota.** The reservation is made after the evidence packet is assembled and immediately before
  DeepSeek is called; a later failure still consumes it. Limits: three per account and thirty in
  total per UTC day; the loopback test account is exempt. Personal keys do not bypass the quota.
  Exhaustion returns 429 with `Retry-After` on the synchronous route; on the stream, which is already
  open, it is a `run_failed` event and the run route then returns 502. Neither the API nor Caddy
  applies a general request-rate limit; provider adapters are individually bounded.
- **Study payload.** `study` holds the sections, `quality`, the selected `evidence_packet`,
  `packet_quality` and `observability` (`schema_version` 1, overall status, twelve ordered stages from
  `film_context` to `end_to_end` each with status `completed`, `failed`, `degraded`, `skipped` or
  `not_run`, milliseconds, attempts and failures, and allow-listed aggregate counts; see
  [Architecture](ARCHITECTURE.md)).
- **Stream.** Authentication, key syntax and the feature gate are checked before the stream opens.
  Each frame is `event: progress` whose `data` may contain only `run_id`, `kind`, `sequence`,
  `message` (server allow-list, ≤180 characters), `elapsed_ms` and optional `counts`
  (`theory_sources`, `critical_claims`, `attributed_sources`, `sections`). Prompts, credentials,
  passages, review bodies, model output and exception text have no field. The browser uses a streamed
  `fetch()` rather than `EventSource` so it can send the bearer and personal-key headers.

```text
event: progress
data: {"run_id":"…","kind":"evidence_assessed","sequence":3,"message":"The evidence boundary is ready for synthesis.","elapsed_ms":42,"counts":{"theory_sources":4,"critical_claims":8,"attributed_sources":5}}
```

| `kind` | Emitted today | Meaning |
|---|---|---|
| `film_resolving` | Yes | Confirming the selected film |
| `existing_evidence_loading` | Yes | Loading cached evidence |
| `evidence_assessed` | Yes | Evidence packet ready, with counts |
| `study_drafting` | Yes | Structured synthesis running |
| `quality_checked` | Yes | Deterministic checks finished (`passed` or `limited` message) |
| `run_completed` | Yes | Result ready at the run route |
| `run_failed` | Yes | Stopped at a redacted boundary: film missing, quota exhausted or unavailable, invalid study, or safe stop (a client disconnect is recorded only in the run store) |
| `film_needs_choice`, `research_planning`, `tool_started`, `tool_completed`, `tool_failed`, `study_repairing` | No | Reserved in the allow-list |

### Clip analysis

| Route | Access | Multipart fields | Response |
|---|---|---|---|
| `POST /api/analyze` | Feature gated: `FIRSTROLL_VIDEO_ANALYSIS_ENABLED`, on by default locally, off in public mode | `video` (required); `scene_sensitivity` (6, clamped to 1–10); `shot_threshold` (0.35, clamped to 0.05–0.95); `include_object_detection` (true); `include_shot_scale` (true) | `meta`, `global`, `shots`, `scenes`, `outputs` (server paths under `img/<clip stem>/`); 503 disabled; 400 missing filename; 500 analysis failure |

The upload is read into memory, written to a temporary file and removed in `finally`, with no explicit
size limit; derived frames and CSVs remain in `img/`. The pipeline is
`app/backend/analysis_pipeline.py` with `app/backend/algorithms`.

### Compatibility rules

1. Additive response fields are allowed within the `0.1.x` prototype.
2. Removing or renaming a field, route, event kind or error meaning requires an API version decision
   and an update to this document.
3. Local-only routes must stay absent in public mode rather than relying on interface hiding.
4. New progress fields, counts or messages must pass the explicit allow-lists and privacy tests.
5. New durable endpoint data must first be described in [Part 2](#2-data-model).
