# FirstRoll Evaluation

**Last reconciled:** 21 August 2026

**Canonical result directory:** `evals/results/`

This document defines how FirstRoll records quality, latency and failure behaviour. A result is
versioned evidence, not a timeless product claim. The source of truth is the newest reviewed JSON
artefact committed under `evals/results/`; screenshots and copied Markdown tables are explanatory
views only.

The active fixed-workflow improvement sequence, frozen user journeys and Agent entry targets are in
[Pre-Agent Product Hardening](PRE_AGENT_HARDENING.md), backed by the machine-readable
[`pre_agent_scorecard.json`](../evals/pre_agent_scorecard.json). That scorecard governs future work;
it does not replace a measured result or retroactively add unobserved metrics to this baseline.

## Latest Versioned Baseline

The newest result currently present in the repository is
[`baseline-2026-08-18.json`](../evals/results/baseline-2026-08-18.json). It evaluates the production
fixed workflow against the five frozen cases in
[`agent_cases.json`](../evals/agent_cases.json). Its UTC `recorded_at` value is
17 August 2026 18:54:33, which falls on 18 August in the project's Singapore timezone.

If a later run has been completed elsewhere, it is not the versioned baseline until its complete,
redacted JSON artefact is reviewed and committed. Documentation must not reconstruct new metrics
from memory or an image.

### Run configuration

| Field | Recorded value |
|---|---|
| Suite | `firstroll-agent-comparison-v1` |
| System | Fixed workflow baseline |
| Model | `deepseek-v4-pro` |
| Python/platform | Python 3.11.7 / macOS 26.5.2 arm64 |
| Private library | 7 documents; 4,381 chunks |
| Retrieval | SQLite FTS5 plus `paraphrase-multilingual-MiniLM-L12-v2` embeddings |
| Configured providers | DeepSeek and YouTube |
| Available without stored credentials | Douban and Letterboxd adapters |
| Configuration fingerprint | `e648c6a826485971` |

“Credential absent” in an evaluation fingerprint does not mean that a provider adapter is missing.
For this run, Douban was available through anonymous MCP operation and public Letterboxd acquisition
did not require official OAuth credentials. The fingerprint records credential configuration, not
whether cached evidence from those providers was present.

### Summary

| Measure | Fixed workflow |
|---|---:|
| Cases attempted | 5 |
| Cases completed | 4 / 5 |
| Operational failure rate | 20% |
| Deterministic quality-gate pass rate | 100% of completed studies |
| Quality acceptance failure rate | 0% of completed studies |
| Mean quality score | 98.94 / 100 |
| Median quality score | 99.5 / 100 |
| Mean end-to-end latency | 65.798 s |
| P50 / P95 end-to-end latency | 66.409 s / 96.451 s |
| Repair rate | 0% of completed studies |
| DeepSeek calls / total tokens | 4 / 46,950 |

### Case results

| Case | Challenge | Result | Quality | End-to-end latency |
|---|---|---|---:|---:|
| *Syndromes and a Century* | Formal specificity without clip evidence | Passed | 100 | 77.212 s |
| *In the Mood for Love* | Abundant secondary interpretation | Passed | 96.75 | 31.080 s |
| *Memoria* | Multilingual identity and sound perspective | DeepSeek timeout | — | 101.261 s |
| *The Thing* (1982) | Ambiguous title identity | Passed | 99 | 53.029 s |
| *We Are All Strangers* | Sparse evidence and honest limitation | Passed | 100 | 66.409 s |

The *Memoria* attempt had no quality outcome because the study-stage DeepSeek call timed out. It is
an operational failure and remains in the latency denominator; it is not counted as a rejected
study.

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
4. update this document's “Latest Versioned Baseline” tables directly from that JSON;
5. add a dated entry to `docs/PROGRESS.md` explaining policy or configuration changes; and
6. commit the case fixture, evaluator, result and documentation together when any contract changed.

Do not overwrite a historical result or update only the README table. A baseline is reproducible
only when its cases, policy, configuration fingerprint and raw aggregate record travel together.
Packet-only measurements follow the cold/warm and redaction rules in the Pre-Agent scorecard and
must remain distinguishable from provider acquisition and model transport.
