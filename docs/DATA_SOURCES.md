# Film Data and Research Source Policy

FirstRoll separates film identity, criticism and AI-readable evidence. A source being
technically accessible does not automatically make it reliable, redistributable or safe
to send to an LLM.

## Current Source Roles

| Source | FirstRoll role | Required | LLM boundary |
| --- | --- | --- | --- |
| Wikidata | Title, year, director and structured identity | Yes, with offline fallback | CC0 structured data may enter the identity context |
| Wikipedia | Attributed overview and article link | No | CC BY-SA text must retain attribution and licence information |
| Wikimedia Commons | Optional image referenced by a Wikidata item | No | Check the individual file licence before reuse |
| Curated offline catalogue | Demonstration and network fallback | No | May be used inside FirstRoll |
| Douban MCP | Optional Chinese-language review summaries and attributed critic claims | No | Selected summaries may enter DeepSeek claim extraction only after an explicit user action |
| User-provided documents | Private, page-cited study retrieval | No | Allowed only when the user has the necessary rights; documents and derived index remain local |
| DeepSeek | Grounded synthesis over selected evidence | No | Receives the film record, user focus and retrieved excerpts only after the user selects Generate study |

## Why Wikidata Is the Default

Wikidata provides key-free structured identity data under CC0. It is suitable for the
first task FirstRoll must solve: matching a title, year and director without tying the
product to a proprietary API account.

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
- it runs locally and requires a separate Node build/configuration;
- some functions may require a personal Douban cookie;
- unofficial access can break when Douban changes its pages or anti-automation controls;
- the MCP server's MIT licence covers its code, not the copyright or reuse rights of
  Douban reviews returned through it.

For those reasons it remains optional and never becomes the canonical film identity
provider. The implemented adapter attaches review ID, source URL, retrieval time,
language and content-scope labels. The MCP output does not supply reviewer names, so
FirstRoll leaves author empty rather than inventing attribution. It degrades cleanly
when the local server or review endpoint is unavailable.

DeepSeek converts summaries into Pydantic-validated `critic_reported` claims. Scene,
observation, technique, alternative reading and timecode fields remain empty when the
summary does not contain them. FirstRoll stores the private result beneath
`.firstroll/criticism` and links readers back to the original Douban review.

## Planned Research Adapters

Good candidates should be evaluated separately for metadata access and content reuse:

- OpenAlex and Crossref for locating scholarly work and stable identifiers;
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
