# FirstRoll Architecture Atlas

**Status:** As-built documentation

**Runtime source revision:** `126b606f862569cac8056c4cd5416f7cdf2c5f35`

**Generated with:** [Archify](https://github.com/tt-a1i/archify)

This atlas is the visual entry point to FirstRoll's architecture. It documents what the current
source does, where trust and persistence boundaries sit, and which Agent capabilities remain
experimental. Each rendered HTML file is self-contained: open it directly in a browser, then use
its built-in search, zoom, minimap and export controls. The adjacent JSON file is the typed source
used to generate it.

## Guided views

| Question | Open this view | What it establishes |
|---|---|---|
| What runs where? | [Runtime architecture](architecture/firstroll-runtime.architecture.html) · [source JSON](architecture/firstroll-runtime.architecture.json) | Browser, Azure, Supabase, external-provider and private-local boundaries. |
| What happens during Deep Study? | [Deep Study sequence](architecture/firstroll-deep-study.sequence.html) · [source JSON](architecture/firstroll-deep-study.sequence.json) | Authentication, evidence preparation, quota reservation, synthesis, validation, repair and owner-scoped result retrieval. |
| How does evidence become an answer? | [Evidence dataflow](architecture/firstroll-evidence.dataflow.html) · [source JSON](architecture/firstroll-evidence.dataflow.json) | Canonical identity, adapters, hybrid retrieval, evidence packets, quality gates and the distinction between evidence and instructions. |
| How is the LangGraph experiment bounded? | [Agent lifecycle](architecture/firstroll-agent.lifecycle.html) · [source JSON](architecture/firstroll-agent.lifecycle.json) | Typed phases, application-owned tool authorisation, budgets and terminal outcomes. |
| How does code reach production? | [Delivery workflow](architecture/firstroll-delivery.workflow.html) · [source JSON](architecture/firstroll-delivery.workflow.json) | Branch/PR/CI controls, human release approval, immutable artifacts and rollback. |

## System truth at a glance

| Concern | Current production truth | Local or experimental boundary |
|---|---|---|
| Frontend | Static browser application on Azure Static Web Apps at `firstroll.app`. | Local FastAPI can serve the same browser shell for private development. |
| API | Containerised FastAPI on Azure Container Apps at `api.firstroll.app`. | Local mode additionally exposes private-library and clip-analysis capabilities. |
| Identity | Supabase email/password authentication; bearer tokens protect account operations. | A loopback-only development identity exists for local UI and quota testing. |
| Durable user data | Supabase PostgreSQL with row-level ownership for profiles, preferences and saved films. | Recent searches and some view state remain browser-local conveniences. |
| Deep Study state | Authenticated quota accounting is durable; an active study result is process-local and expires after ten minutes. | Durable study history is not implemented. |
| Retrieval | Hosted evidence uses public film, criticism, scholarly and video providers. | Private books, FTS5 and local embeddings never leave the private edition. |
| Agent | The fixed workflow remains the product path. | LangGraph is default-off, local-only and evaluation-gated. |
| Deployment | GitHub Actions builds the frontend; Azure serves the frontend and API. | An agent may prepare code and evidence but cannot grant production approval. |

## 1. Runtime architecture

The runtime view is the map of deployable units and trust boundaries. Follow solid request edges
from the visitor through Azure Static Web Apps to FastAPI. FastAPI validates Supabase identity for
protected work, reads or writes account-owned PostgreSQL rows through the intended data path, and
calls bounded external adapters. Dashed edges show configuration, local-only access or experimental
paths rather than ordinary production requests.

The most important separation is not frontend versus backend; it is **public hosted data versus
private filmmaker material**. Uploaded clips, managed books, derived vectors and local credentials
stay in the local boundary. The hosted application can retrieve public evidence and run an
authenticated Deep Study, but it does not publish the private library.

The diagram's source-evidence panel contains 17 file and symbol references verified against the
pinned runtime revision. This makes the picture auditable: a reader can move from a node or edge to
the source that justifies it.

## 2. Deep Study request sequence

The sequence view traces one hosted request from browser event to rendered output:

1. The signed-in browser sends the film identity, study focus and bearer token to FastAPI.
2. FastAPI validates the token and creates an owner-scoped transient run.
3. The application canonicalises the film and constructs an `EvidencePacket` from bounded cached,
   public and configured sources.
4. Only after the evidence exists does the quota service reserve the permitted model use.
5. DeepSeek receives the constrained synthesis request.
6. Pydantic/schema checks, citation checks and the deterministic quality gate validate the result.
7. At most one bounded repair is allowed for a repairable draft. Transport timeouts require an
   explicit user retry instead of silently spending another provider call.
8. Redacted progress is streamed over SSE; the final study is fetched through a separate
   owner-scoped result request and rendered by the browser.

Authentication, quota accounting, evidence normalisation and validation are application-owned.
Language generation is probabilistic. Provider failures, insufficient evidence, exhausted quota,
invalid citations and expired transient results therefore have explicit safe-stop positions.

## 3. Evidence dataflow

The dataflow view explains why retrieval is more than a search box. A question and canonical film
identity constrain all subsequent retrieval. Source-specific adapters convert provider output into
normalised records; local retrieval combines lexical FTS5 and multilingual vector similarity; a
bounded evidence-packet builder ranks, deduplicates and records omissions before synthesis.

Retrieved text is **data, not authority**. A review can support a claim, but instructions embedded
inside that review cannot change system policy, call tools or override budgets. The model sees
stable evidence IDs, while deterministic output checks require citations to resolve back to the
supplied packet.

Request-scoped personal provider keys are deliberately absent from the dataflow. They authorise one
provider call in memory and are not evidence, Agent state or stored account content.

## 4. Agent lifecycle

The Agent lifecycle documents the controlled LangGraph experiment, not a production promise. Its
typed phases are normalisation, film/evidence loading, gap planning and application authorisation,
synthesis, validation and terminal reporting. The model may propose a tool; Python policy decides
whether that proposal is permitted and constructs verified arguments.

The experiment is bounded by:

- 8 graph steps;
- 4 planning calls;
- 3 external tool calls, with at most 1 call per provider;
- 12 evidence items and 36,000 evidence characters;
- a 45-second research deadline;
- 1 synthesis call;
- at most 1 repair call; and
- 6 total model calls.

Completion, `needs_user` and `safe_stop` are terminal outcomes. Authentication, credential handling,
ownership and quota reservation remain outside the graph. The fixed workflow stays preferable until
repeated evaluation shows that adaptive acquisition improves completion or evidence quality enough
to justify its extra latency, cost and failure surface.

## 5. Delivery workflow

The workflow view follows a change through a short-lived branch, pull request, automated checks,
merge, release build and human production approval. The approved immutable artifact is deployed to
Azure and then verified. A failed gate stops the release; a failed production verification triggers
rollback rather than a silent rebuild.

Terraform describes Azure infrastructure, but it does not own the Spaceship DNS zone, Supabase
project or application release approval. Those ownership distinctions matter because infrastructure
as code is an execution mechanism, not an authority to expand the deployment scope.

## Validation and known presentation limitation

All five JSON sources pass Archify's deterministic `showcase` profile with **9/9 checks, zero errors
and zero warnings**. The runtime architecture additionally passes repository-evidence validation
with 17 verified references.

Automated browser checks confirm readable projected text, visible viewer controls and successful
captures at the required desktop viewports. They also correctly report a strict containment failure:
these detailed standalone documents scroll vertically instead of fitting an entire diagram into one
screen. No horizontal overflow was detected. This atlas treats scrolling as a documented trade-off
for detail; a future presentation-specific edition can split or compact the views without changing
their architectural claims.

## Regenerating locally

The Archify skill is installed at `/Users/luozhiyang/.codex/skills/archify`. From the FirstRoll
repository root, validate and deliver a source with:

```bash
node /Users/luozhiyang/.codex/skills/archify/bin/archify.mjs validate \
  architecture docs/architecture/firstroll-runtime.architecture.json \
  --quality showcase --repo-root . --json

node /Users/luozhiyang/.codex/skills/archify/bin/archify.mjs deliver \
  architecture docs/architecture/firstroll-runtime.architecture.json \
  docs/architecture/firstroll-runtime.architecture.html \
  --quality showcase --repo-root . --json
```

For the other sources, replace the filename and use `sequence`, `dataflow`, `lifecycle` or
`workflow` as the type. Workflow sources use schema version 2. Re-run browser visual checks whenever
layout or content changes; deterministic validation alone does not prove visual quality.

## Maintenance rule

Update the relevant JSON and regenerate its HTML whenever a documented boundary, request order,
budget, terminal state or deployment gate changes. Keep the pinned runtime revision explicit so
future readers can distinguish an as-built record from a target architecture.
