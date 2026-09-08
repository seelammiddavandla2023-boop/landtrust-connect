# Architecture

How LandTrust Connect is put together, and — more usefully — *why* each boundary is where
it is. Most of these boundaries exist to make a research claim structurally true rather
than merely intended.

---

## The organising principle

> A claim's verification status is a derived property of the evidence set, computed in one
> module and nowhere else.

Everything below follows from that sentence. If the extractor could write a status, a
confident misreading of one document would become a green tick. If the assistant could write
one, a fluent sentence would become a fact. Both are prevented by layering, not by
instruction.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ INPUT & IDENTITY          api/deps.py · routes_documents.py · models.User │
│ owner registration · role-based access · secure upload                    │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    ▼   file bytes
┌──────────────────────────────────────────────────────────────────────────┐
│ DOCUMENT INTELLIGENCE                          services/extractor/         │
│ classifier → text acquisition → layout analysis → field grammar → quality │
│ OUTPUT: claims with provenance and confidence. NO verification status.    │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    ▼   ExtractedClaim[]
┌──────────────────────────────────────────────────────────────────────────┐
│ EVIDENCE & REASONING            services/verification/ · contradiction_…/ │
│ temporal scoping → cross-document comparison → verification resolver      │
│                  → temporal ownership graph                              │
│ OUTPUT: statuses, contradictions, support edges, graph. NO risk score.   │
└───────────────────────────────────┬──────────────────────────────────────┘
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌──────────────────────────────┐  ┌───────────────────────────────────────┐
│ INTERACTION   services/       │  │ CONTROL      services/risk_engine/     │
│   privacy/ · evidence_qa/     │  │              resolution_planner/       │
│ gated profile · redaction ·   │  │ rules → aggregation → state controller │
│ consent · relay · assistant   │  │      → minimum-evidence planner        │
└──────────────────────────────┘  └───────────────────────────────────────┘
                    └───────────────┬───────────────┘
                                    ▼
                        services/audit.py — append-only ledger
```

`services/pipeline.py` orchestrates the whole thing. `reassess()` is the heartbeat: it runs
after every upload, consent decision and applied resolution step, and **recomputes from
scratch** rather than patching. Recomputation is what guarantees that what a buyer sees is
always the current consequence of the current evidence, never a cached verdict.

---

## Document Intelligence

### Text acquisition — two real backends, one grammar

`extractor/registry.py` selects a strategy per call and degrades gracefully:

| Mode | Engine | When |
|---|---|---|
| `DEMO` | PyMuPDF text layer | Default. No OCR engine, no model, no key — but a real read of a real file, with word-level geometry. |
| `OCR` | Tesseract at 200 dpi | Requested explicitly, **or automatically** when the text layer yields nothing (i.e. the file is a scan). Per-word confidences come from Tesseract, so displayed confidences are measured. |
| `LLM` | — | Review-3. Falls back to `DEMO` with a stated reason when unconfigured. |

The same field grammar runs over both, so switching backend changes how well the system
reads, not what it understands. That is what makes the evaluation's OCR arm a meaningful
comparison rather than two unrelated numbers.

### Extraction — two passes, and why the second exists

1. **Flow pass** — a label/value grammar (`field_grammar.py`) over the page's reading order.
   Labels are scoped by document type, which is how "Name:" means *taxpayer* on a tax
   receipt and *purchaser* on a deed.
2. **Layout pass** — for any field whose label is visible but whose value the flow did not
   carry, the value is recovered from word geometry: words on the same baseline, to the
   right of the label, stopping at the next label.

The second pass is not a nicety. A PDF edited after issue typically appends the replacement
value to the end of the content stream, which breaks reading order while leaving the page
visually intact. Without the layout pass the platform would silently fail to read exactly
the documents it most needs to scrutinise. Claims recovered this way are marked
`source_region.recovered_by = "layout"` and carry a 15 % confidence discount, and the UI
surfaces the fact.

### Integrity indicators

All computed from the file, all reported as indicators:

| Code | Computed from |
|---|---|
| `INCREMENTAL_SAVE` | Count of `%%EOF` markers in the byte stream minus one |
| `FONT_DISCONTINUITY` | A font contributing ≤ 40 characters to the whole document while appearing in a page body |
| `METADATA_MODIFIED` | `/ModDate` later than `/CreationDate` |
| `MISSING_PAGE` | "Page m of n" declaration vs actual page count |
| `EXPIRED_DOCUMENT` | Declared validity window against the current date |
| `LOW_TEXT_QUALITY` | Mean acquisition confidence below 75 % |

The font check keys on the font **name across the whole document** rather than per page or
per name+size. That is what stops it firing on headers, footers and signature lines, which
reuse the document's own fonts — an earlier per-page version produced a false positive on
every two-page document.

---

## Evidence & Reasoning

### Temporal scoping — the step that makes history legible

`verification/temporal.py`. A land file records *successive* states, not simultaneous
assertions. A 2017 deed naming one purchaser and a 2021 deed naming another are a chain of
title. A 2023 mortgage deed and a 2026 certificate reporting "nil" are a discharged charge.

For each attribute, the succession table names the document types that supersede one another
(deeds for ownership; EC / mortgage / NOC for encumbrance; receipts for tax). The claim from
the most recent effective date wins; the rest are flagged `superseded` — retained for the
graph and the history view, excluded from current-state comparison.

Without this, every property with a past would look fraudulent.

### Document-scoped attributes

A certificate's own number and date are facts about *the document*, not about the parcel.
`domain.INSTRUMENT_SCOPE` routes them to `Document.reference_number` and
`Document.instrument_date` instead of the claim store. Without it, a sale deed's registration
date and a mortgage deed's registration date look like two answers to one question and the
engine reports a conflict between values that were never describing the same thing.

### Comparison policy

`services/normalization.py` holds all of it, one strategy per value kind:

| Kind | Agrees when | Conflicts when |
|---|---|---|
| Person name | Identical after removing titles/case/punctuation; or one form abbreviates a component to an initial | Different given names — even sharing a surname, which is scored as a *weaker* mismatch but still a mismatch |
| Identifier | Equal after separator/case normalisation | Different sub-division of the same parent survey (HIGH), or a different parent (CRITICAL) |
| Area | Within 0.5 % (rounding), or 2 % (surveying variance) | Beyond 2 % — 1800 vs 1650 is 8.3 % |
| Money | Within 0.1 %, after parsing lakh/crore notation | Beyond 5 % |
| Date | Same day, or within a month (registration vs execution) | Beyond a month |
| Categorical | Synonyms resolve: nil = none = clear; active = subsisting | Different status |

Units are converted before comparison, so 2400 sq.ft and 223 sq.m agree.

### Contradiction detection

`contradiction_engine/engine.py`, three families:

1. **Intra-type pairwise** — every pair of claims of the same type from *different*
   documents. Agreements become `ClaimSupport` edges, disagreements become `Contradiction`
   rows. Both directions are stored, because the matrix needs "3 supporting / 1 conflicting",
   not a boolean.
2. **Cross-type semantic** — facts that only contradict when read together: the listing name
   against the evidenced owner, taxpayer against owner, POA expiry against the registration
   it purports to authorise, declared encumbrance against certified encumbrance.
3. **Absence** — expected documents and core claim types that are missing. Silence is not
   safety; a missing encumbrance certificate is recorded so it can carry weight and appear in
   the plan.

**Authority reconciliation.** Where the authority of record for an attribute has spoken, a
disagreement between documents that merely *quote* that attribute is reconciled rather than
recorded as a contradiction. This holds whether or not the authoritative document is one of
the two being compared: once the survey office has certified an extent, a deed and a
certificate that disagree about it were both quoting, and the office has now measured.

Two guards keep it from becoming a way to explain problems away: the authoritative document
must **post-date** every document it settles, and no document involved may carry a HIGH
integrity indicator. The second guard is why the tampered deed in LTC-PR-0005 is *not*
harmonised away by its survey record.

### Verification resolution — the evidence gate

`verification/resolver.py`, in precedence order:

| # | Status | Condition |
|---|---|---|
| 1 | `CONFLICTING` | Another document materially disagrees |
| 2 | `EXPIRED` | Every supporting document's validity has lapsed |
| 3 | `OWNER_PROVIDED` | The only source is the owner's own declaration |
| 4 | `VERIFIED` | **(a)** ≥ 2 independent documents agree by exact or normalised match with combined authority ≥ 0.90, **or (b)** a single document that is the authority of record for that attribute, unexpired, adequate quality, and carrying no HIGH integrity indicator |
| 5 | `PARTIALLY_VERIFIED` | Corroborated only approximately (initials, tolerance bands), or supported by exactly one non-authoritative source, or extraction confidence below 55 % |
| 6 | `PENDING` | Expected but no evidence at all |
| 7 | `UNVERIFIED` | Anything else |

**Rule 5's single-source case is the research contribution made operational.** Appearing in
one uploaded document leaves a claim `PARTIALLY_VERIFIED` however confident the extraction
was. `test_acceptance.py::test_a_single_document_never_verifies_a_claim_on_its_own` asserts
this across the whole corpus.

**Impeachment.** A document carrying a HIGH integrity indicator is removed from the set of
usable witnesses entirely — not merely barred from verifying alone. Corroboration means two
sources independently attesting to the same fact, and a file that may have been altered
attests to whatever the alteration says; counting it as the second of two witnesses would let
a single edit manufacture the corroboration the evidence gate exists to require. Where such a
document is the *only* source, the claim resolves to PARTIALLY_VERIFIED with a note that a
certified copy from the issuing authority is required.

**Sworn name equivalence.** A name variant across documents cannot be closed by asserting that
one form is correct — both documents already say what they say. What closes it is evidence
about the *relationship between the two names*, which is exactly what a notarised
name-discrepancy affidavit provides. That relationship is extracted as its own claim type
(`NAME_EQUIVALENCE`), and only a document that is the authority of record for it — a sworn
affidavit, not an owner's declaration — carries weight. Where a sworn equivalence covers every
differing pair in a group, the agreement is treated as exact in substance and the claim may
reach VERIFIED.

**Evidential authority** (`verification/authority.py`) is per (document type, claim type):
the survey office determines extent (1.00) while a tax receipt merely quotes it (0.60); the
encumbrance certificate determines encumbrances (1.00) while a deed's recital that the
property is "free from all encumbrances" is the vendor's warranty, not a search (0.75, and
the prose extractor refuses to read it as a finding at all). Independent authorities combine
by noisy-OR, so two 0.8 witnesses are stronger than one but twenty 0.2 witnesses never become
an authority.

### Ownership graph

`graph/builder.py` behind a `GraphStore` interface. `SqlGraphStore` materialises nodes and
edges from the event ledger; `Neo4jGraphStore` is the documented Review-3 seam with an
identical signature. The graph is **temporal**: every edge carries `valid_from` and, where
known, `valid_to`, which is what lets the platform distinguish a discharged mortgage from a
subsisting one.

Layout in the UI is deterministic rather than force-directed — a chain of title has a natural
reading order, and a force simulation would rearrange it on every load, which is the last
thing you want when the same diagram must be explained twice in a review.

---

## Control

### Risk aggregation

`risk_engine/rules.py` holds 31 inspectable rules; `engine.py` holds the arithmetic. They are
separate files so a learned scorer can replace or augment the rules without touching
aggregation.

```
category_sum   = Σ rule weights in that category      (mitigations negative)
category_score = 100 · (1 − e^(−max(0, sum) / 40))
overall        = 100 · (1 − Π_c (1 − influence_c · category_score_c / 100))
```

Two deliberate choices:

- **Saturating inner form.** The first serious problem in a category moves the score a lot;
  the fifth moves it little. Real risk does not accumulate linearly.
- **Noisy-OR outer form.** Risks combine as independent chances of the transaction being
  unsafe. A plain weighted mean would let six benign categories average away one critical
  one — precisely the failure that produces a "medium risk" score for a property with an
  expired power of attorney. `test_engines.py::test_aggregation_does_not_dilute_a_single_critical_category`
  asserts the property directly.

Both forms are monotone in every rule weight, which is what makes the resolution planner's
counterfactuals exact rather than approximate.

Category influence: ownership 0.75 · encumbrance 0.62 · survey 0.55 · document 0.55 ·
interaction 0.35 · valuation 0.30 · payment 0.30.

**Residual risk.** `BASELINE_NO_OFFICIAL_CONFIRMATION` (+18, document) applies to every
property. Verification here is against supplied documents, not the government register; a
perfectly evidenced file therefore scores about 17, not 0. Stating that as a scored factor is
more honest than presenting a fully-evidenced file as risk-free.

### Transaction state

Thresholds are half-open so no score falls between bands:
`[0,25) PROCEED · [25,50) WARN · [50,75) HOLD · [75,100] ESCALATE`.

`REJECT` has no band of its own: it is reachable only through the categorical overrides below,
never by score alone. A file is refused because of *what* the evidence shows, not because of
how much of it there is.

**Categorical overrides** run after the arithmetic and can only make a state *stricter*:

| Trigger | Forced state |
|---|---|
| `UNVERIFIED_SELLER_AUTHORITY` | ESCALATE |
| `EXPIRED_POA` + `OWNER_CONTRADICTION` | ESCALATE |
| `SUSPICIOUS_EDIT` + `OWNER_CONTRADICTION` | REJECT |
| `OWNER_CONTRADICTION` | HOLD |
| `ACTIVE_MORTGAGE` | HOLD |

Some failures are categorical rather than quantitative: if the system cannot establish that
the seller may sell, no arithmetic should let the transaction proceed.

Blocked actions are refused **by the API** (`POST /api/transactions/{id}/attempt/{action}`)
and the refusal is audited. The UI's disabled button is a courtesy, not the control.

### Resolution planning

`resolution_planner/planner.py`. Each candidate action declares which rules it would
neutralise and which mitigations it would grant. Because aggregation is monotone in every
weight, an action's effect is evaluated *exactly* by re-running the scorer with those rules
suppressed — a genuine counterfactual.

A greedy search then takes, at each step, the action with the best
`(risk_reduction + 12 · state_improvement) / effort_cost`, until the state reaches PROCEED or
nothing improves. Greedy is appropriate because the aggregation is submodular in practice
(each additional fix helps less), and it keeps the plan explainable: every step shows the
score it moves from and to.

**Predictions are a lower bound, not an equality.** Suppressing an action's rules models what
that action *removes*. It cannot model what the evidence additionally *earns* — a certified
name equivalence moves the owner to VERIFIED, which unlocks mitigations that did not exist
before the document arrived. The applied score is therefore always at least as good as the
prediction, never worse. For a system that decides whether a transaction may proceed, erring
toward under-promising is the correct direction, and `test_acceptance.py` asserts it.

Not every case should reach PROCEED. Where ownership itself is contradicted, a plan that
stops short and refers the case to a legal reviewer is the correct answer; the evaluation
harness scores those cases separately using the corpus's `expected_resolvable` flag.

---

## Interaction

### The two independent gates

| Gate | Decided by | Answers |
|---|---|---|
| **Evidence gate** | The verification resolver | *Is this fact supported?* |
| **Consent gate** | The owner, per item, optionally time-limited | *May this person see its value?* |

They are independent by design. A buyer looking at a masked owner name still learns that the
name is `PARTIALLY_VERIFIED` and why — the status travels even when the value does not.

`privacy/redaction.py` reduces each attribute in the way that attribute needs: names to
initials, identity numbers to their last four characters, phones to their last four digits,
addresses to their locality. `domain.NEVER_DISCLOSED` holds items refused regardless of
consent — currently identity documents, which are stripped even from a blanket approval.

### The relay

Property-scoped messaging. Outbound text is scanned for identity numbers, PAN, card numbers,
phone numbers, e-mail addresses, bank accounts, UPI handles and off-platform contact
suggestions; matches are replaced before delivery, the raw body never leaves the server, and
the attempt is scored as an interaction risk. Moving a negotiation off the audited channel
removes the protections the platform provides, so it is treated as a risk signal rather than
silently allowed.

### The evidence assistant

`evidence_qa/` — retrieval over **structured records**, not free text. That is what makes
grounding checkable: an answer either cites claim records that exist in the database, or
there is nothing to answer from.

The contract:

1. Retrieval happens first and is never delegated to a model.
2. If retrieval is empty, the answer is a refusal. No exceptions.
3. Citations are computed from retrieved records **before** any generation.
4. Questions outside what a land-evidence file can answer — legal advice, price forecasts,
   contact details, requests to certify title, and **anything about a different parcel** —
   are refused with a reason rather than answered evasively.

That last clause was added after evaluation. "Who is the neighbouring plot's owner?" contains
every keyword that routes to the owner handler, and the assistant returned *this* property's
owner: a fluent answer to a question nobody asked. A subject-scope check now runs before
intent routing, and the refusal rate went from 75 % to 100 %.

`llm_adapter.py` documents how a model may be introduced without losing the guarantee: it may
only rephrase content already present in the retrieved records, the citation set is fixed
before generation, and `verify()` checks every number and proper noun in the output against
the retrieved corpus, falling back to the deterministic answer on any violation.

---

## Data model

Sixteen entities with typed columns. JSON is used only where the payload is genuinely
heterogeneous — OCR regions, layout blocks, rule parameters, evidence references.

```
User ──< Property ──< Document ──< DocumentPage
                 │            └──< Claim ──< ClaimSupport (claim ↔ related claim)
                 ├──< Contradiction
                 ├──< OwnershipEvent
                 ├──< ConsentRequest
                 ├──< Message
                 ├──< ResolutionAction
                 ├──< AuditEvent
                 ├──< AssistantQuery
                 └──< Transaction ──< RiskAssessment ──< RiskFactor
```

Notable columns:

- `Claim.verification_status` — written **only** by `verification/resolver.apply()`.
- `Claim.superseded` — written only by `verification/temporal.apply_supersession()`.
- `Claim.source_region` — `{x, y, w, h}` normalised 0–1, driving the UI highlight.
- `Document.integrity_flags` — computed indicators, never a stored verdict.
- `Property.closed_rules` — rules closed against evidence the platform cannot verify by
  re-computation (a registrar's written confirmation, say). A closure is only permitted when a
  document was actually ingested to cite, or for actions completed entirely in-platform; each
  entry names the action and that document, so a closure is never anonymous. Closure is
  evaluated *after* a full recomputation, so a factor the new evidence genuinely clears is
  never closed administratively instead. No scenario in the corpus requires one.
- `RiskFactor` — one row per triggered rule, so any score is fully reconstructable.

Storage: SQLite by default, PostgreSQL by setting `DATABASE_URL`. No schema change required.

---

## What is deliberately not built

| Area | Status | Where the seam is |
|---|---|---|
| Government registry integration | Review-3 | No endpoint simulates a successful official check |
| Aadhaar / eKYC | Review-3 | Identity documents are never disclosed; no verification is faked |
| Bank / escrow / payment | Review-3 | `attempt/{action}` demonstrates the block; nothing moves money |
| Blockchain anchoring | Review-3 | The audit ledger is the natural anchor point |
| ML risk calibration | Review-3 | `rules.py` separate from `engine.py` |
| LLM extraction and phrasing | Review-3 | `registry.LLMExtractorAdapter`, `evidence_qa/llm_adapter.py` |
| Neo4j | Review-3 | `graph/builder.GraphStore` |
| Production authentication | Out of scope | `api/deps.py` — role via header. *Authentication* is thin by design; *authorisation* is enforced: masking, consent and the privileged-action check on `/resolution/apply` all run server-side |

Production authentication would need session or token auth with rotation, per-property ACLs
rather than global roles, and audit of every read as well as every write. The prototype
implements the *authorisation* model faithfully and leaves *authentication* deliberately
thin, because the research question is about what may be disclosed, not about how a password
is checked.
