# FirstRoll — Evidence-Grounded Film Study

FirstRoll is a local film-study platform for filmmakers. It combines open film metadata,
attributed criticism, a private study library, evidence-constrained language-model
synthesis and clip-based visual analysis.

The central rule is simple: identity records, critic reports, theory frameworks, model
hypotheses and measured film observations are different kinds of evidence. FirstRoll
keeps those layers visible instead of presenting one fluent but unsupported answer.

> **Current status:** local working prototype. Discover, private-library retrieval,
> Crossref scholarship, optional Douban, Letterboxd and Guardian criticism, DeepSeek
> synthesis and clip analysis are implemented. The
> next major milestone is connecting measured clip evidence to Deep Study.

See [Project Progress](docs/PROGRESS.md) for completed milestones, verification results,
known limitations and the next priorities.

## Lineage and Attribution

FirstRoll is an independent evolution of
[CBD-Lab/pyCinemetrics](https://github.com/CBD-Lab/pyCinemetrics). The original project
provided the computational film-analysis foundation, including work on shot boundaries,
shot scale, colour and object analysis. FirstRoll retains that contribution in its Git
history and `upstream` remote while developing a new web interface, API, discovery and
evidence-grounded research architecture.

The original GPL-3.0 licence and contributor attribution remain applicable. See
[Original pyCinemetrics Work](#original-pycinemetrics-work).

## What Works

### Discover and study

- Search by title, year and director through key-free Wikidata.
- Read an attributed Wikipedia overview and poster after Wikidata resolves the film.
- Retrieve matched scholarly abstracts and DOI links through Crossref.
- Browse a private local library without publishing books or file paths.
- Retrieve page-cited theory through hybrid SQLite FTS5 and local multilingual vectors.
- Use the study focus and attributed critic claims to plan retrieval.
- Fuse lexical and semantic rankings, then reduce page, document and semantic duplicates.

### Critical perspectives

- Optionally run the unofficial local Douban MCP connector.
- Retrieve attributed reviews from Letterboxd public film pages in local-only mode.
- Retrieve attributed Guardian film reviews through its public content index and pages.
- Connect approved Letterboxd OAuth credentials through the official API.
- Keep each provider in a separate selectable and refreshable evidence bundle.
- Retrieve source text first, cache and display it, then structure it in a separate step.
- Ask DeepSeek to extract Pydantic-validated, attributed critical claims.
- Preserve missing scenes, observations, techniques and alternative readings as missing.
- Keep critic reports separate from verified film observations and creator statements.

### Deep Study

- Configure a DeepSeek key from the local Settings page.
- Build a typed evidence packet from the film record, retrieved theory and criticism.
- Generate four to six sections with separate fields for:
  - critic reports;
  - theory explanations;
  - FirstRoll hypotheses;
  - proposed formal mechanisms;
  - alternative readings;
  - verification tasks and confidence.
- Validate every theory and critic citation against supplied evidence IDs.
- Run a deterministic specificity and evidence-quality gate.
- Permit at most one bounded repair request.
- Label unresolved work as **insufficient evidence** rather than silently accepting it.
- Show the retrieval plan, source rationale and expandable evidence excerpts in the UI.

### Analyse

- Import a private film clip through the browser.
- Generate duration, resolution, frame-rate and frame-count metadata.
- Detect shot and scene boundaries.
- Calculate global and scene-level average shot length.
- Estimate shot-scale composition.
- Summarise scene-level dominant colour.
- Aggregate detected objects or use clearly identified fallback results when optional
  inference is unavailable.
- Export backend results as JSON and CSV.

Clip measurements do not yet enter Deep Study automatically. Until that bridge is
implemented, film-specific formal claims remain viewing hypotheses.

## System Architecture

FirstRoll is organised as a local-first pipeline. Each layer has one responsibility:
the interface gathers intent, application services acquire and process material, the
evidence layer preserves provenance, and the study pipeline turns only selected evidence
into a validated essay.

```mermaid
flowchart TB
    MAKER(["Filmmaker"])

    EXPERIENCE["1 · LOCAL EXPERIENCE<br/><b>Discover · Deep Study · Analyse</b>"]

    subgraph SOURCES["INPUTS AND ATTRIBUTED SOURCES"]
        direction LR
        RESEARCH["External research<br/>Wikidata · Wikipedia · Crossref<br/>Douban · Letterboxd · Guardian"]
        LIBRARY[("Private library<br/>books · notes · local vectors")]
        VIDEO[("Private film clip")]
    end

    SERVICES["2 · LOCAL APPLICATION SERVICES<br/><b>Film discovery</b> · <b>Criticism adapters</b><br/><b>Hybrid retrieval</b> · <b>Clip analysis</b>"]

    EVIDENCE["3 · LOCAL PROVENANCE-PRESERVING EVIDENCE<br/>Verified film record · Attributed critic claims<br/>Page-cited theory passages"]
    MEASURE["Measured clip evidence<br/>timecodes · scene and shot metrics"]

    PACKET["4A · LOCAL EVIDENCE ASSEMBLY<br/><b>Typed evidence packet</b><br/>record · criticism · theory"]
    DEEPSEEK["4B · EXTERNAL SYNTHESIS<br/><b>DeepSeek structured draft</b><br/>selected evidence only"]
    GATE["4C · LOCAL VALIDATION<br/><b>Schema · citations · evidence quality</b><br/>one repair maximum"]

    OUTPUTS["5 · LOCAL OUTPUTS<br/><b>Critical essay</b> · inline citations<br/><b>Insufficient evidence</b> clearly labelled<br/><b>Analysis exports</b> · JSON · CSV"]

    MAKER --> EXPERIENCE --> SERVICES
    RESEARCH -->|"attributed context and reviews"| SERVICES
    LIBRARY -->|"local retrieval"| SERVICES
    VIDEO -->|"local analysis"| SERVICES

    SERVICES --> EVIDENCE --> PACKET
    SERVICES --> MEASURE
    MEASURE -->|"JSON · CSV"| OUTPUTS
    MEASURE -. "planned evidence bridge" .-> PACKET

    PACKET -->|"only this packet leaves the device"| DEEPSEEK
    DEEPSEEK --> GATE --> OUTPUTS

    classDef person fill:#2f5d50,stroke:#2f5d50,color:#ffffff;
    classDef service fill:#e8f0ed,stroke:#5d7f74,color:#17211e;
    classDef evidence fill:#fff3dc,stroke:#b8792a,color:#2a2115;
    classDef study fill:#f2eafa,stroke:#77569a,color:#21192b;
    classDef private fill:#eef0df,stroke:#7c824f,color:#1f2117;
    classDef external fill:#f8e8e4,stroke:#a55445,color:#2b1b18;

    class MAKER person;
    class EXPERIENCE,SERVICES service;
    class EVIDENCE,MEASURE evidence;
    class PACKET,GATE,OUTPUTS study;
    class LIBRARY,VIDEO private;
    class RESEARCH,DEEPSEEK external;
```

The numbered bands show the path from user intent to a cited essay. Layers labelled
**local** run on the user's machine; books, vectors, clips and exports stay there. External
research services return attributed source material, while DeepSeek is the only synthesis
service. When the user chooses **Generate study**, only the typed, selected evidence packet
leaves the device—not complete books, local vectors, clips or private file paths. The dotted
connection is planned work: clip measurements do not yet support claims in Deep Study.

## Research and Criticism Acquisition

FirstRoll does not ask an LLM to browse blindly. Every source has a bounded adapter, an
identity check and a normalised evidence record. Retrieval and interpretation are separate:

```text
verified film identity
        ↓
provider-specific search and identity matching
        ↓
attributed raw source + canonical URL
        ↓
private local cache (claim status: pending)
        ↓
optional DeepSeek claim extraction
        ↓
Pydantic validation + source-ID checks
```

This separation is why a fetched review remains readable when DeepSeek is unavailable or
returns malformed structured output. A provider failure also affects only its own tab; it
does not erase evidence cached from another provider.

### Wikidata: canonical film identity

Wikidata is the first lookup because it offers key-free, CC0 structured metadata. FirstRoll:

1. searches items with `wbsearchentities`;
2. retrieves candidate entities with `wbgetentities`;
3. rejects items that do not look like films;
4. filters or ranks by title, release year and director; and
5. retains the Wikidata QID as FirstRoll's canonical external identity.

The entity claims supply release date, runtime, director, writer, cinematographer, genre,
country, poster filename and IMDb ID when present. Related entity labels are fetched in
batches. The IMDb ID is especially useful for resolving the same film safely in other
services. If Wikidata is unavailable, a small, explicitly labelled demo catalogue keeps the
interface usable in degraded mode; it is never presented as a live match.

### Wikipedia: overview and poster

Wikipedia enrichment happens only after Wikidata supplies an English Wikipedia sitelink.
FirstRoll calls the Wikipedia REST summary endpoint, retains the article URL and CC BY-SA
attribution, and keeps the overview separate from Wikidata's CC0 identity record.

For posters, FirstRoll accepts only Wikimedia upload URLs returned by the article summary.
It prefers the original image, falls back to the thumbnail, rejects invalid dimensions and
avoids landscape images that are unlikely to be posters. Wikipedia prose establishes
attributed context, not creator intention or formal analysis.

### Research: Crossref scholarship

The **Research** tab uses Crossref's public metadata API rather than returning generic search
links. Its query combines the film title, director and film/cinema terms, requesting records
that contain abstracts. FirstRoll then applies a second local relevance check:

- the title or original title must occur in the work title or abstract;
- short or ambiguous film titles require the director or explicit film context;
- records without a usable abstract, attribution or HTTP(S) source URL are rejected; and
- accepted items retain author, publication, year, work type and canonical DOI URL.

Up to six matched abstracts are cached as attributed secondary evidence. Crossref is the
discovery and metadata channel; the named author and publication remain the actual source.

### Douban: optional local MCP

The Douban adapter starts the separately installed MCP server over stdio and calls only
`search-movie` and `list-movie-reviews`. It prefers a title-and-year match and refuses a weak
identity match rather than silently selecting the first result.

The connector returns Markdown tables, so FirstRoll reconstructs logical rows when long
Chinese summaries contain line breaks and repairs unescaped pipe characters without losing
the final review ID. Each accepted row receives a stable Douban review URL and language
label. Authentication blocks, empty tables, missing columns and schema drift produce
different diagnostics; an empty response is not treated as proof that no reviews exist.

### Letterboxd: public pages and verified identity

The local-only public-web adapter resolves identity before collecting reviews. Its priority
order is:

1. use the verified IMDb ID at Letterboxd's `/imdb/{id}/` route and follow the redirect to
   the canonical film page;
2. fall back to title and title-year slugs when no IMDb ID exists; and
3. compare JSON-LD director metadata when a fallback page supplies it.

This matters because Letterboxd can contain different films with the same English title and
release year. Title-year matching alone selected the wrong *An Unfinished Film* page; the
IMDb redirect correctly resolves Lou Ye's film to `an-unfinished-film-2024`, while the
director guard rejects the unrelated namesake.

After resolution, FirstRoll reads popular-review links from the canonical film page, opens a
bounded number of individual public review pages and extracts the JSON-LD `Review` object.
It preserves member name, rating, language, complete source URL and up to 12,000 characters
for local processing. Requests are restricted to HTTPS Letterboxd hosts and size-limited.
This adapter is unofficial and can fail if public markup or access controls change.

The separate official Letterboxd adapter remains available for approved OAuth clients. It
uses client credentials, `/search` for film matching and `/log-entries` for public reviews.

### Guardian: professional criticism

The Guardian adapter searches its public content index for an exact film-title query within
the film section and review tag, ranks headline matches, then retrieves a bounded set of
public articles. It reads headline and author from JSON-LD and collects paragraphs only from
the Guardian article-body container. Redirects outside Guardian, oversized responses and
weak film matches are rejected.

### Raw evidence, structuring and cache

Each provider first returns a `CriticalResearchBundle` with raw attributed sources and a
`pending` claim status. FirstRoll saves it beneath `.firstroll/criticism` and displays it
immediately. A second endpoint sends small batches to DeepSeek, validates the returned
`critic_reported` claims and replaces the pending bundle only after validation succeeds.

Refreshes preserve previously validated claims when the provider returns the same source
IDs. Missing scenes, techniques, observations or alternative readings remain `null` or
explicitly missing; FirstRoll does not ask DeepSeek to invent them.

## Quick Start

FirstRoll supports Python 3.11 and uses
[uv](https://docs.astral.sh/uv/) for environment and dependency management.

```bash
git clone https://github.com/Luo-Z-Y/FirstRoll.git
cd FirstRoll
uv sync
uv run firstroll
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The frontend and API are served by the same FastAPI process; no separate frontend server
or TMDB credential is required. Full macOS, Windows and Linux instructions are in
[Local Setup](docs/LOCAL_SETUP.md).

### Local settings

Open [http://127.0.0.1:8000/settings](http://127.0.0.1:8000/settings) to configure optional
connectors and manage the private study library. Secrets are write-only from the browser's
perspective and are stored in the Git-ignored `.firstroll/settings.json` file with local-only
permissions.

Environment variables are also supported:

```bash
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-pro
DOUBAN_COOKIE=
FIRSTROLL_EMBEDDINGS=1
FIRSTROLL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
FIRSTROLL_LIBRARY_PATH=
FIRSTROLL_LIBRARY_MANIFEST=
FIRSTROLL_LIBRARY_INDEX=
FIRSTROLL_DOUBAN_MCP_PATH=
```

Use [.env.example](.env.example) as the reference. FirstRoll does not automatically load
an `.env` file; export variables before starting the process or use Settings.

FirstRoll defaults to `deepseek-v4-pro` for stronger long-form synthesis. Set
`DEEPSEEK_MODEL=deepseek-v4-flash` for a faster, lower-cost option; the retrieval,
evidence schema and quality gate are identical for both models.

## Private Study Library

Open **Settings → Study library** to:

- add a PDF, EPUB, Markdown or text document to FirstRoll's private managed library;
- remove a document from FirstRoll without deleting the original source file;
- review the current local catalogue without exposing file paths; and
- rebuild the local PDF search index after catalogue changes.

PDF content can supply page-cited passages to Deep Study after indexing. EPUB, Markdown and
text files are currently catalogue-only.

Existing registered books remain available until the user explicitly removes them. Uploaded
documents, catalogue preferences and derived index data remain under `.firstroll`, which is
excluded from Git.

For manual or automated setups, place documents in `.firstroll/library`, or register absolute
paths in `.firstroll/library.json`:

```json
{
  "documents": [
    "/absolute/path/to/a-film-book.pdf",
    "/absolute/path/to/research-notes.md"
  ]
}
```

Build or rebuild the private index from Settings, or run:

```bash
uv run firstroll-index
```

The current index schema provides:

- page-bounded, token-aware chunks with overlap;
- stable SHA-256-derived chunk IDs;
- document, page, section, topic and language metadata;
- SQLite FTS5 lexical retrieval;
- 384-dimensional local multilingual embeddings;
- reciprocal-rank fusion and diversity selection;
- an FTS-only fallback when local embeddings are disabled or unavailable.

The default embedding model supports multilingual semantic similarity and is downloaded
on the first embedding build. Set `FIRSTROLL_EMBEDDINGS=0` before rebuilding to keep only
the lexical index.

Books, derived chunks, vectors, criticism caches and credentials remain under
`.firstroll`, which is excluded from Git. Only index material you are entitled to use.

## Optional Douban MCP

Douban MCP is an unofficial research adapter, not a core dependency. Install it only in
the private Git-ignored connector directory:

```bash
mkdir -p .firstroll/connectors
git clone https://github.com/moria97/douban-mcp.git .firstroll/connectors/douban-mcp
cd .firstroll/connectors/douban-mcp
npm install
cd ../../..
```

FirstRoll uses the connector's `search-movie` and `list-movie-reviews` tools. A personal
Douban cookie may be required when anonymous requests fail. Never commit or share the
cookie. Provider behaviour may break when Douban changes its pages or access controls.

See [Data Sources](docs/DATA_SOURCES.md) for the source, copyright and model-use policy.

## Letterboxd Configuration

The **Letterboxd** tab uses the local-only public-web adapter described above and requires
no credentials. It is intentionally bounded to public film and review pages, stores its
cache locally and may require maintenance when Letterboxd changes markup or access controls.

### Optional official API

FirstRoll supports Letterboxd's official OAuth client-credentials flow. Request API access
from Letterboxd, then enter the granted **Client ID** and **Client Secret** on the local
Settings page. Alternatively, set `LETTERBOXD_CLIENT_ID` and
`LETTERBOXD_CLIENT_SECRET` before starting FirstRoll.

The official adapter searches `/search` and retrieves popularity-ranked public reviews
through `/log-entries`. It remains separate from the public-web adapter: selecting
**Letterboxd API** never silently falls back to HTML, and selecting **Letterboxd** never uses
OAuth credentials. Credentials remain write-only in `.firstroll/settings.json` and are
never returned to the browser or committed to Git.

## API Overview

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Local process health |
| `GET /api/contract` | Public API summary |
| `GET /api/settings` | Masked local connector status |
| `GET /api/settings/library` | Private catalogue and local index status for Settings |
| `POST /api/settings/library` | Add a document to the managed private library |
| `DELETE /api/settings/library/{document_id}` | Unregister a document without deleting its source file |
| `POST /api/settings/library/rebuild` | Rebuild the private search index locally |
| `GET /api/discovery/status` | Discovery and private-index status |
| `GET /api/discovery/search` | Film identity search |
| `GET /api/discovery/films/{film_id}` | Full film dossier |
| `POST /api/discovery/films/{film_id}/criticism/crossref` | Retrieve and cache matched scholarly abstracts |
| `POST /api/discovery/films/{film_id}/criticism/douban` | Retrieve and cache Douban criticism |
| `POST /api/discovery/films/{film_id}/criticism/letterboxd-web` | Retrieve and cache public Letterboxd reviews locally |
| `POST /api/discovery/films/{film_id}/criticism/guardian-web` | Retrieve and cache Guardian film criticism |
| `POST /api/discovery/films/{film_id}/criticism/letterboxd` | Retrieve and cache official Letterboxd reviews |
| `POST /api/discovery/films/{film_id}/criticism/{provider}/structure` | Structure an already cached provider bundle with DeepSeek |
| `POST /api/discovery/films/{film_id}/study` | Generate an evidence-grounded Deep Study |
| `GET /api/library/status` | Private library and index status |
| `POST /api/analyze` | Analyse an uploaded private clip |

Health check:

```bash
curl http://127.0.0.1:8000/api/health
```

## Repository Structure

```text
FirstRoll/
├── app/
│   ├── backend/
│   │   ├── algorithms/          # inherited and adapted pyCinemetrics analysis
│   │   ├── criticism.py         # Research/criticism adapters, schemas and private cache
│   │   ├── discovery.py         # Wikidata/Wikipedia discovery
│   │   ├── evidence.py          # typed synthesis boundary
│   │   ├── library.py           # private document catalogue
│   │   ├── library_index.py     # chunking, embeddings and hybrid retrieval
│   │   ├── main.py              # FastAPI routes
│   │   ├── settings.py          # local credential store
│   │   └── study_service.py     # DeepSeek synthesis and quality gate
│   └── web/
│       ├── app.js
│       ├── index.html
│       └── styles.css
├── docs/
│   ├── DATA_SOURCES.md
│   ├── LOCAL_SETUP.md
│   ├── PROGRESS.md
│   └── RELEASE.md
├── tests/
├── .env.example
├── pyproject.toml
└── uv.lock
```

## Evidence and Reliability Rules

1. Wikidata and Wikipedia establish identity and attributed context, not intention.
2. A critic claim is a report of that critic's interpretation.
3. A theory passage supplies an analytical framework; it does not describe the film.
4. Without clip evidence, formal claims must remain conditional viewing hypotheses.
5. Creator intention requires an attributable creator statement.
6. Model outputs may cite only evidence identifiers supplied in their request.
7. Missing evidence should produce a verification task or insufficient-evidence result.
8. Private source text is treated as untrusted data, never as model instructions.

## Development and Verification

Run the test suite:

```bash
uv run pytest
```

Run scoped lint and frontend checks:

```bash
uv run ruff check app/backend/library_index.py app/backend/evidence.py \
  app/backend/study_service.py app/backend/main.py tests
node --check app/web/app.js
git diff --check
```

The current verification baseline is recorded in [Project Progress](docs/PROGRESS.md).
Some inherited algorithm modules still contain historical lint warnings and pragmatic
fallback behaviour; these are tracked separately from the new FirstRoll modules.

## Roadmap

| Milestone | Status | Outcome |
|---|---|---|
| Film discovery and dossier | Complete | Key-free identity, context and visible research routes |
| Private RAG foundation | Complete | Token chunking, FTS5, local vectors, hybrid retrieval and citations |
| Attributed criticism | Complete | Crossref, Douban, Letterboxd and Guardian retrieval with structured critic claims |
| Evidence-grounded Deep Study | Complete | Typed evidence, Pydantic output, quality gate and layered UI |
| Clip analysis web migration | Complete | Scene, shot, colour, object and export workflow |
| Clip-to-study evidence bridge | Next | Feed measured scenes, shots and timecodes into synthesis |
| Creator primary-source layer | Planned | Search, store and cite interviews or production records |
| Persistent film projects | Planned | Retain film records, clips, analyses, notes and studies |
| Evaluation suite | Planned | Retrieval relevance, citation accuracy, abstention, latency and cost |

Progress is maintained in [docs/PROGRESS.md](docs/PROGRESS.md), including dated changes
and acceptance evidence. Update that file whenever a milestone changes state.

## Known Limitations

- Deep Study does not yet observe the film itself; it produces viewing hypotheses.
- Creator interviews and production records are not yet automatically collected.
- Crossref may contain no sufficiently matched abstract for a new or rarely studied film.
- Douban MCP is unofficial and may return sparse summaries or stop working.
- Letterboxd public-web retrieval is unofficial and may break when markup or access controls
  change; the official API still requires explicitly granted credentials.
- Guardian search may have no confidently matched review for a film.
- The first semantic retrieval after process start may pause while the local model loads.
- A study may correctly remain labelled insufficient evidence after its one repair pass.
- Some inherited computer-vision dependencies are large and have platform-specific setup.
- Object and shot-scale analysis may use labelled fallbacks when optional models fail.

## Original pyCinemetrics Work

FirstRoll remains indebted to the original pyCinemetrics contributors.

- Source: [CBD-Lab/pyCinemetrics](https://github.com/CBD-Lab/pyCinemetrics)
- Project portal: [movie.yingshinet.com](https://movie.yingshinet.com)
- Research paper: [SoftwareX article](https://www.sciencedirect.com/science/article/pii/S2352711024000578)

When publishing work based on the inherited analysis pipeline, cite the original project
and paper as well as describing FirstRoll's subsequent changes.
