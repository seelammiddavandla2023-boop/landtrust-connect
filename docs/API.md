# API reference

FastAPI. Interactive schema at <http://127.0.0.1:8000/docs>, OpenAPI JSON at `/openapi.json`.

All endpoints are under `/api`. The active role travels in the `X-Demo-Role` header
(`OWNER | BUYER | VERIFIER | LEGAL_REVIEWER | ADMIN`, default `BUYER`).

Exact response shapes with worked examples: [`CONTRACTS.md`](CONTRACTS.md).

`{id}` accepts either the internal id or the human reference (`LTC-PR-0002`).

---

## Platform

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Status, version, and which extraction backends are actually usable |
| `GET` | `/api/roles` | The five roles and what each may see |
| `GET` | `/api/dashboard` | Summary cards, recent activity and every chart series |
| `GET` | `/api/audit` | Global audit ledger. `?action=` `?limit=` |

## Properties

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/properties` | List. `?state=` `?band=` `?district=` `?q=` |
| `GET` | `/api/properties/{id}` | Summary: verification level, risk, transaction, counts |
| `GET` | `/api/properties/{id}/documents` | Evidence on file with integrity indicators |
| `GET` | `/api/properties/{id}/documents/{docId}` | One document with page text, geometry and its claims |
| `GET` | `/api/properties/{id}/claims` | **The Claim–Evidence Matrix.** `?status=` `?claim_type=` `?include_superseded=` |
| `GET` | `/api/properties/{id}/claims/{claimId}/evidence` | Everything the evidence drawer shows |
| `GET` | `/api/properties/{id}/contradictions` | `?include_resolved=` |
| `GET` | `/api/properties/{id}/graph` | Temporal ownership graph plus timeline |
| `GET` | `/api/properties/{id}/risk` | Latest assessment with every factor. `?history=true` |
| `GET` | `/api/properties/{id}/resolution` | The minimum-evidence plan |
| `GET` | `/api/properties/{id}/audit` | Per-property ledger. `?action=` `?limit=` |
| `GET` | `/api/properties/{id}/profile` | **Evidence-gated profile, as the calling role may see it** |
| `POST` | `/api/properties/{id}/reassess` | Force a full recomputation |

`/claims` returns both `items` (individual assertions) and `matrix` (one row per attribute,
with supporting/conflicting counts, the resolver's explanation, and the attribute's history
including superseded values).

## Documents

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/documents/modes` | Available extraction backends, pipeline stages, accepted types, size cap |
| `POST` | `/api/documents/upload` | `multipart/form-data`: `property_id`, `file`, optional `mode`. Runs the real pipeline and returns stage telemetry, the document, its claims and the recomputed assessment |
| `GET` | `/api/documents/{id}/file` | The stored PDF, for the viewer |
| `GET` | `/api/documents/{id}/pipeline` | Server-sent events replaying the stored processing stages |

Accepted: `.pdf .png .jpg .jpeg .tif .tiff .txt`, up to 25 MB.

## Consent

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/consent/items` | The disclosure catalogue and each item's policy |
| `GET` | `/api/consent` | Requests. `?property_id=` |
| `POST` | `/api/consent` | `{property_id, items[], purpose}` |
| `POST` | `/api/consent/{id}/decision` | `{approve, items?, time_limited?, note?}` — role must be OWNER |
| `POST` | `/api/consent/{id}/revoke` | Withdraw a granted access |

`IDENTITY_DOCUMENT` is `requestable: false` and is stripped from a request *and* from any
approval. Time-limited grants expire on their own and the expiry is audited.

## Relay

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/messages?property_id=` | Thread for one property |
| `POST` | `/api/messages` | `{property_id, body}` → `{message, warning}` |

The returned `body` is **already redacted**; the raw text never leaves the server. When
`warning` is non-null the message contained contact or identity details.

## Assistant

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/assistant/suggestions` | Suggested questions and the grounding contract |
| `POST` | `/api/assistant/ask` | `{property_id, question}` → `{kind, answer, confidence, intent, evidence[], caveats[], disclaimer}` |
| `GET` | `/api/assistant/log` | Prior exchanges with their kinds. `?property_id=` |

`kind` is `GROUNDED`, `REFUSED` or `OUT_OF_SCOPE`. A refusal is a correct outcome, returned
with HTTP 200 — it is not an error.

## Transaction control

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/transactions` | Every transaction with its state and banner |
| `GET` | `/api/transactions/states` | Thresholds, per-state blocked actions, and the full rule catalogue with weights |
| `POST` | `/api/transactions/{id}/attempt/{ACTION}` | Attempt an action. Blocked ones are **refused by the API** and the refusal is audited |

Actions: `PROCEED_TO_AGREEMENT`, `INITIATE_PAYMENT`, `SHARE_IDENTITY`, `TOKEN_ADVANCE`,
`SITE_VISIT_BOOKING`. No payment is processed anywhere in this codebase.

## Resolution

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/resolution/catalogue` | Every candidate action, what it resolves, who is responsible |
| `POST` | `/api/resolution/simulate` | `{property_id, action_keys[]}` → before/after/delta. **Writes nothing** |
| `POST` | `/api/resolution/apply` | `{property_id, action_key}` → ingests the evidence for real and recomputes |

`/apply` is the acceptance-test call. The returned score is computed from the enlarged
evidence set, not written by the endpoint, which is why it matches `/simulate` exactly.

## Demo and research

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/demo/scenarios` | Each scenario with its injected anomalies, expected vs actual state |
| `POST` | `/api/demo/reset` | Rebuild the database from the synthetic corpus (role ADMIN) |
| `GET` | `/api/demo/presentation` | The 14-step presentation script, bound to real records |
| `GET` | `/api/research/metrics` | `data/metrics.json`. 404 with instructions if the eval has not been run |
| `GET` | `/api/research/gap` | Literature positioning and the novelty wording |
| `GET` | `/api/research/architecture` | The five layers with real module paths and component status |

---

## Conventions

- **Timestamps** are UTC ISO-8601 with a `Z` suffix.
- **Errors** are `{"detail": "..."}` with a message written for a person, not a code.
- **Masking** is applied server-side by role. A masked value is returned already reduced,
  with `mask_reason` explaining why and `unlockable_by` naming the consent item that would
  release it (or `null` when nothing will).
- **CORS** defaults to `*` for local development; set `CORS_ORIGINS` to restrict it.
- **No authentication.** Deliberate for a university prototype — see
  [`ARCHITECTURE.md`](ARCHITECTURE.md#what-is-deliberately-not-built) for what production
  would need. Authorisation, unlike authentication, is real: `backend/tests/test_api.py`
  asserts a buyer cannot retrieve a masked value by any route.
