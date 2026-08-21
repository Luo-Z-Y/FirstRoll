# Film Data and Research Source Policy

FirstRoll separates film identity, criticism and AI-readable evidence. A source being
technically accessible does not automatically make it reliable, redistributable or safe
to send to an LLM.

## Current Source Roles

| Source | FirstRoll role | Required | LLM boundary |
| --- | --- | --- | --- |
| TMDb API | Primary title search, posters, synopsis, runtime, credits and IMDb/Wikidata identity links when configured | No; open fallback remains available | Catalogue fields may enter identity context; display TMDb attribution and review commercial terms before monetisation |
| Wikidata | Key-free fallback title, year, director and structured identity | Yes, with offline fallback | CC0 structured data may enter the identity context |
| Wikipedia | Fallback attributed overview, crew reconciliation and article link | No | CC BY-SA text must retain attribution and licence information |
| Wikimedia Commons | Optional image referenced by a Wikidata item | No | Check the individual file licence before reuse |
| Curated offline catalogue | Demonstration and network fallback | No | May be used inside FirstRoll |
| Douban MCP | Optional Chinese-language review summaries and attributed critic claims | No | Selected summaries may enter DeepSeek claim extraction only after an explicit user action |
| Crossref REST API | Scholarly metadata, abstracts and DOI links | No | Matched abstracts may enter claim extraction after an explicit user action |
| Letterboxd public web | Local-only attributed public reviews | No | Selected public review text may enter claim extraction after an explicit user action |
| Letterboxd API | Optional popularity-ranked public reviews and attributed critic claims | No | Official API review text enters claim extraction only after an explicit user action |
| Guardian public web | Professional film-review articles | No | Selected attributed article text may enter claim extraction after an explicit user action |
| User-provided documents | Private, page-cited study retrieval | No | Allowed only when the user has the necessary rights; documents and derived index remain local |
| DeepSeek | Grounded synthesis over selected evidence | No | Receives the film record, user focus and retrieved excerpts only after the user selects Generate study |

## Catalogue Selection Policy

TMDb is the primary catalogue when `TMDB_BEARER_TOKEN` is configured because its official
application API supplies stronger candidate posters, synopses, runtime, crew roles and external
identity links in a predictable schema. FirstRoll makes one search request and hydrates at most eight
candidates through four concurrent detail calls. It then rechecks release year and director locally;
the model never selects an ambiguous film.

The token remains in the backend environment or the local mode-0600 secret store. It is never sent
to the browser. TMDb records carry provider-qualified `tmdb:{id}` keys plus available IMDb and
Wikidata IDs. FirstRoll displays: “This product uses the TMDB API but is not endorsed or certified by
TMDB.” TMDb permits free non-commercial use with attribution but requires separate commercial-use
review; current deployments must not infer a commercial licence from technical API access.

If the token is absent, Wikidata/Wikipedia is the normal key-free path. If a configured TMDb search
times out or fails, the response records degraded failover before using the open path. An optional
provider therefore improves quality without controlling availability.

## Why IMDb Is an Identity Bridge, Not the Default API

The official IMDb real-time API is available through AWS Data Exchange and supports GraphQL search
and selected title/credit fields. It also requires an AWS account, an approved IMDb subscription,
API and dataset identifiers and SigV4 credentials. FirstRoll retains IMDb title IDs from TMDb or
Wikidata for exact secondary-provider reconciliation, but does not scrape IMDb HTML or impose that
licensed AWS boundary on every installation. A future enterprise adapter can implement the same
provider-qualified contract.

OMDb is not selected as the primary catalogue: it offers convenient title/IMDb lookups but has
shallower crew and poster coverage, and its published usage conditions are a poor match for a hosted
catalogue foundation.

## Why Wikidata Remains the Open Fallback

Wikidata provides key-free structured identity data under CC0. It is suitable for the
availability task FirstRoll must preserve: matching a title, year and director without tying every
installation to a proprietary API account.

Wikidata is not treated as proof of a creator's intentions. Film dossiers label it as an
identity source, preserve the source entity URL, and leave criticism and interpretation
to separately attributed evidence.

When a matching English Wikipedia article exists, FirstRoll retrieves its concise page
summary and displays the article link and CC BY-SA attribution. It does not merge the
summary into Wikidata or relabel it as FirstRoll's own analysis.

## Douban MCP Assessment

The `moria97/douban-mcp` listing exposes movie search and review-related tools through a
local MCP server. It is interesting for Chinese-language perspectives, but it is not a
stable public API contract for FirstRoll because:

- the registry listing marks it as unvalidated;
- it requires a separately built Node runtime, pinned and bundled into the hosted image;
- some functions may require a personal Douban cookie;
- unofficial access can break when Douban changes its pages or anti-automation controls;
- the MCP server's MIT licence covers its code, not the copyright or reuse rights of
  Douban reviews returned through it.

For those reasons it remains optional and never becomes the canonical film identity
provider. The hosted edition uses anonymous access and never requests a visitor cookie; if Douban
requires authentication, the source degrades cleanly instead of collecting credentials. The
implemented adapter attaches review ID, source URL, retrieval time,
language and content-scope labels. The MCP output does not supply reviewer names, so
FirstRoll leaves author empty rather than inventing attribution. It degrades cleanly
when the local server or review endpoint is unavailable.

DeepSeek converts summaries into Pydantic-validated `critic_reported` claims. Scene,
observation, technique, alternative reading and timecode fields remain empty when the
summary does not contain them. FirstRoll stores the private result beneath
`.firstroll/criticism` and links readers back to the original Douban review.

## Letterboxd Sources

### Public web adapter

The local-only public adapter first attempts Letterboxd's IMDb-ID redirect using the IMDb
identifier supplied by Wikidata. This avoids ambiguous slug guesses and resolves the
canonical film page. If no IMDb ID exists, title and title-year candidates are checked, and
JSON-LD director metadata rejects a known wrong-director match.

The adapter collects a bounded number of popular-review links from the canonical film page,
then reads the JSON-LD `Review` object from each public review page. Only HTTPS Letterboxd
hosts are accepted and responses are size-limited. This is unofficial public-page access;
it does not bypass authentication and may require maintenance when Letterboxd changes its
markup or access controls.

### Official API

FirstRoll also supports Letterboxd's documented OAuth API. Users must obtain a Client ID and
Client Secret from Letterboxd and store them locally in Settings or the corresponding
environment variables. This official adapter does not scrape pages or fall back to the
public-web adapter.

The adapter uses client-credentials OAuth, matches a film through `/search`, and requests
public log entries filtered to reviews and ordered by review popularity. It retains the log
entry ID, member attribution, rating, language and source link before DeepSeek extracts
bounded `critic_reported` claims. Multiple provider bundles are stored separately so Douban
and Letterboxd evidence can coexist in a study.

API access and permitted use remain controlled by Letterboxd's approval and terms. FirstRoll
being technically compatible does not itself grant access or reuse permission. The official
and public-web adapters are separate selectable providers and do not silently fall back to
one another.

## Crossref Research

Crossref's public REST API supplies bibliographic metadata deposited by scholarly publishers.
FirstRoll queries for film-title, director and cinema terms, requests records with abstracts,
then locally rejects records without a title match, usable attribution or source URL. Short,
ambiguous titles require additional director or film context. Accepted records retain their
author, venue, publication year, work type and DOI URL.

Crossref metadata locates scholarship; it does not make the abstract a verified description
of the film or a creator statement. Abstract copyright can remain with its publisher or
author, so FirstRoll keeps retrieval bounded, attributed and local.

## Guardian Public Reviews

The Guardian adapter uses the public content index to locate film-section review articles,
then fetches only confidently matched Guardian URLs. Headline and author come from JSON-LD;
article text is restricted to paragraphs inside the Guardian body container. Retrieved text
remains attributed professional criticism and is not treated as direct film observation.

## Planned Research Adapters

Good candidates should be evaluated separately for metadata access and content reuse:

- OpenAlex for locating additional scholarly work when its required API key is configured;
- publisher or newspaper APIs with explicit quotation and LLM terms;
- creator interviews and production records from rights-cleared sources;
- user-owned notes, subtitles and documents stored in the local RAG database.

FirstRoll should link to criticism when full-text reuse is not licensed. It should quote
only within the applicable permission and always preserve attribution.

## Private Library Boundary

`uv run firstroll-index` extracts page-level text into a local SQLite hybrid index. Chunks
use token-aware overlap, stable content IDs and page/section metadata. FirstRoll fuses
FTS5 and local multilingual vector ranks with reciprocal-rank fusion, then applies
document, page and semantic-duplicate diversity limits.
Discover may display relevant passages with the book title and PDF page, but never sends
the original path to the browser. The books and derived index live under `.firstroll`,
which is excluded from Git. Users should index only material they are entitled to use.

Deep Study sends only the retrieved passages shown in the dossier, their book/page
citations, the verified film record and the user's optional focus. Its prompt treats
book passages as analytical frameworks rather than proof about the chosen film, labels
unverified visual claims as viewing hypotheses and rejects unknown citation identifiers.
