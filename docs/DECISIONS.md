# FirstRoll Architecture Decision Register

**Decision owner:** FirstRoll maintainer  
**Last reconciled:** 19 August 2026

This register captures the major decisions that shape the current product. It does not attempt to
record every CSS or parsing implementation detail. A choice belongs here when changing it would
alter trust boundaries, persistence, deployment, evidence semantics, provider policy, cost or the
public API.

## Decision Index

| ADR | Decision | Status | Main trade-off |
|---|---|---|---|
| 001 | Evolve pyCinemetrics with preserved attribution | Accepted | Faster foundation versus inherited complexity |
| 002 | Local-first private edition plus constrained hosted beta | Accepted | Private depth versus public convenience |
| 003 | Split static frontend and FastAPI service across Azure and Render | Accepted | Explicit boundary and fast shell versus multi-platform configuration |
| 004 | Use Wikidata identity and explicit ambiguity confirmation | Accepted | Correct identity versus one-click speed |
| 005 | Use bounded provider adapters, not unconstrained LLM browsing | Accepted | Provenance and control versus breadth |
| 006 | Type evidence by epistemic role | Accepted | Honest uncertainty versus simpler prose generation |
| 007 | Keep private RAG in local SQLite FTS5 and embeddings | Accepted | Privacy and portability versus shared hosted search |
| 008 | Use DeepSeek structured output, deterministic validation and one repair | Accepted | Reliability versus latency and model cost |
| 009 | Use Supabase bearer verification and atomic quota RPCs without service-role keys | Accepted | Least privilege versus an extra network dependency |
| 010 | Stream allow-listed SSE progress and fetch the full result separately | Accepted | Privacy and authentication versus transient run state |
| 011 | Keep the bounded LangGraph Agent behind a production gate | Accepted | Measured benefit versus premature orchestration complexity |
| 012 | Keep clip analysis local in the public beta | Accepted | Privacy and feasible hosting versus no hosted visual analysis yet |
| 013 | Make secondary providers optional and independently degradable | Accepted | Resilience versus uneven evidence coverage |
| 014 | Avoid durable study/project storage in the beta | Accepted, temporary | Smaller data-risk surface versus no history/resume |

## ADR-001: Evolve pyCinemetrics with preserved attribution

**Status:** Accepted  
**Date:** Project inception

### Context

pyCinemetrics already supplied working shot, colour, object and shot-scale analysis. Replacing it
would delay the film-study product and erase the lineage of the computational foundation.

### Decision

Develop FirstRoll as an independent evolution in the same Git history, retain the GPL-3.0 licence,
the `upstream` remote and explicit README attribution, while moving new web, discovery, research and
evidence code under the FirstRoll identity.

### Options considered

| Option | Benefit | Cost |
|---|---|---|
| Preserve and adapt upstream | Reuses tested film analysis and preserves history | Carries large dependencies and historical code style |
| Clean-room rewrite | Uniform architecture | High schedule risk and duplicated work |
| Treat upstream as a remote service | Isolates dependencies | Adds deployment and data-transfer complexity |

### Consequences

- Inherited algorithms remain attributable and reviewable.
- New code must coexist with heavyweight model assets and pragmatic fallbacks.
- Releases must preserve upstream notices and never push FirstRoll changes to `upstream`.

### Revisit when

Individual inherited modules can be replaced with verified, licence-compatible implementations
without losing measured behaviour.

## ADR-002: Local-first private edition plus constrained hosted beta

**Status:** Accepted  
**Date:** 15 August 2026

### Context

The deepest product requires private books, extracted text, embeddings, provider credentials and
film clips. A public site is still important for access, demonstration and film discovery.

### Decision

Maintain two explicit runtime modes. Local mode enables the private library, connector settings and
clip analysis. Hosted public mode publishes discovery, the 3D shelf and authenticated quota-bounded
Deep Study, but returns 404/503 for private or expensive local features.

### Alternatives considered

| Option | Privacy | UX | Operational cost |
|---|---|---|---|
| Local only | Strong | Installation required | Low hosted cost |
| Upload all private material | Weakest | Seamless across devices | Highest storage/compliance cost |
| Two explicit modes | Strong for private material | Public discovery plus deeper local workflow | Moderate complexity |

### Consequences

- “Local-first” is a data-placement rule, not a claim that no website exists.
- Backend gates, not hidden buttons, enforce the mode boundary.
- Some features intentionally differ between the Render and local editions.

### Revisit when

Encrypted user-owned storage, deletion policy, consent and operating budget justify hosted private
projects.

## ADR-003: Split static frontend and FastAPI service across Azure and Render

**Status:** Accepted  
**Date:** 15 August 2026

### Context

The frontend should load even when a free backend instance is asleep. The API also needs Docker for
Python and the optional Douban MCP runtime.

### Decision

Deploy the browser bundle through Azure Static Web Apps and FastAPI as a separate Render Docker Web
Service from `master`. Inject the API origin at static build time and configure exact CORS origins
in the API. Define the planned Render-to-Azure Container Apps migration in Terraform without
importing the existing Static Web App during the first infrastructure milestone.

### Options considered

| Option | Assessment |
|---|---|
| One combined Web Service | Simpler origin model, but every page load waits for backend cold start |
| Separate Azure static and Render API services | Faster shell and explicit boundary; requires CORS and multi-platform operations |
| Serverless functions | Poor fit for heavyweight Python/provider runtime and longer study requests |

### Consequences

- Public values are supplied to Azure's frontend build and the Render backend with different
  variable names.
- Bearer and request-scoped-key headers must be explicitly allowed by CORS.
- The backend root identifies the API instead of serving a second visitor website.

### Revisit when

The Container Apps migration is complete and `api.firstroll.app` has passed the rollback window.

## ADR-004: Use Wikidata identity and explicit ambiguity confirmation

**Status:** Accepted  
**Date:** 15 August 2026

### Context

Film titles are not unique. Choosing the first search result can attach reviews, crew, videos and a
study to the wrong work.

### Decision

Use Wikidata IDs as the canonical discovery identity, validate title/year/director signals and
require a bounded browser choice whenever more than one candidate remains. IMDb identity is used
where available to reconcile provider records; provider-local titles alone are insufficient.

### Alternatives considered

| Option | Risk |
|---|---|
| Always choose first result | Fast but silently wrong for remakes and reused titles |
| Ask the model | Non-deterministic and difficult to audit |
| Explicit identity confirmation | One extra action but preserves downstream provenance |

### Consequences

- Discovery can interrupt instead of pretending certainty.
- Every downstream bundle is keyed to a canonical film ID.
- Multilingual title matching remains a provider-adapter responsibility.

## ADR-005: Use bounded provider adapters, not unconstrained LLM browsing

**Status:** Accepted  
**Date:** 8–14 August 2026

### Context

Critical writing comes from sources with different APIs, markup, identity conventions and failure
modes. Asking a model to “research the web” would obscure provenance and make cost, safety and
reproduction difficult.

### Decision

Implement one bounded adapter per provider, with an identity check, response-size/time boundary,
normalised attributed record and typed failure. Retrieval and model-based structuring are separate
operations.

### Alternatives considered

| Option | Provenance | Maintenance | Coverage |
|---|---:|---:|---:|
| Model browsing | Weak | Hidden provider coupling | Broad but unpredictable |
| One generic scraper | Medium | Brittle shared parser | Uneven |
| Provider adapters | Strong | More explicit code | Bounded and testable |

### Consequences

- Markup changes can break one source without breaking the platform.
- Provider details and repair techniques are documented independently.
- Acquired reviews remain secondary evidence, never direct observation.

## ADR-006: Type evidence by epistemic role

**Status:** Accepted  
**Date:** 12 August 2026

### Context

A film record, textbook framework, critic interpretation, creator statement, measured clip and model
hypothesis do not support the same claims. A single untyped context block encourages fluent
overstatement.

### Decision

Build an inspectable `EvidencePacket` with explicit evidence types, source IDs, locators, permitted
claims and boundaries. Require the final study to distinguish critic reports, theory explanations,
hypotheses, mechanisms, alternatives and verification tasks.

### Alternatives considered

| Option | Assessment |
|---|---|
| Concatenate all text | Simplest prompt, weakest epistemic control |
| Retrieval metadata only | Better attribution but no permitted-claim boundary |
| Typed evidence packet | More schema work, strongest validation and inspectability |

### Consequences

- Citation validators can reject invented source IDs.
- Theory can define a concept but cannot prove that a film uses it.
- Without clip evidence, formal claims remain viewing hypotheses.

## ADR-007: Keep private RAG in local SQLite FTS5 and embeddings

**Status:** Accepted  
**Date:** 7–12 August 2026

### Context

The source books are private and potentially copyrighted. Retrieval needs page citations,
multilingual semantics and a distributable setup without a hosted vector account.

### Decision

Extract and chunk PDFs locally, store canonical chunks in SQLite, use FTS5 BM25 plus optional local
Sentence Transformer embeddings, fuse rankings and return page-cited excerpts. Rebuild atomically
and exclude all derived data from Git.

### Options considered

| Option | Privacy | Operations | Search quality |
|---|---:|---:|---:|
| Hosted vector database | Lower | Account/service required | Strong semantic search |
| FTS5 only | Strong | Simple | Weaker multilingual conceptual matches |
| Local hybrid index | Strong | Larger first build | Lexical plus multilingual semantic recall |

### Consequences

- First build may download and load an embedding model.
- SQLite is excellent for one device, not a shared multi-user corpus.
- EPUB/Markdown/text can be catalogued, while the current extractor indexes PDFs.

## ADR-008: Use DeepSeek structured output, deterministic validation and one repair

**Status:** Accepted  
**Date:** 7–18 August 2026

### Context

Early prose was generic and difficult to verify. Free-form retries could increase cost without a
clear acceptance boundary.

### Decision

Use DeepSeek Pro by default for the local study, request a Pydantic-compatible structure, validate
citations, score specificity/calibration/mechanisms deterministically and permit at most one repair.
Generic wording and weak causal signalling lower quality scores; missing mechanisms and unsupported
central assertions remain blocking.

### Alternatives considered

| Option | Assessment |
|---|---|
| Free-form article | Natural presentation but weak machine validation |
| Reject every wording defect | High false-rejection rate |
| Structured draft plus scored gate | More code, clearer distinction between prose quality and safety |

### Consequences

- A study can complete with explicit limitations instead of looping.
- Quality scores are proxies for structure and grounding, not proof that unseen film form is true.
- Model latency remains the largest fixed-workflow cost.

## ADR-009: Use Supabase bearer verification and atomic quota RPCs without service-role keys

**Status:** Accepted  
**Date:** 15 August 2026

### Context

Hosted model calls cost money and must be tied to real user sessions. Concurrent requests must not
overshoot account or demo limits. Shipping a service-role key would unnecessarily enlarge impact.

### Decision

Use Supabase passwordless email sessions, verify each bearer through Supabase Auth and call two
`authenticated`-only `SECURITY DEFINER` RPCs with the user's token and publishable key. Store only
UUID/day/counters. Serialise reservations with a per-day advisory transaction lock.

### Alternatives considered

| Option | Assessment |
|---|---|
| In-memory counters | Lost on restart and inconsistent across instances |
| Service-role writes | Powerful but violates least privilege |
| User-token RPCs | Durable, atomic and least privilege; adds Supabase dependency |

### Consequences

- Three account calls and thirty demo calls per UTC day are enforced atomically.
- A call is charged at reservation, even if DeepSeek later fails.
- Prompts and studies never enter Supabase quota tables.

## ADR-010: Stream allow-listed SSE progress and fetch the full result separately

**Status:** Accepted  
**Date:** 18 August 2026

### Context

Deep Study can take tens of seconds. The browser needs meaningful progress but must never receive
hidden reasoning, private passages, credentials or raw provider errors in a trace stream.

### Decision

Use an authenticated POST whose response body is SSE. Project internal work onto a fixed event and
message vocabulary. Store the complete result separately under a run UUID and owner UUID; require a
second authenticated GET after `run_completed`.

### Alternatives considered

| Option | Assessment |
|---|---|
| Poll only | Simple but less responsive and repeats requests |
| Native `EventSource` | Automatic reconnect but cannot attach the required bearer header cleanly |
| WebSocket | Unnecessary bidirectional operational surface |
| Fetch-readable SSE | Fits one-way progress and authenticated POST |

### Consequences

- Public progress has a small auditable schema and fixed copy.
- The result store is process-local, capped at 50 and expires after ten minutes.
- Durable or multi-instance runs require a new owner-scoped store and resume protocol.

## ADR-011: Keep the bounded LangGraph Agent behind a production gate

**Status:** Accepted  
**Date:** 18 August 2026

### Context

LangGraph can make tool choice, interrupts and bounded recovery explicit, but installing a framework
does not prove better answers. Agency adds latency, cost, persistence and failure surface.

### Decision

Implement and test the graph core with fake service interfaces, deterministic tool authorisation,
bounded reducers and explicit terminal states. Keep the fixed workflow as production and fallback
until a real adapter runs the same frozen cases and demonstrates a justified gain.

### Alternatives considered

| Option | Assessment |
|---|---|
| Immediate Agent cut-over | Fast demonstration, no trustworthy comparison |
| Never use an Agent | Simpler, cannot adapt research actions to evidence gaps |
| Feature-gated measured adoption | More work, evidence-based decision |

### Consequences

- The repository contains an Agent core that is not falsely described as the public execution path.
- Production adapters, durable checkpoint ownership and Agent evaluation remain required.
- Model-proposed tools never bypass deterministic authorisation.

## ADR-012: Keep clip analysis local in the public beta

**Status:** Accepted  
**Date:** 15 August 2026

### Context

Clip analysis uses large computer-vision dependencies, user-supplied media and potentially long CPU
or GPU work. The Render beta has an ephemeral filesystem and limited free compute.

### Decision

Enable `/api/analyze` locally by default and return 503 in public mode unless an explicit future
deployment enables it. Keep uploads temporary and remove them after analysis.

### Consequences

- Film clips remain on the user's machine in the supported workflow.
- The hosted product cannot yet provide scene-by-scene visual analysis.
- A future hosted design requires upload limits, job storage, deletion, malware/media validation,
  worker isolation and a cost model.

## ADR-013: Make secondary providers optional and independently degradable

**Status:** Accepted  
**Date:** 7–15 August 2026

### Context

Douban MCP and public-web adapters are unofficial; official APIs may require credentials or return no
match. Treating any one provider as core would make discovery fragile.

### Decision

Keep Wikidata film identity independent of criticism. Represent provider readiness and failure in
the UI, cache each bundle separately and let Deep Study proceed with available evidence or report
insufficiency.

### Consequences

- A provider outage reduces breadth instead of taking down the film dossier.
- Results differ by configured credentials and current public availability.
- Provider-specific technical details and limitations must remain documented.

## ADR-014: Avoid durable study/project storage in the beta

**Status:** Accepted, temporary  
**Date:** 18 August 2026

### Context

Persisting prompts, evidence, studies, clips and notes would create deletion, ownership, retention,
export and breach responsibilities. The immediate goal is to validate study quality and workflow.

### Decision

Do not create hosted film-project or study-history tables yet. Keep only Supabase account/quota data
durable; keep final streamed results in a bounded ten-minute process store.

### Consequences

- Refreshing after expiry or backend restart loses the generated result.
- Horizontal scaling and resume are not supported.
- The data model remains small while product requirements are still changing.

### Revisit when

The product specifies project ownership, retention, deletion, export, encryption, multi-device sync
and the legal basis for retaining user-submitted material. Any replacement must include a migration,
RLS policy, owner checks, operational runbook and deletion tests.

## How to Add or Change a Decision

1. Add a numbered entry to the index with `Proposed` status.
2. State the constraint and at least two credible alternatives.
3. Record privacy, cost, reliability and maintenance consequences.
4. Link the implementation and acceptance evidence in `docs/PROGRESS.md`.
5. Mark the old ADR `Superseded` rather than rewriting its historical decision.
