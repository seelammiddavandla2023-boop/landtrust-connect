# LandTrust Connect

**An AI-Based Evidence-Gated Land Ownership Verification, Secure Owner Interaction and Autonomous Transaction Risk Resolution System**

B.Tech research project · Vellore Institute of Technology · **Review-2 prototype**

[![CI](https://github.com/SathvikMendu/landtrust-connect/actions/workflows/ci.yml/badge.svg)](https://github.com/SathvikMendu/landtrust-connect/actions/workflows/ci.yml)

The badge runs the full suite, the Review-2 acceptance sequence and the evaluation harness
on every push.

> **Research prototype — decision support only.** LandTrust Connect describes agreement
> between the documents uploaded to it. It is not a government land registry, not a
> certification of legal title, not an identity-verification service, and not a payment
> system. Every property, person, survey number and institution in the demonstration
> corpus is synthetic; no real land record is reproduced.

---

## Contents

- [The research problem](#the-research-problem)
- [The research gap](#the-research-gap)
- [What the prototype does](#what-the-prototype-does)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Deployment](#deployment)
- [Demo scenarios](#demo-scenarios)
- [The acceptance demonstration](#the-acceptance-demonstration)
- [Evaluation](#evaluation)
- [Roles](#roles)
- [Technology](#technology)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Review-2 scope](#review-2-scope)
- [Review-3 work](#review-3-work)
- [Responsible-AI commitments](#responsible-ai-commitments)

---

## The research problem

Land transactions involve high-value assets, many stakeholders and large collections of
legal, financial, survey and identity documents. Buyers depend on information supplied by
sellers or brokers; owners must disclose enough to build trust without over-exposing
personal data. Conventional due diligence is fragmented and largely manual, and a document
can look entirely valid on its own while contradicting another in owner name, survey
number, extent, registration date or encumbrance status.

The specific failures this project addresses:

- Fake or duplicate listings posted by someone who is neither the owner nor an authorised
  representative.
- Buyers shown seller-entered claims with no way to know which document supports each field.
- Full deeds and identity documents over-exposing personal information to unknown buyers.
- Owner names, survey numbers, extents and dates differing across documents.
- Encumbrances, mortgages, joint ownership and powers of attorney hidden or incompletely
  disclosed.
- Blockchain preserving data without guaranteeing it was ever correct; AI assistants
  answering beyond the available evidence.
- Static risk reports that describe a problem without stating the minimum action that would
  resolve it, on platforms that do not stop a high-risk payment.

## The research gap

Document extraction, blockchain registries, self-sovereign identity, graph-based valuation,
tampering detection and graph fraud analysis are **individually mature** research areas. The
central unresolved problem is not digitising records.

> Existing systems **rarely combine** claim-level provenance, evidence-gated disclosure,
> consent-based owner interaction, temporal ownership reasoning, dynamic transaction-state
> control and counterfactual minimum-evidence resolution **in one framework**.

That wording is deliberate. No claim is made that any of these capabilities is individually
unprecedented; the contribution is their integration on a single claim store, so that a
disclosure decision and a transaction decision rest on the same evidence.

**The mechanism that carries the contribution:** a claim's verification status is a *derived
property of the evidence set*, computed in one module and nowhere else. The extractor is
structurally forbidden to write it. Appearing in one uploaded document therefore cannot make
a claim look verified — the resolver requires either two independent corroborating documents,
or a single document that is the *authority of record* for that specific attribute.

## What the prototype does

| | |
|---|---|
| **Reads real documents** | Text-layer extraction by default (PyMuPDF); Tesseract OCR for scans, selected automatically when a file has no text layer. Word-level geometry gives every claim a highlightable region. |
| **Extracts claims with provenance** | Each claim carries document, page, character span, page region, confidence and extraction method. A second *layout pass* recovers values by geometry when a file's reading order has been disturbed — which is exactly what editing a PDF after issue does. |
| **Checks document integrity** | Incremental-save count from the PDF byte stream, metadata modification, isolated fonts in the body, declared-vs-actual page counts, validity windows. All computed from the file; all reported as indicators, never as findings of forgery. |
| **Scopes claims in time** | Successive deeds and a discharged mortgage form a chain of title, not a set of contradictions. Superseded assertions are retained for the graph and excluded from current-state comparison. |
| **Detects contradictions** | Type-aware comparison: names tolerate initials but not different people; areas tolerate 2% but not 8%; encumbrance synonyms resolve; survey sub-divisions do not. Plus cross-type checks (listing vs deed, taxpayer vs owner, POA expiry vs registration date) and explicit absence checks. |
| **Derives verification status** | VERIFIED · PARTIALLY VERIFIED · CONFLICTING · PENDING · EXPIRED · OWNER PROVIDED · UNVERIFIED, from evidential authority, corroboration count, match quality, expiry and document integrity. |
| **Builds a temporal ownership graph** | Parties, parcels, deeds, charges and authorisations as nodes; edges carry validity intervals. Rendered as an interactive graph and as a chronological timeline. |
| **Gates disclosure** | Status is decided by evidence; visibility is decided by consent. The two are independent, so a buyer always learns whether a fact is supported even when they may not see its value. Identity documents are refused outright, with or without consent. |
| **Runs a secure relay** | Property-scoped messaging that strips identity numbers, card numbers, phone numbers, e-mail addresses and UPI handles before delivery, and scores the attempt as an interaction risk. |
| **Answers only from evidence** | The assistant retrieves structured claim records, answers from them with citations, and refuses when there is no such record. Questions about neighbouring parcels, valuations, legal advice or contact details are refused by design. |
| **Scores transaction risk** | 31 inspectable rules across 7 categories, saturating per category and combining by noisy-OR so a single critical category is never diluted by benign ones. Every point traces to a rule and the evidence that fired it. |
| **Enforces transaction state** | PROCEED · WARN · HOLD · ESCALATE · REJECT. Blocked actions are refused by the API and the refusal is audited. Categorical failures override the arithmetic and can only make a state stricter. |
| **Plans the minimum evidence path** | A greedy search over counterfactual re-scorings finds the smallest set of documents that would clear the hold, with an exact predicted score for each step. |
| **Audits everything** | Append-only ledger: uploads, OCR runs, claim status changes, contradictions, consent decisions, recalculations, holds, releases and assistant refusals. |

---

## Architecture

```
┌─ INPUT & IDENTITY ────────── owner registration · consent · secure upload · RBAC
│
├─ DOCUMENT INTELLIGENCE ───── classification · text acquisition (text layer / OCR)
│                              layout analysis · claim extraction · quality checks
│
├─ EVIDENCE & REASONING ────── claim store · temporal scoping · contradiction engine
│                              verification resolver · ownership knowledge graph
│
├─ INTERACTION ─────────────── evidence-gated profile · redaction · grounded assistant
│                              consent-based owner relay
│
└─ CONTROL ─────────────────── risk engine · state controller · resolution planner
                               audit ledger
```

Full detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The running app renders the
same architecture, with each component's real module path and status, at `/architecture`.

The layering exists to stop hallucination structurally rather than by instruction:
extraction cannot assert verification, verification cannot assert risk, and the assistant
can only speak from records the reasoning layer produced.

---

## Quick start

**Requirements:** Python 3.11+, Node 18+. Optional: `tesseract-ocr` for the real-OCR path.
No API keys. No external services. Works offline.

```bash
# 1. install
npm install                 # root: the one-command runner
npm run setup               # backend requirements + frontend packages

# 2. generate the synthetic corpus and seed the database
npm run seed

# 3. run both servers together
npm run dev
```

- Frontend — <http://localhost:3000>
- API docs (OpenAPI) — <http://localhost:8000/docs>

<details>
<summary>Running the two services separately</summary>

```bash
# terminal 1 — API
cd backend
pip install -r requirements.txt          # add --break-system-packages on Debian/Ubuntu
python -m app.seed.generate              # render the synthetic PDFs
python -m app.seed.seed --reset          # process them through the real pipeline
uvicorn app.main:app --reload --port 8000

# terminal 2 — UI
cd frontend
npm install
npm run dev
```
</details>

<details>
<summary>Docker</summary>

```bash
docker compose up --build
```
Serves the API on 8000 and the UI on 3000, seeding on first start.
</details>

<details>
<summary>Configuration (all optional)</summary>

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | SQLite at `data/landtrust.db` | Set to `postgresql+psycopg://…` for PostgreSQL |
| `EXTRACTION_MODE` | `DEMO` | `DEMO` (text layer), `OCR` (Tesseract), `LLM` (Review-3) |
| `NEXT_PUBLIC_API_URL` | `http://127.0.0.1:8000` | Backend the Next.js dev proxy targets |
| `LLM_API_KEY` / `LLM_MODEL` | unset | Reserved for Review-3 LLM extraction and answer phrasing |

The prototype is designed to run with none of these set.
</details>

---

## Deployment

Frontend on **Vercel**, API on **Render** as a Docker service. The split is not arbitrary:
the API needs the Tesseract binary and a writable filesystem for uploaded documents, and a
serverless function provides neither.

```bash
# 1. API — Render reads render.yaml from the repository root
#    dashboard.render.com/blueprints → New Blueprint Instance → this repo
#    gives you https://<name>.onrender.com

# 2. Frontend — vercel.com/new → import this repo
#    set NEXT_PUBLIC_API_URL to the Render URL BEFORE the first deploy

# 3. Lock CORS_ORIGINS on Render to the Vercel URL
```

On Render's free tier the service sleeps after 15 minutes idle and the database is rebuilt
from the synthetic corpus on each cold start — which conveniently means the demonstration
always begins in a known state. Open `/api/health` a few minutes before a live review so
the first click is instant.

Full walkthrough, including the alternatives to Render and what to check if the deployed
dashboard comes up empty: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

---

## Demo scenarios

Six properties spanning the risk spectrum. Every anomaly is deliberately injected and
declared in `data/synthetic/ground_truth.json`, which is also the evaluation answer key.

| Ref | Scenario | Injected anomalies | Result |
|---|---|---|---|
| **LTC-PR-0001** | Clean Title | Two prior owners; mortgage created 2023, released 2025 | **17 / PROCEED** |
| **LTC-PR-0002** | Area Conflict + Active Mortgage | 1800 vs 1650 sq.ft; ₹18,00,000 charge; stale EC; name variant; no survey record | **74 / HOLD** |
| **LTC-PR-0003** | Possible Impersonation | Listing party absent from every document; POA expired 31-12-2024; active charge | **90 / ESCALATE** |
| **LTC-PR-0004** | Joint Ownership / Missing EC | Two owners; no encumbrance certificate; owner-declared "no mortgage" | **50 / WARN** |
| **LTC-PR-0005** | Document Modification | Overtyped extent (2000 → 5000); incremental save; isolated font; incomplete certificate | **87 / REJECT** |
| **LTC-PR-0006** | Clean Title — Madurai | None | **17 / PROCEED** |

Three of these are worth opening for what they teach:

- **LTC-PR-0001** proves the system reads history as history. A previous owner and a
  discharged mortgage produce *no* contradictions.
- **LTC-PR-0004** proves the evidence gate applies to honest owners too. The owner's own
  "no encumbrance to my knowledge" is presented as OWNER PROVIDED, not as a clean title.
- **LTC-PR-0005** is the only file that reaches REJECT, and the indicators that put it there
  are computed from the PDF's byte stream and font metrics, not stored as a flag.

**Presentation Mode** (`/presentation`) walks all of this in a 14-step sequence with
presenter notes and direct links to each screen.

---

## The acceptance demonstration

The Review-2 acceptance sequence, runnable in the UI and asserted in the test suite.

Open **LTC-PR-0002** → the sale deed says 1800 sq.ft, the encumbrance certificate says
1650 sq.ft, and an ₹18,00,000 charge is subsisting.

| Step | What you see |
|---|---|
| 1–2 | Both area claims extracted, each bound to its document, page and page region — *Claims* tab, click any row |
| 3 | The 150 sq.ft difference recorded as a HIGH-severity `AREA_DISCREPANCY` |
| 4 | The active encumbrance identified from the certificate |
| 5 | Property Area resolves to **CONFLICTING**; Survey Number stays **VERIFIED**; Owner Name is **PARTIALLY VERIFIED** because of the "Priya S. Sharma" variant |
| 6–7 | Composite risk **73.8 / 100 · HIGH · HOLD** — *Risk Analysis* tab |
| 8 | Every point explained by rule and evidence; *Proceed to agreement* is refused by the API |
| 9 | *Resolution Plan* tab: three steps to PROCEED, each with an exact predicted score |
| 10–13 | Apply them in order — the evidence is ingested through the real pipeline each time |

```
plan:     73.8 HOLD ──▶ 56.9 HOLD ──▶ 33.3 WARN ──▶ 22.8 PROCEED
applied:  73.8 HOLD ──▶ 56.9 HOLD ──▶ 33.3 WARN ──▶ 17.3 PROCEED
                   lender release   certified survey   name affidavit
```

The first two steps land exactly on the prediction. The third lands *better* — 17.3 against a
predicted 22.8 — and the reason is worth stating, because it is a property of the method
rather than an error in it.

A counterfactual simulates an action by suppressing the rules that action would clear. Real
evidence does more than that: the affidavit does not merely stop `OWNER_NAME_VARIANT` firing,
it moves the owner name to VERIFIED, which in turn earns the `VERIFIED_OWNER` and
`ALL_CORE_CLAIMS_VERIFIED` mitigations. Suppression cannot model a mitigation that only exists
once the evidence arrives.

**So the planner's prediction is a guaranteed lower bound on the improvement, never an
overstatement** — the applied score is always at least as good. That direction is the safe one
for a system that decides whether a transaction may proceed, and the test suite asserts it.

**Every step here clears by re-derivation, not by suppression**, and each one clears something
a different way:

- The lender's release supersedes the 2023 charge, so `ACTIVE_MORTGAGE` stops firing because
  the *current* encumbrance position changed.
- The certified survey record is the authority of record for extent and post-dates both
  documents that were quoting it, so the 1800-vs-1650 disagreement is reconciled rather than
  averaged or ignored.
- The notarised affidavit swears that "Priya Sharma" and "Priya S. Sharma" denote the same
  person. That is evidence about *the relationship between the two names* — the thing actually
  in question — so the resolver upgrades the owner name from PARTIALLY VERIFIED to VERIFIED.
  A sworn equivalence is extracted as its own claim type and only a notarised affidavit
  carries authority for it; an owner's unsworn say-so does not.

The test suite asserts this: `test_acceptance.py` reports which factors, if any, were closed
against a document rather than re-derived, and on the current corpus the answer is *none*.

Run it headlessly:

```bash
cd backend && python -m pytest tests/test_acceptance.py -q -s
```

Then `npm run seed` (or the **Reset demo** button in Presentation Mode) to restore the
starting state.

---

## Evaluation

Metrics are **computed**, not written. `backend/app/eval/run_eval.py` scores the running
system against the ground-truth answer key and writes `data/metrics.json`, which the
Research Results page reads. If a number moves, the system's behaviour moved.

```bash
npm run eval          # text-layer arm (fast)
npm run eval:ocr      # adds the Tesseract arm — slower, and the more informative figure
```

Measured on the synthetic corpus (6 properties, 31 documents, 21 injected anomalies):

| Metric | Result |
|---|---|
| Classification accuracy | 100 % |
| Extraction accuracy — text layer | 100 % |
| **Extraction accuracy — Tesseract OCR** | **98.4 %** |
| Contradiction precision / recall / F1 | 100 % / 100 % / 100 % |
| Verification agreement | 100 % |
| Transaction-state accuracy | 100 % |
| Grounded-answer citation rate | 96.7 % |
| Unsupported-answer blocking | 100 % |
| Resolution-outcome accuracy | 100 % |

**Read these honestly.** The corpus is synthetic and the field grammar was written against
documents of this shape, so a near-perfect text-layer figure measures the grammar rather than
the reader. That is why the harness includes an **OCR arm**: it rasterises every page at
200 dpi and re-reads it through Tesseract, introducing real character errors. The 1.6-point
gap between the two arms — and the specific failures it exposes, such as `Ilango` read as
`llango` — is the figure that actually characterises extraction. `meta.caveat` in
`metrics.json` says all of this, and the Research Results page renders it verbatim above the
numbers.

The two sub-100 % figures are also the interesting ones. Unsupported-answer blocking reached
100 % only after a scope guard was added: "Who is the neighbouring plot's owner?" originally
returned *this* property's owner — a fluent answer to a question nobody asked. The failure
and the fix are both in the history.

---

## Roles

Switch role from the top bar. The role is sent as `X-Demo-Role` and **the server decides what
to return** — masking and consent are enforced in the API, so the buyer view is not a
client-side illusion. `backend/tests/test_api.py` asserts a buyer cannot retrieve a masked
value by any route.

| Role | Sees |
|---|---|
| **Buyer** | The evidence-gated profile. Personal values masked until the owner consents; identity documents never. |
| **Land Owner** | Their own file in full, incoming access requests, consent controls, the relay. |
| **Verifier** | Full claims, contradictions and integrity indicators. |
| **Legal Reviewer** | Escalated cases with the full evidence set and audit trail. |
| **Administrator** | Platform operations, demo control, research dashboards. |

No passwords: authentication is deliberately not over-engineered for a university prototype
(and `docs/ARCHITECTURE.md` says what production would need instead). Authorisation is not
simulated.

---

## Technology

**Backend** — Python 3.11 · FastAPI · SQLAlchemy 2 · SQLite (PostgreSQL-ready) · PyMuPDF ·
Tesseract (optional) · ReportLab · pytest

**Frontend** — Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS ·
Framer Motion · Recharts · lucide-react

**Deliberately not used:** no vector database, no graph database and no LLM are *required*.
Neo4j sits behind a `GraphStore` interface with a working SQL implementation; LLM extraction
and answer phrasing sit behind adapters that document exactly what an implementation must
preserve. The prototype runs entirely offline so a review demonstration cannot fail because
of a network or a quota.

---

## Project layout

```
landtrust-connect/
├── backend/
│   ├── app/
│   │   ├── domain.py              canonical vocabulary — the single source of truth
│   │   ├── models.py              16 SQLAlchemy entities, typed columns
│   │   ├── serializers.py         one place decides what each role may see
│   │   ├── api/                   routes: properties, documents, interaction, control, platform
│   │   ├── services/
│   │   │   ├── extractor/         classifier · text layer · OCR · field grammar · quality
│   │   │   ├── verification/      authority · temporal scoping · resolver  ← the evidence gate
│   │   │   ├── contradiction_engine/
│   │   │   ├── risk_engine/       rules · aggregation · state controller
│   │   │   ├── resolution_planner/
│   │   │   ├── evidence_qa/       retriever · answerer · LLM adapter
│   │   │   ├── graph/             ownership graph, Neo4j seam
│   │   │   ├── privacy/           redaction · consent · gated profile
│   │   │   ├── normalization.py   type-aware comparison policy
│   │   │   └── pipeline.py        end-to-end orchestration
│   │   ├── seed/                  synthetic corpus generator + seeder
│   │   └── eval/run_eval.py       the evaluation harness
│   └── tests/                     91 tests
├── frontend/
│   ├── app/                       landing · dashboard · properties · documents · assistant
│   │                              buyer · owner · research · research-gap · architecture
│   │                              presentation
│   ├── components/                ui primitives · workspace tabs · document viewer · relay
│   └── lib/                       api client · domain mirror · formatting
├── data/
│   ├── synthetic/                 generated PDFs + ground_truth.json (the answer key)
│   └── metrics.json               computed evaluation output
└── docs/                          ARCHITECTURE · API · DEMO_GUIDE · TESTING · CONTRACTS
```

---

## Troubleshooting

**`sqlite3.OperationalError: disk I/O error` when seeding.** The project is on a folder
whose filesystem does not implement the file locking SQLite needs — a OneDrive-synced
folder, a mapped network drive, or a Linux VM's view of a Windows directory. Either move
the project to a local path such as `C:\dev\landtrust-connect`, or keep the code where it
is and put only the database elsewhere:

```bash
# PowerShell
$env:DATABASE_URL = "sqlite:///C:/temp/landtrust.db"
# bash
export DATABASE_URL="sqlite:////tmp/landtrust.db"
```

Nothing else needs to change; the schema is identical.

**`npm run dev` says port 3000 or 8000 is already in use.** A previous run is still
holding it. On Windows: `netstat -ano | findstr :3000` then `taskkill /PID <pid> /F`.

**The deployed dashboard is empty but `/api/health` responds.** `NEXT_PUBLIC_API_URL` is
missing on Vercel, or was added after the build. It is inlined at build time, so add it and
**redeploy** — restarting is not enough.

**The hosted API takes ~50 seconds on the first request.** Render's free tier sleeps after
15 minutes idle. Open `/api/health` a few minutes before a live demonstration.

**OCR is unavailable.** Tesseract is optional. Without it the prototype runs in text-layer
mode and `npm run eval:ocr` reports the OCR arm as unavailable, saying so explicitly.
Install it from <https://github.com/UB-Mannheim/tesseract/wiki> on Windows,
`brew install tesseract` on macOS, `apt install tesseract-ocr` on Linux.

---

## Testing

```bash
npm test                                    # all 91 tests
cd backend && python -m pytest tests/test_acceptance.py -q -s   # the Review-2 sequence
```

| Suite | Covers |
|---|---|
| `test_engines.py` | Comparison policy, evidential authority, risk aggregation, band boundaries |
| `test_scenarios.py` | Every property lands on its declared state, status and contradiction set |
| `test_api.py` | Masking, consent, relay redaction, state enforcement, assistant grounding |
| `test_acceptance.py` | The 13-point Review-2 acceptance sequence, end to end |

Some tests assert *research* properties rather than code paths — that a single document never
verifies a claim on its own, that risk explanations never accuse anyone of fraud, that the
band thresholds leave no gap a score could fall into. Details in
[`docs/TESTING.md`](docs/TESTING.md).

---

## Review-2 scope

One mechanism deserves explicit mention because it is the one place the platform stops short
of deriving an outcome: some evidence cannot be verified by re-computation — a registrar's
written confirmation, for instance. Where a resolution step supplies such evidence, the
corresponding risk factor is **closed against that specific document**, recorded with the
document that closed it, and shown as a closure rather than as a derivation (Resolution Plan
tab → "Risk factors closed against evidence"). A closure is refused outright if no document
was supplied. On the current corpus no scenario needs one.

Working: UI · dashboards · document upload · classification · text-layer and OCR extraction ·
structured claims · claim-level provenance · temporal scoping · verification resolution ·
cross-document contradiction detection · ownership graph and timeline · evidence-gated
profile · consent with expiry and revocation · buyer–owner relay with redaction · rule-based
risk engine · transaction-state control · resolution planner · evidence-grounded assistant ·
audit trail · synthetic corpus · computed evaluation dashboard · presentation mode.

**Approximately 70–75 % of the complete research prototype.**

## Review-3 work

Deliberately out of scope, with interfaces in place and nothing faked:

- Government land-registry integration (`/api/research/architecture` marks the seam)
- Aadhaar / eKYC identity verification — the platform never simulates a successful check
- Bank and escrow integration; no payment is processed anywhere in this codebase
- On-chain deployment and anchoring
- ML-based risk calibration — `services/risk_engine/rules.py` is separated from
  `engine.py` precisely so a learned scorer can replace or augment it
- LLM-assisted extraction and answer phrasing — `registry.LLMExtractorAdapter` and
  `evidence_qa/llm_adapter.py` document the contract an implementation must preserve,
  including post-hoc grounding verification
- Neo4j backend — `graph/builder.py` has the interface and a working SQL implementation
- Production authentication, deployment hardening, security certification
- Licensing, IP and patent-oriented disclosure

## Responsible-AI commitments

These are enforced in code and asserted in tests, not merely stated:

1. **Nothing unsupported is ever shown as verified.** The status is computed from evidence in
   one module; the extractor cannot write it.
2. **The word "verified" means "against the uploaded evidence".** The phrase *legally
   verified* appears nowhere in the product.
3. **Integrity findings are indicators, not accusations.** Every explanation describes the
   evidence, not the person. `test_scenarios.py` asserts that no risk explanation contains
   "fraud", "forger", "criminal" or "guilty".
4. **The assistant refuses rather than infers.** No retrieved record, no answer.
5. **Identity documents are never disclosed**, with or without owner consent.
6. **Uncertainty is shown, not hidden** — confidence, authority, supporting and conflicting
   counts are on the face of every claim.
7. **No government verification is simulated.** Where the prototype cannot verify something,
   it says so, and a residual `BASELINE_NO_OFFICIAL_CONFIRMATION` factor keeps even a
   perfectly evidenced file from scoring zero.

---

### Team

S.M Navaneeth (23BCT0164) · S. Sai Anudeep (23BDS0260) · P Sanjay Sharwan
Faculty guide: Anitha E · School of Computer Science and Engineering, VIT
