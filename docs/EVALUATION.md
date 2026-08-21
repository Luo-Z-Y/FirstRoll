# FirstRoll Evaluation

**Last reconciled:** 21 August 2026

**Canonical result directory:** `evals/results/`

This document defines how FirstRoll records quality, latency and failure behaviour. A result is
versioned evidence, not a timeless product claim. The source of truth for each result family is its
newest reviewed JSON artefact committed under `evals/results/`; a packet-only result complements but
does not replace a complete workflow result. Screenshots and copied Markdown tables are explanatory
views only.

The active fixed-workflow improvement sequence, frozen user journeys and Agent entry targets are in
[Pre-Agent Product Hardening](PRE_AGENT_HARDENING.md), backed by the machine-readable
[`pre_agent_scorecard.json`](../evals/pre_agent_scorecard.json). That scorecard governs future work;
it does not replace a measured result or retroactively add unobserved metrics to this baseline.

## Latest Complete-Workflow Baseline

The newest complete result is
[`baseline-2026-08-21.json`](../evals/results/baseline-2026-08-21.json). It evaluates the unchanged
fixed workflow against the five frozen cases in
[`agent_cases.json`](../evals/agent_cases.json). It was recorded at 21 August 2026 14:44:59 UTC
(22:44:59 Singapore time) from source revision `c913bbd`.

### Run configuration

| Field | Recorded value |
|---|---|
| Schema / suite | 2 / `firstroll-agent-comparison-v1` |
| System | Fixed workflow baseline |
| Model | `deepseek-v4-pro` |
| Python/platform | Python 3.11.7 / macOS 26.5.2 arm64 |
| Private library | 7 documents; 4,381 chunks |
| Retrieval | SQLite FTS5 plus `paraphrase-multilingual-MiniLM-L12-v2` embeddings |
| Configured providers | DeepSeek and YouTube |
| Available connector states | TMDb, DeepSeek, Douban, Letterboxd and YouTube available; NYT and Guardian planned |
| Configuration fingerprint | `42f89877219dcb53` |

“Credential absent” in an evaluation fingerprint does not mean that an adapter or cached evidence is
missing. The fingerprint records non-secret configuration state, not source participation in every
case.

### Summary

| Measure | Fixed workflow |
|---|---:|
| Cases attempted | 5 |
| Cases completed | 4 / 5 |
| Operational failure rate | 20% |
| Deterministic quality-gate pass rate | 100% of completed studies |
| Quality acceptance failure rate | 0% of completed studies |
| Mean / median quality score | 97.02 / 97.38 |
| Mean end-to-end latency | 79.452 s |
| P50 / P95 end-to-end latency | 77.679 s / 91.225 s |
| Mean combined study-stage latency | 61.403 s |
| Repair rate | 0% of completed studies |
| DeepSeek calls / total tokens | 5 / 63,764 |
| All-call median / P95 prompt tokens | 10,527 / 14,776.8 |
| Completed-study median / P95 prompt tokens | 9,577 / 14,830.6 |

### Case results

| Case | Challenge | Result | Quality | End-to-end latency |
|---|---|---|---:|---:|
| *Syndromes and a Century* | Formal specificity without clip evidence | Passed | 98 | 79.958 s |
| *In the Mood for Love* | Abundant secondary interpretation | Passed | 93.33 | 94.042 s |
| *Memoria* | Multilingual identity and sound perspective | Passed | 100 | 69.129 s |
| *The Thing* (1982) | Ambiguous title identity | Passed | 96.75 | 76.452 s |
| *We Are All Strangers* | Sparse evidence and honest limitation | Invalid structured response | — | 77.679 s |

The sparse-evidence case consumed one model call but returned no assessable study because DeepSeek's
JSON did not validate. It is an operational study-stage failure, remains in latency and cost totals
and is excluded from completed-study quality denominators.

The previous 18 August result remains available for history. The two runs both completed four of five
cases but failed on different films. The latest mean quality is 1.92 points lower, still above the
scorecard's 96.94 non-inferiority floor. Its P50 is 11.270 seconds higher while P95 is 5.226 seconds
lower. This is not a paired performance comparison: the newest run had substantially fewer prompt
cache hits and different live-provider timing. It establishes a current starting point rather than
an optimisation claim.

## Latest Packet-Only Baseline

[`packet-baseline-2026-08-21.json`](../evals/results/packet-baseline-2026-08-21.json) was recorded at
21 August 2026 14:53:51 UTC from revision `d968110` and configuration fingerprint
`29d00f82075f3756`. It used no model calls: two fresh processes and five post-warm-up samples for
each frozen case produced 35/35 completed packet preparations.

| Packet measure | Cold process | Warm process |
|---|---:|---:|
| Samples | 10 | 25 |
| Mean | 9,513.659 ms | 137.466 ms |
| P50 | 9,420.905 ms | 138.240 ms |
| P95 | 10,013.910 ms | 182.306 ms |
| Minimum / maximum | 9,135.250 / 10,197.685 ms | 82.910 / 186.837 ms |

| Stage | Cold P95 | Warm P95 |
|---|---:|---:|
| Criticism cache | 3.165 ms | 0.471 ms |
| Video cache | 0.496 ms | 0.125 ms |
| Retrieval planning | 10.124 ms | 2.971 ms |
| Lexical retrieval | 138.791 ms | 132.239 ms |
| Semantic retrieval | 9,886.688 ms | 47.355 ms |
| Fusion and selection | 6.009 ms | 4.921 ms |
| Packet assembly | 0.359 ms | 0.121 ms |

The warm P95 is already below the provisional two-second budget. Cold preparation is dominated by
local embedding-model initialisation, while warm preparation is dominated by lexical retrieval; the
actual typed-packet assembly is sub-millisecond. These are measurements, not a claimed reduction,
because no pre-instrumentation packet-only baseline exists.

Every case selected ten theory passages from 211–433 fused candidates. Attributed selection ranged
from zero to twenty items; all current eligible attributed candidates fit, so omission and
truncation totals were zero. Packet JSON shape ranged from 14,022 to 45,004 characters. These counts
measure volume and selection pressure, not relevance, factual correctness or human usefulness.

## Latest UI Hierarchy Checkpoint

[`ui-hierarchy-2026-08-21.json`](../evals/results/ui-hierarchy-2026-08-21.json) records a local Chrome
DevTools Protocol audit at 1,280 × 1,000 and 390 × 844 CSS pixels from revision `d3b3c19`. All six
frozen journeys retained a usable hierarchy with zero P0/P1 blockers and zero horizontal overflow.
Six immediate response observations produced P50/P95 of 7.35/12.05 ms against the 300 ms budget.

The audit made no model calls. It reused the complete workflow result for synthesis coverage and
explicitly defers detailed failure copy, retry, cancellation, keyboard, focus, announcement and
contrast assessment to Step 5. Screenshots remain local acceptance aids; only public fixture IDs and
redacted measurements are versioned.

## Metric Dictionary

| Metric | Definition | Denominator |
|---|---|---|
| Case completion | A study reaches a terminal result that can be quality-assessed | All attempted cases |
| Operational failure rate | Search, identity, detail or study execution fails before an assessable result | All attempted cases |
| Quality-gate pass rate | Completed studies whose deterministic gate accepts the central argument and required sections | Completed studies only |
| Quality acceptance failure rate | Completed studies rejected after the permitted repair policy | Completed studies only |
| Quality score | Weighted proxy for identity, structure, gate result, citation integrity, calibration, verifiability and evidence coverage | Each completed study |
| Repair rate | Completed studies that required the one permitted repair call | Completed studies only |
| End-to-end latency | Search start through terminal success or failure | All attempted cases |
| P50/P95 | Linear-interpolated `(n - 1)` percentiles reported by the evaluator | All attempted cases |
| Model calls/tokens | Provider-reported calls and token use during the run | Complete suite |

Generic wording, a generic central argument and weak causal signalling reduce the deterministic
score. They do not by themselves reject an otherwise supported study. Missing mechanisms and
unsupported central assertions remain blocking because fluent prose cannot substitute for an
explanatory claim tied to evidence.

### Study observability contract

New study results include a schema-versioned `observability` object. It uses a monotonic clock and an
allow-list of stage and count names; it cannot accept prompts, source excerpts, credentials, model
output or exception messages. Each stage reports `completed`, `failed`, `degraded`, `skipped` or
`not_run`, aggregate milliseconds, attempts and failures. The complete stage order is film context,
criticism cache, video cache, retrieval planning, lexical retrieval, semantic retrieval, fusion and
selection, packet assembly, prompt serialisation, model transport, validation/repair and end to end.

Provider-reported prompt, completion and total tokens are bounded integer counts. The evaluator
retains this record as `study_observability`; the latest result contains a complete trace for each of
its four assessable studies. Failed callers retain the safe trace in server logs rather than the HTTP
error body. The historical 18 August baseline predates the schema and remains unchanged; neither
run's combined `study` timing may be presented as a packet-only measurement.

## What the Score Does Not Establish

The automated score is a structural, citation, calibration and verifiability proxy. It does not
prove that an unseen shot, edit, sound or performance actually occurs in the film. Until measured
clip evidence enters the study packet, film-form statements remain hypotheses to verify while
watching. Five cases are sufficient for a regression fixture, not for a statistically stable model
or provider reliability estimate.

## Frozen Evaluation Contract

Every fixed-workflow/Agent comparison must:

1. reuse the same film identity, question and challenge in `evals/agent_cases.json`;
2. preserve ambiguous-title confirmation rather than silently selecting a candidate;
3. record a non-secret configuration fingerprint, provider states and index dimensions;
4. report operational and quality failures separately;
5. retain per-stage and end-to-end latency, citations, repair use, model calls and tokens;
6. treat retrieved instructions as untrusted evidence, never as tool authorisation;
7. save safe failure as a valid behavioural result where evidence is insufficient; and
8. compare the production fixed workflow and Agent under the same rubric before a cut-over.

## Packet-Only Baseline Protocol

Measure local packet preparation without spending model tokens or writing packet contents:

```bash
uv run python tools/benchmark_evidence_packet.py \
  --output evals/results/packet-baseline-YYYY-MM-DD.json
```

The default protocol reuses the five frozen identities/questions, resolves their canonical IDs from
the reviewed fixed-workflow baseline, runs two fresh cold processes and one unrecorded warm-up plus
five measured warm samples per case. Film resolution happens before the packet clock. The report
contains only stage observations, aggregate packet shape, selected/unselected theory counts,
attributed candidate/selection/omission/truncation totals, public IDs and a non-secret configuration
fingerprint; the harness rejects film queries, questions, titles, directors and evidence-text fields
before writing. It never invokes `DeepSeekStudyService.generate` and records zero model calls.

A packet result complements rather than replaces the complete workflow baseline. Keep cold and warm
samples separate: cold semantic retrieval includes process/model initialisation, while warm samples
measure repeated preparation with the embedding model already resident.

## Updating the Baseline

Run the evaluator from the repository root with the configured local environment:

```bash
uv run --extra dev python tools/evaluate_workflow.py \
  --output evals/results/baseline-YYYY-MM-DD.json
```

Then:

1. inspect every case result and confirm no key, prompt, private passage or full review body appears;
2. keep the previous artefact for historical comparison;
3. name the new file with its evaluation date under `evals/results/`;
4. update this document's “Latest Complete-Workflow Baseline” tables directly from that JSON;
5. add a dated entry to `docs/PROGRESS.md` explaining policy or configuration changes; and
6. commit the case fixture, evaluator, result and documentation together when any contract changed.

Do not overwrite a historical result or update only the README table. A baseline is reproducible
only when its cases, policy, configuration fingerprint and raw aggregate record travel together.
Packet-only measurements follow the cold/warm and redaction rules in the Pre-Agent scorecard and
must remain distinguishable from provider acquisition and model transport.
