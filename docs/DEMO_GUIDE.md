# Demonstration guide

For the Review-2 presentation. Roughly 12 minutes at a comfortable pace.

`/presentation` in the running app walks this same sequence with presenter notes and a
direct link to each screen, and it remembers your place across a refresh.

---

## Before you start

```bash
npm run seed     # restores the corpus to its starting state
npm run dev      # API on :8000, UI on :3000
```

Confirm <http://localhost:3000/dashboard> loads and shows 6 properties, 31 documents.
Set the role switcher (top right) to **Buyer**.

If a step goes wrong mid-demo: **Presentation Mode → Reset demo** rebuilds the database and
re-runs the whole pipeline in about ten seconds.

---

## 1 · The problem (1 min) — `/research-gap`

> "Document extraction, blockchain registries, identity, valuation and fraud detection are
> each mature research areas. None of them decides whether a land detail may be *shown* as
> verified, or stops a transaction while it cannot be."

Point at the Limitation column. Then the six pillars underneath: the contribution is the
combination, and the novelty wording says *rarely combined*, not *never attempted*.

## 2 · Upload evidence (1 min) — `/documents`

Select **LTC-PR-0002**, drag in any PDF from `data/synthetic/LTC-PR-0002/`.

> "Classification, text acquisition, layout analysis, claim extraction. The stage timings on
> screen are measured, not scripted — this is the pipeline reporting what it actually did."

Point out the mode selector: the text layer by default, Tesseract available, and OCR selected
automatically when a file has no text layer.

## 3 · Claim-level provenance (1.5 min) — `/properties/LTC-PR-0002?tab=claims`

The Claim–Evidence Matrix. One row per *attribute*, not per document.

Click the **Property Area** row.

> "Document, page, extraction confidence, the exact text it was read from, and the region of
> the page it sat in. Then supporting evidence, conflicting evidence, and the recorded
> contradiction."

## 4 · Contradiction detection (1 min) — same tab

> "The deed says 1800 sq.ft. The certificate says 1650. The system does not average them,
> does not prefer the larger, and does not stay silent. The row is CONFLICTING and the
> difference is quantified: 150 sq.ft, 8.3 %, HIGH severity."

Contrast with **Survey Number**, still VERIFIED — contradiction is per attribute, not per file.

## 5 · The evidence gate (1.5 min) — `/properties/LTC-PR-0001?tab=claims`

Switch to the clean file.

> "Owner name here is VERIFIED because three independent documents agree. On a file with only
> one supporting document it would stay PARTIALLY VERIFIED, however confident the extraction
> was — appearing once proves only that someone wrote it down."

Then the **Owner Name** row on LTC-PR-0002: "Priya Sharma" and "Priya S. Sharma" is a name
variant, not a different person. Partially verified — never verified, never conflicting.

Scroll to **Superseded assertions**.

> "This file has two prior owners and a mortgage created in 2023 and released in 2025. The
> system reads that as history, not contradiction. Without this, every property with a past
> would look fraudulent."

## 6 · Temporal ownership graph (1 min) — `?tab=graph`

Click a node. Switch to **Timeline**.

> "Edges carry validity intervals. That is what distinguishes a discharged mortgage from a
> subsisting one — and every edge cites the document that evidences it."

## 7 · The buyer's view (1.5 min) — `/buyer/LTC-PR-0002`

> "Five sections, visually distinct: verified, partially verified, conflicting, owner
> provided, and not evidenced. A buyer cannot mistake the owner's own text for a certified
> fact."

Point at the masked owner name.

> "Masked — but the buyer still learns the status is PARTIALLY VERIFIED and why. Status is
> decided by evidence, visibility by consent. The two are independent."

Then Restricted information → **Identity document**: never disclosed, with or without consent.

## 8 · Risk and the hold (1.5 min) — `?tab=risk`

> "73.8 out of 100. HIGH. HOLD."

Category breakdown, then the factor list.

> "Every point traces to a rule with a weight, an explanation and the evidence it fired on.
> Nothing here is a black box."

Click the struck-through **Initiate payment** button.

> "Refused — and by the API, not by a disabled button. The refusal is in the audit trail."

## 9 · Minimum-evidence resolution (1 min) — `?tab=resolution`

> "Detecting a problem is the easy half. This is the smallest set of documents that would
> make the transaction safe to progress."

Point at the staircase, then at one step's expected score.

> "Computed by re-running the scorer with that step's rules suppressed. A real counterfactual,
> not a stored guess."

Press **Simulate** on one step to show it changes nothing.

## 10 · Apply the evidence (1.5 min) — the acceptance sequence

Apply the steps in order. Each ingests a real PDF through the full pipeline.

```
73.8 HOLD → 56.9 HOLD → 33.3 WARN → 17.3 PROCEED
```

> "The score fell because the evidence changed — same scorer produced both the prediction and
> the result."

If a reviewer notices the last step beats its prediction (17.3 against 22.8), that is worth
explaining rather than glossing: the simulation suppresses the rules an action would clear,
but real evidence also *earns* mitigations that did not exist before it arrived — here the
affidavit moves the owner name to VERIFIED, which unlocks two of them. The prediction is a
guaranteed lower bound on the improvement, never an overstatement.

If asked how the last step works: the affidavit swears that the two name forms denote the same
person. That is evidence about the *relationship between the names*, which is what was actually
in question — so the resolver reconciles the variant and the owner name becomes VERIFIED.
Nothing is suppressed; `test_acceptance.py` prints which factors, if any, were closed
administratively, and on this corpus the answer is none.

## 11 · Impersonation (1 min) — `/properties/LTC-PR-0003`

> "Listed by Arjun Reddy. Every registered document names Mohan Reddy. The only link is a
> power of attorney that expired on 31 December 2024."

Read the state reason aloud.

> "Note the wording: *seller authority could not be established from the available evidence*.
> Not an accusation. The system reports what the evidence supports and escalates to a human."

## 12 · Document modification (1 min) — `/properties/LTC-PR-0005?tab=documents`

> "Two indicators on the deed: an incremental save, and a font used for ten characters and
> nowhere else in the file. Both computed from the PDF itself. That is what overtyping a
> single field leaves behind."

> "State: REJECT. And the tampered deed loses its standing as an authority — a document that
> may have been altered cannot verify its own contents."

## 13 · The assistant (1 min) — `/assistant`

Ask **"Why is the area marked conflicting?"** — grounded, with citations.

Then click one of the questions in the second row, e.g. **"Who is the neighbouring plot's
owner?"**

> "It refuses. It holds no evidence about a different parcel, and answering from this
> property's documents would be answering a different question. A refusal here is the
> designed behaviour, not a failure."

## 14 · Measured results (1 min) — `/research`

> "Computed by an evaluation script against a ground-truth answer key. Not typed into the
> page."

Point at the caveat panel, then at the OCR comparison.

> "The text-layer figure is 100 %, and the caveat says why that is expected — the grammar was
> written against documents of this shape. So the harness also re-reads every page through
> Tesseract. 98.4 %, with the actual failures listed. That gap is the number that
> characterises extraction."

---

## Likely questions

**"Isn't 100 % just overfitting to your own corpus?"**
Yes, on the text-layer arm, and the page says so above the number. That is precisely why the
OCR arm exists: same answer key, same grammar, a genuinely lossy reader, 98.4 %. The two
sub-100 % figures — citation rate and the OCR arm — are the informative ones.

**"How is this different from an OCR pipeline with validation rules?"**
An OCR pipeline tells you what a document says. This decides whether what it says may be
*shown as verified*, controls who may see the supporting evidence, blocks a transaction while
it cannot, and computes the minimum evidence that would unblock it. The verification status
is computed in a module the extractor cannot reach — that separation is the contribution.

**"What stops the AI from hallucinating?"**
Layering, not instruction. The extractor cannot write a status. The assistant retrieves
structured records and can only speak from them; empty retrieval means refusal, and the
citations are computed before any text is produced. The LLM adapter documents the same
contract for a future model, including post-hoc verification of every number and proper noun.

**"Why does a perfect file still score 17?"**
`BASELINE_NO_OFFICIAL_CONFIRMATION`. Verification here is against supplied documents, not the
government register. Presenting a fully-evidenced file as zero-risk would overstate what the
platform knows.

**"Could this be used to accuse someone of fraud?"**
The wording is constrained deliberately, and it is tested: no risk explanation may contain
"fraud", "forger", "criminal" or "guilty". Integrity findings are indicators requiring
authorised examination. The system escalates to a human; it does not adjudicate.

**"What is actually left for Review-3?"**
Government and eKYC integration, escrow, ML risk calibration, LLM extraction, Neo4j,
production auth and deployment. Every one has a documented interface and nothing is faked in
the meantime — `/architecture` marks each seam.

---

## Quick reference

| | |
|---|---|
| Acceptance case | **LTC-PR-0002** — 73.8 HOLD → 22.8 PROCEED |
| Clean comparison | **LTC-PR-0001**, **LTC-PR-0006** — 17 PROCEED |
| Escalation | **LTC-PR-0003** — 90 ESCALATE |
| Rejection | **LTC-PR-0005** — 87 REJECT |
| Owner-declared, unverified | **LTC-PR-0004** — 50 WARN |
| Reset | Presentation Mode → Reset demo, or `npm run seed` |
| Headless acceptance run | `cd backend && python -m pytest tests/test_acceptance.py -q -s` |
