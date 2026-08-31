# Agent Benchmark Audit and Improvement Plan

**Recorded:** 31 August 2026

**Benchmark subject:** `f582387516e02f7d8c1167a676e0956415af0e2e`

**Status:** historical evidence audited; GuideLLM and lm-evaluation-harness mock-qualified; current native Agent unmeasured

The machine-readable audit is
[`agent-benchmark-audit-2026-08-31.json`](../evals/results/agent-benchmark-audit-2026-08-31.json).
It fingerprints every source report and can be rebuilt with
`tools/audit_agent_benchmarks.py`. Third-party tooling qualification is recorded separately in
[`benchmark-tooling-smoke-2026-08-31.json`](../evals/results/benchmark-tooling-smoke-2026-08-31.json).

## Executive conclusion

FirstRoll has useful benchmark evidence, but it does **not** yet have a passing benchmark for the
current autonomous Agent.

- The fixed workflow has a five-case 5/5 checkpoint at mean quality `98.65`, but five observations do
  not establish reliability.
- The original Agent failed completion and quality.
- The repeated Agent completed 15/15 but failed the frozen P50 and P95 latency ratios.
- The structural revision completed 15/15 and passed aggregate machine targets, but exercised no
  repair, lost its private artefact safely and lowered the only changed packet's study quality by
  `2.28` points.
- A01 did not establish planner/acquisition value and produced no owner-review packet.
- A02 showed a strong targeted-patch signal—9/9 valid versus 4/9 regeneration—but its frozen aggregate
  gate failed and nine samples are not reliability evidence.
- A01R's native `tool_calls`, A02R's 24-sample patch gate, A03, and the autonomous finisher remain
  unmeasured against the configured provider.

GuideLLM and lm-evaluation-harness are now reproducibly usable, but only against local mock or dummy
models in this checkpoint. Their mock latency, throughput and exact-match results are explicitly not
FirstRoll product evidence.

## What was audited

The audit reads immutable redacted aggregates only:

1. fixed synthesis reliability;
2. original fixed-versus-Agent comparison;
3. repeated synthesis comparison;
4. structural-repair revision;
5. A01 acquisition/planner ablation;
6. A02 repair ablation;
7. model-free packet latency;
8. the current autonomous programme contract;
9. third-party tooling smoke evidence.

No prompt, private passage, generated study, reviewer note, packet, API key or provider response is
read or written by the audit tool.

## Current benchmark inventory

### Fixed workflow reference

Source: [`baseline-reliability-2026-08-21.json`](../evals/results/baseline-reliability-2026-08-21.json)

| Measure | Result |
|---|---:|
| Completed cases | 5 / 5 |
| Mean quality | 98.65 |
| P50 / P95 end to end | 55.407 / 62.129 s |
| Model calls | 5 |
| Total tokens | 38,875 |

This demonstrates capability over five frozen cases. It does not meet the programme's minimum of
twenty comparable observations for a reliability claim.

### Original local Agent

Source: [`local-agent-paired-2026-08-24.json`](../evals/results/local-agent-paired-2026-08-24.json)

| Measure | Fixed | Agent |
|---|---:|---:|
| Completion | 5 / 5 | 4 / 5 |
| Mean quality | 97.40 | 94.77 |
| Model calls | 5 | 7 |
| Total tokens | 39,124 | 48,575 |

Outcome: formal machine failure. The additional orchestration did not earn its cost.

### Repeated synthesis

Source: [`text-agent-repeated-2026-08-25.json`](../evals/results/text-agent-repeated-2026-08-25.json)

| Measure | Result |
|---|---:|
| Scheduled/completed per lane | 15 / 15 |
| Agent minus fixed quality | +0.63 |
| P50 latency ratio | 1.100404 |
| P95 latency ratio | 1.993109 |
| Token ratio | 1.186853 |

Outcome: failed frozen latency targets. Parseable invalid drafts could fall into expensive complete
regeneration, producing the unacceptable tail.

### Structural revision

Source:
[`text-agent-structural-repair-2026-08-25.json`](../evals/results/text-agent-structural-repair-2026-08-25.json)

| Measure | Result |
|---|---:|
| Scheduled/completed per lane | 15 / 15 |
| Agent minus fixed quality | −0.44 |
| P50 / P95 latency ratio | 1.003191 / 0.888329 |
| Token ratio | 1.002379 |
| Repair samples observed | 0 |
| Complete private artefact | No |

The only changed case, `the-thing-ambiguous-identity`, averaged fixed `98.25` versus Agent `95.97`, a
`−2.28` delta. Aggregate success therefore did not establish acquisition value. The post-run private
write failed safely, so no owner review exists.

### A01 acquisition and planning

Source:
[`autonomous-agent-acquisition-2026-08-28.json`](../evals/results/autonomous-agent-acquisition-2026-08-28.json)

- three model-planner calls;
- four unique physical provider observations;
- three turns in each active lane;
- deterministic lane failed;
- model lane failed;
- no private packet or human review.

A01 used the historical assistant-content JSON planner. The corrected A01R harness now requires native
`tool_calls`, explicit evidence classes and zero remaining required gaps, but has no paid result.

### A02 controlled repair

Source:
[`autonomous-agent-repair-2026-08-28.json`](../evals/results/autonomous-agent-repair-2026-08-28.json)

| Measure | Targeted patch | Regeneration |
|---|---:|---:|
| Valid outputs | 9 / 9 | 4 / 9 |
| P95 latency | 2.079 s | 39.931 s |
| Tokens | 9,628 | 29,859 |

This is the strongest positive Agent signal. It remains bounded to nine controlled samples, and A02's
mandatory regeneration-completion target failed. A02R is designed to test patch reliability directly
over 24 scheduled samples.

### Packet preparation

Source:
[`packet-latency-prewarm-2026-08-21.json`](../evals/results/packet-latency-prewarm-2026-08-21.json)

| Measure | Result |
|---|---:|
| Completed samples | 35 / 35 |
| Cold P95 after explicit prewarm | 361.549 ms |
| Warm P95 | 182.709 ms |

Packet preparation is not the present latency bottleneck. Model synthesis, provider acquisition and
rare repair paths deserve priority over further packet-assembly optimisation.

## GuideLLM assessment

### What it is suitable for

GuideLLM `0.7.3` can measure an OpenAI-compatible generative endpoint with:

- request latency;
- time to first token (TTFT);
- inter-token latency (ITL);
- token throughput;
- request throughput;
- concurrency and saturation;
- native tool-call turns;
- bounded request/error constraints.

A local mock run exercised four requests and two native tool calls successfully. The initial default
macOS `fork` worker died with signal 11; `spawn`, one worker and disabled tokenizer parallelism fixed
the tooling run. Both the failure and repair are retained in the tooling report.

### What it does not currently measure

FirstRoll has no Agent HTTP route and no OpenAI-compatible product endpoint. The fixed product endpoint
also returns a complete FirstRoll study rather than a generic chat completion. Pointing GuideLLM
directly at DeepSeek would measure the provider, not identity resolution, packet preparation,
authorisation, evidence reassessment, validation, repair or owner-visible latency.

Therefore:

- mock throughput is not FirstRoll throughput;
- a direct provider benchmark is not an Agent benchmark;
- an OpenAI route must not be added to production merely to satisfy a benchmark tool;
- concurrent SaaS load must not be generated without an explicit request and token budget.

A future representative solution is a standalone, loopback-only benchmark adapter. It should expose
only commit-safe synthetic planner or synthesis fixtures, preserve FirstRoll call accounting, reject
external binding and write outputs under `.firstroll`. It must never become an Agent production route.

## lm-evaluation-harness assessment

### What it is suitable for

lm-evaluation-harness `0.4.12` can provide repeatable model-level diagnostics over public fixtures.
FirstRoll now includes a 12-case `firstroll_claim_support` task covering:

- direct framework support;
- theory incorrectly treated as film fact;
- attributed criticism;
- creator-intention overclaiming;
- calibrated hypotheses;
- metadata incorrectly treated as formal observation;
- verified creator statements;
- unverified video context;
- retrieved prompt injection;
- whole-film generalisation from one review;
- alternative readings;
- calibrated central arguments.

The allowed labels match the autonomous claim auditor:

- `directly_supported`;
- `reasonable_interpretation`;
- `unsupported`;
- `stronger_than_evidence`.

The task and local JSONL dataset validate successfully. A dummy model processed all 12 cases, which
qualifies task loading only; its score is not retained as model evidence.

### What it does not replace

A generic model task does not exercise:

- native `tool_calls` parsing and authorisation;
- provider acquisition;
- packet fingerprints;
- FirstRoll citation-path validation;
- graph-owned retries;
- end-to-end latency and cost;
- owner usefulness judgements.

lm-evaluation-harness should be a diagnostic layer beneath A01R–A03, not a replacement gate. Its
standard academic tasks may describe general model competence but do not establish filmmaker value.
Private studies or passages must not be passed through `--log_samples` or committed caches.

## Reproducible no-spend tooling smoke

Run:

```bash
tools/run_benchmark_tooling_smoke.sh
```

The script:

1. pins GuideLLM `0.7.3` and lm-evaluation-harness `0.4.12` through `uvx`;
2. refuses if its fixed loopback port is occupied;
3. starts GuideLLM's named local mock server;
4. uses `spawn` to avoid the recorded macOS fork crash;
5. runs a four-request native tool-call GuideLLM profile;
6. validates both lm-eval task configurations;
7. runs the three-case lm-eval API smoke against that same local mock;
8. verifies request and tool-call counts;
9. writes mode-`0600` output beneath `.firstroll/benchmarks/tooling-smoke`.

It contains no DeepSeek URL, provider key or configurable remote target. The first execution may
download the pinned packages and public GPT-2 tokenizer into the user's tool cache.

Rebuild the redacted benchmark inventory with:

```bash
uv run python tools/audit_agent_benchmarks.py \
  --output evals/results/agent-benchmark-audit-current.json
```

## Improvement priorities

### P0 — Prove causal Agent value

1. **Run A01R under a fresh exact budget.** Verify native tool compatibility, both active lanes,
   origin/class diversity and zero remaining gaps. Then obtain the owner's blinded packet scores.
2. **Run A02R independently.** Require all 24 scheduled patch samples, complete telemetry and strict
   field preservation. This is the nearest path to a supported reliability claim for one Agent
   capability.
3. **Run A03 only after A01R passes.** Freeze the exact accepted packet, make no planner/provider call
   and test whether changed evidence improves studies. Preserve repetitions 1, 5 and 10 for personal
   owner review.

These are more important than broad benchmark scores because they isolate whether the Agent adds
product value.

### P1 — Add model-level grounding diagnostics

After a separate exact approval, run `firstroll_claim_support` against the configured model:

- 12 expected and maximum model requests;
- temperature zero;
- at most 16 completion tokens per sample;
- zero planner and acquisition-provider calls;
- no retries;
- fresh local output path;
- no `--log_samples` in a committed or shared location.

Treat exact-match accuracy as a regression diagnostic only. Expand to at least twenty comparable
cases before using it as model-selection evidence. Add multilingual and mixed-evidence cases before
claiming broad grounding competence.

### P1 — Make GuideLLM representative before measuring throughput

Build a loopback-only benchmark adapter rather than pointing GuideLLM at production. Start with:

1. synchronous native planner calls;
2. one stream only;
3. actual safe planner prompt-length distribution;
4. exact native-call validity as well as TTFT/ITL;
5. complete failed-request and token accounting.

Only after that passes should a separate approval consider concurrency 2 and 4. Saturation sweeps are
not justified against a paid shared API or while production uses one warm application replica.

### P1 — Improve latency observability

Current reports record complete request latency but not provider TTFT or ITL. To locate synthesis
latency accurately:

- add streaming transport instrumentation without exposing token text;
- retain request start, first-token, final-token and validation completion timestamps;
- separate planner, physical provider, synthesis, repair and deterministic-validation latency;
- retain timeouts and invalid responses in end-to-end percentiles;
- avoid treating shared acquisition replay as zero physical latency.

### P1 — Focus optimisation on expensive paths

The current evidence suggests these priorities:

1. preserve targeted structural patching and avoid full regeneration;
2. reduce synthesis input only when citation coverage and human usefulness remain stable;
3. select deterministic routing if model planning cannot beat it;
4. avoid repeated provider calls by freezing observations during comparisons;
5. stop honestly when no provider can close a measured class or origin gap.

Further packet micro-optimisation is lower value while warm packet P95 is `182.709 ms` and synthesis
latency remains tens of seconds.

### P2 — Broaden reliability and human evidence

Before describing the Agent as solid:

- gather at least twenty comparable observations for each retained critical strategy;
- include malformed, timeout, provider-unavailable and safe-stop samples;
- test claim audit, targeted editing, re-audit and coaching against the configured provider;
- perform owner review personally rather than substituting another model;
- record cost, tokens and complete lifecycle latency for every scheduled sample;
- retain the fixed workflow as production until all causal gates pass.

## Suggested benchmark hierarchy

Use different tools for different questions:

| Question | Correct evidence |
|---|---|
| Is packet preparation fast? | Existing FirstRoll packet benchmark |
| Does native planner transport work? | A01R plus bounded GuideLLM planner profile |
| Does model planning add useful evidence? | A01R deterministic/model/human ablation |
| Does the model respect support boundaries? | lm-eval claim-support diagnostic |
| Does targeted patching recover reliably? | A02R |
| Does changed evidence improve studies? | A03 plus owner review |
| Can the serving layer handle concurrency? | GuideLLM against a representative authorised endpoint |
| Is the complete Agent useful and safe? | FirstRoll end-to-end causal and human gates |

No single GuideLLM throughput number or lm-eval accuracy score can answer all of these questions.
