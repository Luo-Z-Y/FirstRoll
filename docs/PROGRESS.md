# FirstRoll Project Progress

### 28 August 2026 — Distinct revision and patch-reliability gates implemented

Delivered without a model or provider call:

1. Added A01R as a distinct class-aware acquisition experiment. It cannot reuse A01's result, private
   lock, output path or consumed budget.
2. Preserved the acquire-once fixed/deterministic/model lanes and proposed maxima of three planner
   calls, five physical provider calls and three external turns per active lane.
3. Strengthened A01R machine acceptance: both active lanes must finish, each must retain at least two
   independent origins and two explicit film-specific evidence classes, and no required gap may
   remain. Fixed-lane zero calls and every prior sampling/budget target still apply.
4. Updated blinded acquisition review to preserve either `A01` or `A01R` identity through private
   scoring and redacted aggregation. A03 now binds all machine/private/human artifacts to the exact
   accepted acquisition experiment rather than silently assuming the historical A01.
5. Added A02R as a patch-only reliability gate instead of paying again for the A02 regeneration lane
   that failed 5/9 citation checks.
6. A02R schedules six repetitions across four controlled fixtures—one citation, one schema field,
   two citation fields, and one mixed schema/citation pair—for 24 comparable targeted patches.
7. Froze A02R at 24/24 valid exact-preserving outputs, mean quality at least `99`, P95 no greater than
   five seconds, at most 36,000 tokens, complete telemetry and 24 expected/48 maximum model calls.
   Planner/provider calls remain zero.
8. Both harnesses bind future approval to committed source, exact fresh report/private paths and a
   mode-`0600` one-run lock before spend. Both currently refuse because confirmations are null.

Known constraints:

- A01R requires new provider sampling and owner packet review; no result can be inferred from the
  synthetic semantic fix.
- A02R's thresholds are frozen from the demonstrated patch latency plus explicit headroom, but 24
  samples still cover synthetic controlled faults rather than arbitrary prose defects.
- A03 remains blocked by A01R. Finisher provider validation and durable reliability remain later
  gates; production remains fixed.

Next actionable work:

1. Commit and merge the no-call harness checkpoint after full CI.
2. Request separate exact A01R and A02R budgets only after the owner inspects these frozen contracts.
3. Run neither harness under A01/A02's consumed authorisations.

### 28 August 2026 — Post-result evidence semantics corrected without paid calls

A01 diagnosis:

1. `EvidencePacket` normalised every Crossref abstract, public review and unverified video description
   or caption to `critic_reported`. The Agent therefore measured one film-specific evidence class even
   when it had acquired scholarship plus video context or criticism.
2. `AgentEvidenceAssessment.sufficient` checked base packet status and independent origins but did not
   require its own `evidence_class_diversity` gap to close. This produced the contradictory retained
   telemetry `agent_status: sufficient` plus a remaining gap.
3. After the third planning turn, evidence-only mode still passed through the synthesis-oriented total
   model-call guard. It therefore stopped budget-exhausted before converting sufficient evidence to
   `EVIDENCE_READY`, even though evidence-only evaluation makes no synthesis call.

No-call correction:

- added explicit `scholarly_abstract` and `video_context` evidence types while preserving
  `critic_reported`, verified `creator_stated` and film-observation boundaries;
- Crossref abstracts and video context now constitute real epistemic classes rather than provider
  names hidden inside one class;
- a recovered packet is sufficient only when base quality passes and every required typed gap is
  closed; an initially passed packet retains its zero-call guarantee;
- Crossref and video-text actions may address evidence-class diversity, and deterministic routing
  chooses the strongest remaining class-aware action;
- evidence-only mode reserves one virtual completion slot after the final planner turn. It makes no
  synthesis call and does not relax planner, provider, step, deadline, character or item limits;
- tests reproduce two criticism origins remaining insufficient, Crossref closing the class gap and
  evidence-only completion after the final permitted planner slot.

Integrity boundary:

- historical A01 and A02 reports, outcomes, calls and denominators are unchanged;
- the fixes do not select a planning policy or reconstruct a private packet;
- any provider-backed validation requires a distinct experiment ID, fresh exact budget, fresh paths
  and committed source; no such spend is authorised.

Next actionable work:

1. Validate all static and synthetic contracts and merge this no-call correction.
2. Design a distinct revised acquisition experiment and a patch-only reliability experiment; freeze
   them before asking for any new budget.
3. Keep A03, hosted routing, production cut-over and clip-Agent work blocked.

### 28 August 2026 — A02 patching succeeds, but the frozen aggregate gate fails

Measured A02 result from source `9be19e7b`:

| Measure | Targeted field patch | Complete regeneration | Gate |
|---|---:|---:|---|
| Completion | 9 / 9 | 4 / 9 | Failed on regeneration |
| Mean quality, failures as zero | 100.00 | 40.89 | Patch non-inferiority passed |
| Citation/schema validity | 1.0000 | 0.4444 | Patch passed |
| Accepted fields preserved | 9 / 9 | not applicable | Passed |
| P50 latency | 1.754 s | 31.707 s | `0.055319×`, passed |
| P95 latency | 2.079 s | 39.931 s | `0.052065×`, passed |
| Tokens | 9,628 | 29,859 | `0.322449×`, passed |
| Model calls | 9 | 9 | 18 total, passed |

Outcome:

1. Every controlled one-citation, one-schema-field and two-field fault was repaired in one targeted
   call. Every complete candidate revalidated, and every unrequested field remained exactly equal.
2. Five of nine complete regenerations failed citation validation. They remain zero-scored with their
   complete 29.761–39.491-second latency and token cost; no output was discarded from the denominator.
3. Ten of eleven frozen targets passed, including all patch correctness, preservation, latency, token,
   quality, budget and transport-telemetry requirements.
4. `regeneration_completion_ratio` failed. Because the contract required both lanes to complete 9/9,
   the aggregate experiment is a machine failure despite the strong targeted-patch evidence.
5. The run made exactly 18 DeepSeek calls, with zero acquisition-planner/provider calls. No prompt or
   generated response was written to the redacted report.
6. A02 supplies provider-backed evidence that exact field patching can be dramatically cheaper and
   more reliable for these three fixtures, but three repetitions do not establish reliability and the
   failed frozen gate is not upgraded retrospectively.
7. A01 and A02 authorisations are consumed. A03 remains blocked by A01; no paid validation, hosted
   Agent route, production cut-over or clip-Agent work is authorised.

Next actionable work:

1. Preserve and version the immutable A02 report; do not rerun either consumed experiment.
2. Diagnose A01 evidence-class/status semantics and A02 regeneration citation failures without paid
   calls, then freeze any revision contract before requesting new spend.
3. Keep production on the fixed workflow and continue to describe the Agent as not yet solid.

### 28 August 2026 — A01 fails its machine gate; A02 becomes active

Measured A01 result from source `497be3c1`:

| Measure | Fixed | Deterministic router | Model planner |
|---|---:|---:|---:|
| Terminal status | not run | budget exhausted | budget exhausted |
| Base packet status | limited | passed | passed |
| Independent origins | 0 | 3 | 2 |
| Film-specific evidence classes | 0 | 1 | 1 |
| External turns | 0 | 3 | 3 |
| Planner calls/tokens | 0 / 0 | 0 / 0 | 3 / 1,643 |
| Acquisition latency | 0 s | 18.272 s | 8.729 s |

Outcome:

1. Both active lanes changed the packet and obtained enough independent origins, but each retained the
   `evidence_class_diversity` gap and exhausted its frozen three-turn allowance.
2. Guardian failed once in the acquire-once pool. Crossref returned one review, video search returned
   16 textual resources and Letterboxd returned three reviews; every observation or failure was
   shared without repeating a physical request.
3. The run used three planner calls, four physical provider calls and six logical lane requests. It
   stayed below all cost ceilings and made no synthesis call.
4. `deterministic_lane_completed` and `model_lane_completed` failed. The remaining eight machine
   targets passed, but the complete machine gate failed exactly as frozen.
5. No private packet snapshot was written, no human review is available and no planning strategy is
   selected. A03 remains blocked and the A01 authorisation is consumed.
6. The report's aggregate `agent_status` says `sufficient` while each active lane still lists the
   evidence-class gap and terminates budget-exhausted. The result is retained without reinterpretation;
   the status/gap semantic mismatch requires no-call diagnosis before any future acquisition design.
7. The separately approved A02 structural-repair ablation is now the only active paid experiment. Its
   18 expected/36 maximum limits and exact fresh paths are unchanged.

Next actionable work:

1. Commit this immutable redacted A01 result and A02 activation checkpoint after validation and CI.
2. Run A02 once from that exact committed source, retaining every failed patch/regeneration as zero.
3. Do not run A01 review or A03; neither has the required private packet evidence.

### 28 August 2026 — A01/A02 value experiments receive exact sequential approval

Owner decisions:

1. Approved production deployment run `33176634496` for exact commit `4529e2fe`; the sealed
   deployment completed as live build `v178`, API health remained `{"status":"ok"}` and no Agent
   route was exposed.
2. Approved one A01 acquisition ablation with at most three planner calls, five physical provider
   calls and three external turns per active lane. Synthesis remains zero.
3. Separately approved A02 with 18 expected and 36 maximum DeepSeek calls and zero acquisition
   planner/provider calls. A02 is recorded but must remain inactive until A01 is consumed.
4. Did not approve A03, hosted Agent routing, production Agent cut-over or clip-Agent work.

Pre-spend controls:

- A01 is bound to committed source, `evals/agent_cases.json`, the frozen canonical identity report, a
  fresh dated redacted report, a fresh mode-`0600` private packet snapshot and a fresh private one-run
  lock;
- A02 is bound to its own fresh dated report and private lock;
- both evaluators reject alternate programme, report, packet, case-suite or lock paths before a paid
  call;
- the main `.firstroll` directory resolves inside the repository with mode `0700`; all approved paths
  were confirmed absent before authorisation;
- DeepSeek and all five allow-listed Agent acquisition actions report ready without exposing secret
  values;
- no paid call was made while recording these authorisations.

Pre-spend failure retained:

- the first A01 command stopped with `canonical_film_identity_not_bound` because the case suite stores
  queries/expectations while the harness incorrectly expected an inline `film_id`;
- the failure occurred before the one-run lock, planner construction or provider acquisition: model
  planner calls `0`, physical provider calls `0`, and the authorisation remains unconsumed;
- the corrected harness binds the target to `wikidata:Q210756` from the immutable baseline reference,
  rejects any alternate reference path and writes the consumption lock before film detail or packet
  preparation; it also rechecks title, year and director against the frozen expectation.

Next actionable work:

1. Commit and merge this exact authorisation checkpoint after CI.
2. Run A01 once, retain every failure and consume its authorisation.
3. Preserve the redacted report and private packet only if machine gates permit owner review.
4. Activate and run A02 once from a later committed checkpoint, then consume its separate approval.

### 28 August 2026 — Autonomous research-Agent foundation begins

Owner direction:

1. Continue until FirstRoll has a solid autonomous Agent rather than limiting the design to one tool
   selection step.
2. Choose useful research, review, editing and coaching capabilities and add or change bounded
   providers where evidence justifies them.
3. Preserve the existing privacy, cost, human-attestation and production gates. The instruction does
   not provide a numeric paid-call budget or authorise a hosted route/cut-over.

Delivered without a model or provider call:

1. Defined “solid” as demonstrated value against both the fixed workflow and a transparent
   deterministic baseline, plus independent human, reliability, recovery and durability evidence.
2. Added typed gaps for missing film-specific evidence, independent origins, evidence-class
   diversity and focus relevance. The planner now returns one allow-listed gap plus one allow-listed
   tool rather than an unscoped action or free-form reasoning.
3. Preserved the zero-call guarantee for packets that were already sufficient. A packet recovered
   from `limited` or `failed` now needs base quality `passed` and at least two independent
   film-specific web origins; several excerpts from one domain no longer count as recovery.
4. Added a deterministic no-model gap router over the same allow-list. It is the mandatory acquisition
   ablation baseline, not a fallback whose results can be omitted.
5. Added the existing constrained Crossref scholarship adapter to Agent status, planning and
   acquisition alongside Guardian, Douban, Letterboxd and video text.
6. Added safe planning-decision telemetry containing only strategy, gap and tool identifiers. Source
   text, titles, URLs, model reasoning and provider details remain excluded.
7. Versioned the successor contract in `evals/autonomous_agent_programme.json` and documented separate
   acquisition, repair and changed-packet synthesis ablations. Historical reports remain immutable.
8. Added the A01 acquire-once pool: each physical provider result or failure is sampled once and
   replayed to deterministic/model lanes, while logical actions and physical costs remain separate.
9. Added a mode-`0600` one-run lock, committed-source/fresh-path/private-boundary preflights and a
   three-packet blinded owner review. Equal usefulness and equal calls explicitly prefer the
   deterministic router.
10. Added A02 controlled fault injection for one citation, one schema field and two citation fields,
   with three alternating repetitions of field patch versus complete regeneration. The report keeps
   calls, failures, quality, latency and tokens but no generated response.
11. Froze A02 requirements: complete validity, exact accepted-field equality, no more than
   `0.80/0.90` P50/P95 latency ratios, no more than `0.60` token ratio, quality within one point and a
   36-call ceiling. Its proposed 18–36 calls are not authorised.
12. Implemented exact claim-support audit validation, one at-most-four-path editor, mandatory re-audit
   and evidence-linked filmmaker exercises. Interpretations cannot be labelled directly supported,
   and exercises cannot use weak paths or citations outside their section.
13. Added a local research-to-finisher controller with two audit, one editor, one coach and four total
   model-call ceilings. It stops on excessive weak claims, failed edits, failed re-audit or exhausted
   budget and exposes no HTTP route.
14. Added private durable phase checkpoints for research, audit, edit, re-audit and coaching. Files use
   hashed names, owner checks, atomic mode-`0600` writes and cancellation between phases.
15. Persist an in-flight marker before each potentially paid phase. A process interruption stops
   failed-safe on resume instead of automatically replaying a call with unknown spend.
16. Added A03 exact changed-packet synthesis: ten alternating generations per lane, zero
   reacquisition, candidate-only source-use measurement, acquisition-inclusive lifecycle latency and
   three predeclared blinded owner-review pairs.
17. The A01 source pool now records per-lane counterfactual provider latency, so a cache hit used for
   fair provider sampling cannot make the selected policy appear instant in A03 lifecycle results.
18. Recorded successful owner approval and deployment of run `32871204646`: live frontend build
   `v174` reports commit `1f2c3cff`, while API health remains `{"status":"ok"}`. The deployment did
   not expose an Agent route.

Acceptance evidence:

- a recovered one-origin packet remains insufficient while two independent origins pass;
- the deterministic baseline targets Crossref after a first criticism origin and makes zero planner
  model calls;
- sparse graph execution performs two distinct acquisitions before synthesis; one success after a
  failed provider stops honestly insufficient when the two-call budget is exhausted;
- planner prompts expose safe gaps/counts but no evidence or provider-private values;
- the A01 evaluator refuses the current unconfirmed budget, caches provider successes/failures
  without exposing exception details and produces a stable complete blind mapping;
- blinded review advances model planning only when its packet passes the rubric and beats the
  deterministic packet, or ties while using fewer external calls;
- claim audit rejects missing paths, cross-path citations and direct-support labels on interpretations;
- coaching rejects weak paths, duplicate exercises, untraceable citations and instructions without
  an observable action;
- the local autonomous controller skips unnecessary editing, requires re-audit after editing and
  excludes provider exception details from safe metrics;
- durable tests prove mode `0700/0600`, hashed filenames, owner isolation, cancellation, phase resume,
  edited-study re-audit and no automatic replay after an interrupted in-flight phase;
- A03 tests bind machine, private-packet and human A01 artifacts, ignore reassigned evidence IDs when
  finding new sources, measure actual new-source citations and preserve stable blinded repetitions;
- changed-study review excludes private notes and requires owner attestation, two candidate usefulness
  wins, no fixed evidence-responsibility win and no severe candidate grounding concern;
- text, acquisition and changed-study review readers reject a `.firstroll` symlink that resolves
  outside the repository before reading any private artifact;
- all 367 automated tests pass with the retained Starlette/httpx deprecation warning;
- scoped Ruff, new-module MyPy, compilation, JSON and documentation-link checks pass; no paid call
  was made.

Known constraints:

- A01, A02 and A03 harnesses are implemented; A01/A02 have no paid authorisation and A03 is also
  blocked until A01 selects an owner-approved private packet;
- no numeric paid budget is active;
- model planning has not shown value over the deterministic router;
- the field-patch mechanism still lacks provider-backed evidence;
- claim audit, targeted editing and filmmaker coaching have synthetic implementation only; provider
  value and reliability remain gated; local durability has synthetic single-process evidence only;
- production stays on fixed Deep Study and clip-Agent work remains deferred.

Next actionable work:

1. Keep A01 and A02 fail-closed until each exact proposed numeric budget is explicitly confirmed.
2. Add controlled provider ablations for audit/editor/coaching only after A01/A02 settle.
3. Validate owner-scoped checkpointing and cancellation during a later authorised local pilot.
4. If A01 passes, retain its winning packet and execute A03 only under a later separate budget.

### 25 August 2026 — Revised Agent passes machine gates but loses private review artifact

Measured result:

| Measure | Fixed packet lane | Agent packet lane | Gate |
|---|---:|---:|---|
| Completion | 15 / 15 | 15 / 15 | Passed |
| Mean automated quality | 98.32 | 97.88 · `−0.44` | Passed |
| Quality standard deviation | 1.27 | 2.08 | Descriptive |
| P50 latency | 42.304 s | 42.439 s · `1.003191×` | Passed |
| P95 latency | 52.413 s | 46.560 s · `0.888329×` | Passed |
| Synthesis calls | 15 | 15 | No repairs |
| Total tokens | 116,037 | 116,313 including planner · `1.002379×` | Passed |

What worked:

1. All 30 scheduled generations completed on their first attempt. Temperature-zero Agent synthesis
   had no invalid response, quality repair or full regeneration, eliminating the previous 95–103
   second recovery tail in this draw.
2. Every frozen completion, quality, citation, identity, instruction, selectivity, packet-change,
   provider-repeat, telemetry, latency and token target passed.
3. Four sufficient packets remained byte-identical and made no planner/provider call. The target used
   one 417-token plan and one 2.902-second Letterboxd acquisition, added three reviews and moved
   `limited → passed`.
4. Actual spend was 30 synthesis calls, one planner call and one provider call, within the approved
   90/10/10 maxima. Every call and sample remains in the report.

What did not work:

1. No response needed structural repair, so the new field-patch mechanism has synthetic coverage but
   no provider-backed exercise. The run supports stable one-call behaviour, not patch reliability.
2. The sole changed packet's three studies averaged 95.97 versus 98.25 for the fixed packet. Overall
   non-inferiority therefore does not establish that the extra evidence improved generated prose.
3. After the redacted machine-pass report was written, private snapshot output resolved through the
   evaluation worktree's `.firstroll` symlink to a location outside the worktree. The security
   boundary correctly rejected it and the command exited with status 1 after all paid calls.
4. The process-local changed packet was lost when the command exited. No private snapshot or human
   review can be reconstructed without another acquisition, which is not authorised.

Integrity response:

- the run was not repeated, tuned or partially replaced;
- `evals/results/text-agent-structural-repair-2026-08-25.json` keeps the machine pass, all 30 samples,
  exact calls/tokens/timings and a safe `private_output_boundary_rejected` post-run status;
- human readiness and artifact completeness are forced false despite all machine targets passing;
- the one-run authorisation is consumed;
- the evaluator now preflights the resolved private-output boundary before any paid call, with a
  regression test for an escaping symlink;
- all 278 automated tests, scoped Ruff, compilation, JSON parsing, report privacy, documentation links
  and whitespace checks pass after the result was recorded;
- production remains fixed and T02–T05 plus clip-Agent work remain blocked.

Known constraints:

- three repetitions still do not establish reliability;
- no provider evidence exists for structural patch latency or success;
- no owner-attested diversity/actionability evidence exists for the changed packet;
- machine non-inferiority is not a meaningful Agent-value claim when the only changed packet scored
  lower and cannot be reviewed.

Next actionable work:

1. Do not rerun this comparison or reacquire the packet under the consumed budget.
2. Continue no-call T01 analysis around a reproducible private-artifact fixture and a more causal
   changed-packet measure before asking for any new spend.
3. Keep T02 blocked until a future, separately approved design can produce complete machine and human
   evidence without weakening the path boundary.

### 25 August 2026 — Structural-repair deployment and one paid validation approved

Recorded decisions:

1. The owner approved exact production run `32844112600` for commit `221c0fa3`. The sealed frontend
   deployment succeeded as live build `v171`; `firstroll.app` reports the expected commit and the API
   health endpoint returns `{"status":"ok"}`.
2. The owner separately approved one complete structural-repair comparison with 30–90 synthesis
   calls, up to ten planner calls and up to ten external-provider calls.
3. The historical comparison authorisation remained consumed. The new confirmation was recorded as a
   distinct unconsumed record; the result above documents its later consumption.
4. The run must use committed tracked code, the complete five-case/three-repetition schedule, frozen
   thresholds, alternating lane order and zero-scored failures. It does not authorise T02, hosted
   routing or production Agent cut-over.

Acceptance evidence:

- `evals/text_agent_programme.json` binds all four approved maxima and requires the exact new status,
  implementation contract, unconsumed confirmation and consumed historical confirmation;
- the evaluator refuses dirty tracked source and existing output paths before any paid call;
- no synthesis, planner or provider call was made while recording this decision.

Next actionable work:

1. Commit and run this exact authorised checkpoint once; retain all attempts and do not tune or rerun.
2. Publish only the redacted aggregate and immediately consume the authorisation.
3. If every machine target passes, open only the private changed-packet review for owner attestation;
   otherwise preserve the failure and continue T01 without beginning later stages.

### 25 August 2026 — Parseable Agent failures now receive bounded structural patches

Diagnosis:

1. The two 95.411/103.249-second samples did not use the service's targeted repair path. Their
   initial responses were invalid, so no `last_valid_draft` survived and the graph made a second full
   generation with the same 6,926-token prompt.
2. Those model transport pairs took `42.739 + 49.344` and `48.168 + 51.636` seconds. A full second
   study cannot fit the previous 61.313-second Agent P95 ceiling.
3. Safe telemetry recorded only `invalid`, so the historical result cannot distinguish schema,
   citation, empty-content or malformed-JSON failures. The generated responses were correctly not
   retained and cannot be replayed.

Delivered without a provider call:

1. Added a bounded failure taxonomy. Safe attempt metrics may record only category, strategy, calls
   and tokens; candidate text never enters graph state, logs or reports.
2. Made Agent initial synthesis deterministic at temperature `0`. The fixed production workflow
   remains at `0.2` with its existing single internal repair.
3. Retain a parseable invalid candidate only inside the process workspace and derive at most four
   deterministic field paths from schema/citation validation.
4. Added structural repair responses of the form `{"updates":[{"path":...,"value":...}]}` with an
   800-token completion ceiling. The repair prompt includes only affected candidate sections and the
   evidence classes needed by those fields; it must cover exactly the requested paths and cannot
   change an accepted field.
5. Merge patches in deterministic code, then revalidate the complete `GroundedStudy`, all source,
   critic and attributed-evidence IDs, evidence status and the quality gate.
6. Keep a second invalid field eligible for the graph's final repair. Malformed, unpatchable or
   failed patches fall back within the existing maximum of three generation calls.
7. Extended future report schema 3 with initial-failure, targeted structural/quality repair, full
   regeneration, per-strategy P50/P95 and safe failure-category aggregates.
8. Added a distinct unconfirmed revision budget slot. The consumed historical approval cannot be
   reused, and the evaluator requires committed tracked code and refuses to overwrite an existing
   report or private snapshot.

Acceptance evidence:

- synthetic transports prove one and two invalid citations use 800-token field patches while every
  unrequested section remains byte-for-byte equivalent after validation;
- malformed JSON exposes no candidate; an out-of-scope patch is rejected; private synthetic prose
  never appears in `safe_metrics`;
- graph tests prove a patchable initial failure dispatches `targeted_structural_repair` rather than
  `generate_once()` and remains within the existing two-repair budget;
- all 275 automated tests, scoped Ruff, compilation, JSON parsing, documentation links and whitespace
  checks pass without a model or provider call;
- the historical result, latency thresholds, fixed production workflow, HTTP surface and hosted
  routing remain unchanged.

Known constraints:

- the completed paid run did not retain the invalid-response subtype, so this patch targets the
  demonstrated control-flow defect but cannot prove those exact responses were patchable;
- an 800-token ceiling does not guarantee a 10–15-second provider response;
- malformed JSON still requires a full generation because FirstRoll will not guess missing prose;
- no fresh paid comparison, meaningful-value claim, human packet review or T02 entry is authorised.

Next actionable work:

1. Keep the fixed workflow and the evaluator's new budget slot unconfirmed.
2. Obtain a separate, explicit budget decision before any provider compatibility probe or repeated
   comparison; do not reuse the consumed authorisation.
3. On approval, keep every retry in end-to-end P95 and report normal generation, structural repair,
   full regeneration and failure categories separately. Advance T02 only if revised T01 passes.

### 25 August 2026 — Repeated text-Agent run recovers quality but fails latency gates

Measured result:

| Measure | Fixed packet lane | Agent packet lane | Gate |
|---|---:|---:|---|
| Completion | 15 / 15 | 15 / 15 | Passed |
| Mean automated quality | 97.17 | 97.80 · `+0.63` | Passed |
| Quality standard deviation | 1.57 | 1.38 | Descriptive |
| P50 latency | 41.881 s | 46.086 s · `1.100404×` | **Failed** (`≤1.10×`) |
| P95 latency | 49.050 s | 97.762 s · `1.993109×` | **Failed** (`≤1.25×`) |
| Model calls | 15 | 17 synthesis + 1 planner | Within budget |
| Total tokens | 114,737 | 136,176 including planner · `1.186853×` | Passed |

Findings:

1. The isolated acquisition result repeated: four sufficient packets made no planner/provider call or
   mutation; the target used one 417-token Letterboxd plan and one 3.112-second acquisition, added
   three reviews and moved `limited → passed`.
2. The same graph-owned retry controller produced 15/15 terminal studies in both lanes. Automated
   quality, citations, identity, instruction containment and provider/token telemetry all passed.
3. Two Agent samples for an unchanged sufficient packet returned invalid initial generations. The
   Agent owned and successfully executed one retry for each, restoring completion and contributing to
   the higher 97.80 mean, but the samples took 95.411 and 103.249 seconds.
4. Those recovery attempts make Agent P95 `1.993109×` fixed. P50 also misses its frozen limit by
   `0.000404` ratio points. The failed attempts remain in the denominator and the limits were not
   rounded or changed after observation.
5. The owner-approved budget was consumed by 32 synthesis calls, one planner call and one provider
   call, below the declared 90/10/10 maxima. No rerun occurred.
6. Machine targets did not all pass, so no private packet snapshot or human review was produced.
   Stages T02–T05 and all clip-Agent work remain blocked.

Acceptance evidence:

- `evals/results/text-agent-repeated-2026-08-25.json` retains all 30 scheduled samples, both retries,
  exact target outcomes, packet fingerprints, safe attempt records, timing and provider token usage;
- `evals/text_agent_programme.json` binds the result to source `f442f5c`, marks the one-off budget
  authorisation consumed and makes the evaluator refuse a rerun;
- all 265 automated tests, scoped Ruff, compilation, JSON parsing, documentation links, report
  privacy scans and whitespace checks pass;
- production remains the fixed workflow and no Agent HTTP or hosted route exists.

Known constraints:

- three repetitions demonstrate the cost of recovery but do not establish a broad reliability rate;
- a latency contract that compares final recovered P95 directly with single-call control P95 will
  normally reject any slow retry, but changing that measurement now would be a new decision;
- the mechanically improved packet still lacks the required human diversity/actionability rating.

Next actionable work:

1. Keep the fixed workflow in production and do not rerun this paid comparison.
2. If the owner wants to continue, record REVISE before choosing one causal path: reduce invalid
   initial generations, or separate no-retry latency non-inferiority from a predeclared recovery SLO.
3. Begin claim/citation review only after the revised T01 entry condition passes; keep clip analysis
   out of the Agent programme until all text stages settle.

### 25 August 2026 — Agent-owned retries and isolated text protocol implemented

Delivered:

1. Recorded the owner's REVISE decision as a five-stage text programme: Agent-owned retries, bounded
   claim/citation review, genuine diversity review, targeted section editing and filmmaker coaching.
   Clip-Agent work is blocked until those text stages establish an accepted baseline.
2. Split synthesis into `generate_once()` and `repair_once()`. Agent calls have no hidden service
   retry; the graph owns one initial attempt and at most two repairs. The fixed production workflow
   retains its existing single internal repair and no Agent route was added.
3. Increased the graph repair limit to two, enforced total model-call budget checks and allowed a
   quality-passing draft to complete on the final permitted step.
4. Added local `evidence_only` and `synthesis_only` graph modes. The former freezes one bounded
   acquisition before writing; the latter gives fixed and enriched packets the exact same generation
   and retry policy without extra provider calls.
5. Added a fail-closed repeated evaluator. It prepares/acquires once, schedules three samples per lane
   and case, alternates lane order, scores failures as zero, includes acquisition planning in Agent
   token cost and writes only changed private packets after every machine target passes.
6. Added a resumable local human-review tool that requires mode-`0600` machine-gated packets, keeps
   notes private and emits only score aggregates after personal attestation.
7. Declared the complete cost before execution: 30 minimum and 90 maximum synthesis calls, plus at
   most ten planner/provider calls. Implementation approval does not authorise that paid run.

Acceptance evidence:

- graph tests prove two successful repairs, two-repair exhaustion, evidence-only termination,
  synthesis-only isolation and total call/step boundaries;
- service tests prove `generate_once()` never repairs and `repair_once()` makes exactly one call;
- evaluator tests prove alternating order, complete denominators, zero-scored failures, acquisition
  cost accounting, report redaction and fail-closed budget authorisation;
- all 264 automated tests, scoped Ruff, compilation, JSON parsing, documentation links and whitespace
  checks pass without a provider or synthesis call;
- the hosted/public fixed route, model behaviour and API surface are unchanged.

Known constraints:

- three repetitions reduce one-draw noise but cannot support a reliability claim;
- the full frozen run can consume up to 90 synthesis calls if every sample uses both repairs;
- packet-level human diversity/actionability remains unknown until machine targets pass and the owner
  reviews changed packets;
- the experimental graph remains process-local with no durable hosted checkpoint.

Next actionable work:

1. Obtain explicit owner confirmation of the declared paid-run budget before changing the
   machine-readable programme to `approved_revised_local_comparison`.
2. Run the complete frozen repeated comparison once, retain every sample and publish only its
   redacted aggregate result.
3. If T01 passes, begin T02 claim/citation review as a separate measurable change. Otherwise diagnose
   retry or packet effects without silently tuning against individual generated outputs.

### 25 August 2026 — Production-generated API documentation disabled

Delivered:

1. Made FastAPI application construction mode-aware: local development retains Swagger, ReDoc and
   OpenAPI, while `FIRSTROLL_PUBLIC_MODE=true` registers none of their HTTP routes.
2. Kept `/api/health` public for Azure Container Apps health probes and left endpoint-level bearer,
   quota and local-only controls unchanged.
3. Added regression coverage for both route sets and reconciled README, API-reference, hosting and
   Obsidian project documentation with the production security boundary.

Acceptance evidence:

- the public application shell has no `/docs`, `/redoc` or `/openapi.json` route;
- the local application shell retains all three development aids;
- all 243 automated tests and Ruff checks passed before release;
- immutable image `firstroll46ikj8.azurecr.io/firstroll-api:9d0554a` was smoke-tested locally, pushed
  to Azure Container Registry and deployed as healthy revision `firstroll-api--0000002`;
- live `api.firstroll.app` checks returned HTTP 404 for `/docs`, `/redoc` and `/openapi.json`, and
  HTTP 200 for `/api/health`.

Boundary:

- removing generated documentation reduces endpoint enumeration and accidental public discovery;
  it does not replace authentication or authorisation on protected API operations.

Rollback:

- restore image `firstroll46ikj8.azurecr.io/firstroll-api:9762a08` if the new revision develops a
  production fault; the previous image remains available in Azure Container Registry.

### 24 August 2026 — Local Agent comparison fails gates; NO-GO retained

Measured result:

| Measure | Fixed control | Agent candidate | Gate |
|---|---:|---:|---|
| Completed cases | 5 / 5 | 4 / 5 | **Failed** (required 5 / 5) |
| Mean automated quality | 97.4 | 94.77 completed | **Failed** (required ≥ 96.94) |
| Quality gate / valid citations | 100% / 100% | 100% / 100% completed | Passed |
| P50 end-to-end | 45.573 s | 45.271 s · 0.993373× | Passed |
| P95 end-to-end | 52.964 s | 56.004 s · 1.057397× | Passed |
| Model calls / total tokens | 5 / 39,124 | 7 / 48,575 · 1.241565× | Passed narrowly |
| Local machine gate | Passed control | Failed candidate | **NO-GO** |

Findings:

1. Selectivity behaved as designed: all four initially passing packets made zero planner/external calls
   and retained identical packet fingerprints.
2. The target ambiguous-identity packet used one 417-token planner call, selected Letterboxd, fetched
   three ephemeral attributed sources in 2.566 seconds and moved automated packet quality from
   `limited` to `passed` without a second provider call.
3. The unchanged passing cinematography packet generated an insufficient synthesis even after the
   fixed service's one repair. The graph stopped `failed_safe`; no hidden extra repair was made.
4. A completed sound case scored 86, so mean quality over the four completed Agent studies was 94.77.
5. The frozen contract makes a completion failure an immediate no-go regardless of packet gain,
   passing latency or passing cost. The paid candidate was not rerun after observing the result.
6. No private packet snapshot or human Agent review was produced because local machine targets failed.
7. Post-run hardening removes model-generated section lens text from the redacted artefact and now
   rejects that field alongside prompts, drafts and evidence text.

Acceptance evidence:

- `evals/results/local-agent-paired-2026-08-24.json` contains the complete five-pair denominator,
  target statuses, safe failures, model attempts, token usage and aggregate packet/tool evidence;
- all identity, citation, instruction containment, selectivity, mutation, provider-repeat and graph
  budget checks pass, while completion and mean quality remain visibly failed;
- all 242 automated tests, including the concurrently merged Pi-subagent contract, pass with scoped
  Ruff, compilation, JSON parsing, documentation links, report privacy scans and whitespace checks;
- the decision contract and scorecard now record `no_go`; production and hosted routes remain absent;
- `.agents/` is ignored because local conversion/agent workspaces currently contain extracted private
  book text and must never enter Git.

Known constraints:

- five pairs cannot distinguish provider/model sampling variance from stable quality differences, but
  the predeclared acceptance rule does not permit discarding or rerunning the failed attempt;
- automated packet improvement does not establish the missing human diversity/actionability gain;
- a revised packet-only or deterministic-synthesis experiment would be a new hypothesis and requires
  explicit owner approval before changing controls or spending calls.

Next actionable work:

1. Keep the fixed workflow in production and retain the default-off Agent code as non-production
   experimental infrastructure.
2. Do not rerun or tune against this result. If the owner wants another experiment, record REVISE with
   a new causal hypothesis and thresholds first.
3. Continue fixed-workflow improvements or the separately planned clip-to-study evidence bridge.

### 24 August 2026 — Redacted local Agent paired evaluator ready

Delivered:

1. Added a fail-closed evaluator that requires both the environment switch and the machine-readable
   owner GO before constructing the local Agent service.
2. Stabilises caches and the embedding encoder once, hashes each private initial packet, then runs
   fixed control immediately before Agent candidate for every frozen identity/question.
3. Records completed and failed model attempts, aggregate planner/tool timing and tokens, graph
   budgets, packet diagnostics, identity/citation/quality results and paired latency/cost ratios
   without serialising questions, titles, prompts, drafts or evidence text.
4. Enforces zero external calls and zero packet mutation for initially sufficient packets, at most two
   planner/external calls for a limited packet and no repeated provider tool.
5. Keeps three human targets pending and the no-route UI target deferred rather than manufacturing a
   result. A partial `--case` run is diagnostic and cannot pass the local comparison.
6. Writes full candidate packets only after a complete local machine pass, under ignored
   `.firstroll/evaluations/` with directory mode `0700` and file mode `0600`.

Acceptance evidence:

- all 236 automated tests pass with scoped Ruff, compilation, JSON parsing, documentation links and
  whitespace checks;
- pure target tests prove quality/identity/citation/instruction, P50/P95 and token thresholds map to
  the frozen decision while human/no-route targets remain distinct;
- policy tests fail sufficient-packet acquisition or mutation and repeated/over-budget tool use;
- report guards reject nested source/prompt fields, failed provider exceptions never enter call
  records and private packet output outside `.firstroll` is refused;
- the evaluator help path and full static contract run without any provider or model call.

Known constraints:

- a full paired run spends five fixed synthesis calls, five Agent synthesis calls and up to two
  planner calls plus bounded public-provider acquisition;
- same-day pairing controls timing/configuration drift but five cases still cannot establish provider
  reliability;
- the local CLI has no product route, so visible-response and hosted operational targets remain
  deferred to a separately authorised phase.

Next actionable work:

1. Merge and release this no-production-behaviour checkpoint.
2. Run the complete five-case paired evaluation once with the current configuration and inspect the
   redacted result before versioning it.
3. If every local machine target passes, ask the owner to review only candidate packets whose hashes
   changed; otherwise retain the no-go and diagnose the failed causal layer.

### 24 August 2026 — Project-local Pi subagents available

Delivered:

1. Added a trusted `.pi/extensions/subagent` tool adapted from Pi 0.84.2. It starts each delegated
   task in a separate non-persistent Pi process and supports single, sequential-chain and bounded
   parallel execution, with a fifteen-minute deadline per child.
2. Added project-local scout, planner, reviewer and worker roles. They inherit the dispatching
   session's model and thinking level rather than requiring a second provider account or hard-coded
   model.
3. Made project agents the default scope, added `/subagents` plus three reusable workflow prompts,
   limited chains to six steps and parallel dispatch to eight tasks with four live children, and
   capped total model-visible tool output at 50 KB.
4. Kept reconnaissance, planning and review roles read-only, rejected project-agent directory/file
   symlinks, and made parallel mode refuse agents with write or unrestricted default tools. The
   one-worker-at-a-time contract keeps Git and delivery with the parent and excludes `.firstroll`,
   credentials, private books, extracted text, vectors, cookies and uploaded clips from every role.
5. Documented project trust, `/reload`, provider-cost multiplication, shared-working-tree risks and
   the prompt-level rather than sandboxed nature of the controls. Added the upstream MIT notice.

Acceptance evidence:

- Pi loads the extension from a trusted clean worktree without startup errors;
- a live isolated `gpt-5.4-mini` scout smoke test reads only `AGENTS.md`, returns its first heading,
  reports nested usage, creates no child session and leaves the worktree unchanged;
- live negative smokes reject a symlinked project-agent directory and two parallel workers before any
  child process starts; a final isolated reviewer reports no remaining critical issues or warnings;
- all 239 automated tests pass; focused static coverage verifies project-default discovery, inherited
  models, role tool bounds, output and concurrency caps, private-data exclusions, workflow prompts
  and attribution;
- scoped Ruff, extension and frontend JavaScript syntax, npm audit and repository whitespace checks
  pass.

Known constraints:

- subagents share the parent's working tree and provider allowance; they are not containers, account
  quota boundaries or safe concurrent writers;
- project-agent restrictions are prompts plus parent review, not operating-system enforcement;
- an existing Pi session needs `/reload`, and a new checkout must be trusted before project code can
  execute.

Next actionable work:

1. Use parallel delegation only for independent read-only work and observe token/latency value before
   raising either concurrency limit.
2. Reconcile the adaptation against Pi release notes when upgrading beyond the tested 0.84.2 API.

### 24 August 2026 — Default-off local Agent adapter implemented

Delivered:

1. Added a concrete local `ResearchGraphServices` adapter over the existing selected-film detail,
   fixed packet, attributed provider and DeepSeek synthesis services without registering an HTTP
   route.
2. Reused the unchanged aggregate packet-quality status as the sufficiency boundary: a passing packet
   skips both planner and external acquisition, while a limited packet may enter the two-call graph
   budget.
3. Added one aggregate-only DeepSeek tool-selection call. It receives public film identity, focus,
   allow-listed provider state and safe packet issue/count fields; tests prove injected evidence text
   and provider secrets cannot enter that request.
4. Mapped Guardian, Douban, official-or-public Letterboxd and YouTube/Bilibili adapters into ephemeral
   acquisitions. Candidate sources rebuild the unchanged `EvidencePacket` but are not written to
   criticism or video caches.
5. Reused unchanged synthesis and validation, counted planner tokens separately, and exposed only
   safe planner/tool durations, statuses, counts and packet diagnostics to the future evaluator.
6. Added `FIRSTROLL_LOCAL_AGENT_ENABLED=0`; even when explicitly enabled, it exposes only a Python
   factory and cannot alter local or hosted Deep Study routes.

Acceptance evidence:

- all 229 automated tests pass with scoped Ruff, compilation, JSON parsing, documentation links and
  whitespace checks;
- the frozen aggregate packets prove the diagnostic boundary targets exactly the one human-failed
  case; sufficient packet shapes complete with zero planning/external calls, while a sparse shape
  acquires one review and completes through unchanged synthesis;
- one unavailable provider falls back exactly once within the two-call budget;
- invalid/out-of-policy planner output remains fail-safe, boolean/negative token usage is rejected and
  tool requests still pass deterministic authorisation;
- safe metrics contain no injected review text, prompts, credentials or provider exception details;
- hosted mode forces the flag off, OpenAPI contains no Agent route, and production remains the fixed
  workflow;
- no real provider or DeepSeek comparison call was made, so quality, latency, cost and recovery gains
  remain unclaimed.

Known constraints:

- the adapter currently starts from an explicitly selected canonical film ID; ambiguity remains the
  unchanged pre-research user decision;
- graph evidence is bounded in memory and this local comparison compiles without a checkpointer;
  durable owner-scoped persistence remains mandatory before any hosted proposal;
- integrated synthesis already owns its one repair decision, so the graph cannot spend an additional
  hidden repair call;
- the paired evaluator and real five-case run are still pending.

Next actionable work:

1. Add the redacted same-day paired evaluator with fixed control first and ephemeral Agent acquisition.
2. Run fake timeout/empty/invalid-planner acceptance, then the five frozen cases only when configuration
   fingerprints match.
3. Request human review of Agent packets only if every machine target passes.

### 24 August 2026 — Owner authorises bounded local Agent comparison

Decision:

1. The repository owner selected **GO — bounded comparison only** with the direction “go local
   first”.
2. The authorised scope is a default-off local `ResearchGraphServices` adapter, same-day fixed/Agent
   paired evaluation and a local human packet review only if machine targets pass.
3. Hosted Agent routing, production cut-over, removal of the fixed fallback and unbounded tool/model
   calls remain explicitly unauthorised.
4. The causal hypothesis, controls and acceptance thresholds in `evals/agent_go_no_go.json` are now
   frozen before implementation.

Acceptance evidence:

- the decision record names the repository owner role, UTC decision time, authorised scope and
  explicit exclusions without storing personal data;
- all 220 automated tests, scoped Ruff, JSON parsing, documentation links and whitespace checks pass;
- the scorecard marks all twelve Pre-Agent steps complete while retaining a separate no-go for
  production route cut-over;
- no Agent quality, latency, token or recovery result is invented: real adapter/evaluation fields
  remain false until measured.

Next actionable work:

1. Implement the default-off local adapter over existing identity, packet, provider and synthesis
   services without adding a hosted route.
2. Prove deterministic sufficiency and tool-authorisation behaviour with fake failure coverage.
3. Run the same-day paired five-case evaluation and request human review only if every machine target
   passes.

### 24 August 2026 — Scoped Agent decision prepared; owner review pending

Delivered:

1. Wrote the Step 12 go/no-go brief against the frozen fixed-workflow evidence rather than treating
   the existence of a LangGraph core as proof of value.
2. Isolated one measurable hypothesis: at most two gap-directed attributed-source acquisitions should
   raise the failed ambiguous-identity packet from diversity/actionability `2/3` to at least `3/4`
   without changing identity, theory retrieval, packet selection, synthesis, validation, model or UI.
3. Predeclared same-day paired quality, recovery, identity, safety, latency, cost and operational
   targets before implementing or observing a real Agent adapter.
4. Recommended a conditional GO only for a default-off local adapter/evaluation and recorded an
   explicit NO-GO for production route cut-over until every comparison target passes.
5. Kept all real Agent fields honest: the current graph has fake-service policy tests but no real
   service adapter, frozen-suite run, human packet review, latency, token or production-route result.

Decision evidence:

| Dimension | Fixed control | Agent evidence now | Required candidate |
|---|---:|---:|---:|
| Human packets | 4 / 5 | Unmeasured | 5 / 5 |
| Failed-case diversity / actionability | 2 / 3 | Unmeasured | ≥ 3 / ≥ 4 |
| Complete workflow / automated quality | 5 / 5 · 98.65 | Unmeasured | 5 / 5 · ≥ 96.94 |
| Quality gate / citations | 100% / 100% | Fake only | 100% / 100% |
| End-to-end P50 / P95 | 55.407 / 62.129 s | Unmeasured | ≤ 110% / ≤ 125% of paired control |
| Calls / total tokens | 5 / 38,875 | Unmeasured | ≤ 2 extra planner calls · ≤ 125% tokens |
| Production route | Fixed workflow live | Disabled | Remains disabled during comparison |

Acceptance evidence:

- all 220 automated tests, scoped Ruff, JSON parsing, documentation links and whitespace checks pass;
- the machine-readable decision is tied to the final gate, human failed case and reliability result;
- tests prevent a recommendation from being represented as observed Agent evidence and require the
  default-off flag, fixed fallback and no-cut-over state;
- the brief compares quality, recovery, latency, cost and operational complexity under the same
  frozen identities/questions and explicitly retains failures and safe stops in the denominator;
- the decision artefact contains aggregate metrics and limits only—no prompt, source text, private
  passage, review body, vector, cache, credential or uploaded clip.

Blocked:

- Step 12 requires the repository owner's explicit GO, NO-GO or REVISE decision;
- no production-compatible Agent adapter or Agent evaluation may begin before that decision;
- public route cut-over remains a separate no-go even if the bounded comparison is authorised.

Next actionable work:

1. Owner reviews `docs/AGENT_GO_NO_GO.md` and records GO, NO-GO or REVISE.
2. On GO, implement only the default-off local adapter and paired evaluation contract; on NO-GO,
   leave the fixed workflow live; on REVISE, freeze changed targets before implementation.

### 21 August 2026 — Fixed-workflow baseline frozen; Agent entry gate passed

Delivered:

1. Accepted the repository owner's five-case personal packet review at runtime revision `6b24f1b8`
   and versioned only its attested score aggregate; private notes and packet evidence remain local.
2. Combined the human result with every versioned machine result and checked both target and required
   step completion rather than allowing green metrics to bypass an incomplete programme step.
3. Froze Step 11 and moved Step 12 to `next`; `agent_entry_ready` now means the comparison decision is
   permitted, not that production Agent integration is approved.
4. Hardened interactive review input to replace malformed terminal bytes instead of losing a
   completed score set to `UnicodeDecodeError`.
5. Preserved the failed ambiguous-identity packet as a visible limitation rather than altering the
   frozen threshold or padding sparse evidence.

Final gate:

| Measure | Observed | Required | Status |
|---|---:|---:|---|
| Required targets | 17 / 17 | 17 / 17 | Passed |
| Required steps | 11 / 11 | 11 / 11 | Passed |
| Failed / pending targets | 0 / 0 | 0 / 0 | Passed |
| Human packet cases | 4 / 5 | ≥ 4 / 5 | Passed |
| Human packet ratio | 0.8 | ≥ 0.8 | Passed |
| Mean relevance / traceability | 4.4 / 5.0 | Reported | Passed |
| Mean diversity / calibration / actionability | 3.8 / 5.0 / 4.2 | Reported | Passed |

Acceptance evidence:

- all 219 automated tests, scoped Ruff, backend/tool compilation, JSON parsing, documentation links
  and repository whitespace checks pass;
- the attested review contains exactly five safe case IDs, numeric dimension scores and pass flags;
  no reviewer note, private passage, prompt, review body, vector or cache is versioned;
- four cases pass all human rules; the ambiguous-identity case fails honestly at diversity 2 and
  actionability 3 while retaining traceability 5 and calibration 5;
- the final gate records 17 passed targets, 11 completed required steps, no blockers and
  `agent_entry_ready: true`;
- tests prove that an incomplete required step still blocks entry even when all 17 target values
  pass, and malformed input bytes are replaced rather than crashing the private review.

Known constraint:

- passing at the exact 0.8 threshold does not erase the failed packet: complementary film-specific
  evidence and immediate viewing actionability remain weak for the ambiguous-identity case;
- the five-case synthesis run remains a regression fixture, not a provider-reliability claim;
- production Agent integration remains prohibited until Step 12 reaches an explicit reviewed go
  decision.

Next actionable work:

1. Write the Step 12 comparison brief around the measured fixed-workflow deficiency rather than a
   generic Agent aspiration.
2. Decide whether a bounded Agent can improve sparse film-specific evidence diversity/actionability
   under the same identities, questions, quality, latency, token, cost and recovery contract.
3. Keep the fixed workflow in production unless that comparison supports an explicit go decision.

### 21 August 2026 — Final machine gate passes; human packet review pending

Delivered:

1. Added a deterministic final-gate checker that reads only versioned aggregate results and maps all
   required scorecard targets to their exact evidence paths, comparisons and thresholds.
2. Added a local resumable human-review tool for the five real packets. It prints private selected
   evidence only in the terminal, stores scores/notes with mode `0600` under `.firstroll` and emits a
   separate score-only aggregate after explicit uppercase `YES` attestation.
3. Added pass-rule coverage: focus relevance, traceability and filmmaker actionability must each be
   at least 4, no dimension may be below 3 and at least four of five packets must pass.
4. Added a private reviewer guide with dimension-specific 1/3/5 anchors, privacy instructions,
   resume behaviour and the final gate command.
5. Versioned the machine gate at the tooling source revision without inventing a human result.

Machine-gate result:

| Gate | Observed | Required | Status |
|---|---:|---:|---|
| Machine-assessable targets | 16 / 16 | 16 / 16 | Passed |
| Failed machine targets | 0 | 0 | Passed |
| Warm packet P95 | 0.204671 s | ≤ 2 s | Passed |
| Prompt median / P95 | 6,327 / 7,415.6 | ≤ 8,000 / 12,000 | Passed |
| Provenance / citation / instruction containment | 100% / 100% / 100% | 100% | Passed |
| Maximum duplicate ratio | 0% | < 10% | Passed |
| Complete workflow / mean quality | 5 / 5 · 98.65 | 5 / 5 · ≥ 96.94 | Passed |
| Paired P50 improvement / P95 regression | 16.9011% / −20.1406% | ≥ 15% / ≤ 0% | Passed |
| Human packet pass ratio | Not supplied | ≥ 80% | **Pending** |

Acceptance evidence:

- all 217 automated tests, scoped Ruff, tool/backend compilation and repository whitespace checks
  pass;
- machine gate reports 17 required targets, 16 passed, zero failed and one pending, with
  `agent_entry_ready: false`;
- tests prove a five-case attested score-only review at 80% completes the target, while weak core or
  any sub-3 score fails the case;
- private reviewer notes cannot enter the redacted aggregate, and a partial review is saved for
  revision-safe resume rather than treated as acceptance;
- the committed machine-gate result contains no packet, prompt, private passage, vector, cache or
  reviewer note.

Blocked:

- Step 11 cannot complete until the repository owner personally inspects and scores all five packets;
- Step 12 and all Agent development remain blocked while `human_packet_pass_ratio` is pending.

Next actionable work:

1. On current clean `master`, run `uv run python tools/review_evidence_packets.py`, inspect all five
   packet evidence sets privately, enter the five dimension scores and type `YES` only after personal
   review.
2. Rerun `tools/check_pre_agent_gate.py` with the redacted local aggregate; commit the final gate and
   freeze Step 11 only if at least four cases pass.

### 21 August 2026 — Bounded synthesis recovery and concise output

Delivered:

1. Held the Step 8 packet fixed and added explicit 120–180-word central and 140–210-word per-section
   guidance with a 3,200-token completion ceiling, down from 3,600.
2. Unified recovery under one total extra model call: an invalid initial schema/citation response can
   retry once at temperature zero, while a valid draft that fails quality retains its existing one
   repair. Either path consumes the single repair budget.
3. Kept timeout/unavailability retries explicit and user-controlled because an upstream request may
   already have consumed provider usage; transport failure receives no hidden second call.
4. Added deterministic fake coverage for successful invalid-response recovery, repeated invalid
   citation stop, total call/token accounting and one-call timeout behaviour.
5. Ran the same five-case live workflow on the same machine/configuration and compared it with the
   immediately preceding held-packet checkpoint.

Measured comparison:

| Measure | Held-packet Step 8 | Reliability checkpoint | Change |
|---|---:|---:|---:|
| Cases completed | 5 / 5 | 5 / 5 | No regression |
| Mean / median quality | 98.30 / 99.25 | 98.65 / 98.25 | +0.35 mean |
| Gate / valid citations | 100% / 100% | 100% / 100% | No regression |
| Input-token median / P95 | 6,288 / 7,376.6 | 6,327 / 7,415.6 | Within budget |
| Completion-token median / P95 | 2,969 / 3,225.2 | 2,287 / 2,552.4 | −22.97% / −20.86% |
| Model-latency median / P95 | 52.887 / 55.195 s | 38.694 / 42.654 s | −26.84% / −22.72% |
| End-to-end P50 / P95 | 66.676 / 77.798 s | 55.407 / 62.129 s | −16.9011% / −20.1406% |
| Model calls / total tokens | 5 / 42,234 | 5 / 38,875 | −7.95% tokens |

Acceptance evidence:

- all 214 automated tests, scoped Ruff, backend/tool compilation, frontend JavaScript syntax, npm
  audit and repository whitespace checks pass;
- all five live cases complete without repair, all citations validate and all completed studies pass
  the deterministic gate at 98.65 mean quality, above the 96.94 floor;
- paired P50 improves more than the required 15%, P95 improves rather than regresses and provider
  prompt P95 remains below 12,000 tokens;
- invalid initial fake output recovers on exactly one retry with two validation attempts; repeated
  invalid citations stop after two calls and a synthetic timeout stops after one;
- the result contains no private title or 120-character private passage fragment.

Known constraints:

- five successful cases remain a regression fixture, not the twenty attempts required for a
  provider-reliability claim;
- provider latency varies independently of prompt/output changes, so paired results support a release
  gate rather than a causal performance proof;
- shorter prose still requires the final human usefulness/actionability review;
- explicit user retry after timeout can still incur a second external charge, which the UI boundary
  already discloses.

Next actionable work:

1. Complete Step 11 by freezing the integrated fixed-workflow baseline, rerunning all automated,
   packet, adversarial, desktop/mobile and human packet gates and closing any remaining P0/P1 defect.

### 21 August 2026 — Inspectable Deep Study progress, packet and citations

Delivered:

1. Retained the complete allow-listed research-event history instead of replacing each prior stage
   with one current sentence. The latest message alone remains live for assistive technology, while
   the visual history and elapsed times remain available after completion or failure.
2. Kept hosted pre-model transparency within the existing public SSE contract: theory, critic-claim,
   attributed-text and section counts only. No prompt, token, source text, hidden reasoning or new
   event field enters the stream.
3. Attached the existing redacted packet-quality assessment to the authenticated/local complete study
   result and rendered selected/candidate/omitted counts for theory, critic claims and attributed
   text, plus selected characters and recognised omission reasons.
4. Added result-level provenance, duplicate, lexical-focus and provider input-token metrics, explicit
   film-specific/clip evidence gaps and expandable stage/timing observations.
5. Turned every inline `S`, `C` and `E` marker into a keyboard-focusable link to one exact expandable
   theory passage, critic claim or attributed source; activation opens, centres and focuses the
   target.
6. Versioned a zero-model, synthetic-safe mobile transparency audit and reran automated privacy,
   citation, stream and accessibility contracts.

Acceptance evidence:

- all 212 automated tests, frontend JavaScript syntax, scoped Ruff, hosted frontend build, npm audit
  and repository whitespace checks pass;
- a completed synthetic run retains three progress events and all four safe aggregate count types;
- the result renders three packet layer cards, recognised omission details, two evidence-gap items,
  four timing rows and provider input-token count without rendering a prompt or hidden reasoning;
- all three synthetic inline citations resolve to three unique evidence targets; activating `S1`
  opens it and moves focus with zero navigation failure;
- Chrome at 390 × 844 reports no horizontal overflow, axe WCAG violation or incomplete check in the
  complete transparency context;
- backend tests prove every returned valid study receives the aggregate `packet_quality` object,
  while authenticated SSE ordering/field redaction remains unchanged;
- the acceptance audit makes zero model calls and commits no synthetic source excerpt in its result.

Known constraints:

- the local synchronous route cannot report intermediate server stages before its response; it shows
  a waiting state followed by complete result-level packet/timing diagnostics;
- lexical-focus percentage is a structural proxy, not semantic or human relevance;
- complete selected evidence is intentionally owner-visible, so opening a citation can display
  private local excerpts in the local result even though SSE and the audit remain redacted;
- durable/resumable hosted history still depends on replacing the ten-minute process-local run store.

Next actionable work:

1. Complete Step 10 by isolating model/timeout reliability from the now-bounded packet, running paired
   controlled trials and retaining only changes that preserve the 98.3 quality checkpoint.

### 21 August 2026 — Focus-ranked bounded packet selection

Delivered:

1. Replaced first-in packet filling with focus-aware ranking that retains retrieval order as a
   deterministic tie-break and gives selected critic sources plus verified creator speech explicit
   priority.
2. Added exact/near duplicate removal, per-title/source/domain diversity limits and inferred `en`/`zh`
   language for otherwise-unlabelled video descriptions while preserving source URLs and locators.
3. Bounded synthesis to eight theory passages, twelve critic claims and twelve attributed excerpts,
   with 12,000-character claim, 18,000-character attributed and 3,000-character per-item limits.
   Every omitted candidate receives one aggregate reason.
4. Renumbered selected `S`, `C` and `E` identifiers contiguously and extended redacted observability
   with candidate/omission counts; citation validation remains unchanged.
5. Compacted only the provider prompt's JSON/fields. The complete selected typed evidence, provenance,
   boundaries and selection manifests remain inspectable in the returned study.
6. Reran the synthetic quality suite, all 35 frozen packet preparations and one five-case live
   fixed-workflow evaluation at the same source revision.

Packet and synthetic acceptance:

| Measure | Result |
|---|---:|
| Frozen packet samples completed | 35 / 35 |
| Applicable provenance completeness | 100% |
| Mean / maximum selected duplicate ratio | 0% / 0% |
| Mean lexical focus relevance | 82.73% |
| Packet status | 28 passed samples · 7 honestly limited *The Thing* samples |
| Median / maximum packet JSON | 26,150 / 33,556 characters |
| Median / maximum compact synthesis prompt | 23,242 / 29,360 characters |
| Synthetic packet status | 5 passed · 1 honestly sparse limited |
| Synthetic malicious items flagged / contained | 2 / 2 |
| Packet/synthetic model calls | 0 |

Complete-workflow acceptance:

| Measure | Pre-selection | Bounded selection |
|---|---:|---:|
| Cases completed | 4 / 5 | 5 / 5 |
| Mean / median automated quality | 97.02 / 97.38 | 98.30 / 99.25 |
| Valid citations / deterministic gate | 100% | 100% |
| Completed-study prompt median / P95 | 9,577 / 14,830.6 | 6,288 / 7,376.6 |
| P50 / P95 end to end | 77.679 / 91.225 s | 66.676 / 77.798 s |
| Model calls / total tokens | 5 / 63,764 | 5 / 42,234 |

Acceptance evidence:

- all 211 automated tests, scoped Ruff, backend/tool compilation, frontend JavaScript syntax, JSON
  parsing, npm audit and repository whitespace checks pass;
- deterministic tests enforce contiguous IDs, 8/12/12 item limits, layer character budgets,
  source/domain quotas, duplicate omission and redacted selection manifests;
- the synthetic duplicate case moves from limited to passed with 0% selected duplication; the
  intentionally sparse case remains limited and both malicious evidence items remain contained;
- all five live workflow cases complete without repair, retain valid citations and pass the quality
  gate; mean quality is above both the 96.94 floor and the pre-selection checkpoint;
- completed-study median/P95 input tokens improve 34.34%/50.26%, establishing both 8,000/12,000
  scorecard budgets, while complete-suite token use falls 33.77%;
- scans across all three results find no private title or 120-character private passage fragment.

Known constraints:

- focus overlap and ranking are deterministic lexical heuristics rather than semantic or human
  relevance judgements;
- omission improves model context but does not delete cached source material; users can still inspect
  provider bundles separately in the dossier;
- *The Thing* remains honestly limited because no film-specific attributed source is cached;
- one five-case model run is a regression checkpoint, not a provider-reliability estimate or proof
  that selection alone caused every latency/quality change;
- human usefulness and actionability still require the final blind rubric.

Next actionable work:

1. Complete Step 9 by showing packet readiness, selected/omitted counts, completed progress history,
   evidence gaps and inspectable citation targets without exposing prompts or private text in SSE.

### 21 August 2026 — Synthetic pre-synthesis packet-quality baseline

Delivered:

1. Added six commit-safe packet fixtures covering abundant complementary evidence, honest scarcity,
   duplicate criticism, multilingual provenance, explicit same-title identity and malicious
   retrieved instructions without modifying the frozen Agent comparison suite.
2. Added deterministic pre-synthesis diagnostics for film identity, citation-ID readiness,
   applicable provenance, exact/near duplication, lexical focus overlap, evidence/language diversity,
   sufficiency, selection pressure, packet size and instruction containment.
3. Added a packet boundary stating that retrieved source instructions are untrusted evidence and
   cannot authorise tools or change FirstRoll policy, reinforcing the existing system-prompt rule.
4. Kept reports redacted by construction: only counts, ratios, allow-listed issue/status codes and
   language/evidence-type labels can be emitted; film/focus/title/prompt/review/passage/source-text
   fields are rejected before write.
5. Added a zero-model evaluator and versioned the first fixture fingerprint/result at the exact source
   revision under assessment.

Baseline result:

| Measure | Result |
|---|---:|
| Cases assessed / expectation failures | 6 / 0 |
| Packet status | 4 passed · 2 limited · 0 failed |
| Mean provenance completeness | 100% |
| Mean duplicate ratio | 3.33% |
| Mean lexical focus relevance | 94.45% |
| Malicious items flagged / contained cases | 2 / 1 |
| Model calls | 0 |

Acceptance evidence:

- all 210 automated tests, scoped Ruff, backend/tool compilation, frontend JavaScript syntax, JSON
  parsing and repository whitespace checks pass;
- direct coverage blocks missing theory, wrong identity and invalid citation IDs; reports incomplete
  attributed provenance and unknown language without returning evidence text;
- all six fixture identities match, required `en`/`zh` languages survive and all fixture
  expectations pass;
- the malicious case flags both instruction-bearing evidence items while the containment boundary
  remains true and no `instruction_containment_missing` issue appears;
- the sparse case remains honestly limited by `film_specific_evidence_sparse`, while the duplicate
  case remains limited by `duplicate_evidence_present` at a 20% case-level duplicate ratio;
- the committed result passes its forbidden-field scan and reads no private library or provider data.

Known constraints:

- lexical focus overlap is a deterministic diagnostic, not semantic relevance or a human judgement;
- synthetic provenance and instruction coverage prove contract behaviour, not the factual quality of
  live criticism, captions or private books;
- exact/near duplicate detection measures the selected packet but does not yet remove anything;
- creator/actionability scoring and blind human review remain later gates.

Next actionable work:

1. Complete Step 8 by applying focus-aware, provenance-conscious deduplication and token budgets to
   actual packet selection, then rerun both synthetic and frozen packet-only measurements.

### 21 August 2026 — Background semantic prewarm removes cold packet stall

Delivered:

1. Added a local-only startup handler that loads the unchanged multilingual query encoder in one
   daemon thread while the API and Discover remain responsive. Hosted public mode never loads the
   private index.
2. Added model-initialisation and encode locks so startup, an early study request and index rebuild
   cannot construct duplicate encoder instances or run unsafe concurrent inference.
3. Exposed only `idle`, `warming`, `ready`, `failed` or `unavailable`, aggregate milliseconds and the
   background flag through existing local index status. The warm-up embeds one fixed FirstRoll phrase
   and reads no private chunk.
4. Made Discover announce temporary background preparation and honest lexical fallback after a
   failed warm-up; `FIRSTROLL_PREWARM_EMBEDDINGS=0` restores deferred loading.
5. Extended the packet harness with an explicit prewarm protocol that keeps encoder startup outside
   packet timing while retaining its cost as a separate distribution.
6. Versioned a 35/35-sample candidate from the same five cases with zero model calls and exactly the
   same aggregate packet-shape object as the unprewarmed baseline.

Measured comparison:

| Measure | Baseline | Prewarmed candidate | Change |
|---|---:|---:|---:|
| Cold-process P50 | 9,420.905 ms | 272.919 ms | −97.1030% |
| Cold-process P95 | 10,013.910 ms | 361.549 ms | −96.3895% |
| Warm P50 | 138.240 ms | 149.896 ms | +8.4317% |
| Warm P95 | 182.306 ms | 182.709 ms | +0.2211% |
| Semantic cold-stage P95 | 9,886.688 ms | 237.969 ms | −97.5930% |
| Background encoder warm-up P95 | Included in request | 10,155.338 ms | Reported separately |

Acceptance evidence:

- all 205 automated tests, scoped Ruff, backend/tool compilation, frontend JavaScript syntax,
  hosted frontend build, npm audit and repository whitespace checks pass;
- deterministic concurrency coverage proves one encoder construction across concurrent callers,
  one idempotent warm-up and redacted failure state without exception details;
- startup coverage proves local default prewarm, explicit disablement and public-mode exclusion;
- a live local API starts accepting status requests while state is `warming`, then reports `ready`
  after 9,979.749 ms without a restart;
- all ten fresh-process warm-ups complete, all 35 packet samples complete and warm P95 remains far
  below the two-second budget;
- theory, criticism, attributed, selected/unselected, omission/truncation and character metrics are
  byte-for-byte equal at the aggregate level between baseline and candidate.

Known constraints:

- prewarming moves roughly ten seconds of encoder initialisation off the packet request path; it does
  not reduce its CPU, memory or model-file cost;
- a user who requests semantic study retrieval before readiness can still wait on the same
  single-flight load, while a failed load falls back to lexical retrieval;
- cold-process timing retains normal operating-system/model-file caches and remains machine-specific;
- warm P50 varies upward while P95 is effectively unchanged, so no warm-speed improvement is claimed.

Next actionable work:

1. Complete Step 7 by adding synthetic packet-quality fixtures for abundant, sparse, duplicate,
   multilingual, ambiguous and malicious retrieved content without changing the frozen Agent cases.

### 21 August 2026 — Actionable states and WCAG-audited keyboard flow

Delivered:

1. Replaced raw search, dossier, video, criticism, saved-film and Deep Study failures with bounded
   state panels that explain what remained unchanged and expose a direct retry or corrective action.
2. Added browser-side Deep Study cancellation with request IDs and `AbortController` signals across
   local, streamed and result fetches. **Stop waiting** prevents stale rendering and warns honestly
   that already-started provider work may still finish and consume external quota.
3. Added busy semantics and focus movement for search, dossier, evidence-provider, study and result
   transitions, while removing oversized live regions that could announce an entire dossier.
4. Completed roving keyboard tab contracts for analysis, settings, account mode, video category and
   criticism controls, including Arrow, Home and End movement and labelled controlled panels.
5. Corrected generic-container ARIA use, excluded hidden processing media from the accessibility
   tree and introduced theme-specific primary-action text colour after axe identified a 3.05:1 dark
   contrast defect.
6. Versioned a no-model UI state/accessibility audit covering eight terminal states, four keyboard
   tablists and three axe contexts at the source revision under test.

Acceptance evidence:

- all 199 automated tests, JavaScript syntax, scoped Ruff, hosted frontend build, npm audit and
  repository whitespace checks pass;
- search connection, empty filtered search, dossier, video and criticism synthetic failures all move
  focus to a status/alert, clear `aria-busy`, preserve the relevant identity/input/evidence and expose
  an explicit action without rendering synthetic private exception text;
- Deep Study cancellation exposes a busy state and stop control, responds in 6.1 ms, restores
  generation and focuses an honest retry state; a synthetic provider failure responds in 215.7 ms,
  redacts its private detail and preserves the film/evidence/focus;
- valid synthetic study completion focuses the result and clears both busy and stop controls without
  spending a model call;
- analysis, settings, account and dynamic video tablists each retain one selected tab stop and move
  focus/panel correctly with Arrow or End keys;
- axe-core 4.13 reports zero WCAG 2 A/AA/2.1 AA violations and zero incomplete checks on Discover,
  the 390 × 844 dossier and its Deep Study error/retry state;
- dark primary-action contrast improves from 3.05:1 to 5.79:1 against the 4.5:1 AA requirement, and
  all audited mobile states retain zero horizontal overflow.

Known constraints:

- aborting browser fetches cannot terminate synchronous provider work already running in a backend
  worker; user copy states this boundary and no cost-saving cancellation claim is made;
- synthetic bounded failures exercise deterministic UI behaviour without creating paid provider
  calls, but do not estimate real timeout frequency;
- automated axe and keyboard checks do not replace VoiceOver/NVDA user testing, Safari/Firefox,
  physical devices, browser zoom or operating-system high-contrast validation;
- detailed completed-stage/evidence transparency remains Step 9 rather than being folded into this
  error-state checkpoint.

Next actionable work:

1. Complete Step 6 by addressing measured latency only: warm packet P95 already passes at 182.306 ms,
   so concentrate on the approximately ten-second cold semantic-model initialisation path without
   changing evidence selection.

### 21 August 2026 — Task-led responsive product hierarchy

Delivered:

1. Replaced the nearly context-free Discover landing state with a compact product promise that tells
   filmmakers to confirm identity, inspect attributed perspectives and prepare precise viewing
   questions before the search form.
2. Marked title as required, year/director as optional and added examples without changing the exact
   identity contract or recent-search/session boundaries.
3. Moved primary dossier actions ahead of the catalogue synopsis, bounded long synopsis copy behind
   a native disclosure and collapsed secondary credit/fact detail by default at 390-pixel width.
4. Added a numbered route through **Watch & verify**, **Read perspectives** and **Build the study**,
   with evidence-aware counts and explanatory section copy that preserves the difference between
   viewing context, attributed interpretation and synthesis.
5. Re-applied the dossier scroll after final render, preventing asynchronously changing shelf height
   from leaving a requested film below the viewport.
6. Versioned a redacted Chrome DevTools Protocol hierarchy audit over all six frozen journeys; it
   contains public fixture IDs and measurements only, with no screenshots, prompts or model call.

Acceptance evidence:

- all 198 automated tests, JavaScript syntax, scoped Ruff, hosted frontend build, npm audit and
  repository whitespace checks pass;
- six immediate-response observations report P50/P95 of 7.35/12.05 ms against the 300 ms budget;
- exact search presents its pending state in 10.1 ms and dossier opening in 5.3 ms; external terminal
  catalogue/detail latency remains separately visible rather than being labelled interface time;
- the ambiguous *The Thing* journey presents fourteen explicit choices at 390 pixels with no
  horizontal overflow;
- the *In the Mood for Love* dossier exposes three loaded provider tabs, six visible attributed
  sources, six applicable source links and all three dossier routes without mobile overflow;
- loaded dossier alignment finishes at 0.328 CSS pixels from the section top; on mobile, primary
  actions move from 792.156 to 208.609 CSS pixels and hero height falls from 1,749.688 to 1,037.688;
- Settings and the selected film restore after reload, and sparse criticism retains four acquisition
  actions plus a visible Deep Study route without displaying stale output.

Known constraints:

- this checkpoint audits hierarchy in local Chrome at 1,280 × 1,000 and 390 × 844 CSS pixels; Safari,
  Firefox and physical-device rendering remain unmeasured;
- Deep Study was not called again for a hierarchy-only audit; its current complete-workflow result is
  referenced instead;
- detailed empty/error/timeout copy, retry/cancellation, focus, keyboard, announcements and contrast
  belong to Step 5 and are not claimed complete here.

Next actionable work:

1. Complete Step 5 by making every loading, empty, sparse, degraded, timeout and retry state specific
   and actionable, then run keyboard, focus, announcement and critical-contrast checks.

### 21 August 2026 — Measured fixed-workflow and packet baselines

Delivered:

1. Added a model-free packet benchmark that resolves the five frozen canonical identities outside
   the packet clock, runs each case in two fresh processes and records five samples after one
   same-case warm-up without writing packet contents.
2. Versioned 35/35 successful packet preparations with full redacted stage observations, aggregate
   packet shape, source-selection pressure and a non-secret index/provider fingerprint aligned with
   workflow evaluation.
3. Added aggregate attributed candidate, selected, omitted and truncated item/character accounting
   to `EvidencePacket.retrieval`; this records selection pressure without retaining titles, authors,
   URLs or source text and does not change the initial synthesis prompt.
4. Ran one controlled five-case fixed-workflow evaluation with the new observability schema and
   source revision. Four studies completed, all four passed the deterministic gate and the sparse
   case ended as an operational invalid-JSON response after one billed model call.
5. Made source revision part of all future complete-workflow results and linked both measured
   checkpoints from the machine-readable Pre-Agent scorecard.

Measured packet result:

| Measure | Cold process | Warm process |
|---|---:|---:|
| Samples completed | 10 / 10 | 25 / 25 |
| Mean | 9,513.659 ms | 137.466 ms |
| P50 / P95 | 9,420.905 / 10,013.910 ms | 138.240 / 182.306 ms |
| Semantic retrieval P95 | 9,886.688 ms | 47.355 ms |
| Lexical retrieval P95 | 138.791 ms | 132.239 ms |
| Packet assembly P95 | 0.359 ms | 0.121 ms |

Measured complete-workflow result:

| Measure | Result |
|---|---:|
| Cases completed | 4 / 5 |
| Mean / median automated quality | 97.02 / 97.38 |
| P50 / P95 end to end | 77.679 / 91.225 s |
| Mean combined study stage | 61.403 s |
| Model calls / total tokens | 5 / 63,764 |
| Completed-study prompt-token median / P95 | 9,577 / 14,830.6 |

Acceptance evidence:

- all 197 automated tests, scoped Ruff, backend/tool compilation, JSON parsing and repository
  whitespace checks pass;
- the packet harness rejects query, question, title, director and evidence-text fields before write;
  repository scans find no credentials, private passages, local paths, prompts, excerpts or caches
  in either new result;
- every packet stage completed in all 35 samples, no model call occurred, and packet candidate/
  omission totals reconcile with selected evidence counts;
- the latest complete result preserves operational versus quality denominators and its four returned
  observability traces show model transport taking 48.498–64.058 seconds, far above warm packet
  preparation;
- README, evaluation reference, hardening plan and scorecard all identify Step 4 as next.

Known constraints:

- “cold” means a fresh Python process with empty process caches but a retained local index and normal
  operating-system/model-file caches; it is not a clean-machine or first-download measurement;
- the warm packet target already passes, but no improvement is claimed because this is the first
  packet-only baseline;
- the complete run is five cases, not a provider-reliability estimate or same-day paired optimisation
  trial; lower prompt-cache reuse makes direct latency attribution to the 18 August run invalid;
- packet relevance, factual correctness and filmmaker usefulness still require the later deterministic
  fixtures and human rubric.

Next actionable work:

1. Complete Step 4 by measuring and improving interface hierarchy across the six frozen desktop and
   390-pixel mobile journeys without combining packet or model changes.

### 21 August 2026 — Redacted study-stage observability

Delivered:

1. Added one shared monotonic trace spanning film-context loading, criticism/video caches, public or
   private retrieval, fusion, packet assembly, prompt serialisation, model transport,
   validation/repair and end-to-end study execution.
2. Made every stage terminal and explicit: completed, failed, degraded after mixed attempts, skipped
   when inapplicable or not run after an earlier stop. Repeated model, validation and repair attempts
   aggregate without hiding failures.
3. Restricted the schema to fixed stage/count allow-lists, bounded non-negative integers and timing
   metadata. Prompts, evidence excerpts, credentials, model output, URLs and exception messages have
   no accepted field.
4. Attached the trace to completed owner-visible studies and emitted the same redacted object to
   application logs on success or failure, while leaving the smaller public SSE contract unchanged.
5. Recorded retrieval/evidence counts, prompt characters, model and repair attempts,
   provider-reported token use and section totals, and taught the evaluator to retain this safe
   object in future results without altering the historical baseline.
6. Replaced CI's curated test-file subset with the complete hosted-safe `tests` suite so packet,
   evaluator, observability, stream and study-service contracts cannot pass only on a developer
   machine.

Acceptance evidence:

- all 193 automated tests, scoped Ruff, backend compilation, frontend JavaScript syntax and
  repository whitespace checks pass;
- deterministic-clock coverage verifies completed, skipped, failed and degraded stages, aggregate
  attempts/failures, exact durations, token totals and rejection of arbitrary names or values;
- public-framework tests prove lexical/semantic stages are explicitly skipped, while a synthetic
  local SQLite/embedding index proves planning, lexical, semantic and fusion stages complete;
- service coverage proves one repair records two prompt/model attempts and three validation passes,
  and invalid citations produce failed validation and end-to-end stages;
- synthetic private key, prompt, passage and hidden-reasoning sentinels remain absent from both SSE
  and captured observability logs.

Known constraints:

- Step 2 makes packet-stage latency measurable but records no product-performance claim; cold/warm
  measurements and instrumentation overhead still require the controlled Step 3 baseline;
- failed HTTP/SSE responses remain deliberately redacted for callers; their safe trace is available
  in server logs rather than expanding the public error schema.

Next actionable work:

1. Complete Step 3 by adding a packet-only benchmark harness and committing a reviewed cold/warm
   result over the five frozen cases before making any optimisation.

### 21 August 2026 — Step-based Pre-Agent product scorecard

Delivered:

1. Replaced the calendar-based proposal with twelve ordered, acceptance-gated steps that can be
   completed at a flexible pace while keeping production Agent integration out of scope until the
   fixed workflow is stable.
2. Froze six local-first user journeys covering exact and ambiguous discovery, evidence inspection,
   Deep Study, navigation continuity and honest failure recovery, with hosted behaviour retained as
   a regression lane.
3. Added a machine-readable scorecard for interface response, packet-stage observability, cold/warm
   latency, prompt size, provenance, duplication, citation integrity, adversarial containment,
   human usefulness and final workflow reliability.
4. Preserved the five existing Agent-comparison cases and the 18 August raw baseline instead of
   rewriting unknown packet or human-quality measurements as historical claims.
5. Defined the human packet rubric, paired-run controls, sensitive-data policy and explicit Agent
   entry gate, and corrected the percentile documentation to match the evaluator's `(n - 1)` linear
   interpolation.

Acceptance evidence:

- automated contract coverage proves that the scorecard references the frozen suite and raw
  baseline, reproduces their recorded summary, has one ordered next step and cannot name a missing
  Agent-entry target;
- all 187 automated tests, scoped Ruff and repository whitespace checks pass;
- README status, roadmap and evaluation documentation link to the same step-based contract.

Known constraints:

- packet-stage latency, duplicate ratio, provenance completeness, human packet usefulness and UI
  journey timing remain explicitly unmeasured; Step 1 defines how to measure them but claims no
  result;
- the then-current 98.94 automated score remains a structural/citation/calibration proxy rather than
  evidence of factual film-analysis correctness.

Next actionable work:

1. Complete Step 2 by adding redacted monotonic timing and status data for each applicable evidence,
   model and validation stage without exposing prompts, private passages, credentials or responses.

### 21 August 2026 — Local and hosted account-shell parity

Delivered:

1. Separated account-interface availability from the backend's public execution mode.
2. Made every genuine loopback test-account session use the hosted **Discover / Analyse / Settings**
   navigation and integrated Settings screen instead of the legacy standalone Settings link.
3. Retained private local capabilities, including clip analysis and local review structuring; the
   change affects the browser shell rather than the API trust or data boundary.
4. Versioned the application script and added a static regression contract for the loopback shell.
5. Reconciled the README, architecture, local setup and Obsidian project notes.

Acceptance evidence:

- all 186 automated tests, frontend JavaScript syntax, scoped Ruff and repository whitespace checks
  pass;
- live loopback browser verification shows the same three-item account navigation and integrated
  Settings hero as the hosted site;
- production mode and the loopback-only authentication predicate remain separate controls.

### 21 August 2026 — Protected branches and human production approval

Delivered:

1. Replaced direct-to-`master` agent publication with short-lived feature, fix, documentation or
   chore branches, required pull requests and automatic branch deletion after merge. A permanent
   `local` or `develop` branch is explicitly prohibited.
2. Protected `master` for administrators and other writers: changes require a current pull request,
   the GitHub Actions `checks` result and resolved conversations; force pushes and deletion are
   blocked.
3. Added a required repository-owner review to the branch-restricted GitHub `production`
   environment. A green merge may build and seal a release, but agents must stop at the pending gate
   and cannot approve or bypass production on the user's behalf.
4. Added a pull-request delivery checklist, workflow contract coverage and seven-day artefact
   retention so the owner has time to inspect an immutable candidate before approval.
5. Updated the README and hosting runbook with the branch, merge, approval and post-deployment
   verification sequence.

Acceptance evidence:

- all 186 automated tests, action-workflow validation, the hosted frontend build, npm audit and
  repository whitespace checks pass;
- GitHub reports enforced administrator protection, strict required `checks`, pull-request-only
  `master`, blocked force-push/deletion and automatic merged-branch cleanup;
- the `production` environment reports one required owner reviewer, permits only `master` and keeps
  the Azure token outside repository-wide secrets;
- the implementation itself travels through a short-lived branch and green pull request, while its
  deployment pauses for separate human approval.

Known constraint:

- the sole repository owner can approve their own environment deployment, so this is a deliberate
  human release-intent gate rather than independent two-person review; add another trusted reviewer
  if collaborative production ownership is introduced.

Next actionable work:

1. Add an automated post-deployment HTTP/build-identity smoke check that runs after human approval
   and reports a direct rollback target without weakening the gate.

### 21 August 2026 — Launch-independent localhost test account

Delivered:

1. Removed the hosted-preview feature-flag dependency from the development identity. The test
   account now appears on any genuine loopback-served FirstRoll interface, including the standard
   `127.0.0.1:8000` process and the `127.0.0.1:4173` hosted-mode preview.
2. Kept the boundary fail-closed by requiring both the requested URL host and connected client to be
   loopback before publishing the account or accepting its token. Production Supabase behaviour is
   unchanged.
3. Allowed the local account-integration endpoint in private mode, preserving the browser-local
   profile, preferences and saved films and the explicit unlimited FirstRoll test allowance.
4. Added regression coverage for the ordinary private launcher as well as the hosted preview and
   reconciled the README, architecture, local setup and Obsidian project notes.

Acceptance evidence:

- automated tests, JavaScript syntax, Ruff and repository whitespace checks pass;
- local API configuration and browser verification confirm that port `8000` publishes the test
  account, retains the session after reload and displays the unlimited local allowance;
- non-loopback URL or client addresses fail the local-account predicate.

Boundary:

- the local allowance bypasses only FirstRoll's daily demo counters. External DeepSeek, YouTube and
  other provider limits, balances and billing remain in force.

Next actionable work:

1. Keep authentication acceptance tests exercising both local launch commands whenever the runtime
   configuration or web bootstrap changes.

### 21 August 2026 — Refresh-safe Discover workspace

Delivered:

1. Added a versioned, 500 KB-capped per-tab Discover snapshot containing the latest public query,
   candidate summaries, selected native shelf, shelf readiness and optional open-dossier film ID.
2. Restored completed shelves synchronously for up to twenty-four hours without repeating search or
   related-film requests. A refresh that interrupts loading reissues only the latest query, while
   malformed, stale or incompatible snapshots are discarded.
3. Kept Discover mounted while moving among Discover, Analyse and Settings, and preserved each
   product view's scroll offset plus the active view across refresh.
4. Excluded dossier bodies, reviews, criticism, studies, credentials, authentication tokens and
   account records from session storage; an open dossier is re-fetched by canonical ID.
5. Recorded ADR-019 and reconciled the README, architecture and data-model boundaries.

Acceptance evidence:

- all 185 automated tests, Ruff, frontend JavaScript syntax, npm audit and repository whitespace
  checks pass;
- live local Chromium verification loads all four *Resurrection* shelf covers, switches through
  Analyse and Settings while the complete hidden Discover DOM remains unchanged, then refreshes on
  Settings and restores the same active view, query and four-card shelf;
- the refreshed page makes no repeated discovery-search or related-film request; returning to
  Discover restores its prior scroll region with all four images loaded, no horizontal overflow and
  no console errors.

Known constraints:

- continuity belongs to one browser-tab session and is intentionally neither cross-device nor durable
  account history;
- reopening a previously open dossier still depends on the API because only its canonical film ID is
  stored.

Next actionable work:

1. Keep this snapshot boundary summary-only if future Discover modules add private or generated
   content; durable projects require a separate explicit data model.

### 21 August 2026 — TMDb primary catalogue with open failover

Delivered:

1. Added the official TMDb API as an optional primary discovery catalogue, configured through the
   local Settings page or the backend-only `TMDB_BEARER_TOKEN` environment variable.
2. Replaced the serial metadata pattern with one movie search plus at most eight candidate detail
   hydrations across four workers. Each detail call appends credits, external IDs, alternative titles
   and release dates, then local code revalidates title, year and director before display.
3. Added provider-qualified `tmdb:{id}` routing and retained IMDb/Wikidata external IDs for exact
   reconciliation by criticism, video and research adapters. Same-title ambiguity still requires an
   explicit browser choice.
4. Kept Wikidata/Wikipedia as the automatic key-free fallback. A missing token is a normal fallback;
   a configured-provider failure is surfaced as degraded failover rather than silently hidden.
5. Built the TMDb director shelf from verified person movie credits without per-film detail calls,
   added dynamic overview provenance and the required TMDb non-endorsement notice.
6. Recorded ADR-018 and reconciled architecture, API, data-source, data-model, setup, README and
   Obsidian business-logic documentation.

Acceptance evidence:

- all 184 automated tests pass; the 53 focused discovery/settings/browser-asset checks, Ruff,
  JavaScript syntax and repository whitespace checks also pass;
- contract tests cover candidate hydration and filtering, detailed crew provenance, IMDb/Wikidata
  links, same-director filmography, absent-token fallback and configured-provider timeout failover;
- the adapter caps response bodies at 4 MB, uses a ten-second request deadline, allow-lists TMDb API
  paths and keeps the bearer token server-side;
- no live latency number is claimed because this machine has no configured TMDb token. ADR-018 keeps
  live p50/p95 measurement as an explicit post-configuration action rather than inventing a result.

Known constraints:

- TMDb non-commercial use requires attribution, and monetisation requires a commercial-terms review;
- search detail caches are process-local and rebuild after a backend restart;
- the official IMDb API remains a future licensed enterprise adapter rather than a dependency.

Next actionable work:

1. Add a TMDb Read Access Token, run representative English, translated-title and same-title cases,
   and record cold/warm p50 and p95 search latency in the evaluation fixture.

### 21 August 2026 — Complete shelf covers and unobscured release years

Delivered:

1. Removed the production poster-enrichment bottleneck that could take about seventy seconds and
   outlive the browser's former sixty-second request boundary. Director-only enrichment now reuses
   lightweight shelf entities and resolves all Wikipedia page images in one batch.
2. Added a bounded, four-worker Letterboxd fallback for films without a supported article image or
   IMDb claim. A title-derived candidate is accepted only when its structured title, release year
   and director all match the canonical Wikidata film.
3. Cached completed enriched responses separately from fast filmography responses and increased the
   cancellable browser safety boundary to ninety seconds, so a cold provider response can still
   hydrate the already-usable shelf instead of being discarded.
4. Made the at-most-twelve shelf images eager, moved the wooden shelf edge below the card metadata
   and added a protected gap under every release year.

Acceptance evidence:

- all 177 automated tests, Ruff, frontend JavaScript syntax, npm audit and repository whitespace
  checks pass;
- a fresh live-provider adapter run returns all three related Bi Gan covers in 3.2 seconds, including
  a strictly identity-matched cover for *The Poet and the Singer*, versus the observed seventy-second
  production path before this change;
- live local Chromium verification for *Resurrection* loads all four shelf images at their natural
  dimensions, leaves about forty CSS pixels below every year label, has no horizontal overflow at
  1,108-pixel desktop or 390-pixel mobile widths and emits no console errors.

Known constraints:

- upstream Wikidata, Wikipedia and Letterboxd availability still controls optional cover hydration;
  a film keeps its designed title/year cover if no page can pass the identity checks;
- enriched responses are process-memory caches and are rebuilt after an API restart.

Next actionable work:

1. Observe poster-cache rebuild latency after routine API revision restarts and retain the strict
   identity gate if another cover provider is added.

### 21 August 2026 — Always-available native director shelf

Delivered:

1. Replaced the Three.js/WebGL room and Blender GLB with a native HTML/CSS filmography shelf that
   requires no graphics capability, module graph or model download.
2. Rendered the selected film synchronously with five designed loading cases, then replaced those
   placeholders in place with up to twelve verified directing works from one bounded fast request.
3. Made native poster images optional over title-and-year fallback covers, retained case selection
   and kept the responsive shelf at six columns on wide panels and three on narrow screens. A slower,
   best-effort request can upgrade additional posters without returning the shelf to loading.
4. Changed fast-provider failure from a missing or unavailable shelf into a stable one-film state:
   loading cases are removed, the selected edition remains and a visible retry can restart the request.
5. Added a separate shelf request identity so cancelled, retried or stale fast and poster-enrichment
   work cannot overwrite the latest film. Fast and enriched responses are cached separately;
   enrichment failure leaves the ready shelf unchanged.
6. Removed the obsolete 3D runtime, vendored Three.js files, GLB and Blender build tool from the web
   package; the hosted build is now approximately 748 KB rather than 1.5 MB.

Acceptance evidence:

- all 175 automated tests, frontend JavaScript syntax, npm audit and repository whitespace checks
  pass;
- live local browser verification for *Interstellar* shows one selected case and five placeholders
  immediately, then twelve selectable cases with no console errors or horizontal overflow;
- the same browser run passes at 1,440-pixel desktop and 390-pixel mobile widths, while a synthetic
  provider failure leaves one selected case, no loading cases and a visible retry;
- live local verification for Bi Gan's *Resurrection* upgrades *Long Day's Journey into Night*,
  *Kaili Blues* and *The Poet and the Singer* to verified covers with no console warnings;
- the production build contains no 3D model, Three.js module or shelf-specific runtime file.

Known constraint:

- the expanded filmography still depends on Wikidata relationship coverage and availability; on a
  sparse or failed response the native shelf deliberately remains useful with the selected film only;
- optional poster enrichment may continue for up to ninety seconds after the shelf is ready, but it
  is cancellable and cannot restore loading or hide the native cases;
- a film without a poster claim, supported article image, IMDb identity or a title/year/director-
  verified page keeps its designed cover rather than risking an unverified poster match.

Next actionable work:

1. Observe the lighter shelf on the hosted CDN and retain the one-film fallback contract when the
   related-film provider is changed or cached more aggressively.

### 21 August 2026 — Hardened frontend CI/CD trust boundary

Delivered:

1. Made pull-request CI explicitly read-only, stopped checkout from persisting its token and pinned
   every GitHub, HashiCorp and Azure action to an immutable full commit SHA.
2. Replaced credentialled pull-request preview deployments with a production-only workflow that
   accepts a successful same-repository `master` push, checks out its exact approved SHA and refuses
   to deploy if a newer revision has reached `master`.
3. Isolated the frontend build, high-severity npm audit and bounded `dist` validation in an
   uncredentialled job that seals its output as an immutable, run-scoped artifact. A separate runner
   checks out no repository code and gives the token only to Azure's build-disabled upload step.
4. Rotated the Azure token out of repository-wide secrets and into a `master`-restricted GitHub
   `production` environment. Reduced the repository's default workflow token to read-only and
   enforced full-SHA action references with a narrow external-action allow-list.
5. Added workflow contract tests, cancellation and timeout bounds, weekly npm and Actions Dependabot
   checks, and operator documentation for the new deployment gate.

Acceptance evidence:

- the 175-test suite, action-workflow and YAML validation, JavaScript syntax, npm audit and repository
  whitespace checks pass locally;
- GitHub reports read-only default workflow permissions, mandatory action SHA pinning, the restricted
  `production` environment secret and no repository-wide Azure deployment secret;
- a successful `master` CI run triggers the production workflow, which uploads only the pre-built
  `dist` directory before `https://firstroll.app` is checked for the approved build.

Known constraint:

- the Azure action is SHA-pinned, but its pinned Dockerfile delegates to Microsoft's maintained
  `staticappsclient:stable` image; the remaining transitive image update boundary is controlled by
  Azure rather than this repository.

Next actionable work:

1. Review weekly Dependabot action and npm updates, retaining full-SHA pins and re-running the
   production smoke check before merging a supply-chain change.

### 21 August 2026 — Interruptible recent-film switching

Delivered:

1. Added an abort controller and monotonically increasing request identity to discovery search.
2. Made every new query abort the preceding title request and all active fast or enriched shelf
   requests before presenting its own progress state.
3. Suppressed abort errors and guarded every late response, so a provider that ignores cancellation
   still cannot replace the newest search results.
4. Kept the search control interactive while loading, allowing recent chips, edited queries or a
   repeated search to interrupt immediately.

Acceptance evidence:

- the 171-test suite, frontend JavaScript syntax and repository whitespace checks pass;
- a live rapid sequence of *The Thing* → *Crash* → *Interstellar* ends only on the *Interstellar*
  identity choices, with no stale progress panel, unavailable error or lingering busy state.

Concurrency contract:

- discovery is deliberately latest-request-wins; cancelled provider work may finish server-side, but
  its browser response is ignored and cannot mutate the active film interface.

### 21 August 2026 — Progressive director shelf loading

Delivered:

1. Split the director shelf into a bounded fast identity request and a non-blocking enriched-poster
   request, with separate browser caches and time budgets.
2. Rendered the fast director film list immediately with available artwork or designed fallbacks,
   then upgraded the live cases when enriched poster data arrived.
3. Prevented slow poster providers from replacing the entire shelf with an error after 28 seconds.
4. Collapsed the shelf column when even the fast identity request fails, retaining the selected film
   card without redundant failure copy or a full-height empty panel.

Acceptance evidence:

- the 170-test suite, frontend JavaScript syntax and repository whitespace checks pass;
- live *Interstellar* verification renders 12 director cases, upgrades 11 poster covers and exposes no
  “full shelf unavailable” text.

Resilience boundary:

- background poster enrichment is best-effort; film identity and designed cover fallbacks remain usable
  when an artwork provider is slow or unavailable.

### 21 August 2026 — Clearable local search history

Delivered:

1. Added an independent close control to every recent-search chip without nesting interactive
   buttons or changing the chip's search-again behaviour.
2. Added a compact clear-all action and removed the local-storage key when the history becomes empty.
3. Kept individual removal, complete clearing and later search additions synchronised between the
   rendered list, in-memory discovery state and browser-local persistence.
4. Updated the README to document the browser-only history controls and the director-only,
   front-facing poster shelf.

Acceptance evidence:

- frontend JavaScript syntax, the 170-test automated suite and repository whitespace checks pass;
- live browser inspection confirms five independently labelled dismiss controls, one clear-all control,
  no nested buttons and the intended compact visual treatment.

Privacy boundary:

- recent searches remain in the current browser's local storage and are not saved to a FirstRoll
  account or sent to the backend as history records.

### 20 August 2026 — README dual-runtime architecture graph

Delivered:

1. Replaced the README's older five-layer local pipeline diagram with the current dual-runtime
   topology: Azure Static Web Apps, Azure Container Apps, Supabase identity and RLS-owned account
   data, backend quota PostgreSQL, transient hosted study results and the local private edition.
2. Drew the hosted request path and private-runtime path in one Mermaid graph, including public
   provider acquisition, typed evidence assembly, DeepSeek structured synthesis, deterministic
   validation and the planned clip-to-study evidence bridge.
3. Updated the adjacent architecture explanation and stack table so they no longer describe the
   API as a Render service or imply that private books, vectors, secrets and clips enter the hosted
   runtime.

Acceptance evidence:

- the compact README graph agrees with `docs/ARCHITECTURE.md` on hosting, identity, persistence,
  quota and privacy boundaries;
- Mermaid node labels containing punctuation are quoted and every edge target is declared;
- Markdown whitespace and local-link validation pass.

Known constraint:

- the graph deliberately summarises the system; field-level persistence, API contracts and decision
  history remain in the linked architecture, data-model, API-reference and ADR documents.

Next actionable work:

1. Keep the README graph and `docs/ARCHITECTURE.md` in the same checkpoint whenever a deployment or
   trust boundary changes.

### 20 August 2026 — Persistent Supabase accounts

Delivered:

1. Kept Supabase as the production identity provider and replaced the magic-link-only interface
   with password sign-up, password sign-in, confirmation-aware account creation and password
   recovery. Supabase continues to persist and refresh the browser session.
2. Added a production migration for user profiles, preferences and saved films. Every record
   references `auth.users(id)` with cascading deletion; all exposed tables enable RLS and limit
   operations to `(select auth.uid()) = user_id`.
3. Added “Save to account” to film dossiers and a persistent saved-film collection in Settings,
   including removal and cross-device reload through the signed-in Supabase client.
4. Recorded ADR-017: Entra remains staged for learning or a later enterprise requirement, but is
   no longer on the public-beta critical path.

Acceptance evidence:

- static tests reject a regression to `signInWithOtp()` and require password sign-up/sign-in,
  session persistence and recovery;
- migration tests require all three RLS boundaries, Auth foreign keys, `anon` revocation and the
  new-user trigger;
- the production migration reports three RLS-enabled tables, ten policies, profile and preference
  backfills for both existing Auth users, and the new-user trigger;
- local PostgreSQL acceptance testing proves Account B sees only its own saved film, a cross-account
  insert is blocked, and Auth deletion cascades all three user-owned record types;
- frontend deployment, refresh-session and password-recovery browser acceptance remain.

### 20 August 2026 — Azure API cut-over and account-authentication staging

Delivered:

1. Published FastAPI through Azure Container Apps at `https://api.firstroll.app`, verified managed
   TLS, health, discovery and exact-origin CORS, and rebuilt the Azure Static Web Apps frontend with
   the stable API origin.
2. Imported the live API custom-domain association into Terraform. The production plan now reports
   no drift and protects both frontend and API domains from accidental destruction.
3. Staged a provider-selectable Microsoft Entra External ID implementation: MSAL in the browser,
   strict JWT issuer/audience/signature/scope validation in FastAPI and corresponding Terraform
   variables. Supabase remains the only active provider.
4. Chose email-and-password customer accounts rather than email OTP. Activation is blocked until an
   administrable External ID customer tenant exists.
5. Added an identity-neutral PostgreSQL quota adapter and migration. FastAPI now has a provider plus
   immutable-subject persistence contract, a dedicated backend connection path and a guarded legacy
   Supabase rollback adapter; Entra cannot be configured with the visitor-token quota RPC.

Acceptance evidence:

- `https://api.firstroll.app/api/health` returns HTTP 200;
- production discovery returns the expected canonical film for an exact title/year query;
- the deployed frontend runtime configuration points to `https://api.firstroll.app`;
- Terraform validates and reports `No changes` against the live Azure state;
- provider-selection and Entra-token tests pass while the production Supabase path remains intact.
- quota tests prove that the PostgreSQL boundary does not receive the browser bearer token and that
  the migration retains the atomic daily advisory lock.

### 19 August 2026 — Hosted architecture and technical reference pack

Delivered:

1. Corrected the product description from a merely local or deployment-ready application to a
   local-first system with an active Azure frontend and Render API. The documentation now treats
   “local-first” as a privacy and data-placement decision while describing the hosted browser/API
   boundary separately.
2. Split detailed technical material into linked, maintainable references: current architecture,
   complete HTTP/SSE API dictionary, Supabase/SQLite/JSON/in-memory data model, architectural
   decision register and evaluation contract.
3. Added field-level table designs for the Supabase quota schema and local retrieval index,
   including keys, constraints, RLS/RPC ownership, atomic reservation behaviour and persistence
   boundaries.
4. Added an endpoint-by-endpoint access, request, response and failure dictionary, plus the safe SSE
   event and header contracts. Local-only, bearer-protected, conditionally authenticated and
   feature-gated operations are now distinguished explicitly.
5. Recorded fourteen major product and architecture decisions with context, alternatives,
   consequences and revisit conditions. These cover lineage, dual runtime, Render topology, film
   identity, provider adapters, evidence types, local RAG, quality policy, Supabase, progress
   streaming, the gated Agent, clip locality, provider degradation and temporary result storage.
6. Removed the mutable baseline table from the README and made the newest reviewed JSON under
   `evals/results/` canonical. Added metric definitions, case-level results, limitations and a
   replacement procedure that prevents screenshots or copied prose from silently becoming a new
   baseline.

Acceptance evidence:

- every README documentation-map target exists and the repository tree lists the new references;
- the API dictionary covers every FastAPI route currently declared in `app/backend/main.py`;
- the data tables reconcile with the checked-in Supabase migration and local SQLite/index models;
- the Render deployment is documented as active without inventing service origins that are not
  versioned in the repository;
- the latest available raw evaluation artefact remains
  `evals/results/baseline-2026-08-18.json`; its recorded metrics are reproduced in
  `docs/EVALUATION.md` and no newer values were inferred from an image.

Known constraints:

- if a newer baseline has been run outside this repository, its complete redacted JSON report must
  still be added before it can replace the versioned 18 August baseline;
- the exact Render frontend and API origins are dashboard configuration and are not currently
  recorded in the repository;
- the decision register captures consequential architecture/product choices, not every visual or
  parser implementation detail.

Next actionable work:

1. Commit the next complete evaluation artefact and update only the canonical evaluation document.
2. Record the exact public origins in hosting documentation if stable publication of those URLs is
   desired.
3. Continue the production Agent comparison and clip-to-study evidence bridge under the documented
   decision and evaluation contracts.

### 19 August 2026 — README architecture and status reconciliation

Delivered:

1. Reconciled the README status with the implemented hosted boundary: Supabase authentication,
   atomic quota reservation and redacted SSE progress now appear as delivered capabilities rather
   than future prerequisites.
2. Updated the Agent boundary to distinguish completed fixed-workflow streaming and baseline work
   from the still-pending production graph adapter and like-for-like Agent evaluation.
3. Added an authenticated Deep Study sequence diagram covering bearer verification, the fixed
   workflow, public event projection, transient owner-scoped result storage and the separate result
   request.
4. Made the roadmap and known limitations explicitly retain the outstanding interactive browser
   observation and the process-local ten-minute run-store constraint.

Acceptance evidence:

- README architecture, API and roadmap statements now agree with the implementation and this
  progress log;
- Markdown whitespace validation passes and no runtime behaviour changed in this documentation
  checkpoint.

Next actionable work:

1. Complete the synthetic privacy observation in a human-opened localhost browser tab.
2. Replace the transient run store before multi-instance or resumable research execution.
3. Implement the production graph service adapter and compare it against the frozen baseline.

### 18 August 2026 — Authenticated, redacted browser research progress

Delivered:

1. Added an authenticated `POST /api/discovery/films/{film_id}/study/stream` endpoint for hosted
   Deep Study. Supabase bearer validation and hosted availability checks complete before an SSE
   response is created.
2. Added a strict public event projector with an allow-list for lifecycle kinds, bounded public
   messages, monotonic sequence numbers, elapsed time and four non-sensitive aggregate counts.
   Prompts, credentials, retrieved passages, review bodies, model output and hidden reasoning have no
   field in this contract.
3. Mapped provider and application exceptions to fixed public failure messages. Raw exception text
   cannot enter the stream even when it contains request credentials or private source material.
4. Kept the full result outside SSE. The browser retrieves it through
   `GET /api/research/runs/{run_id}`, which authenticates again, enforces run ownership and gives
   unknown and cross-account callers the same 404 response.
5. Updated the hosted browser to consume the POST response as a readable stream, show only each
   public progress message, require ordered events and fetch the final study separately. The local
   edition retains its existing synchronous route.
6. Kept the transport independent of the production Agent decision: it currently projects the
   deterministic Deep Study workflow and can later receive the bounded graph's safe lifecycle
   events without exposing graph state.

Acceptance evidence:

- authenticated integration coverage injects a synthetic personal DeepSeek key, private prompt,
  private book passage and synthetic hidden-reasoning field, then proves none appears anywhere in
  the SSE response while the separately authenticated result retains the private study payload;
- ownership coverage proves a second authenticated account receives 404 for the run, and failure
  coverage proves provider exceptions are redacted;
- public-contract coverage rejects arbitrary messages, event kinds and token-like counts, while frontend
  contract coverage verifies the streamed request, ordered parser and separate result request;
- all 142 automated tests pass; scoped Ruff, JavaScript syntax and whitespace checks pass.

Known constraints:

- the final result store is process-local, bounded to 50 runs and expires entries after ten minutes;
  durable, owner-scoped storage is required before multi-instance or resumable execution;
- this progress transport does not switch the public Deep Study route to the LangGraph Agent;
- the in-app browser automation client blocked programmatic localhost navigation during acceptance.
  A human-opened localhost tab is still required for the final interactive browser observation.

### 18 August 2026 — Bounded LangGraph research Agent core

Delivered:

1. Added LangGraph 1.2 to local and hosted dependency sets and locked version 1.2.11.
2. Preserved the framework-neutral research contract as the deterministic policy boundary around
   the graph rather than duplicating authentication, budget and tool-authorisation rules.
3. Implemented typed graph state, bounded reducers, safe public progress events, runtime-injected
   service interfaces, named nodes, conditional routing and explicit terminal states.
4. Split model-proposed tool choice from deterministic application authorisation and provider
   execution. Retrieved evidence remains untrusted data and cannot authorise an action.
5. Added bounded recovery for an unavailable provider, empty evidence, invalid planning and one
   failed quality pass. A repair can run only once.
6. Added optional LangGraph checkpoint compilation and verified that a completed thread is
   checkpointed without placing credentials or service clients in graph state.
7. Kept the current fixed Deep Study route unchanged as the production comparison and fallback.

Acceptance evidence:

- 18 focused contract-and-graph tests pass, covering existing evidence, ambiguous film identity,
  empty research, provider timeout recovery, malicious retrieved instructions, one-shot repair,
  repeated quality failure, invalid or out-of-policy planner output, final-budget authorisation,
  reducers, graph structure and checkpoint state;
- all 137 automated tests pass;
- the new graph, contract and tests pass Ruff, and the graph plus contract pass MyPy;
- the graph compiles with named nodes and runs entirely with deterministic fake services in CI.

Known constraints:

- the graph does not yet replace `POST /api/discovery/films/{film_id}/study`;
- production criticism, retrieval and DeepSeek adapters still need to implement the graph service
  protocol behind a feature flag;
- authenticated checkpoint ownership and durable production checkpoint storage remain pending;
- the Agent must run the frozen five-case evaluation before any public cut-over.

Next actionable work:

1. Implement a production `ResearchGraphServices` adapter over the existing discovery, evidence,
   criticism and study services.
2. Add a feature-flagged authenticated endpoint and safe SSE event projection.
3. Run the fixed workflow and Agent on the same golden cases, then retain the Agent only if its
   quality and recovery gains justify its latency, cost and operational complexity.

### 18 August 2026 — Fixed-workflow baseline for future Agent evaluation

Delivered:

1. Froze five representative film-study cases covering formal specificity without a clip,
   abundant secondary interpretation, multilingual identity, ambiguous-title resolution and
   sparse-evidence limitation.
2. Added a reproducible evaluator for the current fixed workflow. It records film identity,
   per-stage and end-to-end latency, operational failures, deterministic quality acceptance,
   repair use, citation validity, evidence coverage, DeepSeek call count and token usage.
3. Stored a non-secret configuration fingerprint with the result: DeepSeek Pro and YouTube were
   configured; Douban and official Letterboxd credentials were absent; the local index contained
   seven documents, 4,381 chunks and multilingual MiniLM embeddings.
4. Reclassified `generic_language`, `central_argument_generic` and `mechanism_not_causal` as scored
   quality defects rather than hard rejections. An accepted study receives the gate's 25 points in
   proportion to its raw score; unsupported central assertions and absent mechanisms remain blocking.
5. Kept operational and quality failure rates separate and documented that the automated score
   does not establish factual correctness for film form that has not been observed from a clip.
6. Reran the same five live cases after the policy change and preserved central and per-section
   gate diagnostics in the baseline artefact.

Baseline results:

| Measure | Result |
|---|---:|
| Cases completed | 4 / 5 |
| Operational failure rate | 20% |
| Quality-gate pass rate | 100% of completed studies |
| Quality acceptance failure rate | 0% of completed studies |
| Mean / median quality score | 98.94 / 99.5 |
| Mean end-to-end latency | 65.798 s |
| P50 / P95 end-to-end latency | 66.409 s / 96.451 s |
| Repair rate | 0% of completed studies |
| Model calls / total tokens | 4 / 46,950 |

Case results:

| Case | Quality | Gate | End-to-end latency |
|---|---:|---|---:|
| *Syndromes and a Century* — cinematography | 100 | passed | 77.212 s |
| *In the Mood for Love* — constrained space | 96.75 | passed | 31.080 s |
| *Memoria* — sound perspective | — | DeepSeek timeout | 101.261 s |
| *The Thing* — ambiguous identity | 99 | passed | 53.029 s |
| *We Are All Strangers* — sparse evidence | 100 | passed | 66.409 s |

Interpretation:

- the fixed workflow is operationally reliable on this small case set and resolved the deliberately
  ambiguous *The Thing* query to the 1982 John Carpenter film;
- all four completed studies passed; weak causal signalling remained visible as a deduction for
  *In the Mood for Love* and *The Thing* rather than triggering repair or rejection;
- *Memoria* received no quality decision because DeepSeek timed out after 91.759 seconds at the study
  stage; this is recorded as an operational failure, not a quality failure;
- quality scores, gate rates and repair rates now use completed studies as their denominator, while
  end-to-end latency and operational failure continue to include every attempted case;
- the five-case run is a functional baseline, not a statistically stable provider failure estimate.
  Any Agent comparison must reuse the case file and report its run count, configuration fingerprint
  and both failure rates.

Acceptance evidence:

- all 124 automated tests pass and the modified Python files pass Ruff;
- the live result is stored in `evals/results/baseline-2026-08-18.json` without credentials or private
  source excerpts;
- all five cases used the same fixed workflow and acceptance rubric intended for later Agent runs.

### 15 August 2026 — Ambiguous film identity confirmation

Delivered:

1. Replaced automatic first-result selection with an explicit confirmation step whenever discovery
   returns more than one possible film.
2. Added accessible candidate cards showing the poster, release year, director and original title so
   similarly named works can be distinguished before any dossier or related-film indexing begins.
3. Kept single-result searches immediate and prevented rejected same-title candidates from being
   treated as related films on the selected film's shelf.

Acceptance evidence:

- frontend contract coverage verifies that ambiguous searches cannot bypass the selection gate;
- browser acceptance with *The Thing* exposed four attributed candidates, selected the 1982 John
  Carpenter film and confirmed that the chooser was removed before the shelf opened;
- the narrow responsive check reported no horizontal overflow, and all 105 automated tests pass.

### 15 August 2026 — Non-blocking shelf loading

Delivered:

1. Decoupled the Blender/Three.js room from related-film indexing, so the first interactive frame
   appears while Wikidata relationships continue loading in the background.
2. Added a bounded fast path for shelf summaries: twelve results per relationship group, at most
   sixty hydrated candidate entities, no secondary labels, award descriptions, Wikipedia summaries
   or sequential Letterboxd poster fallbacks on the critical path.
3. Added backend related-film caching and a browser-session cache, with a fifteen-second request
   boundary and at most one retry instead of three unbounded attempts.
4. Made case construction synchronous and streamed poster textures onto existing cases, preventing
   a slow or unavailable image host from blocking the scene-ready state.
5. Preserved the full enrichment route for callers that explicitly need it; the fast shelf summaries
   are not written into the canonical film-detail cache, so opening a dossier still retrieves complete
   metadata.

Acceptance evidence:

- the previous cold related-film request exceeded thirty seconds; the bounded cold request measured
  10.24 seconds and the cached request measured 2.1 milliseconds;
- browser instrumentation showed the interactive room in 2.8 seconds, with twenty-six real cases
  completing in the background at 14.3 seconds and no console errors;
- all 104 automated tests pass, including fast-path caching, canonical-detail isolation and
  non-blocking poster regressions.

### 15 August 2026 — Hosted Douban MCP runtime

Delivered:

1. Added a Node 22 build stage to the production image and pinned `moria97/douban-mcp` to commit
   `1adc26d39532db893616ceb7ea851733948ae69e` for reproducible builds.
2. Copied only the built connector, production dependencies and Node runtime into the Python image.
3. Made authenticated Settings report the live hosted connector state while deliberately providing
   no Douban cookie or visitor-credential field.
4. Retained anonymous provider access and graceful degradation when Douban blocks or rate-limits the
   unofficial connector.

Acceptance evidence:

- the complete production image builds with zero reported npm production vulnerabilities;
- its cookie-free MCP handshake exposes `search-movie` and `list-movie-reviews`;
- an anonymous container lookup matched *In the Mood for Love* to Douban subject `1291557` and
  returned its live community score;
- the full application suite passes with 103 tests.

### 15 August 2026 — Authenticated public Settings and session integrations

Delivered:

1. Added a responsive hosted Settings view with verified Supabase account identity, live Deep Study
   quota status and explicit sign-in, refresh and sign-out controls.
2. Added optional personal DeepSeek and YouTube keys held only in JavaScript memory for one browser
   tab. They are cleared on refresh or sign-out, never persisted and sent only with the matching
   authenticated request.
3. Preserved the three-study daily account boundary for personal DeepSeek requests and added strict
   key syntax, length, CORS and authentication checks at the API edge.
4. Added Douban MCP as a visible local-edition integration with direct setup guidance while refusing
   Douban cookies on the hosted server.
5. Kept the private local Settings, library and clip-analysis routes unpublished.

Acceptance evidence:

- desktop and mobile production-build visual QA passed without horizontal overflow;
- request-scoped DeepSeek and YouTube keys, unauthenticated rejection, account status and quota
  reporting are covered by backend and frontend contract tests;
- Python lint, JavaScript syntax, production static build and the full suite pass with 102 tests.

### 15 August 2026 — Authenticated Deep Study quotas

Delivered:

1. Added an idempotent Supabase migration with private RLS-enabled daily counters, authenticated-only
   status and reservation RPCs, a fixed three-per-account limit and a thirty-per-demo global limit.
2. Serialised reservations per UTC day inside PostgreSQL, preventing concurrent requests from
   exceeding either limit without requiring a service-role key.
3. Added bounded FastAPI quota validation, HTTP 429 responses with reset timing and an explicit
   hosted feature switch that remains closed unless authentication, quotas and DeepSeek are all
   configured.
4. Replaced the hosted edition's unavailable private PDF index with four transparent, first-party
   formal-analysis frameworks; all generated film-form claims remain viewing hypotheses.
5. Added remaining account/global allowance to successful study results and retained the local
   private-library workflow unchanged.

Acceptance evidence:

- focused authentication and quota tests pass across reservation, account denial, malformed RPC
  response, public evidence and HTTP 429 paths;
- the full suite passes with 95 tests, together with Python lint, JavaScript syntax and whitespace
  checks;
- the paid feature remains fail-closed until the live Supabase migration and Render-only DeepSeek
  environment settings are verified.

### 15 August 2026 — Zoom-safe selected edition

Delivered:

1. Replaced the selected-edition card's viewport-only responsive assumption with a component-width
   container query, so the artwork and film copy collapse to one column before either reaches the
   inner frame.
2. Allowed the collection header, long film titles and dossier action to wrap without increasing
   their grid track or crossing the border at high browser zoom.
3. Bumped the hosted stylesheet asset version so Render visitors receive the corrected layout
   immediately after deployment.

Acceptance evidence:

- measured medium- and high-zoom-equivalent layouts keep the header, title, copy and button within
  the selected-edition panel;
- all 89 automated tests pass, including a regression for the component-width breakpoint.

### 15 August 2026 — Supabase authentication boundary

Delivered:

1. Added passwordless email sign-in and sign-out to the hosted frontend using a bundled Supabase
   browser client with PKCE and persisted user sessions.
2. Added a public `/api/auth/me` endpoint and a bounded FastAPI bearer-token verifier that resolves
   identities through Supabase Auth without accepting client-supplied user details.
3. Protected hosted Deep Study with authentication while retaining a second explicit quota gate;
   no paid model request can run until durable usage limits are enabled.
4. Kept the Supabase secret and service-role keys out of the design. Only the project URL and
   `sb_publishable_...` key may enter the static bundle or backend environment.
5. Extended the atomic hosted build and CI job to install and bundle the pinned authentication
   client, with validation for the public Supabase configuration.

Acceptance evidence:

- all 88 automated tests pass, including valid, missing, malformed and wrong-role token paths;
- hosted-mode tests confirm the public runtime config exposes only a publishable key;
- Deep Study returns HTTP 401 without a session and reaches the HTTP 503 quota gate only after a
  verified account is present.

Known constraint:

- authentication is ready, but hosted Deep Study remains disabled until the per-user and global
  quota tables are installed and enforced.

### 15 August 2026 — Public deployment acceptance fixes

Delivered:

1. Removed the brittle 50-title shelf gate: the 3D shelf now renders every distinct verified film
   returned by Wikidata instead of hiding the whole scene when one row contains fewer than ten.
2. Added stricter Bilibili identity checks so short translated-title collisions such as music
   albums, audio dramas and dance videos are not presented as film resources.
3. Added an explicit hosted YouTube configuration state, replaced the unavailable clip-analysis
   action with its **coming soon** state, and hid the local-only Settings link in public mode.
4. Preserved local Settings and clip analysis unchanged; connector secrets remain server-side and
   are not exposed through the unauthenticated public site.

Acceptance evidence:

- the live related-film endpoint returns real Wong Kar-wai, shared-cast, country and genre matches;
- the hosted API correctly reports YouTube as `credentials_required` and Douban as `not_installed`;
- all 83 automated tests pass, including regressions for partial shelf rows and short-title video
  collisions.

### 15 August 2026 — Deployment-ready public-beta shell

Delivered:

1. Added a Python 3.11 production Docker image and a bounded hosted dependency set that excludes
   TensorFlow, Torchvision, OpenCV, EasyOCR, TransNetV2 and the local embedding model.
2. Added an atomic static-site build that packages the existing HTML, CSS, JavaScript, Three.js,
   Blender GLB and runtime API configuration into a 1.5 MB `dist` directory.
3. Added explicit public-mode gates: remote settings and private-library routes return 404, while
   clip analysis and unauthenticated Deep Study return 503 before loading expensive code or keys.
4. Added exact-origin CORS configuration for the future Render Static Site without permitting a
   wildcard origin.
5. Added a public **Video analysis is coming soon** state while preserving the complete local
   analysis interface by default.
6. Reworked CI to install the same lightweight dependency manifest used by the production image and
   added hosted-mode regressions.
7. Added a click-by-click Render deployment guide that keeps the DeepSeek key absent until Supabase
   JWT verification and quotas are complete.
8. Added an uncached runtime-config endpoint, so hosted delivery reports public mode and
   **Video analysis is coming soon** while the local interface retains its complete analysis
   workflow.
9. Restored the explicit split requested for publication: the CDN-hosted frontend and sleeping API
   use separate origins, and the public API root returns service metadata rather than a duplicate
   website; the combined interface remains available only in local mode.

Acceptance evidence:

- the static production build completes and contains the app, local Three.js runtime and Blender
  model in a 1.5 MB output;
- a clean temporary Python environment installs only `requirements-hosted.txt`, imports the API and
  returns `{"status":"ok"}`;
- the Docker image builds successfully from `python:3.11-slim` and starts Uvicorn on Render's port;
- live container checks return HTTP 200 for health, HTTP 404 for the private library and HTTP 503 for
  unauthenticated Deep Study in public mode;
- all 80 automated tests pass, including 21 focused hosted, discovery and settings checks, together
  with backend compilation, scoped Ruff and both JavaScript syntax checks.

Known constraint:

- authenticated hosted Deep Study remains deliberately disabled until the Supabase milestone; the
  public deployment must not receive a DeepSeek key before that work is complete.

### 14 August 2026 — Compact archive refinement

Delivered:

1. Narrowed the physical Blender room from a wall-spanning archive to an intimate Criterion-style
   bay sized for 10–15 jewel cases across, with matching camera bounds, labels and live-case spacing.
2. Limited every curated live row to 15 cases and moved side-wall collections deeper into the aisle,
   leaving a calm doorway threshold instead of oversized foreground cases intersecting the camera.
3. Reworked the synthetic-looking block palette into translucent jewel shells with muted paper
   inserts, packed smoked-oak, plaster and carpet textures, softer brass and warmer controlled light.
4. Kept sparse data honest while fixing the one-case presentation bug: genuine titles appear first,
   then neutral non-selectable FirstRoll archive cases complete a minimum 12-case centre row.
5. Moved thinner brass plaques below and in front of all case geometry so title, collection and count
   text cannot be covered by a disc case or shelf edge.
6. Removed case collisions by deriving live-case width from a fixed 0.06-metre gap, keeping ambient
   cases upright with wider spacing and reserving an empty joint where side and rear shelves meet.
7. Corrected the remaining oblique-view overlap by reducing case depth from 0.34 to 0.13 metres,
   making Blender inserts paper-thin, removing the duplicate selection-outline mesh and replacing
   hover scaling with a smaller forward-only pull.

Acceptance evidence:

- the Anthony Chen / *Ilo Ilo* reproduction now renders 12 cases instead of one while retaining one
  genuine selectable film and 11 explicitly non-selectable archive fillers;
- the label reads `Anthony Chen · director & related`, sits below the case line and remains visible;
- the compact model loads as a 4.1 MB self-contained GLB, down from 6.1 MB;
- live browser validation confirms the rebuilt scene loads, reports 12 cases and has zero page-level
  horizontal overflow;
- close rear-wall and angled-corner checks show separated case silhouettes, clear hover expansion and
  no side/rear collection intersection;
- an exact *The Third Man* / Carol Reed close-up at the back-wall angle shows separate shallow cases,
  and the hovered case remains clear of both neighbours without a duplicate outline;
- 76 automated tests, JavaScript syntax and repository whitespace checks pass.

### 14 August 2026 — Blender WebGL film shelf

Delivered:

1. Replaced the simulated CSS room with a real GLB generated by a deterministic Blender
   script, including a gallery shell, one fitted shelf wall, smoked-oak boards, blackened steel,
   brass rails, carpet, ceiling lights, entrance framing and populated ambient archive rows.
2. Added a pinned, locally served Three.js WebGL runtime and GLTF loader; the shelf has no CDN or
   external-rendering dependency and the checked-in GLB requires no Blender installation at runtime.
3. Added a bounded first-person camera with pointer-look, mouse-wheel and W/S walking, A/D strafing,
   reset and visible walk controls, plus a live room-position indicator and radar.
4. Created film-specific transparent jewel cases in the browser so director, shared-cast, production-
   country and relevant-film collections stay connected to live discovery data rather than being baked
   into the model.
5. Added generated paper spines, physical brass shelf plaques, hover pull-out animation, ray-cast case
   picking and selected-film highlighting; selecting a 3D case rebuilds both the edition and shelf.
6. Added a Blender regeneration tool, local Three.js licence, static-asset regression tests, responsive
   WebGL sizing, reduced-motion handling and a visible loading/error fallback.
7. Reframed the experience as a single film shelf: all titled, selectable collections now occupy
   separate horizontal rows on the rear wall, while side-wall shelving was removed. This eliminates
   the cross-wall perspective overlap that remained even after the cases were physically separated.
8. Mounted each collection label on its own shelf fascia so labels no longer cover cases on the row
   below, including at the closest permitted camera position.
9. Prevented partial shelf flashes: the viewer now waits for related-film indexing before mounting,
   renders a complete hidden frame, waits for two browser paint frames and keeps the loading panel in
   place until the canvas fade has finished.
10. Replaced the two remaining decorative GLB rows and all generated placeholders with five live,
    selectable rows of real related-film records. Increased relationship retrieval to 18 per category,
    omitted unresolved Q-ID captions, widened cases to twelve per row and upgraded spine and plaque
    typography for clear close-view reading. Removed the redundant in-scene control hint so it cannot
    cross the bottom shelf caption; hovering a case now exposes its full title, year and director in
    the shelf header without compressing the text onto a narrow spine.
11. Wrapped live cases in their available film-poster artwork with a centre crop and translucent title
    treatment. Poster requests are deduplicated, bounded by a six-second fallback and included in the
    ready gate so artwork does not pop in after the shelf appears.
12. Removed the sparse-response fallback that could reveal one repeated case on every row. Related-film
    retrieval now retries transient failures, requires ten distinct verified records before reveal,
    reports a clear unavailable state instead of inventing fullness, and hydrates the existing archive
    in place so late data no longer causes an unexplained full-panel refresh.
13. Replaced per-row pool reuse with a shelf-wide film and title/year ledger, preventing any edition
    from appearing on more than one row. Expanded each relationship category to sixty candidates and
    standardised the final rows at ten cases, so five complete rows can remain genuinely distinct while
    respecting the requested 10–15-case width. Matched both spine and fascia texture aspect ratios to
    their physical meshes so captions render at natural proportions.
14. Moved the default and reset camera from the distant doorway to close reading distance, while
    retaining the existing step-back and free-walk controls. Added an eight-request, IMDb-verified
    Letterboxd fallback budget for related films that have neither a Wikidata image nor a usable
    Wikipedia poster, with cached artwork reused on later shelf builds.
15. Derived the walking and strafing basis from the rendered Three.js camera's world direction,
    rather than duplicating its yaw maths. W/S now follow the direction actually on screen and A/D
    remain perpendicular to it at every viewing angle.

Acceptance evidence:

- the production GLB loaded successfully from FastAPI into the WebGL canvas;
- visible browser checks confirmed distant and close views of the single fitted shelf wall;
- three Move closer actions moved from `DISTANT VIEW` towards the shelf while retaining the full
  horizontal separation between every case;
- a real pointer hover activated the case pull-out state, and clicking it changed the selected edition
  from *In the Mood for Love* to *Happy Together* before reloading the 3D collection;
- compact validation retained the live scene and produced no page-level horizontal overflow;
- a populated close-view check for *In the Mood for Love* confirmed three parallel rows, unobstructed
  spines and labels mounted clear of the cases;
- loading-state validation confirmed that the shelf stays covered until its live cases and first full
  WebGL frame are ready;
- shelf allocation regression checks confirm that row filling shares one ID and title/year ledger,
  and 3D texture checks preserve the physical aspect ratio of spine and shelf captions;
- a live *We Are All Strangers* audit rendered 50 cases across five full rows and reported 50 unique
  title/year editions; close-view inspection confirmed naturally proportioned fascia and spine text;
- related-film regression coverage confirms that an IMDb identity can supply a source-attributed
  Letterboxd poster when the primary Wikimedia paths are empty;
- live *We Are All Strangers* validation opened directly in `MID VIEW`, returned Reset view to the
  same close position and loaded its real Letterboxd poster through the verified IMDb match; the 3D
  shelf completed with 50 cases and no artwork-loading errors;
- movement-vector regression checks require the basis to come from the rendered camera direction;
  live four-heading validation confirmed W follows front, right, left and rear-facing views, while
  a 90-degree side view confirmed D and A move to the camera's right and left respectively;
- 3D asset tests, the full automated suite, JavaScript syntax and repository whitespace checks pass.

Operational note:

- removing the redundant side shelving reduced the generated GLB from roughly 3.7 MB to about 0.8 MB;
  the asset remains browser-cached and requires no Blender installation at runtime.

### 13 August 2026 — Walkable CSS 3D closet

Delivered:

1. Converted the archive from a panoramic composition into a layered CSS 3D scene with a recessed
   back wall, sharply angled side walls, floor and ceiling planes, and a foreground doorway.
2. Added a bounded camera depth that can move from the entrance to close shelf-reading distance.
3. Mapped vertical pointer dragging, mouse-wheel movement, W/S and Up/Down keys, and visible Walk
   in/Walk out controls to the same camera model; horizontal dragging continues to turn between
   aisles.
4. Added a live depth gauge and entrance/mid-room/close-shelf position labels, with Reset view
   returning both direction and distance to centre.
5. Preserved transformed case hit targets so a film remains selectable at close range, while drag
   completion still suppresses accidental selection.

Acceptance evidence:

- live browser checks moved the camera from `-360` at the entrance to `360` close to the shelves;
- vertical pointer drag reached depth `396`, mouse-wheel movement returned towards the entrance,
  and the W key advanced the same camera by one bounded step;
- a real pointer click selected *Ashes of Time* while the case was on a transformed 3D shelf;
- compact layout retains visible walk controls and no page-level horizontal overflow;
- 73 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Draggable walk-in film closet

Delivered:

1. Replaced the flat related-title shelves with a panoramic three-wall archive room modelled on
   the physical browsing experience of the Criterion Closet.
2. Placed the director's complete available filmography on one uninterrupted, physically labelled
   front row while retaining poster-art jewel cases among non-interactive archive filler cases.
3. Added verified relationship shelves for shared cast, production country and genre/metadata
   affinity, with the matched actor and country names printed on physical shelf labels.
4. Added mouse and touch dragging, native trackpad scrolling, arrow-key navigation, a live aisle
   indicator and a re-centre control.
5. Prevented a completed drag from accidentally selecting the case beneath the pointer and kept
   deliberate case selection connected to the main edition display.
6. Added responsive framing, reduced-motion compatibility and horizontal-page-overflow guards.

Acceptance evidence:

- live *In the Mood for Love* validation populated 19 films on the Wong Kar-wai row, 10 shared-cast
  matches, 12 production-country matches and 12 metadata-affinity recommendations;
- a real pointer drag moved from the centre to the Director aisle without changing the selected
  film, while arrow-key navigation moved the same viewport independently;
- selecting *Ashes of Time* from the closet changed the main edition title, cover and dossier
  target;
- desktop, dark-theme and compact viewport checks show no page-level horizontal overflow;
- 73 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Dossier reception and awards

Delivered:

1. Added attributed Douban and Letterboxd platform scores to the dossier opening panel.
2. Normalised both providers to 100 and added a combined score weighted 50% per source only
   when both ratings are available.
3. Added up to three prominent Wikidata awards with linked names and concise introductions.
4. Omitted missing ratings and awards rather than rendering disabled or empty controls.

Acceptance evidence:

- live *Parasite* validation displays Douban 8.8/10, Letterboxd 4.5/5 and a 89.2/100
  equal-weight aggregate;
- the same dossier displays the Palme d'Or and two Academy Awards with source-linked context;
- browser checks confirm desktop and compact layouts without overflow or console errors;
- 69 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Exact-title Bilibili full-film discovery

Delivered:

1. Retained attributed multilingual Wikidata labels as provider-search aliases.
2. Reordered Bilibili acquisition to search exact CJK titles before qualified topical queries.
3. Expanded complete-film markers and allowed an exact alias plus explicit completeness language
   to trigger bounded detail validation when an upload uses a later distribution year.
4. Preserved year/director safeguards for weak or ambiguous matches and content-type exclusions
   for interviews, criticism, trailers, clips, games and music.
5. Added final revalidation for fresh and persisted Full film cards, rejecting unrelated long
   results and reclassifying long reactions as video essays.

Acceptance evidence:

- a regression reproduces *The World of Love* (2025), exact alias `世界的主人`, upload year 2026,
  BV ID `BV1iHZcBgEzm` and the public 10,294-second duration;
- the supplied result is classified as `full_film` and placed under the Full film tab;
- a live search returned `BV1iHZcBgEzm` as a 10,294-second Full film;
- all 64 automated tests pass;
- scoped Ruff and repository whitespace checks pass.

### 13 August 2026 — Crew-value display validation

Delivered:

1. Prevented embedded MediaWiki style and script content from entering parsed infobox values.
2. Added backend plausibility validation for crew names, rejecting CSS, markup machinery,
   malformed punctuation and unreasonable lengths.
3. Added an independent browser-side crew guard before values are joined and displayed.
4. Added a regression fixture reproducing the leaked `.mw-parser-output` value while retaining
   the legitimate producer names that follow it.

Acceptance evidence:

- the malformed CSS fixture yields only `Kim Se-hun` and `Jenna Ku`;
- all 61 automated tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Attributed review and video text in Deep Study

Delivered:

1. Added bounded raw review bodies from every cached criticism provider to the typed Deep Study
   evidence packet alongside structured critical claims.
2. Added uploader descriptions from relevant interviews, video essays, lectures and production
   material while excluding complete films, trailers and scene extracts from prompt text.
3. Added best-effort public YouTube caption discovery, manual/automatic track labelling, event
   normalisation and private catalogue persistence.
4. Added `E*` attributed-text citations, strict citation validation and expandable source text
   with canonical links in the generated-study interface.
5. Preserved evidence boundaries between criticism, uploader context, fallible captions, verified
   creator statements and direct film observation.

Acceptance evidence:

- focused tests cover review text, video descriptions, caption parsing, prompt inclusion and
  attributed-source citation validation;
- all 60 automated tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Multi-source crew reconciliation

Delivered:

1. Retained Wikidata as the canonical film identity while enriching factual credits from the
   matched English Wikipedia film infobox.
2. Added director, writer/screenplay, producer, cinematographer and editor extraction using a
   bounded standard-library HTML parser.
3. Merged identity-normalised names, filled only missing runtime values and retained field-level
   Wikidata/Wikipedia provenance.
4. Added producer and editor facts plus linked crew sources to the dossier.
5. Included the expanded crew and provenance in the Deep Study evidence packet.

Acceptance evidence:

- live *We Are All Strangers* reconciliation returns Anthony Chen as director, writer and
  producer; Teoh Gay Hian as cinematographer; Hoping Chen as editor; and a 157-minute runtime;
- the dossier visibly links both Wikidata and the Wikipedia infobox as crew sources;
- 57 automated tests pass, including infobox reconciliation and evidence-packet coverage.

### 13 August 2026 — Minimal interface copy

Delivered:

1. Removed decorative header and footer copy from the public interface.
2. Removed repeated section labels, readiness text, connector descriptions and instructional
   empty states across discovery, analysis and Settings.
3. Retained action labels, error messages, source attribution, privacy boundaries and live status
   only where they affect a decision or explain system state.

Acceptance evidence:

- browser checks confirm the simplified public and Settings pages in wide and compact layouts;
- no footer chrome, normal-operation readiness copy or horizontal overflow remains;
- 55 automated tests, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Stable cumulative video discovery

Delivered:

1. Added a private `.firstroll/videos` catalogue that survives backend and browser refreshes.
2. Changed **Refresh videos** to **Find more videos**: each search merges rather than replaces.
3. Deduplicated by platform and provider video ID while preserving the relative order of
   previously accepted videos within each content type.
4. Expanded Bilibili retrieval into focused complete-film, criticism, interview, production
   material and extract queries; increased the per-provider candidate allowance.
5. Capped each film catalogue at 48 accepted items and returned the number added by each search.

Acceptance evidence:

- two live *Memoria* searches expanded the catalogue from 20 to 25 videos;
- all 20 initial videos remained present in the same relative order;
- the expanded result covered seven content types;
- 55 automated tests pass, including cumulative merge and duplicate-ID regression tests.

### 13 August 2026 — Typed video classification

Delivered:

1. Added one content type to every YouTube and Bilibili result: full film, interview,
   video essay/review, lecture, trailer, scene/extract, behind the scenes or other.
2. Treated a complete feature as one **Full film** category without rights subcategories.
3. Added official YouTube duration lookup plus Bilibili search-record duration parsing and
   bounded public-page metadata fallback.
4. Added a second compact Bilibili query for complete films and cross-provider ordering that
   surfaces full films first.
5. Made textual content markers override duration so long interviews and ceremonies are not
   misclassified as films.
6. Added criticism-style category tabs that filter the fetched cards locally, showing only
   categories present in the current result set.

Acceptance evidence:

- a live *Memoria* search classifies the complete film, Cannes press conference, video essays,
  scene extracts and festival ceremony separately;
- browser checks confirm that All, Full film and Trailer tabs expose 12, two and four matching
  cards respectively, without another network request;
- six focused classification and provider tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

### 13 August 2026 — Persistent dark mode

Delivered:

1. Added an accessible light/dark toggle to the main interface and local Settings.
2. Used the operating-system preference for first load and saved explicit choices locally.
3. Added a dark palette for surfaces, typography, controls, evidence panels and the animated logo.
4. Kept the selected theme consistent while navigating between discovery and Settings.
5. Refined the switch and button system with restrained depth, rounded controls, tactile press
   feedback and spring-like motion while retaining FirstRoll's editorial identity.

Acceptance evidence:

- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm both themes, navigation persistence and narrow-width layouts;
- toggle labels and pressed state remain synchronised with the active theme;
- the animated thumb passes through an intermediate position before settling, and reduced-motion
  preferences suppress non-essential transitions.

### 13 August 2026 — Film viewing resources

Delivered:

1. Added a **Watch & study** dossier section with local progress feedback and embedded
   public-video cards.
2. Added official YouTube Data API search with a write-only API-key entry in Settings and
   privacy-enhanced YouTube embeds.
3. Added key-free Bilibili retrieval through its server-rendered public search page after its
   anonymous JSON endpoint returned HTTP 412 risk control.
4. Added film-title, original-title, year, director and film-context relevance checks to
   reject ambiguous namesakes, music and games.
5. Restricted provider requests, redirects, thumbnails and embed URLs to known HTTPS hosts,
   with timeouts, response limits and bounded result counts.
6. Kept videos as attributed viewing resources rather than automatically treating their
   contents as verified evidence or sending them to DeepSeek.

Acceptance evidence:

- live *Memoria* Bilibili check returns three film-specific results after rejecting unrelated
  uses of the title;
- targeted video, settings and discovery tests pass;
- scoped Ruff, JavaScript syntax and repository whitespace checks pass.

This file is the durable implementation ledger for FirstRoll. Update it whenever a
milestone changes state, a meaningful feature is completed, or verification evidence
changes.

Status vocabulary:

- **Complete** — implemented and verified against its current acceptance criteria.
- **In progress** — active implementation exists, but required work remains.
- **Planned** — accepted scope, not yet implemented.
- **Blocked** — cannot progress without a named decision, dependency or permission.

## Current Snapshot

**Last updated:** 14 August 2026

**Release stage:** local working prototype

**Primary development URL:** `http://127.0.0.1:8000`
**Automated verification:** 76 tests passing

| Area | Status | Current evidence |
|---|---|---|
| Film discovery | Complete | Optional TMDb primary catalogue, open Wikidata/Wikipedia failover, attributed dossier enrichment and the native director shelf |
| Public video resources | Complete | Persistent cumulative catalogue; typed tabs; bounded uploader-description and public YouTube-caption extraction |
| Product navigation | Complete | Discover, Analyse and Settings preserve per-tab view content and scroll; Study remains consolidated into Discover |
| Theme support | Complete | System-aware light/dark themes with a locally persisted accessible toggle |
| Local settings | Complete | Write-only connector credentials plus local add, remove and index controls for the private library |
| Private library catalogue | Complete | Seven existing film-study PDFs retained; managed uploads and non-destructive removal; paths and content withheld from public APIs |
| PDF ingestion | Complete | Token-aware page chunks, overlap, section hints, language and stable IDs |
| Local embeddings | Complete | 4,381 of 4,381 chunks embedded with a local multilingual 384-dimension model |
| Hybrid retrieval | Complete | FTS5 + vector candidates, reciprocal-rank fusion and diversity selection |
| Query planning | Complete | User focus, craft taxonomy and attributed criticism generate subqueries |
| Douban adapter | Complete | Optional local MCP connection, title matching, review links and private cache |
| Research adapter | Complete | Crossref abstracts with local identity relevance checks and DOI attribution |
| Letterboxd adapter | Complete | Public-web IMDb identity resolution plus optional official OAuth retrieval |
| Guardian adapter | Complete | Public content-index matching and attributed article-body retrieval |
| Criticism structuring | Complete | Pydantic critic claims with missing-field preservation and evidence labels |
| Criticism source controls | Complete | Tabbed provider switcher; first selection fetches and later selections reuse the cached bundle |
| Evidence packet | Complete | Film record, theory, critic claims, raw review text and attributed video text separated by explicit permitted uses |
| Deep Study schema | Complete | Critic, theory, hypothesis, mechanism, alternative, verification and confidence fields |
| Quality control | Complete | Deterministic gate, citation checks and at most one bounded repair call |
| Evidence-layered UI | Complete | Quality status, validated `S*`/`C*`/`E*` citations, retrieval rationale and expandable excerpts |
| Clip analysis | Complete | Scene/shot metrics, shot scale, colour, objects and JSON/CSV export |
| Clip evidence in Deep Study | Planned | Current study generation does not consume measured clip observations or timecodes |
| Creator primary sources | Partial | Relevant video descriptions and available public captions enter Deep Study; verified speaker attribution remains planned |
| Persistent projects | Planned | Film, clip, study and note sessions are not retained as reusable projects |

## Latest Completed Milestone

### 11 August 2026 — Architecture map with implementation stack

Delivered:

1. Reworked the system diagram into five explicit responsibility layers.
2. Added the shared runtime and specialised technologies to each architectural component.
3. Separated public inputs, private inputs, local processing and external synthesis visually.
4. Added a compact layer-to-stack reference beneath the diagram.

Acceptance evidence:

- every named technology maps to the current project configuration or implementation;
- Mermaid uses GitHub-compatible flowchart, subgraph, class and labelled-edge syntax;
- the local/private boundary and planned clip-evidence bridge remain explicit.

### 11 August 2026 — Simplified discovery landing page

Delivered:

1. Removed the research-principle card from the discovery hero.
2. Removed the empty-state film-dossier explainer and its three descriptive panels.
3. Removed the redundant hero guidance sentence and tightened the surrounding layout.

Acceptance evidence:

- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm clean initial, search-results and narrow-width layouts.

### 11 August 2026 — Douban translated-title identity repair

Delivered:

1. Reproduced the apparent MCP failure for *Memoria* and traced the nested task-group error
   to FirstRoll's film identity guard, not to Douban review availability.
2. Prefer Wikidata's IMDb identifier for Douban film search, with exact-year validation of
   the unique provider result.
3. Retained the stricter title/year scorer when no stable external identifier is available
   or the provider returns ambiguous candidates.
4. Flatten nested MCP exception groups so future failures expose the actionable underlying
   diagnostic.
5. Added regression coverage for translated-title acceptance, same-year ambiguity and
   task-group error unwrapping.

Acceptance evidence:

- live *Memoria* check resolves Douban subject `30137576` and retrieves eight attributed
  long-form reviews;
- scoped criticism tests: 23 passed;
- scoped Ruff checks pass.

### 11 August 2026 — Secondary-evidence technical documentation

Delivered:

1. Documented the complete Crossref, Douban, Letterboxd and Guardian acquisition pipelines.
2. Recorded provider-specific identity resolution, confidence thresholds, result limits,
   attribution fields, response-size limits, redirect restrictions and failure behaviour.
3. Added the *Memoria* translated-title diagnosis as a concrete explanation of IMDb-based
   Douban resolution and MCP task-group error unwrapping.
4. Distinguished Letterboxd public-page acquisition from its official OAuth API without a
   hidden fallback between them.
5. Documented the raw-evidence cache, stable source-ID relationship and Pydantic boundary
   that precede optional DeepSeek claim structuring.

### 11 August 2026 — Source documentation and Letterboxd identity repair

Delivered:

1. Documented the Wikidata, Wikipedia, Crossref, Douban, Letterboxd and Guardian
   acquisition paths in the README.
2. Recorded the raw-retrieval, private-cache and separate DeepSeek-structuring boundary.
3. Replaced ambiguous Letterboxd slug-first matching with verified IMDb-ID resolution when
   Wikidata supplies an IMDb identifier.
4. Added a JSON-LD director guard for title/year fallback pages.
5. Added regressions for same-title, same-year films with different directors.

Acceptance evidence:

- live *An Unfinished Film* check resolves Lou Ye's canonical Letterboxd slug and retrieves
  four attributed reviews;
- automated tests: 43 passed;
- scoped Ruff, frontend JavaScript syntax and repository whitespace checks pass.

### 11 August 2026 — Animated monochrome identity

Delivered:

1. Replaced the framed reel symbol with a minimal black-and-white film-roll mark.
2. Animated the film strip once from its short resting tab to its fully extended state.
3. Applied the same identity to the discovery and local Settings headers.
4. Added a compact SVG favicon and a static reduced-motion state.
5. Slimmed the cylinder and left a short film tab visible in the resting state.

Acceptance evidence:

- SVG validity, frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm the animation cycle, favicon response, Settings header and narrow layout;
- the stylesheet provides a static, fully extended mark when reduced motion is preferred.

### 11 August 2026 — Local recent-search history

Delivered:

1. Removed example values from the film title, year and director fields.
2. Replaced the three suggested films with the five most recent searches.
3. Stored recent searches locally, deduplicated them and kept the newest search first.
4. Made each recent item restore the full title, year and director query and search again.

Acceptance evidence:

- automated tests: 43 passed;
- frontend JavaScript syntax and repository whitespace checks pass;
- browser checks confirm empty, persisted, deduplicated and narrow-width states.

### 11 August 2026 — Criticism source switcher

Delivered:

1. Replaced the separate provider actions with a compact, accessible source tab switcher.
2. Made the first selection of an unloaded source initialise its fetch and structuring flow.
3. Made later selections switch instantly to the cached provider bundle without refetching.
4. Moved refresh controls into the active source panel and marked active and loaded states.
5. Prevented slower background requests from replacing a source selected in the meantime.

Acceptance evidence:

- automated tests: 40 passed;
- frontend JavaScript syntax, scoped Ruff checks and repository whitespace checks pass;
- browser checks confirm cached Douban and Letterboxd switching sends no new request;
- desktop and narrow-width layouts have no horizontal overflow or console errors.

### 11 August 2026 — Settings-based private library management

Delivered:

1. Added a Study library panel to Settings with the current private catalogue and index state.
2. Added local catalogue uploads for PDF, EPUB, Markdown and text documents with a 500 MB
   limit, while clearly identifying PDF as the current indexed format.
3. Added non-destructive removal that unregisters a document without deleting its source file.
4. Added an explicit local search-index rebuild action and visible rebuild recommendation.
5. Preserved all seven books already registered on the development machine.
6. Kept file paths, document contents, uploaded copies and derived index data outside public
   responses and source control.
7. Reduced Settings guidance copy to essential labels, privacy cues and index limitations.

Acceptance evidence:

- automated tests: 40 passed, including add, remove, validation and rebuild flows;
- frontend JavaScript syntax, scoped Ruff checks and repository whitespace checks pass;
- live catalogue metadata still reports seven registered books after the change;
- desktop and narrow-width browser checks show the complete catalogue with no console errors.

### 11 August 2026 — Layered README architecture map

Delivered:

1. Reorganised the system map into five readable layers from user experience to outputs.
2. Simplified service labels while retaining the implemented discovery, criticism,
   retrieval, synthesis, quality-control and clip-analysis flows.
3. Strengthened the visual distinction between local/private processing, provenance-bearing
   evidence and external services.
4. Kept the clip-to-study connection visibly marked as planned work.

Acceptance evidence:

- Mermaid block uses GitHub-compatible flowchart, subgraph and class syntax;
- every architecture node maps to an implemented service, evidence type or documented plan;
- the privacy and external-transmission boundary is stated directly beneath the graph.

### 9 August 2026 — Official Letterboxd API adapter

Delivered:

1. Added write-only Client ID and Client Secret fields to the local Settings registry.
2. Implemented official OAuth client-credentials authentication with clear rejection errors.
3. Added official film search and popularity-ranked public review retrieval.
4. Preserved member attribution, log-entry ID, rating, language and source links.
5. Stored criticism bundles per provider so Letterboxd and Douban claims can coexist.
6. Added a Letterboxd action to film dossiers and combined both providers in Deep Study.
7. Added transport-isolated tests with no scraping or unofficial fallback.

Acceptance evidence:

- automated tests: 29 passed;
- scoped Ruff checks: passed;
- frontend JavaScript syntax and repository whitespace checks: passed;
- live Settings API: Letterboxd exposes separate masked Client ID and Client Secret fields;
- live unconfigured request: returns a specific incomplete-credentials response without making
  an unofficial fallback request.

### 7 August 2026 — README architecture map

Delivered:

1. Expanded the README Mermaid diagram into a boundary-aware system architecture map.
2. Distinguished external services from local/private processing and storage.
3. Documented the film-discovery, criticism, hybrid-retrieval, evidence-packet,
   quality-repair and clip-analysis data flows.
4. Marked the clip-to-study connection as planned rather than implemented.

Acceptance evidence:

- Mermaid block uses GitHub-compatible flowchart and subgraph syntax;
- every implemented data flow corresponds to a current FirstRoll service;
- privacy and external-transmission boundaries are explained directly below the graph.

### 7 August 2026 — Continuous essay presentation

Delivered:

1. Kept the structured evidence sections as an internal generation and validation model.
2. Replaced the visible two-column evidence cards with one continuous critical essay.
3. Joined critic reports, theory, hypotheses, mechanisms and alternative readings into
   successive prose paragraphs with compact inline citations.
4. Moved viewing verification into a collapsed post-essay checklist and retained
   expandable retrieval and source evidence.
5. Tuned the generation prompt so internal sections advance one argument without
   repeating the same thesis.
6. Switched the default synthesis model from `deepseek-v4-flash` to
   `deepseek-v4-pro`; Flash remains available through `DEEPSEEK_MODEL`.

Acceptance criteria:

- [x] continuous article renders without visible evidence-card segmentation;
- [x] theory and critic citations remain visible within the relevant paragraph;
- [x] quality status, creator-intent boundary and source evidence remain inspectable;
- [x] automated tests and frontend syntax checks pass;
- [x] live browser generation uses `deepseek-v4-pro` and renders as one article.

### 6 August 2026 — Deep Study display compatibility fix

Delivered:

1. Added versioned frontend asset URLs so an updated stylesheet cannot load with stale
   study-rendering JavaScript.
2. Disabled HTML shell caching for the local application entry point.
3. Added a backward-compatible renderer for legacy sections that contain `analysis`
   instead of the newer layered evidence fields.
4. Restored explicit text styling for legacy study paragraphs.

Acceptance evidence:

- legacy and layered section fixtures both display substantive analysis text;
- frontend JavaScript syntax check: passed;
- local browser check: study analysis layers render above verification tasks.

### 6 August 2026 — Hybrid retrieval and evidence-quality pipeline

Delivered:

1. Replaced character-count PDF chunks with token-aware, overlapping page chunks.
2. Added stable content IDs and index schema metadata.
3. Added local multilingual embeddings and private SQLite vector storage.
4. Added focus- and criticism-aware query planning.
5. Added FTS/vector reciprocal-rank fusion and diversity constraints.
6. Added typed evidence packets that constrain permitted claim types.
7. Expanded Deep Study into explicit evidence and inference layers.
8. Added deterministic specificity, calibration and citation checks.
9. Added one bounded DeepSeek audit/repair attempt.
10. Added visible quality state, source rationale and full evidence excerpts to the UI.

Acceptance evidence:

- private index: 7 documents, 4,381 cited chunks and 4,381 local vectors;
- automated tests: 22 passed;
- scoped Ruff checks: passed;
- frontend JavaScript syntax check: passed;
- `git diff --check`: passed;
- live API test: hybrid retrieval used film focus and cached criticism;
- live browser test: evidence layers, quality status and citations rendered correctly;
- safety test: an overconfident study remained labelled insufficient evidence after its
  single repair pass.

### 7 August 2026 — Actionable Douban diagnostics

Delivered:

1. Replaced the ambiguous empty-review error with separate authentication, genuinely empty,
   incomplete-row and connector-schema diagnostics.
2. Added safe, length-limited provider-response previews for otherwise unknown formats.
3. Redacted credential-like values and links from diagnostic previews.
4. Added regression tests for each diagnostic path.

Acceptance evidence:

- automated tests: 26 passed;
- scoped Ruff checks: passed;
- `git diff --check`: passed;
- live connector test for *Syndromes and a Century*: correct Douban film match, one
  attributed review summary and four structured critical claims returned.

### 7 August 2026 — Multiline Douban review parsing

Delivered:

1. Reconstructed logical review rows when Douban summaries contain physical line breaks.
2. Preserved multiline review prose rather than rejecting partial Markdown-table lines.
3. Tolerated unescaped pipe characters inside summary text while retaining the final review ID.
4. Added a regression fixture based on the malformed *Kaili Blues* response shape.

Acceptance evidence:

- live *Kaili Blues* response: eight reviews reconstructed from a 280-line table and eight
  attributed critical claims returned;
- focused parser tests and Ruff checks: passed.

## Next Milestone

### Autonomous Agent causal ablations — In progress

Objective: prove which autonomous components add value before integrating claim review, coaching or a
product route.

Acceptance criteria:

- [x] Define typed evidence gaps and require independent origins for recovered packets.
- [x] Add a deterministic acquisition baseline and Crossref Agent action.
- [x] Acquire each provider observation once and share it privately across fixed, deterministic and
  model-planned lanes.
- [x] Blind lane identity during owner packet review.
- [x] Provide a frozen field-patch versus regeneration harness with controlled schema/citation faults.
- [x] Require exact preservation of accepted fields and complete citation validation.
- [x] Freeze value, latency, token, privacy and human thresholds before any paid call.
- [ ] Reuse an accepted private packet for synthesis without reacquisition.
- [ ] Advance claim audit only if the preceding capability earns its cost against the baseline.

## Subsequent Priorities

1. **Claim audit and targeted editor** — classify evidential strength and patch only fields or
   sections named by deterministic validation.
2. **Evidence-grounded filmmaker coach** — turn accepted claims into traceable viewing and production
   exercises without adding film facts.
3. **Durable local Agent pilot** — add owner-scoped checkpointing, cancellation, resume and private
   project retention after reliability gates pass.
4. **Clip-to-study evidence bridge** — remain deferred until the complete text Agent is accepted.
5. **Creator primary-source layer** — ingest attributed interviews, commentaries and production
   records; distinguish direct quotation, paraphrase and inference.

## Known Risks and Constraints

- Douban MCP is unofficial and depends on an external page structure and access policy.
- Review summaries are secondary copyrighted material; retain attribution and source links.
- User-supplied books and clips must remain local and should not be committed to Git.
- DeepSeek sees only the selected evidence packet, but this still transmits excerpt text to
  an external model provider after the user chooses Generate study.
- A strong formal reading cannot be confirmed without viewing evidence.
- Creator intention must not be inferred from style, criticism or theory alone.
- The local multilingual model adds a first-load delay and a sizeable local download.
- Inherited computer-vision dependencies may behave differently across operating systems.

## Maintenance Rule

For each meaningful implementation change:

1. update the relevant row in **Current Snapshot**;
2. add a dated milestone entry when a coherent feature set completes;
3. record automated and live acceptance evidence;
4. move the next actionable milestone into **Next Milestone**;
5. keep limitations explicit rather than silently removing unfinished scope.
