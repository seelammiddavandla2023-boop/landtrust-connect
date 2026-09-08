"""
Response shaping.

One place decides what each role is allowed to see, so no route can accidentally
leak a value that the consent layer masked.  Every serialiser that touches a claim
goes through `privacy.redaction.disclose`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .domain import (
    CLAIM_TYPE_LABELS,
    DOCUMENT_TYPE_LABELS,
    RISK_CATEGORY_LABELS,
    ClaimType,
    DocumentType,
    Role,
    Sensitivity,
    VerificationStatus,
    sensitivity_of,
)
from .models import (
    AuditEvent,
    Claim,
    ClaimSupport,
    ConsentRequest,
    Contradiction,
    Document,
    Message,
    Property,
    ResolutionAction,
    RiskAssessment,
    RiskFactor,
    Transaction,
    User,
)
from .services.privacy.redaction import disclose, mask_identity, mask_name, mask_phone


def iso(value: Any) -> str | None:
    """
    Serialise as an unambiguous UTC instant.

    Stored timestamps are naive UTC. Emitting them without a marker makes every
    browser read them as local time, which silently shifts every "expires in…"
    countdown and audit timestamp by the viewer's offset.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def label_for_claim(claim_type: str) -> str:
    try:
        return CLAIM_TYPE_LABELS[ClaimType(claim_type)]
    except (ValueError, KeyError):
        return claim_type.replace("_", " ").title()


def label_for_doc(doc_type: str) -> str:
    try:
        return DOCUMENT_TYPE_LABELS[DocumentType(doc_type)]
    except (ValueError, KeyError):
        return doc_type.replace("_", " ").title()


# ---------------------------------------------------------------------------
def user_out(user: User | None, viewer: Role = Role.ADMIN) -> dict | None:
    if user is None:
        return None
    full = viewer in {Role.OWNER, Role.ADMIN, Role.VERIFIER, Role.LEGAL_REVIEWER}
    return {
        "id": user.id,
        "name": user.name if full else mask_name(user.name),
        "email": user.email if full else None,
        "role": user.role,
        "organisation": user.organisation,
        "phone": (mask_phone(user.phone) if user.phone else None) if not full else user.phone,
        "identity_number": mask_identity(user.identity_number or "") if user.identity_number
        else None,
    }


def document_out(doc: Document, include_pages: bool = False) -> dict:
    out = {
        "id": doc.id,
        "property_id": doc.property_id,
        "filename": doc.filename,
        "doc_type": doc.doc_type,
        "doc_type_label": label_for_doc(doc.doc_type),
        "classification_confidence": round(doc.classification_confidence, 4),
        "classification_signals": doc.classification_signals or {},
        "status": doc.status,
        "extraction_mode": doc.extraction_mode,
        "ocr_engine": doc.ocr_engine,
        "page_count": doc.page_count,
        "size_bytes": doc.size_bytes,
        "processing_ms": doc.processing_ms,
        "reference_number": doc.reference_number,
        "instrument_date": iso(doc.instrument_date),
        "issued_on": iso(doc.issued_on),
        "valid_until": iso(doc.valid_until),
        "is_expired": doc.is_expired,
        "integrity_flags": doc.integrity_flags or [],
        "quality_score": round(doc.quality_score, 3),
        "uploaded_by_role": doc.uploaded_by_role,
        "created_at": iso(doc.created_at),
        "checksum": (doc.checksum or "")[:16],
        "claim_count": len(doc.claims),
    }
    if include_pages:
        out["pages"] = [
            {
                "page_number": p.page_number,
                "ocr_confidence": round(p.ocr_confidence, 4),
                "width": p.width,
                "height": p.height,
                "text": p.text,
                "layout_blocks": p.layout_blocks or [],
            }
            for p in sorted(doc.pages, key=lambda x: x.page_number)
        ]
    return out


def claim_out(
    claim: Claim,
    viewer: Role,
    granted: set[str],
    doc: Document | None = None,
    supports: list[ClaimSupport] | None = None,
    group=None,
) -> dict:
    d = disclose(claim.claim_type, claim.value, viewer, granted)
    supporting = [s for s in (supports or []) if s.is_supporting]
    conflicting = [s for s in (supports or []) if not s.is_supporting]
    return {
        "id": claim.id,
        "property_id": claim.property_id,
        "document_id": claim.document_id,
        "document_name": doc.filename if doc else "Owner declaration",
        "document_type": doc.doc_type if doc else DocumentType.OWNER_DECLARATION.value,
        "claim_type": claim.claim_type,
        "label": label_for_claim(claim.claim_type),
        "value": d.value,
        "masked": d.masked,
        "mask_reason": d.reason,
        "unlockable_by": d.unlockable_by,
        "normalized_value": claim.normalized_value if not d.masked else None,
        "numeric_value": claim.numeric_value,
        "source_page": claim.source_page,
        "source_span": claim.source_span if not d.masked else None,
        "source_region": claim.source_region or {},
        "confidence": round(claim.confidence, 4),
        "extraction_method": claim.extraction_method,
        "verification_status": claim.verification_status,
        "status_explanation": claim.status_explanation,
        "sensitivity": claim.sensitivity,
        "is_owner_declared": claim.is_owner_declared,
        "superseded": claim.superseded,
        "supporting_count": len({s.related_claim_id for s in supporting}),
        "conflicting_count": len({s.related_claim_id for s in conflicting}),
        "supporting_claim_ids": sorted({s.related_claim_id for s in supporting}),
        "conflicting_claim_ids": sorted({s.related_claim_id for s in conflicting}),
        "created_at": iso(claim.created_at),
    }


def contradiction_out(c: Contradiction) -> dict:
    return {
        "id": c.id,
        "property_id": c.property_id,
        "contradiction_type": c.contradiction_type,
        "claim_type": c.claim_type,
        "claim_label": label_for_claim(c.claim_type),
        "severity": c.severity,
        "left_claim_id": c.left_claim_id,
        "right_claim_id": c.right_claim_id,
        "left_value": c.left_value,
        "right_value": c.right_value,
        "left_source": c.left_source,
        "right_source": c.right_source,
        "difference": c.difference,
        "magnitude": c.magnitude,
        "explanation": c.explanation,
        "detection_rule": c.detection_rule,
        "resolved": c.resolved,
        "resolved_note": c.resolved_note,
        "created_at": iso(c.created_at),
    }


def risk_factor_out(f: RiskFactor) -> dict:
    return {
        "id": f.id,
        "rule_id": f.rule_id,
        "category": f.category,
        "category_label": RISK_CATEGORY_LABELS.get(f.category, f.category),
        "weight": f.weight,
        "severity": f.severity,
        "title": f.title,
        "explanation": f.explanation,
        "evidence_refs": f.evidence_refs or [],
        "is_mitigation": f.is_mitigation,
    }


def assessment_out(a: RiskAssessment, factors: list[RiskFactor]) -> dict:
    return {
        "id": a.id,
        "property_id": a.property_id,
        "transaction_id": a.transaction_id,
        "overall_score": round(a.overall_score, 1),
        "band": a.band,
        "state": a.state,
        "state_reason": a.state_reason,
        "category_scores": a.category_scores or {},
        "category_labels": RISK_CATEGORY_LABELS,
        "engine_version": a.engine_version,
        "created_at": iso(a.created_at),
        "factors": [risk_factor_out(f) for f in
                    sorted(factors, key=lambda x: (x.is_mitigation, -abs(x.weight)))],
    }


def resolution_out(r: ResolutionAction) -> dict:
    return {
        "id": r.id,
        "action_key": r.action_key,
        "title": r.title,
        "description": r.description,
        "required_evidence": r.required_evidence,
        "responsible_party": r.responsible_party,
        "authority_required": r.authority_required,
        "effort": r.effort,
        "priority": r.priority,
        "resolves_rules": r.resolves_rules or [],
        "risk_before": round(r.risk_before, 1),
        "risk_after": round(r.risk_after, 1),
        "risk_delta": round(r.risk_before - r.risk_after, 1),
        "state_after": r.state_after,
        "status": r.status,
        "applied_at": iso(r.applied_at),
    }


def transaction_out(t: Transaction | None) -> dict | None:
    if t is None:
        return None
    return {
        "id": t.id,
        "reference": t.reference,
        "property_id": t.property_id,
        "state": t.state,
        "state_reason": t.state_reason,
        "state_changed_at": iso(t.state_changed_at),
        "stage": t.stage,
        "consideration_inr": t.consideration_inr,
        "blocked_actions": t.blocked_actions or [],
    }


def consent_out(r: ConsentRequest, users: dict[str, User] | None = None) -> dict:
    from .domain import DISCLOSURE_LABELS, DisclosureItem

    def label(item: str) -> str:
        try:
            return DISCLOSURE_LABELS[DisclosureItem(item)]
        except (ValueError, KeyError):
            return item.replace("_", " ").title()

    users = users or {}
    return {
        "id": r.id,
        "property_id": r.property_id,
        "requester": user_out(users.get(r.requester_id), Role.ADMIN),
        "owner_id": r.owner_id,
        "items": [{"item": i, "label": label(i)} for i in (r.items or [])],
        "granted_items": [{"item": i, "label": label(i)} for i in (r.granted_items or [])],
        "denied_items": [{"item": i, "label": label(i)} for i in (r.denied_items or [])],
        "purpose": r.purpose,
        "status": r.status,
        "decision_note": r.decision_note,
        "created_at": iso(r.created_at),
        "decided_at": iso(r.decided_at),
        "expires_at": iso(r.expires_at),
    }


def message_out(m: Message, viewer: Role, users: dict[str, User] | None = None) -> dict:
    users = users or {}
    sender = users.get(m.sender_id)
    return {
        "id": m.id,
        "property_id": m.property_id,
        "sender_role": m.sender_role,
        "sender_name": (
            sender.name if sender and viewer != Role.BUYER or m.sender_role == Role.BUYER.value
            else mask_name(sender.name) if sender else m.sender_role.title()
        ),
        # The relay delivers the redacted text — never the raw body.
        "body": m.redacted_body or m.body,
        "contained_sensitive": m.contained_sensitive,
        "sensitive_kinds": m.sensitive_kinds or [],
        "references_claim_id": m.references_claim_id,
        "created_at": iso(m.created_at),
    }


def audit_out(e: AuditEvent) -> dict:
    return {
        "id": e.id,
        "property_id": e.property_id,
        "transaction_id": e.transaction_id,
        "actor_role": e.actor_role,
        "actor_name": e.actor_name,
        "action": e.action,
        "result": e.result,
        "summary": e.summary,
        "evidence_refs": e.evidence_refs or [],
        "payload": e.payload or {},
        "created_at": iso(e.created_at),
    }


def property_summary(
    db: Session, prop: Property, assessment: RiskAssessment | None = None
) -> dict:
    if assessment is None:
        assessment = db.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.property_id == prop.id, RiskAssessment.is_simulation == False)  # noqa: E712
            .order_by(RiskAssessment.created_at.desc())
        ).first()
    txn = db.scalars(select(Transaction).where(Transaction.property_id == prop.id)).first()
    doc_count = len(db.scalars(select(Document).where(Document.property_id == prop.id)).all())
    claims = db.scalars(select(Claim).where(Claim.property_id == prop.id)).all()
    live = [c for c in claims if not c.superseded]
    contradictions = db.scalars(
        select(Contradiction).where(
            Contradiction.property_id == prop.id, Contradiction.resolved == False  # noqa: E712
        )
    ).all()

    status_counts: dict[str, int] = {}
    seen: dict[str, str] = {}
    for c in live:
        if c.claim_type in seen:
            continue
        seen[c.claim_type] = c.verification_status
        status_counts[c.verification_status] = status_counts.get(c.verification_status, 0) + 1

    # Verification level is measured over the six CORE claim types, so the figure on a
    # card, in a profile and in the evaluation harness all mean the same thing. Counting
    # every extracted attribute instead would let a file look better simply for carrying
    # more incidental fields.
    from .domain import CORE_CLAIM_TYPES

    core_verified = sum(
        1 for ct in CORE_CLAIM_TYPES
        if seen.get(ct.value) == VerificationStatus.VERIFIED.value
    )
    verified = core_verified
    total_types = len(CORE_CLAIM_TYPES)

    return {
        "id": prop.id,
        "reference": prop.reference,
        "survey_number": prop.survey_number,
        "district": prop.district,
        "village": prop.village,
        "state": prop.state,
        "property_type": prop.property_type,
        "claimed_area_sqft": prop.claimed_area_sqft,
        "guideline_value_inr": prop.guideline_value_inr,
        "asking_price_inr": prop.asking_price_inr,
        "listed_owner_name": prop.listed_owner_name,
        "scenario_key": prop.scenario_key,
        "scenario_label": prop.scenario_label,
        "owner": user_out(prop.owner, Role.ADMIN),
        "document_count": doc_count,
        "claim_count": len(live),
        "contradiction_count": len(contradictions),
        "critical_contradictions": len([c for c in contradictions
                                        if c.severity in {"HIGH", "CRITICAL"}]),
        "verification_level": round(verified / total_types, 4),
        "verification_counts": status_counts,
        "risk_score": round(assessment.overall_score, 1) if assessment else None,
        "risk_band": assessment.band if assessment else None,
        "transaction_state": txn.state if txn else (assessment.state if assessment else None),
        "transaction": transaction_out(txn),
        "closed_rules": prop.closed_rules or [],
        "updated_at": iso(prop.updated_at),
    }
