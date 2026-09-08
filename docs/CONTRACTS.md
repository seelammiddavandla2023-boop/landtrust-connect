# Frontend ⇄ Backend contracts

The backend (`backend/app/domain.py`) is the single source of truth for every
enumerated value. `frontend/lib/domain.ts` mirrors it for presentation only.

All requests go to same-origin `/api/...`; `next.config.mjs` proxies them to FastAPI.
The active role travels in the `X-Demo-Role` header (`OWNER | BUYER | VERIFIER |
LEGAL_REVIEWER | ADMIN`) — `lib/api.ts` attaches it automatically.

Interactive schema: <http://127.0.0.1:8000/docs>

---

## Enumerations

| Enum | Values |
| --- | --- |
| `VerificationStatus` | `VERIFIED`, `PARTIALLY_VERIFIED`, `CONFLICTING`, `PENDING`, `EXPIRED`, `OWNER_PROVIDED`, `UNVERIFIED` |
| `TransactionState` | `PROCEED`, `WARN`, `HOLD`, `ESCALATE`, `REJECT` |
| `RiskBand` | `LOW`, `MODERATE`, `HIGH`, `CRITICAL` |
| `Severity` | `INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `RiskCategory` | `OWNERSHIP`, `DOCUMENT`, `ENCUMBRANCE`, `SURVEY`, `VALUATION`, `PAYMENT`, `INTERACTION` |
| `DocumentType` | `SALE_DEED`, `ENCUMBRANCE_CERTIFICATE`, `SURVEY_RECORD`, `TAX_RECEIPT`, `IDENTITY_PROOF`, `POWER_OF_ATTORNEY`, `MORTGAGE_DOCUMENT`, `BANK_NOC`, `OWNER_DECLARATION`, `UNKNOWN` |
| `ConsentStatus` | `REQUESTED`, `APPROVED`, `APPROVED_TIME_LIMITED`, `DENIED`, `EXPIRED`, `REVOKED` |
| `AnswerKind` | `GROUNDED`, `REFUSED`, `OUT_OF_SCOPE` |

Score → state thresholds are half-open: `[0,25) PROCEED`, `[25,50) WARN`,
`[50,75) HOLD`, `[75,100] ESCALATE`. `REJECT` and forced `ESCALATE` come from
categorical overrides, which can only make a state stricter.

---

## Response shapes

### `GET /api/dashboard`
```jsonc
{
  "cards": { "properties_under_review": 4, "verified_properties": 2,
             "documents_processed": 31, "claims_extracted": 188,
             "contradictions_found": 12, "high_risk_transactions": 3,
             "pending_owner_requests": 3, "total_properties": 6 },
  "recent_properties": [PropertySummary],
  "recent_activity": [AuditEvent],
  "charts": {
    "risk_distribution":       [{ "band": "LOW", "count": 2 }],
    "transaction_states":      [{ "state": "PROCEED", "count": 2 }],
    "verification_status":     [{ "status": "VERIFIED", "count": 40 }],
    "document_types":          [{ "doc_type": "SALE_DEED", "count": 7 }],
    "contradiction_types":     [{ "type": "AREA_DISCREPANCY", "count": 2 }],
    "contradiction_severity":  [{ "severity": "HIGH", "count": 5 }],
    "risk_by_property":        [{ "reference": "LTC-PR-0002", "label": "...",
                                  "score": 73.8, "band": "HIGH", "state": "HOLD" }],
    "processing_performance":  [{ "filename": "...", "doc_type": "...",
                                  "ms": 41, "pages": 2 }]
  },
  "disclaimer": "..."
}
```

### `PropertySummary` — `GET /api/properties`, `GET /api/properties/{id}`
```jsonc
{
  "id": "…", "reference": "LTC-PR-0002", "survey_number": "82/4B",
  "district": "Chengalpattu", "village": "Thiruporur", "state": "Tamil Nadu",
  "property_type": "Residential Plot", "claimed_area_sqft": 1800,
  "guideline_value_inr": 6200000, "asking_price_inr": 6800000,
  "listed_owner_name": "Priya Sharma",
  "scenario_key": "area_conflict_active_mortgage",
  "scenario_label": "Area Conflict + Active Mortgage",
  "owner": { "id": "…", "name": "…", "role": "OWNER", "phone": "…",
             "identity_number": "XXXX XXXX 7734" },
  "document_count": 5, "claim_count": 34, "contradiction_count": 4,
  "critical_contradictions": 2, "verification_level": 0.62,
  "verification_counts": { "VERIFIED": 6, "CONFLICTING": 1 },
  "risk_score": 73.8, "risk_band": "HIGH", "transaction_state": "HOLD",
  "transaction": { "id": "…", "reference": "TXN-0002", "state": "HOLD",
                   "state_reason": "…", "state_changed_at": "…",
                   "stage": "DUE_DILIGENCE", "consideration_inr": 6800000,
                   "blocked_actions": ["INITIATE_PAYMENT", "PROCEED_TO_AGREEMENT",
                                       "SHARE_IDENTITY"] },
  "closed_rules": [], "updated_at": "…"
}
```
`GET /api/properties` wraps this as `{ count, items: [...] }` and accepts
`?state=`, `?band=`, `?district=`, `?q=`.

### `GET /api/properties/{id}/claims`
```jsonc
{
  "count": 34,
  "items": [Claim],            // individual assertions
  "matrix": [MatrixRow],       // one row per attribute — the Claim–Evidence Matrix
  "verification_level": 0.62,
  "pending_types": ["mortgage_status"]
}
```

`Claim`:
```jsonc
{
  "id": "…", "document_id": "…", "document_name": "Sale_Deed_2022.pdf",
  "document_type": "SALE_DEED", "claim_type": "property_area",
  "label": "Property Area", "value": "1800 sq.ft",
  "masked": false, "mask_reason": "", "unlockable_by": null,
  "normalized_value": "1800 sq.ft", "numeric_value": 1800,
  "source_page": 2, "source_span": "…Extent / Area: 1800 sq.ft…",
  "source_region": { "x": 0.09, "y": 0.31, "w": 0.14, "h": 0.02,
                     "label": "Extent / Area", "recovered_by": "layout" },
  "confidence": 0.95, "extraction_method": "DEMO",
  "verification_status": "CONFLICTING", "status_explanation": "…",
  "sensitivity": "PUBLIC", "is_owner_declared": false, "superseded": false,
  "supporting_count": 1, "conflicting_count": 1,
  "supporting_claim_ids": ["…"], "conflicting_claim_ids": ["…"],
  "created_at": "…"
}
```

`MatrixRow` is a `Claim` (of the highest-confidence assertion for that attribute)
**plus**:
```jsonc
{
  "claim_type": "property_area", "label": "Property Area",
  "verification_status": "CONFLICTING", "explanation": "…",
  "combined_authority": 0.96, "supporting_documents": 2,
  "conflicting_documents": 1, "contradictions": [Contradiction],
  "is_core": true, "claim_ids": ["…"],
  "history": [{ "claim_id": "…", "value": "1800 sq.ft", "document": "…",
                "document_type": "SALE_DEED", "effective_date": "2022-03-22",
                "page": 2, "superseded": false, "confidence": 0.95 }]
}
```
Rows with `"id": null` are `PENDING` attributes with no evidence at all — render
them, they are the point.

### `GET /api/properties/{id}/claims/{claimId}/evidence`
```jsonc
{
  "claim": Claim,
  "source": { "document": Document, "page": 2, "page_text": "…full page text…",
              "region": { "x": …, "y": …, "w": …, "h": … },
              "span": "…", "ocr_confidence": 1.0 },
  "supporting":   [Claim & { match_type, similarity, note }],
  "conflicting":  [Claim & { match_type, similarity, note }],
  "contradictions": [Contradiction]
}
```
`match_type` ∈ `EXACT_MATCH | NORMALIZED_MATCH | PARTIAL_MATCH | MISMATCH | MISSING | EXPIRED`.

### `Document` — `GET /api/properties/{id}/documents`
```jsonc
{
  "id": "…", "filename": "Sale_Deed_2022.pdf", "doc_type": "SALE_DEED",
  "doc_type_label": "Sale Deed", "classification_confidence": 0.99,
  "classification_signals": { "SALE_DEED:\\bsale\\s+deed\\b": 7.5 },
  "status": "PROCESSED", "extraction_mode": "DEMO",
  "ocr_engine": "pymupdf-textlayer", "page_count": 2, "size_bytes": 4312,
  "processing_ms": 41, "reference_number": "DOC-2022-11934",
  "instrument_date": "2022-03-22T00:00:00", "issued_on": "…", "valid_until": null,
  "is_expired": false,
  "integrity_flags": [{ "code": "FONT_DISCONTINUITY", "label": "…",
                        "detail": "…", "severity": "HIGH", "page": 1 }],
  "quality_score": 1.0, "uploaded_by_role": "OWNER", "created_at": "…",
  "checksum": "3f2a…"
}
```
`GET /api/properties/{id}/documents/{docId}` returns
`{ document: Document & { pages: [{ page_number, ocr_confidence, width, height,
text, layout_blocks }] }, claims: [Claim] }`.

The rendered PDF is at `GET /api/documents/{docId}/file`
(`endpoints.documentFileUrl(id)`) — safe in an `<iframe>` or `<object>`.

### `Contradiction`
```jsonc
{
  "id": "…", "contradiction_type": "AREA_DISCREPANCY", "claim_type": "property_area",
  "claim_label": "Property Area", "severity": "HIGH",
  "left_claim_id": "…", "right_claim_id": "…",
  "left_value": "1800 sq.ft", "right_value": "1650 sq.ft",
  "left_source": "Sale_Deed_2022.pdf p2", "right_source": "Encumbrance…pdf p1",
  "difference": "150 sq.ft (8.3%)", "magnitude": 150.0,
  "explanation": "…", "detection_rule": "PAIRWISE::property_area",
  "resolved": false, "resolved_note": "", "created_at": "…"
}
```
`contradiction_type` ∈ `OWNER_IDENTITY | SURVEY_IDENTITY | AREA_DISCREPANCY |
DATE_CHRONOLOGY | ENCUMBRANCE_DISCLOSURE | AUTHORIZATION_EXPIRY |
DOCUMENT_INTEGRITY | TAXPAYER_MISMATCH | MISSING_EVIDENCE`.

### `GET /api/properties/{id}/graph`
```jsonc
{
  "nodes": [{ "id": "person::ravi_kumar", "type": "PERSON", "label": "Ravi Kumar",
              "sublabel": "Person", "date": null, "status": "NEUTRAL",
              "evidence": [{ "document_id": "…", "filename": "…", "page": 2 }],
              "meta": {} }],
  "edges": [{ "id": "e::…", "source": "…", "target": "…", "type": "TRANSFERRED_TO",
              "label": "transferred 2021", "valid_from": "2021-06-15",
              "valid_to": null, "status": "NEUTRAL", "evidence": [...] }],
  "timeline": [{ "date": "2021-06-15", "year": 2021,
                 "title": "Sale deed registered", "description": "…",
                 "event_type": "SALE_DEED_REGISTERED", "status": "NEUTRAL",
                 "evidence": [...] }],
  "current_owner": "Ravi Kumar", "chain_complete": true, "chain_note": ""
}
```
Node `type` ∈ `PERSON | PROPERTY | DEED | MORTGAGE | POWER_OF_ATTORNEY |
TAX_RECORD | TRANSACTION | SURVEY_RECORD`.
Node/edge `status` ∈ `VERIFIED | CONFLICTING | EXPIRED | CURRENT | NEUTRAL`.
Edge `type` ∈ `OWNS | OWNED | TRANSFERRED_TO | AUTHORIZED | MORTGAGED_TO |
SUPPORTED_BY | CONTRADICTS | RECORDED_IN | RELEASED`.

### `GET /api/properties/{id}/risk`
```jsonc
{
  "id": "…", "overall_score": 73.8, "band": "HIGH", "state": "HOLD",
  "state_reason": "…", "engine_version": "rules-1.0", "created_at": "…",
  "category_scores": { "OWNERSHIP": 18.1, "DOCUMENT": 36.2, "ENCUMBRANCE": 63.2,
                       "SURVEY": 64.3, "VALUATION": 0.0, "PAYMENT": 11.8,
                       "INTERACTION": 0.0 },
  "category_labels": { "OWNERSHIP": "Ownership Risk", … },
  "factors": [{ "rule_id": "ACTIVE_MORTGAGE", "category": "ENCUMBRANCE",
                "category_label": "Encumbrance Risk", "weight": 30.0,
                "severity": "HIGH", "title": "Active encumbrance on the property",
                "explanation": "…",
                "evidence_refs": [{ "kind": "claim", "id": "…", "label": "…",
                                    "page": 2, "document_id": "…" }],
                "is_mitigation": false }],
  "transaction": Transaction
}
```
Add `?history=true` for `history: [{ overall_score, band, state, created_at,
category_scores }]` oldest-first — use it for the risk-over-time chart.
Mitigations have `weight < 0` and `is_mitigation: true`; render them separately.

### `GET /api/properties/{id}/resolution`
```jsonc
{
  "baseline_risk": 73.8, "baseline_state": "HOLD",
  "final_risk": 22.8, "final_state": "PROCEED", "reaches_proceed": true,
  "count": 3,
  "steps": [{ "id": "…", "action_key": "OBTAIN_BANK_NOC",
              "title": "Obtain lender no-objection / mortgage release",
              "description": "…",
              "required_evidence": "Bank NOC or registered release of mortgage",
              "responsible_party": "LENDER",
              "authority_required": "Charge holder (lending institution)…",
              "effort": "MEDIUM", "priority": 1,
              "resolves_rules": ["ACTIVE_MORTGAGE"],
              "risk_before": 73.8, "risk_after": 56.9, "risk_delta": 16.9,
              "state_after": "HOLD", "status": "RECOMMENDED", "applied_at": null }],
  "closed_rules": [], "note": "…"
}
```

- `POST /api/resolution/simulate` `{ property_id, action_keys[] }` →
  `{ before, after, delta, resolved_rules[], actions[] }`. Writes nothing.
- `POST /api/resolution/apply` `{ property_id, action_key }` →
  `{ action, document, before, after, delta, assessment, remaining_steps, closed_rules }`.
  Ingests the evidence for real and recomputes. **This is the acceptance-test call.**
- `GET /api/resolution/catalogue` → every candidate action.

### `GET /api/properties/{id}/profile` (evidence-gated profile)
```jsonc
{
  "property": PropertySummary, "role": "BUYER", "verification_level": 0.62,
  "granted_items": ["LATEST_EC"],
  "restricted_items": [{ "item": "IDENTITY_DOCUMENT", "label": "Identity document",
                         "policy": "Never disclosed…", "requestable": false }],
  "disclaimer": "…",
  "sections": {
    "verified":           [ProfileField],
    "partially_verified": [ProfileField],
    "conflicting":        [ProfileField],
    "owner_provided":     [ProfileField],
    "pending":            [ProfileField]
  }
}
```
`ProfileField`: `{ claim_type, label, value, raw_available, masked, mask_reason,
verification_status, explanation, sensitivity, section, supporting_documents,
conflicting_documents, unlockable_by }`.

Render the five sections **visually distinctly**. A masked value comes back already
masked (`"P**** S*****"`); never attempt to unmask client-side.

### Consent
- `GET /api/consent/items` → `{ items: [{ item, label, requestable, policy }], time_limited_hours: 24 }`
- `GET /api/consent?property_id=…` → `{ count, items: [ConsentRequest] }`
- `POST /api/consent` `{ property_id, items[], purpose }`
- `POST /api/consent/{id}/decision` `{ approve, items?, time_limited?, note? }` (role must be OWNER)
- `POST /api/consent/{id}/revoke`

`ConsentRequest`: `{ id, property_id, requester: {name,…}, items: [{item,label}],
granted_items, denied_items, purpose, status, decision_note, created_at,
decided_at, expires_at }`.

`IDENTITY_DOCUMENT` has `requestable: false` and is stripped even from an approval —
show that as a deliberate policy, not an omission.

### Relay
- `GET /api/messages?property_id=…` → `{ count, items: [Message], notice }`
- `POST /api/messages` `{ property_id, body }` → `{ message, warning }`

`Message`: `{ id, sender_role, sender_name, body, contained_sensitive,
sensitive_kinds: ["PHONE"], references_claim_id, created_at }`.
`body` is **already redacted** — the raw text never leaves the server. When
`warning` is non-null, surface it.

### Assistant
- `GET /api/assistant/suggestions` → `{ questions[], contract }`
- `POST /api/assistant/ask` `{ property_id, question }` →
```jsonc
{
  "kind": "GROUNDED",            // or REFUSED / OUT_OF_SCOPE
  "answer": "…",                  // may contain "\n" and "• " bullets
  "confidence": 0.94, "intent": "CONFLICT_WHY",
  "evidence": [{ "kind": "claim", "document_id": "…",
                 "document_name": "Sale_Deed_2022.pdf", "page": 2,
                 "confidence": 0.95, "excerpt": "…", "claim_id": "…",
                 "verification_status": "CONFLICTING" }],
  "caveats": ["…"], "backend": "deterministic-grounded", "disclaimer": "…"
}
```
A `REFUSED` answer is a **feature**. Render it as a deliberate, confident refusal —
not as an error state.

### Transactions
- `GET /api/transactions` → `{ count, items: [Transaction & { property_reference, scenario_label, banner }] }`
- `GET /api/transactions/states` → `{ thresholds[], states[], rules[], note }`
- `POST /api/transactions/{property_id}/attempt/{ACTION}` →
  `{ allowed, state, action, reason, banner?, note }`.
  Use `PROCEED_TO_AGREEMENT` / `INITIATE_PAYMENT` for the blocked-action demo.

### Documents
- `GET /api/documents/modes` → `{ modes: { DEMO|OCR|LLM: { engine, available, description } },
  pipeline_stages[], supported_categories[], accepted_extensions[], max_bytes }`
- `POST /api/documents/upload` — `FormData` with `property_id`, `file`, optional `mode` →
  `{ document, claims[], stages: [{ stage, status, detail, duration_ms }], assessment }`
- `GET /api/documents/{id}/pipeline` — SSE replay, one `data:` frame per stage.

### Research
- `GET /api/research/metrics` → `data/metrics.json` (404 with a helpful message if
  the eval has not been run). Keys: `headline`, `classification`, `extraction`,
  `contradiction`, `verification`, `transaction_state`, `grounding`, `resolution`,
  `performance`, `ocr_arm?`, `meta`.
- `GET /api/research/gap` → `{ statement, novelty_wording, rows[], combination[], disclaimer }`
- `GET /api/research/architecture` → `{ layers[], flow[], out_of_scope[], disclaimer }`.
  Component `status` ∈ `WORKING | PROTOTYPE | REVIEW_3`.

### Demo
- `GET /api/demo/scenarios` → `{ count, items: [{ key, label, property_id, reference,
  summary, demo_note, injected_anomalies[], expected_state, actual_state,
  expected_band, actual_band, matches_expectation, risk_score, document_count }] }`
- `POST /api/demo/reset` (role ADMIN) — rebuilds the database. Confirm first.
- `GET /api/demo/presentation` → `{ steps: [{ n, title, route, property, say }], disclaimer }`
  `route` may contain `{id}`; substitute `step.property.property_id`.

### Audit
`GET /api/properties/{id}/audit` and `GET /api/audit` →
`{ count, actions?, items: [{ id, actor_role, actor_name, action, result, summary,
evidence_refs[], payload, created_at, property_reference? }] }`.

---

## UI rules that are not negotiable

1. **Never present an unverified value as verified.** A `PARTIALLY_VERIFIED` or
   `OWNER_PROVIDED` field must be visually distinct from a `VERIFIED` one at a
   glance, without reading the label.
2. **Never unmask.** If `masked: true`, show the masked string and the reason.
3. **Refusals are successes.** An assistant refusal is the designed behaviour.
4. **Say "evidence-supported", never "legally verified".** Follow the wording the
   API returns; do not paraphrase a status into a stronger claim.
5. Every number a user can question should be traceable in one click to the
   document, page and rule that produced it.
