# Production Agent Go/No-Go Brief

**Status:** original and revised local comparisons complete — production remains **NO-GO**

The original result remains immutable. The owner has since selected **REVISE** for the separately
versioned [Text-Agent Programme](TEXT_AGENT_PROGRAMME.md): the graph owns two repairs and a future
comparison averages three isolated synthesis samples per lane. Its separately approved run restored
15/15 completion and passed quality/cost, but failed both latency ratios. The run authorisation is
consumed. A structural field-patch revision is implemented and one local validation budget is
approved, but no new result exists; later text stages are blocked and production remains fixed.

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

A redacted paired harness is now ready. It fingerprints the warmed packet snapshot, runs fixed control
then Agent per case, retains failed model attempts, enforces zero calls/mutations for sufficient
packets and refuses to mark a partial suite ready. Full packets can leave memory only as an ignored
mode-`0600` human-review snapshot after all local machine targets pass.

## Paired Result

The single authorised full run is
[`local-agent-paired-2026-08-24.json`](../evals/results/local-agent-paired-2026-08-24.json).
The fixed control completed 5/5 at 97.4 mean automated quality. The Agent completed 4/5 at 94.77 mean
quality over completed cases, failing both the 100% completion and 96.94 quality floor.

| Measure | Fixed control | Agent candidate | Gate |
|---|---:|---:|---|
| Completed cases | 5 / 5 | 4 / 5 | **Failed** |
| Mean automated quality | 97.4 | 94.77 completed | **Failed** |
| Quality gate / valid citations | 100% / 100% | 100% / 100% completed | Passed |
| P50 ratio | 1.0 | 0.993373 | Passed (≤1.10) |
| P95 ratio | 1.0 | 1.057397 | Passed (≤1.25) |
| Total tokens | 39,124 | 48,575 (1.241565×) | Passed (≤1.25×) |

The causal acquisition path itself behaved selectively: four passing packets made zero planner or
external calls and retained identical fingerprints. The ambiguous-identity packet used one 417-token
planner call and one ephemeral Letterboxd acquisition, increasing selected attributed sources from 0
to 3 and moving the automated packet status from `limited` to `passed` in 2.566 seconds. This is a
promising packet result, not an accepted Agent result.

The unchanged sufficient cinematography packet produced a synthesis that remained below the
quality gate after the fixed service's one repair, so the graph stopped `failed_safe`. A separate
completed sound case scored 86, contributing to quality non-inferiority failure. The predeclared rule
makes completion failure an immediate no-go regardless of passing latency/cost. No private packet
snapshot or human Agent review was produced, and the candidate was not rerun after observing the
failure.

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
| Human packet quality | 4/5 passed; mean relevance 4.4, diversity 3.8, actionability 4.2 | Not reviewed because machine gates failed | No human quality claim |
| Automated quality | 5/5 completed; paired control 97.4 mean | 4/5 completed; 94.77 mean completed | Failed completion and quality |
| Recovery | One bounded synthesis repair; explicit timeout/failure states | One unchanged packet stopped safely after synthesis repair remained insufficient | Safe but not operationally non-inferior |
| Latency | Paired P50/P95 45.573/52.964 seconds | 45.271/56.004 seconds | Ratios pass |
| Cost | 5 calls; 39,124 tokens | 7 calls; 48,575 tokens | 1.241565× passes narrowly |
| Operational complexity | Deployed, observable fixed path and fallback | Local adapter/evaluator, one planner/provider call, no route/checkpoint | Benefit does not justify cut-over |

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

The owner selected **GO — bounded comparison only**, and that comparison is now complete. It failed
the frozen completion and mean-quality targets, so the resulting decision remains **NO-GO**. The
owner subsequently selected **REVISE** for a text-only programme with Agent-owned retries and an
isolated repeated protocol. That run completed 15/15 in both lanes at `97.17/97.80` mean quality, but
P50/P95 ratios `1.100404/1.993109` failed. It therefore does not reopen the original result or permit
production routing.
