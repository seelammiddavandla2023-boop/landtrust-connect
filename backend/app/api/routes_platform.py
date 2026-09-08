"""Dashboard, demo control, research results, research gap and architecture."""
from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..domain import (
    DISCLAIMER,
    RISK_CATEGORY_LABELS,
    AuditAction,
    ConsentStatus,
    Role,
    TransactionState,
    VerificationStatus,
)
from ..models import (
    AssistantQuery,
    AuditEvent,
    ConsentRequest,
    Contradiction,
    Document,
    Property,
    RiskAssessment,
    Transaction,
)
from ..models import Claim as ClaimModel
from ..serializers import audit_out, property_summary
from ..services import audit
from .deps import current_role

router = APIRouter(prefix="/api", tags=["platform"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    props = list(db.scalars(select(Property).order_by(Property.reference)).all())
    summaries = [property_summary(db, p) for p in props]
    documents = list(db.scalars(select(Document)).all())
    claims = [c for c in db.scalars(select(ClaimModel)).all() if not c.superseded]
    contradictions = [c for c in db.scalars(select(Contradiction)).all() if not c.resolved]
    consents = list(db.scalars(select(ConsentRequest)).all())
    recent_audit = list(db.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(12)).all())

    state_counts = Counter(s["transaction_state"] for s in summaries if s["transaction_state"])
    band_counts = Counter(s["risk_band"] for s in summaries if s["risk_band"])
    doc_type_counts = Counter(d.doc_type for d in documents)

    status_counts: Counter = Counter()
    for c in claims:
        status_counts[c.verification_status] += 1

    contradiction_type_counts = Counter(c.contradiction_type for c in contradictions)
    severity_counts = Counter(c.severity for c in contradictions)

    verified_props = [
        s for s in summaries
        if s["transaction_state"] in {TransactionState.PROCEED.value}
        and s["verification_level"] >= 0.8
    ]
    high_risk = [s for s in summaries if s["risk_band"] in {"HIGH", "CRITICAL"}]
    pending_requests = [c for c in consents if c.status == ConsentStatus.REQUESTED.value]

    return {
        "cards": {
            "properties_under_review": len([s for s in summaries
                                            if s["transaction_state"] != "PROCEED"]),
            "verified_properties": len(verified_props),
            "documents_processed": len(documents),
            "claims_extracted": len(claims),
            "contradictions_found": len(contradictions),
            "high_risk_transactions": len(high_risk),
            "pending_owner_requests": len(pending_requests),
            "total_properties": len(summaries),
        },
        "recent_properties": summaries[:6],
        "recent_activity": [audit_out(e) for e in recent_audit],
        "charts": {
            "risk_distribution": [
                {"band": b, "count": band_counts.get(b, 0)}
                for b in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
            ],
            "transaction_states": [
                {"state": s.value, "count": state_counts.get(s.value, 0)}
                for s in TransactionState
            ],
            "verification_status": [
                {"status": s.value, "count": status_counts.get(s.value, 0)}
                for s in VerificationStatus
            ],
            "document_types": [
                {"doc_type": k, "count": v}
                for k, v in sorted(doc_type_counts.items(), key=lambda kv: -kv[1])
            ],
            "contradiction_types": [
                {"type": k, "count": v}
                for k, v in sorted(contradiction_type_counts.items(), key=lambda kv: -kv[1])
            ],
            "contradiction_severity": [
                {"severity": s, "count": severity_counts.get(s, 0)}
                for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
            ],
            "risk_by_property": [
                {"reference": s["reference"], "label": s["scenario_label"],
                 "score": s["risk_score"], "band": s["risk_band"],
                 "state": s["transaction_state"]}
                for s in summaries
            ],
            "processing_performance": [
                {"filename": d.filename, "doc_type": d.doc_type, "ms": d.processing_ms,
                 "pages": d.page_count}
                for d in sorted(documents, key=lambda x: -x.processing_ms)[:12]
            ],
        },
        "disclaimer": DISCLAIMER,
    }


# ---------------------------------------------------------------------------
@router.get("/demo/scenarios")
def scenarios(db: Session = Depends(get_db)):
    gt_path = settings.synthetic_dir / "ground_truth.json"
    ground_truth = json.loads(gt_path.read_text("utf-8")) if gt_path.exists() else {
        "properties": []}
    by_ref = {p["reference"]: p for p in ground_truth.get("properties", [])}
    props = list(db.scalars(select(Property).order_by(Property.reference)).all())
    items = []
    for p in props:
        gt = by_ref.get(p.reference, {})
        summary = property_summary(db, p)
        items.append({
            "key": p.scenario_key,
            "label": p.scenario_label,
            "property_id": p.id,
            "reference": p.reference,
            "summary": gt.get("summary", ""),
            "demo_note": gt.get("demo_note", ""),
            "injected_anomalies": gt.get("injected_anomalies", []),
            "expected_state": gt.get("expected_transaction_state"),
            "actual_state": summary["transaction_state"],
            "expected_band": gt.get("expected_risk_band"),
            "actual_band": summary["risk_band"],
            "matches_expectation": (
                gt.get("expected_transaction_state") == summary["transaction_state"]
            ),
            "risk_score": summary["risk_score"],
            "document_count": summary["document_count"],
        })
    return {"count": len(items), "items": items}


@router.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db), role: Role = Depends(current_role)):
    """Rebuild the demo database from the synthetic corpus."""
    from ..seed.seed import run

    db.close()
    result = run(reset=True)
    return {
        "status": "reset",
        "seeded": result,
        "note": "Database rebuilt and every property re-processed through the live pipeline.",
    }


@router.get("/demo/presentation")
def presentation_script(db: Session = Depends(get_db)):
    """
    The Review-2 presentation sequence, bound to real records.

    Each step names the screen to open and the property to open it on, so the
    demonstration follows the argument rather than the menu structure.
    """
    props = {p.scenario_key: p for p in db.scalars(select(Property)).all()}
    clean = props.get("clean_title")
    conflict = props.get("area_conflict_active_mortgage")
    impersonation = props.get("possible_impersonation")
    modified = props.get("document_modification")

    def ref(p):
        return {"property_id": p.id, "reference": p.reference,
                "label": p.scenario_label} if p else None

    steps = [
        {"n": 1, "title": "The problem", "route": "/research-gap",
         "property": None,
         "say": "Existing work solves extraction, registries, identity, valuation and fraud "
                "detection separately. None of them decides whether a land detail may be "
                "*shown* as verified, or stops a transaction while it cannot be."},
        {"n": 2, "title": "Upload evidence", "route": "/documents", "property": ref(conflict),
         "say": "A real file goes through classification, text acquisition, layout analysis and "
                "claim extraction. Watch the stage telemetry — those are measured durations."},
        {"n": 3, "title": "Claim provenance", "route": "/properties/{id}?tab=claims",
         "property": ref(conflict),
         "say": "Every claim carries its document, page, confidence and the region of the page "
                "it came from. Open the evidence drawer on any row."},
        {"n": 4, "title": "Contradiction detection", "route": "/properties/{id}?tab=claims",
         "property": ref(conflict),
         "say": "1800 sq.ft in the deed against 1650 in the encumbrance certificate. The area "
                "row is CONFLICTING — not an average, not the higher number, not silence."},
        {"n": 5, "title": "The evidence gate", "route": "/properties/{id}?tab=claims",
         "property": ref(clean),
         "say": "Compare with the clean file. Note the owner name here is VERIFIED because three "
                "independent documents agree; a single document would leave it PARTIALLY "
                "VERIFIED however confident the extraction was."},
        {"n": 6, "title": "Temporal ownership graph", "route": "/properties/{id}?tab=graph",
         "property": ref(clean),
         "say": "Two prior owners and a mortgage that was created in 2023 and released in 2025. "
                "The system reads that as history, not as a contradiction."},
        {"n": 7, "title": "Evidence-gated profile", "route": "/buyer/{id}",
         "property": ref(conflict),
         "say": "The buyer's view. Verified facts, partially verified facts and owner-provided "
                "text sit in visibly different sections, and the owner's name is masked until "
                "consent is granted."},
        {"n": 8, "title": "Risk and transaction hold",
         "route": "/properties/{id}?tab=risk", "property": ref(conflict),
         "say": "73/100, HIGH, HOLD. Every point traces to a rule with an explanation, and the "
                "'Proceed to agreement' action is disabled."},
        {"n": 9, "title": "Minimum-evidence resolution",
         "route": "/properties/{id}?tab=resolution", "property": ref(conflict),
         "say": "Three steps to PROCEED, each with the risk it removes — computed by re-running "
                "the scorer with that step's rules suppressed."},
        {"n": 10, "title": "Apply the evidence",
         "route": "/properties/{id}?tab=resolution", "property": ref(conflict),
         "say": "Apply them one at a time. The lender's release, then the certified survey, then "
                "the name affidavit. The score falls because the evidence changed."},
        {"n": 11, "title": "Impersonation case", "route": "/properties/{id}?tab=overview",
         "property": ref(impersonation),
         "say": "The listing party is not in any document and the power of attorney expired in "
                "2024. The system escalates and says why — carefully: unverified authority, not "
                "an accusation."},
        {"n": 12, "title": "Document modification", "route": "/properties/{id}?tab=documents",
         "property": ref(modified),
         "say": "An incremental save and an isolated font in the body. Both computed from the "
                "PDF itself. State: REJECT."},
        {"n": 13, "title": "Grounded assistant", "route": "/assistant",
         "property": ref(conflict),
         "say": "Ask it something the file cannot answer. It refuses rather than inventing — "
                "and every answer it does give cites document and page."},
        {"n": 14, "title": "Measured results", "route": "/research", "property": None,
         "say": "These figures are computed by an evaluation script against a ground-truth "
                "answer key, not typed into the page."},
    ]
    return {"steps": steps, "disclaimer": DISCLAIMER}


# ---------------------------------------------------------------------------
@router.get("/research/metrics")
def research_metrics():
    """Evaluation results, computed by app/eval/run_eval.py."""
    if not settings.metrics_path.exists():
        raise HTTPException(
            404,
            "No metrics file found. Run `python -m app.eval.run_eval` to compute results "
            "against the synthetic corpus.",
        )
    return json.loads(settings.metrics_path.read_text("utf-8"))


@router.get("/research/gap")
def research_gap():
    """
    The literature positioning from the Review-1 proposal.

    Novelty is phrased as the proposal phrases it: these capabilities are individually
    mature and are *rarely combined* in one framework. No claim is made that nobody has
    attempted any of them.
    """
    return {
        "statement": (
            "Document extraction, blockchain registries, self-sovereign identity, graph-based "
            "valuation, tampering detection and graph fraud analysis are individually mature "
            "research areas. The unresolved problem is not digitising records. It is an "
            "integrated, claim-level mechanism that determines whether a land detail may be "
            "shown as verified, controls who may view the supporting evidence, reasons about "
            "ownership across time, updates transaction risk as the case evolves, and generates "
            "the smallest corrective evidence path required to proceed safely."
        ),
        "novelty_wording": (
            "Existing systems rarely combine claim-level provenance, evidence-gated disclosure, "
            "consent-based owner interaction, temporal ownership reasoning, dynamic "
            "transaction-state control and counterfactual minimum-evidence resolution in one "
            "framework."
        ),
        "rows": [
            {
                "area": "Document extraction (OCR / LLM)",
                "representative_works": "RealKIE; KIE from business documents; LLM extraction "
                                        "from real-estate transactions [2, 3, 16, 17]",
                "existing_capability": "High-accuracy key-information extraction from "
                                       "semi-structured documents.",
                "limitation": "Extraction only. No cross-document ownership proof and no "
                              "control over what the extracted value is allowed to imply.",
                "contribution": "Extraction is separated from verification. A claim carries "
                                "provenance and confidence; its status is derived afterwards "
                                "from the whole evidence set.",
                "implemented_in": ["Document Intelligence", "Claim–Evidence Matrix"],
            },
            {
                "area": "Identity and blockchain registries",
                "representative_works": "SSI transfer verification; land-registry and "
                                        "smart-contract systems [4, 6, 7, 8, 9, 10, 11]",
                "existing_capability": "Tamper-evident preservation and automation of registry "
                                       "records and transfers.",
                "limitation": "Preserves or automates records but cannot validate incorrect "
                              "initial evidence — a wrong fact recorded immutably stays wrong.",
                "contribution": "Correctness at intake: consistency is tested across independent "
                                "documents before any status is asserted, and unsupported detail "
                                "is never presented as verified.",
                "implemented_in": ["Verification Resolver", "Contradiction Engine"],
            },
            {
                "area": "Property graphs and valuation",
                "representative_works": "Graph valuation; MugRep; neighbour-relation and "
                                        "geo-spatial embedding [12, 13, 14, 15]",
                "existing_capability": "Graph learning over property relationships for price "
                                       "estimation.",
                "limitation": "Optimises price, not title, authorisation or document "
                              "consistency.",
                "contribution": "The graph is temporal and evidential: nodes are parties, "
                                "instruments and charges, edges carry validity intervals, and "
                                "every edge cites the document that supports it.",
                "implemented_in": ["Temporal Ownership Graph", "Timeline"],
            },
            {
                "area": "Forgery and fraud detection",
                "representative_works": "Tampered-text detection; programmatic forgery rules; "
                                        "graph fraud detection [18, 19, 20, 21, 22]",
                "existing_capability": "Detection of manipulated content and anomalous "
                                       "transaction patterns.",
                "limitation": "Detects manipulation or fraud but does not connect it to land "
                              "ownership consequences or to what should happen next.",
                "contribution": "Integrity indicators feed the same risk ledger as evidence "
                                "gaps, drive the transaction state, and are answered by a "
                                "specific corrective action rather than a warning.",
                "implemented_in": ["Quality Checks", "Risk Engine", "Resolution Planner"],
            },
            {
                "area": "Evidence-grounded AI and privacy",
                "representative_works": "PaperTrail; PAGE-RAG; document anonymisation "
                                        "[23, 24, 25]",
                "existing_capability": "Claim–evidence interfaces for grounded QA and automated "
                                       "redaction of documents.",
                "limitation": "Grounding and privacy are not tied to land claims, owner consent "
                              "or transaction state.",
                "contribution": "Grounding, consent and transaction control are one mechanism: "
                                "the assistant answers only from claim records, disclosure is "
                                "gated on both evidence status and owner consent, and both are "
                                "audited.",
                "implemented_in": ["Evidence Assistant", "Consent Layer", "Secure Relay"],
            },
        ],
        "combination": [
            {"pillar": "Claim provenance",
             "detail": "Every displayed value resolves to a document, a page and a region."},
            {"pillar": "Evidence-gated disclosure",
             "detail": "Status is decided by evidence; visibility is decided by consent; the two "
                       "are independent."},
            {"pillar": "Temporal ownership reasoning",
             "detail": "Successive instruments form a chain rather than a contradiction."},
            {"pillar": "Owner consent",
             "detail": "Time-limited, itemised, revocable, and refused outright for identity "
                       "documents."},
            {"pillar": "Dynamic transaction state",
             "detail": "Risk recomputes on every evidence change and can block progression."},
            {"pillar": "Minimum-evidence resolution",
             "detail": "A counterfactual search for the smallest set of documents that reaches "
                       "PROCEED."},
        ],
        "disclaimer": DISCLAIMER,
    }


@router.get("/research/architecture")
def architecture():
    """The five-layer architecture from the proposal, mapped to real modules."""
    return {
        "layers": [
            {
                "key": "INPUT_IDENTITY",
                "name": "Input & Identity Layer",
                "purpose": "Owner registration, consent and secure document upload.",
                "components": [
                    {"name": "Owner Registration", "module": "api/deps.py, models.User",
                     "status": "PROTOTYPE"},
                    {"name": "Secure Upload", "module": "api/routes_documents.py",
                     "status": "WORKING"},
                    {"name": "Role-Based Access", "module": "api/deps.py",
                     "status": "WORKING"},
                    {"name": "eKYC / Aadhaar Verification", "module": "—",
                     "status": "REVIEW_3"},
                ],
            },
            {
                "key": "DOCUMENT_INTELLIGENCE",
                "name": "Document Intelligence Layer",
                "purpose": "Classification, text acquisition, layout analysis, field extraction "
                           "and integrity indicators.",
                "components": [
                    {"name": "Classification",
                     "module": "services/extractor/classifier.py", "status": "WORKING"},
                    {"name": "Text Acquisition (text layer / OCR)",
                     "module": "services/extractor/{text_layer,ocr}.py", "status": "WORKING"},
                    {"name": "Layout Analysis",
                     "module": "services/extractor/service.py", "status": "WORKING"},
                    {"name": "Claim Extraction",
                     "module": "services/extractor/field_grammar.py", "status": "WORKING"},
                    {"name": "Quality & Tamper Checks",
                     "module": "services/extractor/quality.py", "status": "WORKING"},
                    {"name": "LLM-Assisted Extraction",
                     "module": "services/extractor/registry.py", "status": "REVIEW_3"},
                ],
            },
            {
                "key": "EVIDENCE_REASONING",
                "name": "Evidence & Reasoning Layer",
                "purpose": "Claim store, temporal scoping, cross-document consistency and the "
                           "ownership graph.",
                "components": [
                    {"name": "Claim Store", "module": "models.Claim, models.ClaimSupport",
                     "status": "WORKING"},
                    {"name": "Temporal Scoping",
                     "module": "services/verification/temporal.py", "status": "WORKING"},
                    {"name": "Contradiction Engine",
                     "module": "services/contradiction_engine/engine.py", "status": "WORKING"},
                    {"name": "Verification Resolver",
                     "module": "services/verification/resolver.py", "status": "WORKING"},
                    {"name": "Ownership Knowledge Graph",
                     "module": "services/graph/builder.py", "status": "WORKING"},
                    {"name": "Neo4j Backend", "module": "services/graph/builder.py",
                     "status": "REVIEW_3"},
                ],
            },
            {
                "key": "INTERACTION",
                "name": "Interaction Layer",
                "purpose": "Evidence-gated profile, grounded assistant and consent-based relay.",
                "components": [
                    {"name": "Evidence-Gated Profile",
                     "module": "services/privacy/consent.py", "status": "WORKING"},
                    {"name": "Redaction & Masking",
                     "module": "services/privacy/redaction.py", "status": "WORKING"},
                    {"name": "Evidence Assistant",
                     "module": "services/evidence_qa/answerer.py", "status": "WORKING"},
                    {"name": "Secure Owner Relay",
                     "module": "api/routes_interaction.py", "status": "WORKING"},
                ],
            },
            {
                "key": "CONTROL",
                "name": "Control Layer",
                "purpose": "Risk scoring, state enforcement, resolution planning and audit.",
                "components": [
                    {"name": "Risk Engine (rules)",
                     "module": "services/risk_engine/rules.py", "status": "WORKING"},
                    {"name": "Risk Aggregation",
                     "module": "services/risk_engine/engine.py", "status": "WORKING"},
                    {"name": "Transaction State Controller",
                     "module": "services/risk_engine/engine.py", "status": "WORKING"},
                    {"name": "Resolution Planner",
                     "module": "services/resolution_planner/planner.py", "status": "WORKING"},
                    {"name": "Audit Ledger", "module": "services/audit.py",
                     "status": "WORKING"},
                    {"name": "ML Risk Calibration", "module": "—", "status": "REVIEW_3"},
                    {"name": "Escrow / Payment Integration", "module": "—",
                     "status": "REVIEW_3"},
                ],
            },
        ],
        "flow": [
            "Upload Evidence", "Extract Claims", "Verify Evidence", "Build Ownership Graph",
            "Create Verified Profile", "Assess Transaction Risk", "Resolve Issues",
            "Proceed or Hold",
        ],
        "out_of_scope": [
            "Government land-registry integration",
            "Aadhaar / eKYC identity verification",
            "Bank and escrow integration",
            "On-chain deployment",
            "Production legal verification and certification",
            "Commercial licensing and IP workflow",
        ],
        "disclaimer": DISCLAIMER,
    }


@router.get("/audit")
def global_audit(db: Session = Depends(get_db), limit: int = 200, action: str | None = None):
    stmt = select(AuditEvent)
    if action:
        stmt = stmt.where(AuditEvent.action == action.upper())
    rows = db.scalars(stmt.order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    props = {p.id: p for p in db.scalars(select(Property)).all()}
    return {
        "count": len(rows),
        "actions": [a.value for a in AuditAction],
        "items": [
            {**audit_out(e),
             "property_reference": props[e.property_id].reference
             if e.property_id in props else None}
            for e in rows
        ],
    }
