# Autonomous Research Agent Programme

**Status:** A01 machine-failed and consumed; A02 one-run validation authorised; no Agent production route authorised

## Goal

Build a solid autonomous FirstRoll Agent that can turn a filmmaker's question into a bounded,
evidence-grounded research dossier and practical viewing plan. “Autonomous” means that the system can
identify evidence gaps, choose and sequence permitted actions, reassess after every observation,
validate its own candidate through independent code, repair only what failed and stop when evidence or
budget is exhausted. It does not mean unconstrained browsing, hidden reasoning, unlimited retries or
permission to alter production policy.

The Agent is solid only when it demonstrates useful capability against both the fixed workflow and a
transparent deterministic baseline. Merely selecting a provider, adding source count or wrapping one
model call in a graph does not satisfy this goal.

## Product Capability

The intended local workflow is:

```text
filmmaker question
→ resolve one film identity
→ inspect existing theory, criticism and attributed material
→ formulate typed evidence gaps
→ choose a bounded research action
→ acquire and normalise an independent source
→ reassess gaps and adapt or stop
→ synthesise a cited study
→ audit claims, citations and epistemic strength
→ patch only invalid or weak fields
→ produce traceable viewing and production exercises
→ return the result with an inspectable action ledger
```

Production remains on the fixed Deep Study workflow until every acceptance layer below passes. Clip
analysis remains deferred until the text Agent is accepted.

## Non-Negotiable Boundaries

- The deterministic controller, not retrieved text or a model, owns policy and budgets.
- Every model-proposed gap and tool must come from an allow-list supplied for that turn.
- Existing sufficient packets receive no research call and remain byte-identical.
- A recovered packet cannot pass merely because one website returned several excerpts.
- Providers are attempted at most once per run; failures and time remain in all denominators.
- Credentials, cookies and clients stay outside graph state.
- New acquisition is ephemeral unless a private mode-`0600` evaluation or project artifact is
  deliberately written beneath `.firstroll`.
- Generated prose, prompts, source text and human notes never enter Git reports.
- The Agent owns one initial synthesis plus at most two repairs.
- No hosted route, production cut-over, clip integration or paid validation is implied by local code.

## Evidence-Gap Model

The first foundation replaces a source-count-only stop rule with typed gaps:

| Gap | Meaning | Candidate actions |
|---|---|---|
| `film_specific_evidence` | no attributed criticism, statement or observation supports the film focus | Guardian, Crossref, Letterboxd, Douban or video text |
| `independent_origins` | a recovered packet still relies on fewer than two independent web origins | a different remaining provider |
| `evidence_class_diversity` | film-specific material represents fewer than two epistemic classes | scholarship, attributed video/creator text or criticism |
| `focus_relevance` | selected evidence has insufficient lexical relation to the filmmaker's focus | focus-sensitive scholarship, criticism or video search |

A packet that was already `passed` remains sufficient without extra spend. A packet recovered from
`limited` or `failed` must pass the base quality checks and include at least two independent
film-specific origins. This prevents three Letterboxd excerpts from being described as genuine source
diversity.

The model planner now returns a bounded objective and action, for example:

```json
{"target_gap":"independent_origins","tool":"fetch_crossref_research"}
```

It sees film identity, the focus, safe aggregate gaps, each tool's declared gap capabilities and
provider readiness—not evidence text. The controller rejects a mismatched objective/tool pair; when
no remaining tool can address a gap it stops insufficient without a provider call. A separate
deterministic gap router implements the strongest simple baseline. If the model planner
cannot outperform or more efficiently match that baseline, it will be removed rather than preserved
for architectural appearance.

## Provider Portfolio

The local allow-list currently contains:

- Guardian public review search;
- Crossref matched scholarly abstracts;
- Letterboxd official API or constrained public-web fallback;
- Douban MCP review summaries;
- YouTube and Bilibili descriptions or attributed captions.

Crossref is now available to the Agent rather than only through the manual criticism endpoint. Its
film/director matching and abstract-only boundary remain deterministic. Future providers may be added
only with explicit identity matching, attribution, response-size limits, URL restrictions, failure
classification and tests. General arbitrary web browsing is not an acceptable provider.

## Required Ablations

### A01 — Gap and planner ablation

Compare three packet lanes from one frozen initial packet:

1. no acquisition;
2. deterministic gap routing;
3. model-planned gap routing.

Provider responses are acquired once and shared privately so network sampling cannot favour a lane.
The Agent lane must beat the deterministic lane on blinded diversity/actionability or achieve an
equivalent packet with fewer calls. A tie means that deterministic routing wins. On 28 August 2026,
the owner approved exactly one run with at most three planner calls, five physical provider calls and
three external turns per active lane. The confirmation is bound to committed source, the frozen
canonical identity reference and fresh dated report, private-packet and lock paths. Its first command
attempt stopped before the lock or any paid call because the harness had not loaded the canonical
`film_id`; that preflight failure is retained and the identity binding is now explicit.

The corrected one-run A01 then stayed within every cost limit but failed both active-lane completion
targets. Guardian failed; deterministic routing used Crossref and video text, while model routing used
Crossref and Letterboxd. Each lane reached three independent origins and base packet status `passed`,
but still reported only one film-specific evidence class and exhausted all three turns. The run used
three planner calls and four physical provider calls. No private packet was written, no owner review
is available and A03 remains blocked.

### A02 — Structural-repair ablation

Inject controlled citation and schema faults into otherwise valid synthetic candidates. Compare the
800-token field patch with one complete regeneration. Requested fields must be repaired, accepted
fields must remain exactly equal, all citations must validate, and latency/token savings must be
material under frozen thresholds. The owner separately approved 18 expected and 36 maximum model
calls with zero planner/provider acquisition calls. A01 is now consumed, so A02 is the active
one-run machine authorisation on a separately committed checkpoint.

### A03 — Changed-packet synthesis

Only a packet that passes A01 is retained privately and used here. Compare that exact packet with its
fixed origin; do not reacquire it. The accepted A01 result selects either model planning or the
deterministic router; a model tie never overrides the simpler policy.

The harness schedules ten alternating generations per lane: 20 expected synthesis calls and 60 if
every sample consumes both graph repairs. It permits zero planner/provider calls. Machine acceptance
requires 10/10 completion in both lanes, candidate quality at least `96.94`, candidate-minus-fixed
quality at least `0.0`, use of candidate-only attributed evidence in at least `0.80` of samples,
complete quality/citation/identity/token telemetry, synthesis P50/P95 no greater than `1.10/1.25`,
lifecycle P50/P95 including A01 acquisition no greater than `1.25/1.35`, and total tokens no greater
than `1.25×` fixed.

If those gates pass, only predeclared repetitions 1, 5 and 10 are written privately as blinded
fixed/candidate pairs. The owner must prefer candidate usefulness in at least two pairs, never prefer
fixed evidence responsibility and find no severe candidate grounding concern. Unchanged cases are
controls, not evidence of acquisition benefit. A03 remains blocked until A01 machine/human evidence
selects a packet; its proposed budget is not authorised.

## Capability Stages

1. **Evidence-gap research:** adaptive multi-provider acquisition with an honest diversity gate.
2. **Claim and citation audit:** label important claims as directly supported, reasonable
   interpretation, unsupported or stronger than the source; deterministic citation code remains final.
3. **Targeted editor:** repair only fields or sections named by validation and preserve accepted work.
4. **Filmmaker coach:** turn accepted claims into evidence-linked actions to log, compare, count,
   track, mark or inspect.
5. **Reliability and recovery:** test at least twenty comparable observations per critical strategy,
   retain every failure and measure provider degradation and budget exhaustion.
6. **Durable local pilot:** add owner-scoped checkpointing, cancellation and resume before any hosted
   execution is considered.

Stages may be implemented behind the local flag with synthetic tests, but evidence gates advance in
order. Historical T01 results remain immutable and are not retrospectively upgraded by this
programme.

## Definition of Solid

The local Agent may be called solid only when all of the following are recorded:

- selective zero-call behaviour for sufficient packets;
- adaptive completion or honest insufficiency under provider failure;
- at least two independent origins for every recovered packet;
- measurable value over the deterministic acquisition baseline;
- complete schema, citation, identity and instruction-containment validity;
- provider-backed structural repair evidence with accepted-field preservation;
- no material completion, latency, token or quality regression under frozen targets;
- owner-attested source diversity, focus relevance, traceability, epistemic calibration and
  filmmaker actionability;
- reliable strategy-level evidence rather than one or three favourable draws;
- private, resumable local execution with explicit budgets and cancellation;
- a separately reviewed production decision.

## Current State

The independent-origin assessment, typed planning objectives, deterministic baseline and Crossref
Agent adapter are implemented locally with synthetic coverage. The A01 harness now freezes one
initial packet, shares each physical provider observation across deterministic/model lanes, writes a
one-run private lock before spend and blinds all three packets during owner review. An equal packet
with equal calls explicitly favours the deterministic router.

A default-off local pipeline now connects completed research synthesis to claim audit, one optional
targeted edit, mandatory re-audit and filmmaker coaching. The audit must cover every required central
and section path exactly once, may use only citations already available to that path and cannot call
an interpretation directly supported. At most four weak paths receive one edit. Coaching then uses
only accepted distinct paths and must state one observable action plus an uncertainty boundary. This
finisher has a separate maximum of two audits, one edit, one coach and four model calls; no route or
provider validation exists.

A private durable phase engine also checkpoints research, audit, edit, re-audit and coaching beneath
`.firstroll/autonomous-runs/`. It uses owner matching, hashed filenames, mode-`0700/0600` storage,
atomic replacement and cancellation between phases. An in-flight marker is persisted before a paid
phase; an interrupted phase stops for owner review instead of automatically repeating uncertain
spend. This is local single-device durability, not hosted or multi-instance readiness.

The A02 harness constructs three public synthetic fault classes, alternates three field-patch and
regeneration repetitions per class, and retains every failed output as zero. It checks complete
schema/citation validity, exact equality of every unrequested field, quality non-inferiority, at most
`0.80/0.90` P50/P95 latency ratios, at most `0.60` token ratio and a 36-call hard ceiling. Generated
responses are validated in memory and never written to the report.

No model, planner or provider call was made while implementing the foundation or its harnesses. On
28 August 2026, the owner approved the exact A01 and A02 limits above. A01 consumed three planner and
four physical provider calls, failed its active-lane completion targets and produced no private packet.
A02 is now the only active one-run machine authorisation and requires the committed programme plus its
exact fresh paths. A03 still proposes 20 expected and 60 maximum synthesis calls only after an A01
machine and owner-review pass; it is blocked and not authorised.
