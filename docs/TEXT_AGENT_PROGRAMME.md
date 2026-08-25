# Text-Agent Programme

**Status:** one latency-revision comparison budget approved; run not yet consumed; later text stages blocked

## Purpose

The first local Agent comparison mixed two effects: evidence acquisition and variable language-model
writing. The Agent improved the one sparse packet, but separate synthesis draws caused two unchanged
packets to score materially below their fixed controls. The owner therefore selected **REVISE** rather
than authorising production cut-over.

This programme keeps all Agent work local and default-off. It settles the text workflow before any
clip analysis and advances one measurable layer at a time.

## Stage T01 — Agent-Owned Retries and Fair Repeated Comparison

### Retry ownership

The research graph now owns every Agent generation decision:

1. make one initial generation attempt;
2. validate it deterministically;
3. if it fails, make at most two graph-authorised repair attempts; and
4. complete or stop with explicit insufficiency.

`DeepSeekStudyService.generate_once()` never repairs internally. `repair_once()` performs exactly one
targeted repair. This removes the former conflict where the fixed service had already consumed a
repair before the graph entered its own repair node. The existing production fixed workflow retains
its established single internal repair; no product route uses the experimental graph.

The graph-level maximum is three generation model calls per run: one initial attempt plus two repairs.
A passed draft completes even when the final permitted step was just consumed. The total model-call
budget also covers planner calls.

### Isolated comparison

The revised evaluator separates packet preparation, Agent acquisition and synthesis:

```text
fixed packet ───────────────────────────────┐
                                            ├─ same synthesis-only graph and retry policy
fixed packet → bounded acquisition → packet┘
```

For each of the five frozen cases it:

1. prepare and fingerprint the fixed packet once;
2. run the bounded acquisition graph once in `evidence_only` mode;
3. freeze the fixed and candidate packets;
4. generate three independent samples for each packet through the same `synthesis_only` graph;
5. alternate fixed-first and Agent-first order across repetitions; and
6. score every scheduled sample, assigning zero quality to a failure rather than dropping it.

The only lane difference during repeated synthesis is the packet. Identity, model, prompt, validation,
retry policy, machine and provider configuration remain the same. Acquisition latency and planner
cost remain separately visible, and planner tokens are included in the Agent total-token ratio.

Three repetitions reduce the influence of one unusual draw but do **not** support a reliability claim.
At least twenty comparable observations and separately frozen reliability thresholds would still be
required before making one.

### Cost boundary

The full five-case comparison schedules 15 samples per lane. It therefore requires at least 30 paid
synthesis calls. If every sample uses both repairs, the hard maximum is 90 synthesis calls, plus at
most ten planner and ten external-provider calls across the suite. The owner separately confirmed
that budget, and the single authorised run consumed 32 synthesis calls, one planner call and one
external-provider call. Its authorisation is consumed and cannot authorise the separately approved
structural-repair revision.

### Recorded result

The complete redacted result is
[`text-agent-repeated-2026-08-25.json`](../evals/results/text-agent-repeated-2026-08-25.json).

| Measure | Fixed packet lane | Agent packet lane | Gate |
|---|---:|---:|---|
| Completed samples | 15 / 15 | 15 / 15 | Passed |
| Mean automated quality | 97.17 | 97.80 (`+0.63`) | Passed |
| Quality standard deviation | 1.57 | 1.38 | Descriptive |
| P50 latency | 41.881 s | 46.086 s (`1.100404×`) | **Failed** (`≤1.10×`) |
| P95 latency | 49.050 s | 97.762 s (`1.993109×`) | **Failed** (`≤1.25×`) |
| Total tokens | 114,737 | 136,176 including planning (`1.186853×`) | Passed |

All completion, automated quality, citation, identity, instruction, selectivity, packet-change,
provider-repeat, telemetry and cost targets passed. The target packet again moved from `limited` to
`passed` after one 417-token planner choice and one Letterboxd call added three reviews.

Two Agent samples over an unchanged sufficient packet returned invalid initial generations. The
Agent-owned retry recovered both, preserving 15/15 completion, but those calls took 95.411 and
103.249 seconds. Their cost is correctly retained in P95 rather than hidden. P50 also exceeded its
frozen boundary by `0.000404` ratio points. Neither threshold may be rounded away after observation.

The result is therefore **NO-GO under the frozen latency contract**. No private packet snapshot or
human review was produced, and the paid candidate was not rerun.

### T01 latency revision

The owner subsequently asked FirstRoll to continue revising until it finds meaningful Agent value.
That instruction authorises non-paid implementation work, not another model/provider budget or any
hosted route.

The two slow recoveries exposed a concrete defect: when an initial response was parseable but failed
schema or citation validation, the service discarded it. With no valid draft available, the graph's
nominal repair node called `generate_once()` again with the complete 6,926-token prompt and requested
a complete study. The two pairs of model transports consumed `42.739 + 49.344` and
`48.168 + 51.636` seconds.

The revision now:

1. gives Agent initial generation deterministic temperature `0`, while the fixed production method
   retains `0.2`;
2. classifies failures into bounded categories such as empty content, malformed JSON, schema,
   citation, evidence-status and transport failure without retaining response text in telemetry;
3. retains a parseable invalid candidate only in process memory;
4. derives at most four allow-listed invalid field paths from deterministic validation;
5. sends only the candidate sections and evidence classes needed by those paths, then asks for an
   `updates` patch at temperature `0` and at most 800 completion tokens;
6. merges the patch deterministically without regenerating accepted fields and revalidates the
   complete schema, every citation, evidence status and quality gate;
7. permits the final graph repair to patch a second invalid field if validation exposes one; and
8. falls back to one graph-budgeted full regeneration only for malformed, unpatchable or failed
   patches.

Candidates, patches and generated prose never enter safe metrics or versioned reports. Report schema
3 adds only repair strategy, per-strategy P50/P95 and safe failure-category aggregates. Synthetic
transport tests prove
that accepted sections cannot be changed, one or two invalid citations use 800-token field patches,
malformed JSON remains fail-closed and the graph never invokes full regeneration for a patchable
candidate.

This is an implementation candidate, **not measured latency evidence**. Provider latency does not
scale reliably from a token cap, and the exact invalid category from the completed run was not stored.
The old result and `1.10/1.25` thresholds remain immutable. A separate fail-closed revision budget
slot declares the same 30–90 synthesis, ten planner and ten provider-call maxima. On 25 August the
owner confirmed those exact limits for one complete run. The old consumed confirmation cannot
authorise it; this new confirmation is unconsumed and bound to committed tracked code plus fresh
report/snapshot paths, so prior evidence cannot be overwritten.

### Machine targets

- all 15 fixed and all 15 Agent samples complete;
- failures remain in the mean as zero;
- Agent mean automated quality is at least `96.94`;
- Agent minus fixed mean quality is at least `-1.71` points;
- quality-gate, citation, identity, instruction-containment and model-token telemetry ratios are `1.0`;
- already-sufficient packets make zero external calls and retain identical fingerprints;
- the target packet changes and reaches automated `passed` without repeating a provider;
- repeated P50/P95 ratios are at most `1.10/1.25`;
- total Agent tokens, including acquisition planning, are at most `1.25×` fixed tokens.

Passing every machine target would have written only changed packets to mode-`0600` private storage.
That condition was not met, so the following review command remains unavailable for this run:

```bash
uv run python tools/review_text_agent_packets.py
```

The target packet must score at least `3` for source diversity, `4` for filmmaker actionability, `4`
for focus relevance, `4` for traceability and `3` for epistemic calibration. Notes stay private and a
score-only local aggregate is written only after personal attestation. Machine or human success does
not permit hosted or production Agent routing.

## Stage T02 — Bounded Claim and Citation Reviewer

Add a reviewer that labels important statements as directly supported, reasonable interpretation,
unsupported or stronger than the cited source permits. It may suggest a correction but cannot invent
or approve citation identifiers. Deterministic code remains the final citation authority.

**Entry condition:** the revised T01 implementation must pass its separately authorised comparison.
The budget is now approved, but no result exists yet, so T02 remains blocked.

## Stage T03 — Genuine Evidence-Gap and Source-Diversity Reviewer

Replace source-count sufficiency with a stricter view of independent origins, evidence classes,
perspectives and focus relevance. Three excerpts from one website must not be treated as three
independent source types.

**Primary measure:** blinded human diversity and filmmaker-actionability ratings on changed packets.

## Stage T04 — Targeted Weak-Section Editor

Repair only sections named by deterministic validation instead of regenerating an accepted study.
The editor must preserve valid sections, evidence IDs, uncertainty and the filmmaker's original
focus. Its effect is measured separately from acquisition and citation review.

## Stage T05 — Evidence-Grounded Filmmaker Coach

Convert an accepted study into bounded viewing or production exercises. Every exercise must trace to
accepted evidence and state what the filmmaker should log, compare, count, track, mark or inspect.
It cannot add new film facts or silently start research.

## Deferred Work

Clip analysis, multimodal prompting and clip-to-study routing remain explicitly deferred until stages
T01–T05 establish an accepted text baseline. Authentication, quota enforcement, privacy, film identity,
tool authorisation, deterministic citation checks and production deployment remain non-Agent duties.
