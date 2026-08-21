# Pre-Agent Product Hardening

**Status:** active; Steps 1–3 complete and Step 4 is next

**Machine-readable scorecard:** [`evals/pre_agent_scorecard.json`](../evals/pre_agent_scorecard.json)

This programme stabilises FirstRoll's fixed film-study workflow before any production research Agent
integration. It is intentionally step-based rather than date-based: a step may take one session or
several, and work advances only when its acceptance gate has evidence.

The priorities are, in order:

1. make the product interface clear and dependable;
2. measure and reduce evidence-packet latency; and
3. improve the relevance, diversity, provenance and practical value of packet evidence.

The existing LangGraph core remains a tested, non-production component during this programme. Agent
route integration, model/tool comparisons and cut-over work are out of scope until the final entry
gate passes. This prevents an Agent from obscuring fixed-workflow product, retrieval or measurement
defects.

## Working Method

Each step follows the protected delivery workflow:

1. start from current `origin/master` on one short-lived branch;
2. record the user problem, baseline, hypothesis and acceptance gate before changing behaviour;
3. change one causal layer at a time—do not combine interface, packet-selection and model changes in
   one experiment;
4. run proportionate automated, browser and benchmark checks;
5. review the complete diff and commit only redacted evidence;
6. merge a current green pull request into protected `master`;
7. obtain human approval for that exact sealed production deployment; and
8. verify that live `buildCommit` equals `origin/master` before starting the next step.

A completed step is a safe product checkpoint. Intermediate edits and failing experiments are never
production releases.

## Frozen Starting Point

The historical comparison remains
[`baseline-2026-08-18.json`](../evals/results/baseline-2026-08-18.json) over the five cases in
[`agent_cases.json`](../evals/agent_cases.json):

| Measure | Starting value |
|---|---:|
| Completed cases | 4 / 5 |
| Operational failure rate | 20% |
| Mean quality score over completed studies | 98.94 / 100 |
| P50 / P95 end-to-end latency | 66.409 s / 96.451 s |
| Mean combined study-stage latency | 58.52 s |
| Median / P95 input tokens over completed calls | 7,882.5 / 14,322.25 |

The starting combined study timing did not isolate retrieval, packet assembly or model transport.
Step 3 now supplies the first packet-only reference: 35/35 preparations completed, with cold
P50/P95 of 9,420.905/10,013.910 ms and warm P50/P95 of 138.240/182.306 ms. The current complete run
again completed four of five cases, scored 97.02 on average and recorded end-to-end P50/P95 of
77.679/91.225 seconds. These are starting measurements, not an optimisation claim.

The automated quality score remains a structural, citation, calibration and verifiability proxy; its
high value does not establish factual film-analysis correctness or human usefulness. The reviewed
raw values and provider/cache interpretation remain canonical in [Evaluation](EVALUATION.md).

## Frozen User Journeys

Every interface step exercises the same six journeys at 1,280-pixel desktop and 390-pixel mobile
widths, with keyboard operation included:

1. **Exact discovery to dossier:** resolve the intended film, open its attributed dossier and retain
   a usable director shelf without stale content.
2. **Ambiguous identity confirmation:** require an explicit year-and-director choice for a title such
   as *The Thing* before evidence or study work begins.
3. **Inspect attributed evidence:** distinguish providers, source text, critic claims, theory and
   epistemic boundaries, with working public-source links where applicable.
4. **Generate and inspect Deep Study:** submit a focused question, receive immediate visible feedback
   and inspect a terminal result whose citations resolve to supplied evidence.
5. **Navigate and resume work:** move among Discover, Analyse and Settings and refresh without losing
   the documented summary-only workspace or retaining private evidence.
6. **Recover from sparse evidence or provider failure:** present honest, actionable and retryable
   insufficient-evidence, timeout and degraded-provider states without showing stale output as new.

The local private edition is the primary runtime. The hosted public beta is a regression runtime for
shared interface, identity, evidence and study behaviour; private books and clips remain local.

## Ordered Steps

### Step 1 — Define the scorecard — complete

Freeze the journeys, timing boundaries, baseline, quality rubric, targets, safety policy and Agent
entry gate in a validated repository artefact.

**Acceptance:** the contract is machine-readable, references the existing frozen suite and raw
baseline, distinguishes unmeasured values from claims and has automated consistency coverage.

### Step 2 — Instrument evidence preparation — complete

Add monotonic, redacted measurements for film context, criticism/video cache reads, retrieval
planning, lexical and semantic retrieval, fusion, packet assembly, prompt serialisation, model
transport, validation/repair and end-to-end execution. Inapplicable stages must be marked as skipped,
not silently omitted.

**Acceptance:** every applicable stage has duration and terminal status; instrumentation contains no
prompt, credential, private passage, full review body or model response.

### Step 3 — Capture the measured baseline — complete

Run the unchanged fixed workflow with the new instrumentation. Use five warm packet-only samples per
frozen case after one unrecorded warm-up and two cold processes per case. Run model synthesis only
where needed to establish the controlled end-to-end reference and cost.

```bash
uv run python tools/benchmark_evidence_packet.py \
  --output evals/results/packet-baseline-YYYY-MM-DD.json
```

**Acceptance:** a reviewed, redacted result records packet P50/P95, prompt size, selected/omitted
counts, failures and configuration fingerprint. No optimisation is mixed into this result.

### Step 4 — Improve user-interface hierarchy — next

Use the frozen journeys to improve information order, visual priority, navigation, dossier density
and mobile composition. Preserve the evidence taxonomy and private/public runtime boundary.

**Acceptance:** all six journeys complete without a P0/P1 blocker, stale selection or horizontal
overflow; the interface gives visible feedback within a 300 ms P95 budget.

### Step 5 — Improve user-interface states and accessibility

Make loading, empty, sparse-evidence, degraded-provider, timeout, cancellation and retry states
specific and actionable. Correct keyboard order, focus movement, accessible names, status
announcements and critical contrast defects.

**Acceptance:** no critical accessibility defect remains in the frozen journeys and every terminal
failure has a safe next action.

### Step 6 — Reduce evidence-packet latency

Optimise only measured bottlenecks. Candidates include avoiding repeated cache work, deliberate
embedding warm-up, parallel independent reads, earlier deduplication and bounded serialisation.
Provider acquisition and model transport remain separate timing domains.

**Acceptance:** warm packet P95 is at most two seconds. If the Step 3 baseline exceeds that budget,
the first optimisation checkpoint must reduce it by at least 30%. Quality and selected-evidence
fixtures must not regress.

### Step 7 — Establish packet-quality fixtures

Add a separate packet suite for abundant, sparse, duplicate, multilingual, ambiguous and malicious
retrieved content without altering the five frozen Agent-comparison cases. Define deterministic
provenance, duplication, citation and instruction-containment checks.

**Acceptance:** packet quality is assessable before synthesis and every fixture is safe to commit;
private source text is represented only by synthetic substitutes or aggregate metadata.

### Step 8 — Improve packet selection quality

Implement focus-aware selection, canonical deduplication, justified source diversity, complete
applicable provenance, explicit omission reasons and per-layer token budgets.

**Acceptance:** citation and applicable provenance integrity are 100%, selected duplication is below
10%, instruction containment is 100%, median input is at most 8,000 tokens and P95 input is at most
12,000 tokens.

### Step 9 — Improve Deep Study transparency

Expose packet readiness, safe aggregate evidence counts, completed progress stages, missing evidence
and inspectable citation targets. Add cancellation and bounded retry without publishing prompts,
private passages, hidden reasoning or credentials.

**Acceptance:** a filmmaker can explain what evidence supports the result, what is absent and why a
run failed; the owner-scoped hosted result and local private boundary remain intact.

### Step 10 — Tune synthesis reliability

Hold packet selection fixed while testing prompt reduction, timeout handling and model settings one
variable at a time. Use same-day paired runs and retain operational failures in the denominator.

**Acceptance:** all five final cases produce assessable terminal results, deterministic gate pass
rate remains 100% over completed studies, mean automated quality is at least 96.94 and paired median
end-to-end latency improves by at least 15% without a P95 regression. A provider-reliability claim
requires at least twenty attempts; five cases alone remain a regression fixture.

### Step 11 — Freeze the fixed-workflow baseline

Run the full automated suite, desktop/mobile journeys, cold/warm packet benchmark, adversarial
fixtures, human packet rubric and final fixed workflow evaluation. Review every retained artefact for
private data before committing it.

**Acceptance:** all scorecard targets pass, no P0/P1 defect remains and the newest reviewed JSON
artefact, documentation and progress evidence agree.

### Step 12 — Make the Agent go/no-go decision

Only after Steps 1–11 pass, write the comparison brief for the production Agent. It must identify a
measurable deficiency the fixed workflow still has and compare quality, recovery, latency, cost and
operational complexity under the same frozen contract.

**Acceptance:** production Agent integration starts only after an explicit reviewed go decision. A no-go
leaves the stable fixed workflow in production.

## Human Packet Rubric

Score each frozen case from 1 to 5 on:

- **focus relevance** — evidence directly advances the filmmaker's question;
- **traceability** — evidence type, attribution and applicable URL or private locator are clear;
- **source diversity** — complementary evidence is retained without repetitive padding;
- **epistemic calibration** — observations, reports, frameworks and hypotheses stay separate; and
- **filmmaker actionability** — the packet supports specific close-viewing or formal tests.

A case passes when focus relevance, traceability and filmmaker actionability are each at least 4 and
no dimension is below 3. At least four of the five frozen cases must pass. Human assessment is not
replaced by the automated 98.94 baseline score.

## Measurement Rules

- Use a monotonic clock and the evaluator's linear-interpolation `(n - 1)` percentile method.
- The versioned observability record reports only allow-listed stage names, terminal status,
  aggregate duration, attempts, failures and bounded integer counts. Repeated validation, repair or
  model attempts aggregate under the same stage; mixed success/failure is labelled `degraded`.
- **Cold packet:** first preparation in a fresh process, with process caches empty and the persisted
  local index retained.
- **Warm packet:** preparation after one unrecorded same-case warm-up in the same process.
- Stop packet timing after a validated `EvidencePacket`; exclude provider acquisition and model
  transport.
- Record provider acquisition, model transport, validation/repair and end-to-end latency separately.
- Hold film identities, questions, cached evidence, private-index fingerprint, model, provider,
  timeout and machine constant for paired comparisons.
- Change one variable per comparison.
- Commit counts, durations, safe identifiers and aggregate scores only. Never commit API keys,
  cookies, private books, extracted text, prompts, vectors, criticism caches or uploaded clips.

The JSON scorecard is the enforceable list of targets and statuses. This document explains how to
apply it; `docs/EVALUATION.md` remains the canonical history and replacement protocol for reviewed
benchmark results.
