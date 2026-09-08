# Testing

```bash
npm test                                                    # all 91 tests
cd backend && python -m pytest tests/ -q                    # same, directly
cd backend && python -m pytest tests/test_acceptance.py -s  # the Review-2 sequence, verbose
```

Tests assume a seeded database. `npm run seed` restores it; the acceptance suite reseeds
itself at the end so the demonstration is repeatable.

---

## What each suite is for

### `test_engines.py` — 27 tests · the policies, not the plumbing

Comparison policy, evidential authority and risk aggregation, tested as *claims about the
world* rather than as code paths.

- Names: `Priya Sharma` ≈ `Priya S. Sharma` (partial), `Mohan Reddy` ≠ `Arjun Reddy`
  (mismatch — and a shared surname is scored as a *weaker* mismatch, but still a mismatch).
- Areas: 1800 vs 1805 is rounding, 1800 vs 1830 is surveying variance, 1800 vs 1650 is
  material. Units convert first, so 2400 sq.ft agrees with 223 sq.m.
- Authority is attribute-specific: the survey office determines extent, a tax receipt quotes
  it. Twenty weak witnesses never combine into an authority.
- `test_aggregation_does_not_dilute_a_single_critical_category` — the property the whole risk
  model rests on. A weighted mean would average one critical category away; the noisy-OR must
  not, and a saturated ownership category alone must carry the file past 65.
- `test_state_bands_have_no_gaps` — sweeps every half-point 0–100 and checks the boundaries
  explicitly. An earlier version used inclusive integer ranges and 49.5 fell into no band at
  all.

### `test_scenarios.py` — 25 tests · the corpus lands where ground truth says

Parameterised over all six properties against `data/synthetic/ground_truth.json`: transaction
state, risk band, per-attribute verification status, and every expected contradiction type.

If a scenario stops matching its declaration, this fails *before* the published metrics
quietly change.

Plus the behaviours that only appear in one scenario each:

| Test | Asserts |
|---|---|
| `test_clean_title_treats_history_as_history_not_contradiction` | Two prior owners and a discharged mortgage produce no contradictions; the live encumbrance claim is the released one; the superseded claims are still retained for the graph |
| `test_impersonation_case_escalates_without_accusing_anyone` | ESCALATE, and no risk explanation contains "fraud", "fraudster", "criminal", "impostor", "guilty" or "forger" |
| `test_modified_document_is_rejected_and_forfeits_its_authority` | Both integrity indicators fire; the inflated extent is **not** reconciled away by the survey record |
| `test_owner_declaration_alone_never_verifies` | An owner's "no encumbrance to my knowledge" resolves to OWNER_PROVIDED |
| `test_missing_evidence_is_recorded_not_ignored` | An absent encumbrance certificate is an explicit record, not silence |
| `test_cases_needing_authorised_review_do_not_pretend_to_resolve` | The planner does not manufacture a path to PROCEED where none exists |

### `test_api.py` — 29 tests · the guarantees the UI cannot break

Everything here goes through `TestClient`, because these are properties of the *API*. A
frontend bug must not be able to violate them, and a frontend fix must not be needed to
uphold them.

- **Masking** — a buyer requesting claims directly gets `masked: true`, a starred name, and
  `source_span: null` (the span would leak the value). A verifier gets the full value.
- **Consent** — `IDENTITY_DOCUMENT` is `requestable: false`, is stripped from a request, and
  is *still* withheld when an owner approves everything. Withholding it does not block the
  legitimate part of the request.
- **State enforcement** — `INITIATE_PAYMENT` on a held file is refused with a reason over 40
  characters; the same action on a clean file is permitted.
- **Relay redaction** — a message containing a phone number, an e-mail and a PAN arrives with
  all three removed, flagged, and with a warning returned.
- **Grounding** — four answerable questions must be `GROUNDED` with citations; six
  unanswerable ones must be `REFUSED` or `OUT_OF_SCOPE`, and the refusal must not smuggle the
  file's contents out anyway.
- **Simulation writes nothing** — the stored assessment is byte-identical before and after.

### `test_acceptance.py` — 10 tests · the Review-2 demonstration, asserted

The 13-point sequence from the project brief, executed against real PDFs.

The last test, `test_applying_evidence_reduces_risk_and_releases_the_hold`, ingests four
corrective documents in turn and prints the trace:

```
start: 73.8/HOLD → OBTAIN_BANK_NOC: 56.9/HOLD → OBTAIN_CERTIFIED_SURVEY: 33.3/WARN
     → OBTAIN_CURRENT_EC: 33.3/WARN → RECONCILE_NAME_VARIANT: 22.8/PROCEED
```

It asserts the file reaches PROCEED and that the reduction exceeds 40 points — a cosmetic
drop would pass a weaker assertion.

`test_a_single_document_never_verifies_a_claim_on_its_own` deserves separate mention. It
walks every VERIFIED attribute on the file and asserts that either two or more independent
documents support it, or its single source is the authority of record for that specific
attribute. That is the central research claim, tested directly rather than inferred from a
scenario outcome.

`test_reseed_restores_the_starting_state` runs last and returns the corpus to HOLD, so the
demonstration is repeatable without manual cleanup.

---

## The evaluation harness

`backend/app/eval/run_eval.py` is not part of the test suite — it produces the numbers on the
Research Results page rather than passing or failing.

```bash
npm run eval        # text-layer arm
npm run eval:ocr    # adds the Tesseract arm (~2 minutes)
```

It scores classification, extraction, contradiction precision/recall, verification agreement,
transaction-state accuracy, grounding and resolution outcomes against the ground-truth answer
key, and writes `data/metrics.json`.

**Why the OCR arm matters.** The default path reads a lossless digital text layer, so a
near-perfect figure there measures the field grammar, not the reader. The OCR arm rasterises
every page at 200 dpi and re-reads it through Tesseract using the *same* grammar and the
*same* answer key. The resulting 98.4 % — and the specific failures behind it, such as
`Ilango` read as `llango` — is the figure that actually characterises extraction.

`meta.caveat` in the output states the corpus size, the injected-anomaly count, and that
these figures do not transfer to real registry documents. The UI renders it verbatim above
the numbers.

---

## Coverage gaps, stated plainly

- **No browser tests.** Component behaviour was verified by type-checking, a production
  build, and by driving the API the components call. Click-level interaction — drag-and-drop
  upload, highlight animation, SSE stepping — is unverified by automation.
- **No load or concurrency testing.** Single-user prototype; `reassess()` recomputes a whole
  property on every change, which is correct but not optimised.
- **No adversarial document corpus.** The tampering detection is tested against one
  deliberately modified file. Real forgeries vary in ways this corpus does not sample.
- **No multilingual documents.** The field grammar is English-only. Regional-language deeds
  are Review-3.
- **Synthetic corpus only.** No test uses a real land record, and the figures should not be
  read as transferring to one.
