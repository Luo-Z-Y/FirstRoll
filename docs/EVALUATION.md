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

## Pre-Selection Complete-Workflow Baseline

The Step 3 complete result is
[`baseline-2026-08-21.json`](../evals/results/baseline-2026-08-21.json). It evaluates the then-current
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

## Packet Latency Prewarm Checkpoint

[`packet-latency-prewarm-2026-08-21.json`](../evals/results/packet-latency-prewarm-2026-08-21.json)
measures the same 35-sample, zero-model-call protocol from revision `a272d5b`, but each fresh process
loads the unchanged local query encoder before packet timing. The candidate reports the roughly
ten-second encoder initialisation separately; production performs it in a daemon thread while the
local API and Discover remain available.

| Packet measure | Unprewarmed baseline | Prewarmed candidate | Change |
|---|---:|---:|---:|
| Cold-process P50 | 9,420.905 ms | 272.919 ms | −97.1030% |
| Cold-process P95 | 10,013.910 ms | 361.549 ms | −96.3895% |
| Warm P50 | 138.240 ms | 149.896 ms | +8.4317% |
| Warm P95 | 182.306 ms | 182.709 ms | +0.2211% |
| Encoder warm-up P95 | Included in packet | 10,155.338 ms, separate | Moved off request path |
| Completed samples | 35 / 35 | 35 / 35 | No change |

The full aggregate packet-shape object is exactly equal between baseline and candidate: theory,
criticism and attributed counts/characters, selected/unselected totals and omission/truncation totals
do not change. This is a latency-path change, not a retrieval-quality claim. A study requested before
background readiness can still wait on the same single-flight model load; disabling
`FIRSTROLL_PREWARM_EMBEDDINGS` restores deferred loading.

## Synthetic Packet-Quality Baseline

[`packet-quality-baseline-2026-08-21.json`](../evals/results/packet-quality-baseline-2026-08-21.json)
uses six commit-safe cases from [`packet_quality_cases.json`](../evals/packet_quality_cases.json):
abundant/diverse, honestly sparse, duplicate criticism, multilingual provenance, explicitly selected
ambiguous identity and malicious retrieved instructions. It evaluates the packet before synthesis and
loads no private source or model.

| Measure | Result |
|---|---:|
| Cases assessed / expectation failures | 6 / 0 |
| Packet status | 4 passed · 2 limited · 0 failed |
| Mean provenance completeness | 100% |
| Mean duplicate ratio | 3.33% |
| Mean lexical focus relevance | 94.45% |
| Malicious instruction items flagged / contained cases | 2 / 1 |
| Model calls | 0 |

The sparse case is limited by `film_specific_evidence_sparse`; it is not padded into apparent
sufficiency. The duplicate case is limited by `duplicate_evidence_present` with a 20% case-level
ratio. Multilingual `en`/`zh` evidence and the chosen same-title identity pass. Both malicious items
are detected while the packet's explicit boundary keeps them untrusted and unable to authorise tools
or change policy.

The result contains counts, ratios, allow-listed issue codes and language/evidence-type labels only—
no film identity values, focus, title, prompt, review or source text. These deterministic proxies do
not establish factual film-analysis correctness or filmmaker usefulness. Run the suite with:

```bash
uv run python tools/evaluate_packet_quality.py \
  --output evals/results/packet-quality-YYYY-MM-DD.json
```

## Latest Bounded-Selection and Workflow Checkpoint

Revision `88c054c` ranks focus matches while preserving retrieval order as a tie-break, keeps at most
eight theory passages, twelve critic claims and twelve attributed excerpts, removes exact/near
duplicates, enforces source/domain and character budgets and records every omission reason. The
provider prompt receives compact selected records; the complete selected evidence remains in the
owner-visible result.

The synthetic candidate
[`packet-quality-selection-2026-08-21.json`](../evals/results/packet-quality-selection-2026-08-21.json)
keeps all six expectations, 100% provenance, 94.45% mean focus overlap and 2/2 malicious items
contained. Deduplication moves the duplicate fixture from limited to passed and mean duplicate ratio
from 3.33% to 0%; the honestly sparse fixture remains the only limited case.

The private, zero-model packet run
[`packet-selection-2026-08-21.json`](../evals/results/packet-selection-2026-08-21.json) completes all
35 samples:

| Frozen packet measure | Bounded-selection result |
|---|---:|
| Applicable provenance completeness | 100% |
| Mean / maximum selected duplicate ratio | 0% / 0% |
| Mean lexical focus relevance | 82.73% |
| Packet status | 28 passed samples · 7 honestly limited *The Thing* samples |
| Median / maximum packet JSON | 26,150 / 33,556 characters |
| Median / maximum synthesis prompt | 23,242 / 29,360 characters |
| Median selected layers | 8 theory · 5 claims · 11 attributed sources |
| Warm packet P50 / P95 | 141.210 / 204.671 ms |
| Model calls | 0 |

Compared with the pre-selection packet baseline, median packet JSON falls 17.81%, theory passages
fall from ten to eight, median attributed characters fall 28.46% and median critical-claim
characters fall 36.32%. All omitted theory, claim and attributed candidates have bounded duplicate,
source-quota, item-limit, short-content or character-budget reasons. The only frozen packet
limitation is *The Thing*: it correctly has theory frameworks but no film-specific attributed source.

The bounded-selection comparison result is
[`baseline-selection-2026-08-21.json`](../evals/results/baseline-selection-2026-08-21.json):

| Complete workflow measure | Pre-selection | Bounded selection |
|---|---:|---:|
| Cases completed | 4 / 5 | 5 / 5 |
| Mean / median quality | 97.02 / 97.38 | 98.30 / 99.25 |
| Valid citations / gate pass | 100% of completed | 100% of completed |
| Completed-study median / P95 input tokens | 9,577 / 14,830.6 | 6,288 / 7,376.6 |
| P50 / P95 end to end | 77.679 / 91.225 s | 66.676 / 77.798 s |
| Mean combined study stage | 61.403 s | 55.139 s |
| Calls / total tokens | 5 / 63,764 | 5 / 42,234 |

Completed-study input-token median and P95 improve 34.34% and 50.26%; complete-suite token use falls
33.77% while mean quality rises 1.28 points above the pre-selection run and remains above the 96.94
floor. This is one controlled five-case checkpoint, not a provider-reliability estimate or proof
that selection caused every latency/quality difference. It does establish both scorecard token
budgets with no citation, provenance, duplicate or containment regression. Result scans found no
private title or 120-character private passage fragment.

## Latest Synthesis-Reliability Checkpoint

Revision `c680a95` keeps the Step 8 packet fixed, adds concise central/section prose guidance, lowers
the completion ceiling from 3,600 to 3,200 tokens and permits one total repair across either invalid
initial schema/citations or a valid draft that fails the deterministic gate. Invalid initial output
is retried once with the same supplied evidence and temperature zero. Transport timeout/unavailability
is not retried automatically because a timed-out provider request may already have consumed usage;
the user retains the explicit UI retry.

[`baseline-reliability-2026-08-21.json`](../evals/results/baseline-reliability-2026-08-21.json)
records the same five cases, machine and configuration fingerprint:

| Measure | Held-packet Step 8 | Reliability checkpoint | Change |
|---|---:|---:|---:|
| Cases completed | 5 / 5 | 5 / 5 | No regression |
| Mean / median quality | 98.30 / 99.25 | 98.65 / 98.25 | +0.35 mean |
| Gate / valid citations | 100% / 100% | 100% / 100% | No regression |
| Input-token median / P95 | 6,288 / 7,376.6 | 6,327 / 7,415.6 | Within budget |
| Completion-token median / P95 | 2,969 / 3,225.2 | 2,287 / 2,552.4 | −22.97% / −20.86% |
| Model-latency median / P95 | 52.887 / 55.195 s | 38.694 / 42.654 s | −26.84% / −22.72% |
| End-to-end P50 / P95 | 66.676 / 77.798 s | 55.407 / 62.129 s | −16.9011% / −20.1406% |
| Calls / total tokens | 5 / 42,234 | 5 / 38,875 | −7.95% tokens |

All five complete without repair. Deterministic fake-transport coverage separately proves one invalid
initial response can recover on its single schema retry, repeated invalid citations stop after two
calls and a transport timeout receives only one call. The live five-case run therefore satisfies the
15% paired median target with no P95 or quality regression, but it remains a regression fixture—not
a twenty-attempt provider-reliability claim. Its redacted result contains no private title or
120-character private passage fragment.

## Pre-Agent Final Gate

The historical
[`pre-agent-machine-gate-2026-08-21.json`](../evals/results/pre-agent-machine-gate-2026-08-21.json)
passes all 16 machine-assessable targets and honestly leaves the seventeenth target pending. The
repository owner then inspected all five real local packets and supplied the attested score-only
[`human-packet-review-2026-08-21.json`](../evals/results/human-packet-review-2026-08-21.json). No
private note or evidence text is present in that artefact.

| Human packet measure | Result | Target |
|---|---:|---:|
| Cases passed | 4 / 5 | At least 4 / 5 |
| Pass ratio | 0.8 | At least 0.8 |
| Mean focus relevance | 4.4 / 5 | Core dimension at least 4 per passing case |
| Mean traceability | 5.0 / 5 | Core dimension at least 4 per passing case |
| Mean source diversity | 3.8 / 5 | No dimension below 3 per passing case |
| Mean epistemic calibration | 5.0 / 5 | No dimension below 3 per passing case |
| Mean filmmaker actionability | 4.2 / 5 | Core dimension at least 4 per passing case |

The ambiguous-identity packet is the one failed case: diversity is 2 and actionability is 3. It
remains useful and perfectly traceable/calibrated but lacks enough complementary film-specific
evidence to make the formal test immediately actionable. This is a disclosed non-P0/P1 limitation,
not concealed synthetic sufficiency.

[`pre-agent-final-gate-2026-08-21.json`](../evals/results/pre-agent-final-gate-2026-08-21.json)
combines that redacted review with versioned aggregate results. At reviewed runtime revision
`6b24f1b`, all 17 targets and all 11 required steps pass, no target fails or remains pending, and
`agent_entry_ready` is true. This completes Step 11 and opens the Step 12 go/no-go decision; it does
not authorise production Agent integration by itself.

```bash
uv run python tools/check_pre_agent_gate.py \
  --human-review .firstroll/evaluations/human-packet-review-redacted.json \
  --output evals/results/pre-agent-final-gate-YYYY-MM-DD.json
```

## Agent Go/No-Go Contract

[Production Agent Go/No-Go](AGENT_GO_NO_GO.md) and
[`agent_go_no_go.json`](../evals/agent_go_no_go.json) predeclare the only permitted first comparison.
The primary hypothesis is that gap-directed acquisition of at most two new attributed public sources
can raise the failed ambiguous-identity packet from diversity/actionability `2/3` to at least `3/4`,
so all five human packets pass. Identity, theory retrieval, packet selection, synthesis, validation,
model and UI remain fixed.

The recommendation is conditional GO for a local, default-off adapter and same-day paired evaluation,
not a production route cut-over. The candidate must retain 5/5 terminal results, at least 96.94 mean
automated quality, 100% quality-gate/citation/identity/instruction integrity, P50/P95 no greater than
110%/125% of the paired control and total model tokens no greater than 125%. The default-off local
adapter and its real-service factory now exist, with fake provider/model contract tests proving
sufficiency, one fallback and redaction boundaries. On 24 August 2026 the owner authorised this
bounded local comparison only. Step 12 is complete, while hosted integration and production route
cut-over remain unauthorised.

The paired harness runs the fixed control immediately before the Agent candidate for each case after
one unrecorded packet warm-up. It rejects partial suites as acceptance, fingerprints every initial
packet, records failed model attempts, checks zero calls/mutations for sufficient packets and keeps
human and no-route cut-over targets explicitly pending/deferred. Its committed JSON guard rejects
source, prompt, question, title, draft and evidence-packet fields. Only a complete local machine pass
writes full candidate packets to ignored mode-`0600` storage for review.

```bash
FIRSTROLL_LOCAL_AGENT_ENABLED=1 uv run python tools/evaluate_local_agent.py \
  --output evals/results/local-agent-paired-YYYY-MM-DD.json
```

The authorised
[`local-agent-paired-2026-08-24.json`](../evals/results/local-agent-paired-2026-08-24.json) is a
**NO-GO** result. Fixed control completes 5/5 at 97.4 mean automated quality; Agent completes 4/5 at
94.77 mean over completed cases. Completion `0.8 < 1.0` and quality `94.77 < 96.94` fail. P50/P95
ratios `0.993373`/`1.057397` and token ratio `1.241565` pass, as do all identity, citation,
instruction, selectivity and tool-budget checks.

The target packet changes from zero to three attributed sources and automated `limited` to `passed`
after one Letterboxd acquisition, but the Agent's unchanged sufficient cinematography packet stops
`failed_safe` after synthesis remains below the gate following its one repair. Human targets remain
pending by design; no private packet snapshot was written. The failed candidate was not rerun, and
production remains the fixed workflow.

### Revised text-only protocol

The owner has now selected **REVISE** under the
[Text-Agent Programme](TEXT_AGENT_PROGRAMME.md). The graph, rather than the synthesis service, owns
one initial generation plus at most two repairs. Acquisition runs once per case; then the fixed and
Agent-enriched packets each receive three independent generations through the same synthesis-only
graph. Order alternates by repetition and every failure contributes zero to the mean. This isolates
the packet difference from orchestration and reduces one-draw noise without making a reliability
claim.

```bash
FIRSTROLL_LOCAL_AGENT_ENABLED=1 uv run python tools/evaluate_text_agent.py \
  --output evals/results/text-agent-repeated-YYYY-MM-DD.json
```

The owner separately approved the 30–90-call budget and the complete run is recorded in
[`text-agent-repeated-2026-08-25.json`](../evals/results/text-agent-repeated-2026-08-25.json). Both
lanes completed 15/15; fixed/Agent mean quality was `97.17/97.80` and total-token ratio `1.186853`
passed. P50 ratio `1.100404` failed the `1.10` limit, while two successful Agent-owned recovery calls
raised P95 ratio to `1.993109` against `1.25`. Every failure and recovery remains in the denominator.

The consumed authorisation now makes this command refuse a rerun. Because machine targets did not all
pass, no changed-packet snapshot or human review was created. Human ratings cannot be supplied by an
Agent, and no hosted route or production cut-over is implied.

The subsequent latency revision does not rewrite that result. It classifies failures safely, uses
deterministic Agent generation and gives parseable schema/citation failures an exact field-patch
repair capped at four paths and 800 completion tokens. Accepted fields are merged unchanged and the
complete study is revalidated. Report schema 3 counts initial failures, structural repairs, quality
repairs, full regenerations, per-strategy P50/P95 and allow-listed failure categories while retaining
every model call and terminal latency.

The separately authorised result is
[`text-agent-structural-repair-2026-08-25.json`](../evals/results/text-agent-structural-repair-2026-08-25.json).
Both lanes completed 15/15 without repair. Fixed/Agent quality was `98.32/97.88`; P50/P95 ratios
`1.003191/0.888329` and total-token ratio `1.002379` passed. The target again gained three reviews and
moved `limited → passed`, but its study mean was `95.97` against fixed `98.25`. Structural repair was
not exercised.

After report creation, the private packet write was rejected because its symlink resolved outside the
worktree boundary. This operational failure is recorded rather than omitted: machine targets remain
passed, but artifact completeness and human-review readiness are false. No snapshot exists, the run
was not repeated and the authorisation is consumed. A new preflight checks the resolved private path
before any future paid call.

### Autonomous successor and ablation order

The [Autonomous Agent Programme](AUTONOMOUS_AGENT_PROGRAMME.md) and
[`autonomous_agent_programme.json`](../evals/autonomous_agent_programme.json) preserve both historical
results and replace the combined next experiment with three causal ablations:

1. fixed packet versus deterministic gap router versus model gap planner, with provider observations
   sampled once and retained only in private evaluation storage;
2. controlled structural field patch versus full regeneration over injected schema/citation faults;
3. changed-packet synthesis using the exact private packet that passed the acquisition ablation,
   without reacquisition.

A recovered packet must pass base quality and contain at least two independent film-specific origins.
Raw excerpts from one domain do not satisfy that rule. The model planner returns one allow-listed gap
and one allow-listed tool from aggregate diagnostics; a deterministic router over the same provider
states is the baseline. Model planning advances only if it improves blinded usefulness or matches the
baseline with fewer calls. Unchanged cases remain selectivity controls rather than evidence of
acquisition benefit.

The foundation and synthetic tests made no paid call. A01 has a fail-closed harness: it creates a
private consumption lock before spend, samples each physical provider observation once, separates
cache hits from physical costs and writes three mode-`0600` packets under stable blind labels. The
reviewer hides lane identity until owner attestation; equal score and equal calls prefer the
no-model router. On 28 August 2026, the owner approved one run with at most three planner calls, five
physical provider calls and three external turns per active lane. The committed contract binds the
exact dated report, private-packet, lock, case-suite and frozen canonical-identity paths. The first
attempt exposed a missing `film_id` before writing the lock or making a paid call; that preflight
failure is retained, and the corrected harness now loads the identity from the historical reference.
The corrected run used three planner calls and four physical provider calls. Both active lanes reached
base packet status `passed` and at least two origins, but retained an evidence-class-diversity gap and
ended `budget_exhausted` after three turns. The two completion targets failed, so no private packet or
human review exists and A01 is consumed.

A02 also has a fail-closed harness. It injects one invalid citation, one schema-invalid field and two
invalid citation fields into a public synthetic candidate, then alternates three repetitions per
lane. Field patches may use at most two calls; complete regeneration uses one. Every scheduled sample
remains in the denominator. Machine acceptance requires valid schemas/citations, exact preservation
of all unrequested fields, patch P50/P95 ratios no greater than `0.80/0.90`, token ratio no greater
than `0.60`, quality no more than one point below regeneration and no more than 36 total calls. The
owner separately approved 18 expected and 36 maximum calls with no acquisition-planner or external
provider calls. Its one run used exactly 18 calls. Targeted patching completed 9/9 with complete
schema/citation validity and exact accepted-field preservation. Full regeneration completed only 4/9;
five samples failed citation validation. P50/P95 ratios were `0.055319/0.052065`, token ratio was
`0.322449`, and patch quality was non-inferior, but the frozen regeneration-completion target failed.
A02 is therefore a formal machine failure and is consumed.

Post-result no-call analysis found that A01 had flattened Crossref/video items into
`critic_reported`, could label a packet sufficient while retaining a required gap, and let the
synthesis-oriented total model-call check block evidence-only completion after the final planner
turn. The corrected implementation distinguishes `scholarly_abstract` and `video_context`, requires
all mandatory gaps to close and uses one virtual non-call completion slot in evidence-only mode.
These changes have synthetic tests only and do not alter or rerun A01.

A03 now has a fail-closed harness but cannot run until A01 machine and owner-attested evidence selects
an exact private packet and planning policy. It schedules ten alternating generations per packet,
allows no reacquisition and counts failures as zero. In addition to completion, quality, latency,
token, citation, identity and telemetry gates, at least 80% of candidate samples must actually cite a
candidate-only attributed source. Lifecycle latency adds A01 acquisition to candidate synthesis.
Only repetitions 1, 5 and 10 become private blinded study pairs after a machine pass; owner preference
and severe-grounding checks then decide human value.

Every ablation requires fresh paths, frozen thresholds and its own numeric owner budget. A01 and A02
are consumed machine failures; no paid budget remains. A03's proposed 20–60 synthesis calls remain
blocked by A01 and are not authorised. No successor result may
fill the missing private artifact in a historical report retrospectively.

## Deep Study Transparency Checkpoint

[`deep-study-transparency-2026-08-21.json`](../evals/results/deep-study-transparency-2026-08-21.json)
records a 390 × 844 Chrome audit at revision `6c63a77` using a synthetic safe result and zero model
calls. The completed view retains three lifecycle events and four aggregate count types, then shows
all three selected/candidate/omitted packet layers, character counts, provenance/duplicate/lexical
focus diagnostics, provider-reported input tokens, bounded omission reasons, explicit evidence gaps
and four redacted timing rows.

Three inline citations (`S`, `C`, `E`) each resolve to a unique expandable evidence target; activating
`S1` opens it, centres it and moves focus. The transparency context has zero horizontal overflow,
zero axe WCAG 2 A/AA/2.1 AA violations and zero incomplete checks. Prompts, credentials, hidden
reasoning and private source text have no UI field. Hosted pre-model progress still uses only the
existing allow-listed SSE counts; the richer packet and timing diagnostics appear only after the
separately authenticated owner-scoped result is retrieved. Local synchronous studies expose their
waiting state followed by the same result-level diagnostics.

## Latest UI Hierarchy Checkpoint

[`ui-hierarchy-2026-08-21.json`](../evals/results/ui-hierarchy-2026-08-21.json) records a local Chrome
DevTools Protocol audit at 1,280 × 1,000 and 390 × 844 CSS pixels from revision `d3b3c19`. All six
frozen journeys retained a usable hierarchy with zero P0/P1 blockers and zero horizontal overflow.
Six immediate response observations produced P50/P95 of 7.35/12.05 ms against the 300 ms budget.

The audit made no model calls. It reused the complete workflow result for synthesis coverage.
Screenshots remain local acceptance aids; only public fixture IDs and redacted measurements are
versioned.

The follow-on [`ui-states-accessibility-2026-08-21.json`](../evals/results/ui-states-accessibility-2026-08-21.json)
closes the deferred Step 5 checks at revision `a081947`. Eight search, dossier, provider and Deep
Study terminal-state scenarios retained inputs/evidence, moved focus, cleared busy state, redacted
synthetic provider details and exposed a safe retry. Browser-side **Stop waiting** responded in 6.1
ms while explicitly warning that server/provider work might continue.

Arrow/Home/End checks left exactly one tab stop and selected panel in analysis, settings, account and
dynamic video tablists. Axe-core 4.13 reported zero WCAG 2 A/AA/2.1 AA violations and zero incomplete
checks on the Discover landing, mobile dossier and mobile Deep Study error contexts. The initial
dark-theme primary-action contrast defect moved from 3.05:1 to 5.79:1 against a 4.5:1 requirement.
No model call was made for this UI-only checkpoint; physical devices and assistive-technology user
testing remain separate known constraints.

## Metric Dictionary

| Metric | Definition | Denominator |
|---|---|---|
| Case completion | A study reaches a terminal result that can be quality-assessed | All attempted cases |
| Operational failure rate | Search, identity, detail or study execution fails before an assessable result | All attempted cases |
| Quality-gate pass rate | Completed studies whose deterministic gate accepts the central argument and required sections | Completed studies only |
| Quality acceptance failure rate | Completed studies rejected after the permitted repair policy | Completed studies only |
| Quality score | Weighted proxy for identity, structure, gate result, citation integrity, calibration, verifiability and evidence coverage | Each completed study |
| Repair rate | Completed studies that required one or more permitted repair calls | Completed studies only |
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
retains this record as `study_observability`; the latest bounded-selection result contains a complete
trace for all five assessable studies. Failed callers retain the safe trace in server logs rather
than the HTTP error body. The historical 18 August baseline predates the schema and remains
unchanged; neither
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
4. update this document's latest complete-workflow tables directly from that JSON;
5. add a dated entry to `docs/PROGRESS.md` explaining policy or configuration changes; and
6. commit the case fixture, evaluator, result and documentation together when any contract changed.

Do not overwrite a historical result or update only the README table. A baseline is reproducible
only when its cases, policy, configuration fingerprint and raw aggregate record travel together.
Packet-only measurements follow the cold/warm and redaction rules in the Pre-Agent scorecard and
must remain distinguishable from provider acquisition and model transport.
