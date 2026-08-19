# FirstRoll Data Model

**Status:** Current implementation  
**Last reconciled:** 19 August 2026

FirstRoll deliberately uses different stores for different privacy and durability requirements. The
hosted edition persists account identity and quota counters in Supabase. The local edition persists
private books, derived search data, connector settings and acquired research under `.firstroll/`.
Film discovery caches and current hosted study results are process memory.

## Storage Inventory

| Store | Runtime | Durable | Contains | Excluded from Git |
|---|---|---:|---|---:|
| Supabase Auth | Hosted | Yes | User identity and session state managed by Supabase | Not applicable |
| Supabase Postgres private schema | Hosted | Yes | Daily per-user and global Deep Study counters | Not applicable |
| `.firstroll/library.sqlite3` | Local | Yes | Extracted chunks, FTS5 index, float32 embeddings and index metadata | Yes |
| `.firstroll/library/` | Local | Yes | Managed private document files | Yes |
| `.firstroll/library.json` | Local | Yes | Registered paths and managed-file exclusions | Yes |
| `.firstroll/settings.json` | Local | Yes | Optional connector secrets not supplied by environment | Yes |
| `.firstroll/criticism/*.json` | Local | Yes | Attributed provider reviews and structured critic claims | Yes |
| `.firstroll/videos/*.json` | Local | Yes | Accepted video catalogue, descriptions and available captions | Yes |
| Discovery/reception dictionaries | Local and hosted | No | Wikidata/Wikipedia detail, related-film and reception cache | In memory only |
| `StudyRunStore` | Hosted | No | Owner UUID, status and final study for a maximum of ten minutes | In memory only |

## Supabase Postgres

Migration: `supabase/migrations/202608150001_deep_study_quotas.sql`

The application does not maintain a parallel FirstRoll user table. Supabase Auth owns identity in
`auth.users`; FirstRoll's private quota table references that UUID.

```mermaid
erDiagram
    AUTH_USERS ||--o{ DEEP_STUDY_USER_DAILY : "user_id"

    AUTH_USERS {
        uuid id PK
    }

    DEEP_STUDY_USER_DAILY {
        date usage_day PK
        uuid user_id PK_FK
        integer request_count
        timestamptz updated_at
    }

    DEEP_STUDY_GLOBAL_DAILY {
        date usage_day PK
        integer request_count
        timestamptz updated_at
    }
```

### `firstroll_private.deep_study_user_daily`

One row represents one authenticated account's reserved Deep Study calls for one UTC day.

| Column | Type | Null | Default | Key/constraint | Meaning |
|---|---|---:|---|---|---|
| `usage_day` | `date` | No | — | Composite primary key | UTC quota day |
| `user_id` | `uuid` | No | — | Composite primary key; FK → `auth.users(id)` with `ON DELETE CASCADE` | Authenticated account |
| `request_count` | `integer` | No | `0` | `CHECK (request_count >= 0)` | Reservations consumed that day |
| `updated_at` | `timestamptz` | No | `now()` | — | Last reservation update |

The composite primary key provides the lookup index used by status and reservation functions. No
email address, prompt, film ID, evidence or study text is stored.

### `firstroll_private.deep_study_global_daily`

One row represents all reserved public-demo Deep Study calls for one UTC day.

| Column | Type | Null | Default | Key/constraint | Meaning |
|---|---|---:|---|---|---|
| `usage_day` | `date` | No | — | Primary key | UTC quota day |
| `request_count` | `integer` | No | `0` | `CHECK (request_count >= 0)` | Reservations consumed across every account |
| `updated_at` | `timestamptz` | No | `now()` | — | Last reservation update |

### RPC dictionary

| Function | Volatility | Caller | Side effect | Return |
|---|---|---|---|---|
| `public.deep_study_quota_status()` | `STABLE` | `authenticated` only | None | JSONB allowance, reason, account/global counts and next UTC reset |
| `public.reserve_deep_study_quota()` | `VOLATILE` | `authenticated` only | Atomically increments both rows when allowed | Same JSONB contract after the decision |

`reserve_deep_study_quota()` obtains a transaction-scoped advisory lock derived from the UTC day
before checking and incrementing. This serialises concurrent reservations across both tables and
prevents either limit being exceeded by a race. Current constants are three requests per account per
UTC day and thirty across the public demo.

Both tables have row-level security enabled and all direct table privileges are revoked from
`public`, `anon` and `authenticated`. The functions are `SECURITY DEFINER`, set an empty
`search_path`, derive the user with `auth.uid()` and expose execute permission only to
`authenticated`. FirstRoll does not require a Supabase service-role key.

## Local SQLite Retrieval Index

Default path: `.firstroll/library.sqlite3`  
Override: `FIRSTROLL_LIBRARY_INDEX`

The index is rebuilt into `.building.sqlite3`, closed, changed to mode `0600` and atomically renamed
over the live file. This prevents readers from observing a partially built schema.

```mermaid
erDiagram
    CHUNK_RECORDS ||--o| EMBEDDINGS : "chunk_id"
    CHUNK_RECORDS ||--|| CHUNKS_FTS5 : "chunk_id"

    CHUNK_RECORDS {
        text chunk_id PK
        text document_id
        text title
        integer page
        text section
        text topics
        text language
        integer token_count
        text text
    }

    EMBEDDINGS {
        text chunk_id PK_FK
        integer dimension
        blob vector
    }

    INDEX_META {
        text key PK
        text value
    }
```

### `chunk_records`

| Column | SQLite type | Key | Meaning |
|---|---|---|---|
| `chunk_id` | `TEXT` | Primary key | Stable hash of document ID, page and normalised chunk text |
| `document_id` | `TEXT` | — | Stable local document identifier |
| `title` | `TEXT` | — | Cleaned document title used in citations |
| `page` | `INTEGER` | — | One-based PDF page number |
| `section` | `TEXT` | — | Locally inferred section heading, when available |
| `topics` | `TEXT` | — | Pipe-separated catalogue topics |
| `language` | `TEXT` | — | Detected language code |
| `token_count` | `INTEGER` | — | Chunk token estimate used by the chunking policy |
| `text` | `TEXT` | — | Extracted private chunk body |

### `chunks` FTS5 virtual table

| Field | Indexed | Meaning |
|---|---:|---|
| `chunk_id` | No | Join key to `chunk_records` |
| `document_id` | No | Document identity |
| `title` | No | Citation title |
| `page` | No | Page locator |
| `section` | No | Section context |
| `topics` | No | Catalogue topics |
| `text` | Yes | Lexical search body |

Tokenizer: `porter unicode61`. Retrieval uses BM25 candidates per planned query and reciprocal-rank
fusion rather than treating the raw BM25 value as an absolute relevance score.

### `embeddings`

| Column | SQLite type | Key/constraint | Meaning |
|---|---|---|---|
| `chunk_id` | `TEXT` | Primary key; FK → `chunk_records(chunk_id)` | One vector per chunk |
| `dimension` | `INTEGER` | — | Vector length used for validation |
| `vector` | `BLOB` | — | NumPy `float32` bytes generated locally |

The default model is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Embeddings are
optional and can be disabled with `FIRSTROLL_EMBEDDINGS=0`; lexical FTS retrieval remains available.

### `index_meta`

| Key | Meaning |
|---|---|
| `built_at` | UTC ISO-8601 build time |
| `schema_version` | Compatibility gate read by `LocalLibraryIndex.status()` |
| `chunking_version` | Chunk algorithm version |
| `embedding_model` | Local encoder name, or an empty value when embeddings were disabled |

## Local JSON and File Stores

### Library manifest

Default path: `.firstroll/library.json`

| Field | Type | Meaning |
|---|---|---|
| `documents` | array of absolute path strings | User-registered documents outside the managed library |
| `excluded_documents` | array of absolute path strings | Managed documents hidden from the catalogue without deleting the source file |

Managed uploads are copied into `.firstroll/library/`, limited to 500 MB each, written through a
temporary file and set to mode `0600`. API catalogue responses expose stable IDs, cleaned titles,
formats, sizes, topics and source kind, never file paths or document contents.

### Local connector settings

Default path: `.firstroll/settings.json`

This object may contain local secret values such as `deepseek_api_key`, `douban_cookie`,
`letterboxd_client_id`, `letterboxd_client_secret` and `youtube_api_key`. Environment variables take
precedence. The directory is mode `0700`, the file is mode `0600`, writes use atomic replacement and
API responses return only configured state, source and a masked hint.

### Criticism bundle

Default directory: `.firstroll/criticism/`  
File key: sanitised film ID plus provider

| Field | Type | Meaning |
|---|---|---|
| `film_id` | string | Canonical FirstRoll/Wikidata identity |
| `provider` | string | Normalised provider name |
| `provider_film_id` | string | Matched provider identity |
| `provider_film_title` | string | Provider title used for human verification |
| `fetched_at` | ISO-8601 string | Acquisition time |
| `reviews` | `ReviewSource[]` | Attributed title, author, URL, language, rating label and bounded summary |
| `claims` | `CriticalClaim[]` | Optional DeepSeek-structured secondary claims with provenance |
| `claim_status` | `pending | structured` | Whether the cached raw reviews have been structured |
| `notice` | string | Provider/evidence boundary shown to the user |

Pydantic models reject extra fields. Files are written atomically with mode `0600`.

### Video bundle

Default directory: `.firstroll/videos/`  
File key: sanitised film ID

| Field | Type | Meaning |
|---|---|---|
| `film_id` | string | Canonical film identity |
| `query` | string | Search query used for the catalogue |
| `fetched_at` | ISO-8601 string | Last merged search time |
| `videos` | `FilmVideo[]`, maximum 48 | Deduplicated YouTube/Bilibili resources |
| `providers` | string array | Providers contributing accepted results |
| `notice` | string | Limitations and merge summary |

Each video records platform ID, title, creator, description, canonical and embed URLs, optional
thumbnail/published time/duration, category, relevance and up to three text tracks. Text tracks are
bounded to 12,000 characters and retain language, source URL and `speaker_verified`; unverified
captions cannot establish creator intention.

## Process-Memory Records

### `StudyRunStore`

| Field | Type | Meaning |
|---|---|---|
| Run key | UUID string | Opaque ID returned in `X-FirstRoll-Run-ID` |
| `owner_id` | Supabase user UUID | Required again when reading the result |
| `created_at` | monotonic process time | TTL calculation only |
| `status` | `running | complete | failed` | Current terminal state |
| `result` | object or null | Complete study; never placed in SSE |
| `public_error` | allow-listed string or null | Redacted error safe for the owner |

The store has a ten-minute TTL and a maximum of 50 entries. On overflow it evicts the oldest entry.
It is intentionally not a database and cannot support multiple API instances, process restarts or
resumable Agent threads.

### Discovery and reception caches

Wikidata/Wikipedia details, related-film results and reception summaries are cached in dictionaries
for process lifetime. They are accelerators, not records of truth, and are repopulated after restart.

## Data-Lifecycle Rules

1. Never commit `.firstroll`, private books, extracted text, embeddings, provider caches, cookies,
   API keys or uploaded clips.
2. Supabase stores quota counters only; it does not store prompts or generated studies.
3. Render's filesystem is ephemeral and must not be treated as durable application storage.
4. Private local files use restrictive modes and atomic replacement where practical.
5. Schema changes require a new Supabase migration or a bumped local index `schema_version`.
6. A new persisted field must document its owner, retention, privacy class and deletion behaviour in
   this file before release.
