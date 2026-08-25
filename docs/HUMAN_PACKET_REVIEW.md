# Human Evidence-Packet Review

This procedure records the completed fixed-workflow human gate. An Agent cannot supply these ratings
or attest that a filmmaker personally inspected the evidence. If the revised repeated text comparison
passes every machine target, `tools/review_text_agent_packets.py` applies the same rubric only to its
mode-`0600` changed-packet snapshot; that later review remains private and separately attested.

## Privacy Boundary

`tools/review_evidence_packets.py` deliberately prints selected private theory passages and cached
attributed source text in the local terminal. It does not send that material to a new provider and
does not write packet contents into its review files.

- Do not paste terminal output into chat, GitHub, screenshots or notes outside the private machine.
- Private scores, optional notes and resume state stay under Git-ignored
  `.firstroll/evaluations/human-packet-review.json` with mode `0600`.
- The redacted aggregate contains case IDs and numeric scores only—no note, title, prompt, source or
  passage text.
- Run the review from a clean, current `master`; a saved partial review cannot resume after the source
  revision changes.

## Run the Review

From the repository root:

```bash
uv run python tools/review_evidence_packets.py
```

The tool prepares the same five frozen packets without calling DeepSeek. For each case it displays:

1. selected film and focus;
2. selected theory passages and private page locators;
3. selected attributed reviews/video text and public provenance;
4. selected critic claims;
5. epistemic boundaries and aggregate selection/omission manifests; and
6. the automated packet diagnostic, clearly separated from the human score.

Enter a whole-number score from 1 to 5 for every dimension. Enter `q` to save and resume later. After
all five cases, type uppercase `YES` only if you personally inspected every displayed packet. Input is
decoded as UTF-8 with malformed terminal bytes replaced, so a pasted optional note cannot discard the
current case through a decoding crash.

## Rubric

### Focus relevance

**Question:** Does the selected evidence directly help answer the filmmaker's stated focus?

- **1:** Mostly unrelated or generic material.
- **3:** A useful core with noticeable generic or peripheral material.
- **5:** Every retained item materially advances the stated focus.

### Traceability

**Question:** Can the reader tell who said what and return to the applicable source or private
locator?

- **1:** Claims and origins are difficult to distinguish.
- **3:** Most origins are understandable, but some links or locators require inference.
- **5:** Evidence type, attribution and applicable source or locator are unambiguous throughout.

### Source diversity

**Question:** Does the packet balance relevant theory, criticism and available primary or audiovisual
evidence without repetitive padding?

- **1:** One repetitive source class dominates without justification.
- **3:** More than one useful perspective is present, but the balance could improve.
- **5:** The packet uses the strongest available complementary perspectives and explains genuine
  absences.

### Epistemic calibration

**Question:** Does the packet preserve the boundary between observations, attributed reports,
frameworks and hypotheses?

- **1:** Evidence categories or certainty are materially conflated.
- **3:** The main boundaries are visible with occasional ambiguity.
- **5:** Every item has an appropriate evidence type and confidence boundary.

### Filmmaker actionability

**Question:** Would this packet help a filmmaker conduct a more precise close viewing or formal
experiment?

- **1:** It offers little usable direction for viewing or making.
- **3:** It suggests useful lines of inquiry but remains partly generic.
- **5:** It enables specific, observable and practically useful viewing tests.

## Passing Rule

A case passes only when:

- focus relevance is at least 4;
- traceability is at least 4;
- filmmaker actionability is at least 4; and
- no dimension is below 3.

At least four of the five cases must pass, giving a pass ratio of at least `0.8`.

## After Attestation

The tool writes the redacted aggregate to
`.firstroll/evaluations/human-packet-review-redacted.json`. Then run:

```bash
uv run python tools/check_pre_agent_gate.py \
  --human-review .firstroll/evaluations/human-packet-review-redacted.json \
  --output evals/results/pre-agent-final-gate-YYYY-MM-DD.json
```

A passing human result changes the final target from `pending_human_review` to `passed`. It does not
start Agent development automatically: Step 11 must first be frozen in the repository, followed by
the explicit Step 12 go/no-go decision.
