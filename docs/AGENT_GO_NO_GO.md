# Production Agent Go/No-Go Brief

**Status:** owner-approved **GO** for the bounded local comparison; production cut-over remains
**NO-GO**

## Recorded Decision

On 24 August 2026, the repository owner authorised the default-off local adapter and paired evaluation
by directing FirstRoll to “go local first”. This completes Step 12 without claiming that LangGraph
improves FirstRoll and without enabling a hosted or production Agent route.

The **GO** authorises a production-compatible `ResearchGraphServices` adapter behind a default-off flag
and a local paired evaluation. It does not authorise public traffic, a route cut-over, broader tool
access, durable hosted execution or removal of the fixed fallback. A **NO-GO** leaves the tested graph
core dormant and the fixed workflow unchanged.

## Adapter Checkpoint

The default-off local adapter is now implemented over the existing film detail, fixed packet,
Guardian/Douban/Letterboxd/video and DeepSeek services. It uses the unchanged packet-quality result as
its sufficiency decision: a passing packet makes zero planner/external calls, while a limited packet
may enter the bounded graph policy. The planner receives aggregate issue/count fields but no evidence
text. New attributed sources remain ephemeral, then pass through unchanged packet selection and
synthesis. No Agent HTTP route is registered.

This is implementation evidence only. A real frozen-suite run, human Agent-packet review, latency,
token and provider-recovery result remain unmeasured and cannot be inferred from contract tests.

## Measured Deficiency

The fixed workflow passes every machine target and four of five human packet cases. The one failed
case is the ambiguous-identity case:

| Human packet dimension | Score | Passing requirement |
|---|---:|---:|
| Focus relevance | 4 | At least 4 |
| Traceability | 5 | At least 4 |
| Source diversity | 2 | At least 3 |
| Epistemic calibration | 5 | At least 3 |
| Filmmaker actionability | 3 | At least 4 |

This is a narrow, measured deficiency: an identity-safe and well-calibrated packet can still lack
complementary film-specific evidence and therefore leave its close-viewing method too generic. It is
not evidence that every study needs an Agent.

## One Causal Hypothesis

> When the existing packet fails a deterministic sufficiency check, allowing the bounded graph to
> acquire at most two previously unattempted attributed public sources will raise the failed case's
> source-diversity score from 2 to at least 3 and filmmaker-actionability score from 3 to at least 4,
> without changing identity resolution, theory retrieval, packet selection, synthesis or validation.

The isolated causal layer is **gap-directed attributed-source acquisition**. Prompt tuning, model
changes, theory ranking, clip analysis and UI changes are excluded from this comparison.

## Why an Agent Might Help

The fixed workflow loads its current caches and synthesises once. The dormant graph can instead:

1. inspect existing evidence before spending a provider call;
2. stop immediately when that evidence is sufficient;
3. choose one allow-listed source when a specific gap remains;
4. reject repeated, unlisted or evidence-authored tool requests;
5. try another provider after one bounded failure; and
6. stop with explicit insufficiency when budgets expire.

Those behaviours now exist in the default-off adapter and are exercised with fake provider/model
outcomes. They support the hypothesis but do not count as real-packet product evidence.

## Current Comparison

| Dimension | Fixed workflow evidence | Agent evidence today | Decision implication |
|---|---|---|---|
| Human packet quality | 4/5 passed; mean relevance 4.4, diversity 3.8, actionability 4.2 | No real-packet run | A targeted experiment is justified; a quality claim is not |
| Automated quality | 5/5 completed; 98.65 mean; 100% quality-gate/citation pass | Fake draft/validation only | Agent must use the same evaluator and remain non-inferior |
| Recovery | One bounded synthesis repair; explicit timeout/failure states | Fake provider fallback and one repair pass | Real adapters and failures must be measured |
| Latency | P50/P95 55.407/62.129 seconds | Unmeasured; sequential planning/acquisition can add tail latency | Cut-over is prohibited without paired timings |
| Cost | 5 synthesis calls; 38,875 total tokens | Budgets permit multiple planning/tool/model actions; actual usage unknown | Cost must be bounded and reported, not assumed |
| Operational complexity | Deployed, observable fixed path and fallback | Default-off local adapter; no paired evaluator, durable owner checkpoint or route integration | Current production cut-over is a no-go |

## Frozen Paired Experiment

A permitted comparison must use the same five identities and questions in
[`agent_cases.json`](../evals/agent_cases.json), the same machine, provider/model configuration,
private-index fingerprint and cached evidence snapshot. Run the fixed control and Agent candidate on
the same day. Retain every timeout and safe stop in the denominator.

The candidate may change only these behaviours:

- assess whether the existing attributed evidence is sufficient for the stated focus;
- make zero external calls for a sufficient packet;
- for an insufficient packet, make at most two model-planned, independently authorised external
  source calls, each provider at most once; and
- pass the resulting evidence through the unchanged packet selection, synthesis and quality gate.

Retrieved text remains untrusted and cannot authorise tools. Authentication, quota reservation,
credentials and ownership checks remain outside graph state.

## Candidate Acceptance Targets

| Dimension | Required evidence before any cut-over |
|---|---|
| Primary quality | The failed case reaches diversity ≥3 and actionability ≥4; all 5/5 human packet cases pass |
| Quality non-inferiority | 5/5 assessable terminal results, mean automated quality ≥96.94, 100% deterministic gate and valid citations |
| Identity and safety | 5/5 identities match; ambiguous identity still requires explicit choice; instruction containment remains 100% |
| Selectivity | Zero external acquisition for every already-sufficient control packet; no repeated provider call |
| Recovery | Synthetic timeout, unavailable, empty and invalid-planner paths stop or fall back within the declared budget |
| Latency | Same-day Agent P50 ≤110% of fixed control and P95 ≤125%; visible pending response remains ≤300 ms |
| Cost | No more than two extra planner calls and two external tools for the one insufficient case; total model tokens ≤125% of paired fixed control |
| Operational boundary | Default-off flag, fixed fallback, redacted observability and no credential/evidence text in checkpoint or progress events |
| Reliability claim | None until at least twenty comparable attempts exist |

Passing these targets would justify a separate reviewed cut-over decision. Failing the primary human
quality target, identity/safety target, completion target or deterministic quality gate is an
immediate no-go regardless of latency or cost.

## Required Implementation Boundary After a GO

1. Implement the adapter over existing identity, cache, provider, packet and synthesis services.
2. Add deterministic sufficiency logic before any model planner is allowed to choose a tool.
3. Keep the experiment local and the route flag off by default.
4. Record safe aggregate graph steps, provider attempts, model calls, tokens and stage timings.
5. Run fake failure tests and the frozen paired suite.
6. Request a separate owner-reviewed production cut-over only if every candidate target passes.

Hosted resumability remains out of scope for the experiment. Durable owner-scoped checkpoint storage
is mandatory before any multi-instance hosted Agent route could be considered.

## Decision Options

- **GO — bounded comparison only:** authorise the default-off adapter and paired experiment under the
  targets above.
- **NO-GO:** retain the fixed workflow and prioritise deterministic source acquisition or clip
  evidence instead.
- **REVISE:** change the hypothesis or thresholds before implementation; do not alter them after
  seeing Agent results.

The owner selected **GO — bounded comparison only**. Step 12 is complete. Adapter and evaluation work
may proceed within this document's frozen scope; production Agent routing remains prohibited.
