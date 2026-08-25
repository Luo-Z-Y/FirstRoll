# Text-Agent Programme

**Status:** revised implementation complete; repeated paid run awaits explicit budget confirmation

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

For each of the five frozen cases it will:

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
most ten planner and ten external-provider calls across the suite. The evaluator remains fail-closed
until the owner separately confirms this declared budget in
[`text_agent_programme.json`](../evals/text_agent_programme.json).

No paid run is authorised merely by merging this implementation checkpoint.

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

Passing machine targets writes only changed packets to mode-`0600` private storage. The owner then
runs the resumable local review without pasting its evidence elsewhere:

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

**Entry condition:** T01 has a recorded result and retry behaviour is stable.

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
