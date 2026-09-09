"""Property workspace endpoints — the core read surface of the platform."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..domain import (
    CLAIM_TYPE_LABELS,
    CORE_CLAIM_TYPES,
    AssignmentStatus,
    AuditAction,
    ClaimType,
    Role,
    VerificationStatus,
)
from ..models import (
    AuditEvent,
    Claim,
    ClaimSupport,
    Contradiction,
    Document,
    OwnershipEvent,
    Property,
    ResolutionAction,
    RiskAssessment,
    RiskFactor,
    Transaction,
    User,
    VerificationAssignment,
)
from ..serializers import (
    assessment_out,
    audit_out,
    claim_out,
    contradiction_out,
    document_out,
    property_summary,
    resolution_out,
    transaction_out,
)
from ..services import audit, authz, pipeline
from ..services.graph.builder import get_graph_store
from ..services.privacy import consent as consent_service
from ..services.verification import temporal
from .deps import current_role, current_user, get_property, granted_items

router = APIRouter(prefix="/api/properties", tags=["properties"])


@router.get("")
def list_properties(
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    state: str | None = Query(default=None, description="Filter by transaction state"),
    band: str | None = Query(default=None, description="Filter by risk band"),
    district: str | None = None,
    q: str | None = Query(default=None, description="Search reference, survey number or village"),
):
    props = db.scalars(select(Property).order_by(Property.reference)).all()
    out = [property_summary(db, p) for p in props]
    if state:
        out = [p for p in out if p["transaction_state"] == state.upper()]
    if band:
        out = [p for p in out if p["risk_band"] == band.upper()]
    if district:
        out = [p for p in out if p["district"].lower() == district.lower()]
    if q:
        needle = q.lower()
        out = [
            p for p in out
            if needle in p["reference"].lower()
            or needle in p["survey_number"].lower()
            or needle in (p["village"] or "").lower()
            or needle in (p["scenario_label"] or "").lower()
        ]
    return {"count": len(out), "items": out}


@router.get("/{property_id}")
def get_property_detail(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    summary = property_summary(db, prop)
    summary["role_view"] = role.value
    return summary


# ---------------------------------------------------------------------------
@router.get("/{property_id}/documents")
def list_documents(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
):
    docs = db.scalars(
        select(Document).where(Document.property_id == prop.id).order_by(Document.created_at)
    ).all()
    return {"count": len(docs), "items": [document_out(d) for d in docs]}


@router.get("/{property_id}/documents/{document_id}")
def get_document(
    document_id: str,
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    doc = db.get(Document, document_id)
    if doc is None or doc.property_id != prop.id:
        raise HTTPException(404, "Document not found for this property.")
    granted = granted_items(db, prop, role)
    claims = db.scalars(select(Claim).where(Claim.document_id == doc.id)).all()
    supports = db.scalars(
        select(ClaimSupport).where(ClaimSupport.property_id == prop.id)
    ).all()
    by_claim: dict[str, list] = {}
    for s in supports:
        by_claim.setdefault(s.claim_id, []).append(s)
    return {
        "document": document_out(doc, include_pages=True),
        "claims": [claim_out(c, role, granted, doc, by_claim.get(c.id, [])) for c in claims],
    }


# ---------------------------------------------------------------------------
@router.get("/{property_id}/claims")
def list_claims(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    include_superseded: bool = Query(default=False),
    status: str | None = None,
    claim_type: str | None = None,
):
    """
    The Claim–Evidence Matrix.

    Returns both the individual claims and the per-claim-type roll-up, because the
    matrix shows one row per *attribute* with its supporting and conflicting counts,
    while the evidence drawer shows the individual assertions behind that row.
    """
    granted = granted_items(db, prop, role)
    claims = db.scalars(select(Claim).where(Claim.property_id == prop.id)).all()
    docs = {d.id: d for d in db.scalars(
        select(Document).where(Document.property_id == prop.id)).all()}
    supports = db.scalars(
        select(ClaimSupport).where(ClaimSupport.property_id == prop.id)).all()
    contradictions = db.scalars(
        select(Contradiction).where(Contradiction.property_id == prop.id)).all()

    by_claim: dict[str, list] = {}
    for s in supports:
        by_claim.setdefault(s.claim_id, []).append(s)

    ctx = pipeline.build_context(db, prop)
    outcome = ctx.outcome

    visible = [c for c in claims if include_superseded or not c.superseded]
    if status:
        visible = [c for c in visible if c.verification_status == status.upper()]
    if claim_type:
        visible = [c for c in visible if c.claim_type == claim_type]

    items = [
        claim_out(c, role, granted, docs.get(c.document_id), by_claim.get(c.id, []))
        for c in visible
    ]

    matrix = []
    for ct, group in outcome.per_type.items():
        group_claims = [c for c in claims if c.claim_type == ct and not c.superseded]
        if not group_claims and group.status != VerificationStatus.PENDING:
            continue
        primary = max(group_claims, key=lambda c: c.confidence) if group_claims else None
        related_contradictions = [
            contradiction_out(c) for c in contradictions
            if c.claim_type == ct and not c.resolved
        ]
        row = {
            "claim_type": ct,
            "label": CLAIM_TYPE_LABELS.get(ClaimType(ct), ct.replace("_", " ").title())
            if ct in {t.value for t in ClaimType} else ct.replace("_", " ").title(),
            "verification_status": group.status.value,
            "explanation": group.explanation,
            "combined_authority": group.combined_authority,
            "supporting_documents": len(group.supporting_document_ids),
            "conflicting_documents": len(group.conflicting_document_ids),
            "contradictions": related_contradictions,
            "is_core": ct in {t.value for t in CORE_CLAIM_TYPES},
            "history": temporal.history_of(list(claims), list(docs.values()), ct),
            "claim_ids": [c.id for c in group_claims],
        }
        if primary:
            row.update(
                claim_out(primary, role, granted, docs.get(primary.document_id),
                          by_claim.get(primary.id, []))
            )
            row["verification_status"] = group.status.value
            row["explanation"] = group.explanation
        else:
            row.update({
                "id": None, "value": "Not evidenced", "masked": False, "confidence": 0.0,
                "source_page": None, "document_name": None, "document_type": None,
                "source_region": {}, "supporting_count": 0, "conflicting_count": 0,
            })
        matrix.append(row)

    order = {t.value: i for i, t in enumerate(CORE_CLAIM_TYPES)}
    matrix.sort(key=lambda r: (order.get(r["claim_type"], 99), r["label"]))

    return {
        "count": len(items),
        "items": items,
        "matrix": matrix,
        "verification_level": outcome.verification_level(),
        "pending_types": outcome.pending_types,
    }


@router.get("/{property_id}/claims/{claim_id}/evidence")
def claim_evidence(
    claim_id: str,
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    """Everything the evidence drawer shows for one claim."""
    claim = db.get(Claim, claim_id)
    if claim is None or claim.property_id != prop.id:
        raise HTTPException(404, "Claim not found for this property.")
    granted = granted_items(db, prop, role)
    docs = {d.id: d for d in db.scalars(
        select(Document).where(Document.property_id == prop.id)).all()}
    supports = db.scalars(
        select(ClaimSupport).where(ClaimSupport.claim_id == claim.id)).all()
    related_ids = {s.related_claim_id for s in supports}
    related = {c.id: c for c in db.scalars(
        select(Claim).where(Claim.id.in_(related_ids))).all()} if related_ids else {}
    contradictions = db.scalars(
        select(Contradiction).where(
            (Contradiction.left_claim_id == claim.id) | (Contradiction.right_claim_id == claim.id)
        )
    ).all()

    doc = docs.get(claim.document_id)
    page_text = ""
    if doc:
        page = next((p for p in doc.pages if p.page_number == claim.source_page), None)
        page_text = page.text if page else ""

    return {
        "claim": claim_out(claim, role, granted, doc, list(supports)),
        "source": {
            "document": document_out(doc) if doc else None,
            "page": claim.source_page,
            "page_text": page_text,
            "region": claim.source_region or {},
            "span": claim.source_span,
            "ocr_confidence": next(
                (p.ocr_confidence for p in (doc.pages if doc else [])
                 if p.page_number == claim.source_page), None
            ),
        },
        "supporting": [
            {
                **claim_out(related[s.related_claim_id], role, granted,
                            docs.get(related[s.related_claim_id].document_id)),
                "match_type": s.match_type,
                "similarity": s.similarity,
                "note": s.note,
            }
            for s in supports if s.is_supporting and s.related_claim_id in related
        ],
        "conflicting": [
            {
                **claim_out(related[s.related_claim_id], role, granted,
                            docs.get(related[s.related_claim_id].document_id)),
                "match_type": s.match_type,
                "similarity": s.similarity,
                "note": s.note,
            }
            for s in supports if not s.is_supporting and s.related_claim_id in related
        ],
        "contradictions": [contradiction_out(c) for c in contradictions],
    }


# ---------------------------------------------------------------------------
@router.get("/{property_id}/contradictions")
def list_contradictions(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    include_resolved: bool = False,
):
    rows = db.scalars(
        select(Contradiction).where(Contradiction.property_id == prop.id)
    ).all()
    if not include_resolved:
        rows = [c for c in rows if not c.resolved]
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    rows = sorted(rows, key=lambda c: order.get(c.severity, 5))
    return {"count": len(rows), "items": [contradiction_out(c) for c in rows]}


@router.get("/{property_id}/graph")
def ownership_graph(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
):
    docs = db.scalars(select(Document).where(Document.property_id == prop.id)).all()
    claims = db.scalars(select(Claim).where(Claim.property_id == prop.id)).all()
    events = db.scalars(
        select(OwnershipEvent).where(OwnershipEvent.property_id == prop.id)
    ).all()
    contradictions = db.scalars(
        select(Contradiction).where(Contradiction.property_id == prop.id)
    ).all()
    graph = get_graph_store().build(prop, list(docs), list(claims), list(events),
                                    list(contradictions))
    return graph.dict()


@router.get("/{property_id}/risk")
def risk(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    history: bool = Query(default=False, description="Include previous assessments"),
):
    assessments = db.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.property_id == prop.id,
               RiskAssessment.is_simulation == False)  # noqa: E712
        .order_by(RiskAssessment.created_at.desc())
    ).all()
    if not assessments:
        raise HTTPException(404, "No risk assessment has been computed for this property.")
    latest = assessments[0]
    factors = db.scalars(
        select(RiskFactor).where(RiskFactor.assessment_id == latest.id)).all()
    out = assessment_out(latest, list(factors))
    txn = db.scalars(select(Transaction).where(Transaction.property_id == prop.id)).first()
    out["transaction"] = transaction_out(txn)
    if history:
        out["history"] = [
            {
                "id": a.id, "overall_score": round(a.overall_score, 1), "band": a.band,
                "state": a.state, "created_at": a.created_at.isoformat(),
                "category_scores": a.category_scores or {},
            }
            for a in reversed(assessments)
        ]
    return out


@router.get("/{property_id}/resolution")
def resolution_plan(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
):
    actions = db.scalars(
        select(ResolutionAction)
        .where(ResolutionAction.property_id == prop.id)
        .order_by(ResolutionAction.priority)
    ).all()
    latest = db.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.property_id == prop.id,
               RiskAssessment.is_simulation == False)  # noqa: E712
        .order_by(RiskAssessment.created_at.desc())
    ).first()
    steps = [resolution_out(a) for a in actions]
    return {
        "baseline_risk": round(latest.overall_score, 1) if latest else None,
        "baseline_state": latest.state if latest else None,
        "final_risk": steps[-1]["risk_after"] if steps else (
            round(latest.overall_score, 1) if latest else None),
        "final_state": steps[-1]["state_after"] if steps else (latest.state if latest else None),
        "reaches_proceed": bool(steps) and steps[-1]["state_after"] == "PROCEED",
        "count": len(steps),
        "steps": steps,
        "closed_rules": prop.closed_rules or [],
        "note": (
            "Each step's expected risk is computed by re-running the scorer with that "
            "step's rules suppressed — a counterfactual, not a stored estimate."
        ),
    }


@router.get("/{property_id}/audit")
def audit_trail(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    limit: int = Query(default=300, le=2000),
    action: str | None = None,
):
    stmt = select(AuditEvent).where(AuditEvent.property_id == prop.id)
    if action:
        stmt = stmt.where(AuditEvent.action == action.upper())
    events = db.scalars(stmt.order_by(AuditEvent.created_at.desc()).limit(limit)).all()
    return {"count": len(events), "items": [audit_out(e) for e in events]}


@router.get("/{property_id}/profile")
def gated_profile(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    """The evidence-gated property profile as this role may see it."""
    granted = granted_items(db, prop, role)
    claims = db.scalars(select(Claim).where(Claim.property_id == prop.id)).all()
    ctx = pipeline.build_context(db, prop)
    profile = consent_service.build_profile(prop, list(claims), ctx.outcome, role, granted)
    sections = profile.by_section()
    return {
        "property": property_summary(db, prop),
        "role": role.value,
        "verification_level": profile.verification_level,
        "granted_items": profile.granted_items,
        "restricted_items": profile.restricted_items,
        "disclaimer": profile.disclaimer,
        "sections": {
            key: [vars(f) for f in sections.get(key, [])]
            for key in ["verified", "partially_verified", "conflicting", "owner_provided",
                        "pending"]
        },
    }


@router.post("/{property_id}/reassess")
def reassess(
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    authz.require(role, authz.Capability.REASSESS)
    assessment = pipeline.reassess(db, prop, actor_role=role, actor_name=role.value,
                                   reason="Manual reassessment requested")
    factors = db.scalars(
        select(RiskFactor).where(RiskFactor.assessment_id == assessment.id)).all()
    return assessment_out(assessment, list(factors))


class PropertyCreate(BaseModel):
    survey_number: str = Field(min_length=1, max_length=64)
    district: str = Field(min_length=1, max_length=120)
    village: str = Field(min_length=1, max_length=120)
    property_type: str = Field(default="Residential Plot", max_length=120)
    claimed_area_sqft: float = Field(gt=0)
    guideline_value_inr: float = Field(ge=0, default=0)
    asking_price_inr: float = Field(ge=0, default=0)
    listed_owner_name: str = Field(min_length=1, max_length=200)


@router.post("")
def create_property(
    payload: PropertyCreate,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    user: User | None = Depends(current_user),
):
    """
    List a property for sale.

    The listing asserts nothing. `listed_owner_name` is stored as what the *seller
    claims*, deliberately separate from any owner name the documents establish —
    that separation is what lets the platform detect an impersonation later, so a
    new listing starts with every core claim PENDING and a transaction that
    cannot progress until evidence arrives.

    The property is put straight onto a verifier's desk, and the verifier with the
    lightest load takes it. Nobody has to remember to assign it, and a file with
    nobody accountable for it is the failure this avoids.
    """
    authz.require(role, authz.Capability.LIST_PROPERTY)
    if user is None:
        raise HTTPException(400, "No demo user is configured for this role.")

    existing = db.scalars(select(Property).order_by(Property.reference.desc())).first()
    next_number = 1
    if existing and existing.reference.startswith("LTC-PR-"):
        try:
            next_number = int(existing.reference.split("-")[-1]) + 1
        except ValueError:
            next_number = len(db.scalars(select(Property)).all()) + 1

    prop = Property(
        reference=f"LTC-PR-{next_number:04d}",
        survey_number=payload.survey_number,
        district=payload.district,
        village=payload.village,
        property_type=payload.property_type,
        claimed_area_sqft=payload.claimed_area_sqft,
        guideline_value_inr=payload.guideline_value_inr or None,
        asking_price_inr=payload.asking_price_inr or None,
        listed_owner_name=payload.listed_owner_name,
        owner_id=user.id,
        scenario_key="owner_listed",
        scenario_label="Listed by the owner",
        is_demo=False,
    )
    db.add(prop)
    db.flush()

    # Assign to the verifier carrying the fewest properties, so the desk stays even.
    verifiers = db.scalars(
        select(User).where(User.role == Role.VERIFIER.value).order_by(User.name)
    ).all()
    assigned_to = None
    if verifiers:
        loads = {v.id: 0 for v in verifiers}
        for a in db.scalars(select(VerificationAssignment)).all():
            if a.verifier_id in loads:
                loads[a.verifier_id] += 1
        chosen = min(verifiers, key=lambda v: loads[v.id])
        db.add(VerificationAssignment(
            property_id=prop.id,
            verifier_id=chosen.id,
            status=AssignmentStatus.ASSIGNED.value,
            onboarded_by_verifier=False,
        ))
        assigned_to = {"id": chosen.id, "name": chosen.name}

    # Derive the opening position from an empty evidence set, rather than leaving
    # the property without a transaction until somebody uploads something.
    pipeline.reassess(db, prop, actor_role=role, actor_name=user.name,
                      reason="Property listed by the owner")

    audit.record(
        db, AuditAction.DOCUMENT_UPLOADED, property_id=prop.id, actor_role=role,
        actor_name=user.name, result="LISTED",
        summary=f"Property {prop.reference} listed by the owner. "
                f"Nothing is verified until evidence is supplied.",
        payload={"assigned_verifier": assigned_to},
        commit=True,
    )
    return {
        "reference": prop.reference,
        "id": prop.id,
        "assigned_verifier": assigned_to,
        "notice": (
            "The listing is recorded as a claim by the seller, not as fact. Every core "
            "detail starts at PENDING and the transaction cannot progress until documents "
            "support it. Upload evidence from Document Intelligence."
        ),
    }
