"""Consent, the secure owner–buyer relay, and the evidence assistant."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..domain import (
    DISCLOSURE_LABELS,
    NEVER_DISCLOSED,
    AnswerKind,
    AuditAction,
    ConsentStatus,
    DisclosureItem,
    Role,
)
from ..models import (
    AssistantQuery,
    Claim,
    ConsentRequest,
    Contradiction,
    Document,
    Message,
    OwnershipEvent,
    Property,
    ResolutionAction,
    RiskAssessment,
    User,
)
from ..serializers import consent_out, message_out
from ..services import authz, audit, pipeline
from ..services.evidence_qa.answerer import SUGGESTED_QUESTIONS, answer
from ..services.privacy import consent as consent_service
from ..services.privacy.redaction import scan_message
from ..services.resolution_planner.planner import plan as build_plan
from ..services.risk_engine.engine import compute
from .deps import current_role, current_user, get_property

router = APIRouter(prefix="/api", tags=["interaction"])


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------
class ConsentCreate(BaseModel):
    property_id: str
    items: list[str] = Field(..., min_length=1)
    purpose: str = ""


class ConsentDecision(BaseModel):
    approve: bool
    items: list[str] | None = None
    time_limited: bool = False
    note: str = ""


@router.get("/consent/items")
def disclosure_catalogue():
    return {
        "items": [
            {
                "item": i.value,
                "label": DISCLOSURE_LABELS[i],
                "requestable": i not in NEVER_DISCLOSED,
                "policy": (
                    "Never disclosed through this platform, with or without owner consent."
                    if i in NEVER_DISCLOSED else
                    "Released only when the owner approves; approval may be time-limited."
                ),
            }
            for i in DisclosureItem
        ],
        "time_limited_hours": consent_service.TIME_LIMITED_HOURS,
    }


@router.get("/consent")
def list_consent(
    property_id: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(ConsentRequest)
    if property_id:
        prop = db.scalars(
            select(Property).where((Property.id == property_id) |
                                   (Property.reference == property_id))
        ).first()
        if prop is None:
            raise HTTPException(404, "Property not found.")
        stmt = stmt.where(ConsentRequest.property_id == prop.id)
    rows = list(db.scalars(stmt.order_by(ConsentRequest.created_at.desc())).all())
    changed = consent_service.expire_stale(rows)
    for r in changed:
        audit.record(db, AuditAction.CONSENT_EXPIRED, property_id=r.property_id,
                     actor_role=Role.ADMIN, actor_name="consent-service",
                     summary="Time-limited access grant expired and was withdrawn "
                             "automatically.")
    if changed:
        db.commit()
    users = {u.id: u for u in db.scalars(select(User)).all()}
    return {"count": len(rows), "items": [consent_out(r, users) for r in rows]}


@router.post("/consent")
def request_consent(
    payload: ConsentCreate,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    user: User | None = Depends(current_user),
):
    prop = db.scalars(
        select(Property).where((Property.id == payload.property_id) |
                               (Property.reference == payload.property_id))
    ).first()
    authz.require(role, authz.Capability.REQUEST_CONSENT)
    if prop is None:
        raise HTTPException(404, "Property not found.")
    if user is None:
        raise HTTPException(400, "No demo user is configured for this role.")

    blocked = [i for i in payload.items if i in {n.value for n in NEVER_DISCLOSED}]
    requestable = [i for i in payload.items if i not in {n.value for n in NEVER_DISCLOSED}]

    req = ConsentRequest(
        property_id=prop.id,
        requester_id=user.id,
        owner_id=prop.owner_id,
        items=payload.items,
        purpose=payload.purpose,
        status=ConsentStatus.REQUESTED.value,
    )
    db.add(req)
    audit.record(
        db, AuditAction.CONSENT_REQUESTED, property_id=prop.id, actor_role=role,
        actor_name=user.name,
        summary=f"Access requested for: {', '.join(payload.items)}. Purpose: "
                f"{payload.purpose or 'not stated'}.",
        payload={"items": payload.items},
        commit=True,
    )
    users = {u.id: u for u in db.scalars(select(User)).all()}
    return {
        "request": consent_out(req, users),
        "notice": (
            "Identity documents cannot be requested through this platform and were excluded "
            "from this request." if blocked else None
        ),
        "requestable_items": requestable,
    }


@router.post("/consent/{request_id}/decision")
def decide_consent(
    request_id: str,
    payload: ConsentDecision,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    req = db.get(ConsentRequest, request_id)
    if req is None:
        raise HTTPException(404, "Consent request not found.")
    authz.require(role, authz.Capability.DECIDE_CONSENT)

    consent_service.decide(req, payload.approve, payload.items, payload.time_limited,
                           payload.note)
    action = AuditAction.CONSENT_APPROVED if payload.approve else AuditAction.CONSENT_DENIED
    audit.record(
        db, action, property_id=req.property_id, actor_role=role, actor_name="owner",
        result=req.status,
        summary=(
            f"Granted: {', '.join(req.granted_items) or 'nothing'}. "
            f"Withheld: {', '.join(req.denied_items) or 'nothing'}."
            + (f" Expires {req.expires_at:%d-%m-%Y %H:%M} UTC." if req.expires_at else "")
        ),
        payload={"granted": req.granted_items, "denied": req.denied_items},
    )
    prop = db.get(Property, req.property_id)
    if prop:
        pipeline.reassess(db, prop, actor_role=role, actor_name="owner",
                          reason="Consent decision recorded")
    db.commit()
    users = {u.id: u for u in db.scalars(select(User)).all()}
    return consent_out(req, users)


@router.post("/consent/{request_id}/revoke")
def revoke_consent(
    request_id: str,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    req = db.get(ConsentRequest, request_id)
    if req is None:
        raise HTTPException(404, "Consent request not found.")
    authz.require(role, authz.Capability.DECIDE_CONSENT)
    consent_service.revoke(req)
    audit.record(db, AuditAction.CONSENT_DENIED, property_id=req.property_id, actor_role=role,
                 actor_name="owner", result="REVOKED",
                 summary="Previously granted access was revoked by the owner.", commit=True)
    users = {u.id: u for u in db.scalars(select(User)).all()}
    return consent_out(req, users)


# ---------------------------------------------------------------------------
# Secure relay
# ---------------------------------------------------------------------------
class MessageCreate(BaseModel):
    property_id: str
    body: str = Field(..., min_length=1, max_length=4000)
    references_claim_id: str | None = None


@router.get("/messages")
def list_messages(
    property_id: str,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    prop = db.scalars(
        select(Property).where((Property.id == property_id) |
                               (Property.reference == property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found.")
    rows = db.scalars(
        select(Message).where(Message.property_id == prop.id).order_by(Message.created_at)
    ).all()
    users = {u.id: u for u in db.scalars(select(User)).all()}
    return {
        "count": len(rows),
        "items": [message_out(m, role, users) for m in rows],
        "notice": (
            "This channel is property-scoped. Phone numbers, e-mail addresses, identity numbers "
            "and account details are removed before delivery, and every message is recorded in "
            "the audit trail."
        ),
    }


@router.post("/messages")
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    user: User | None = Depends(current_user),
):
    prop = db.scalars(
        select(Property).where((Property.id == payload.property_id) |
                               (Property.reference == payload.property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found.")

    scan = scan_message(payload.body)
    message = Message(
        property_id=prop.id,
        sender_role=role.value,
        sender_id=user.id if user else None,
        body=payload.body,
        redacted_body=scan.redacted,
        contained_sensitive=scan.contained_sensitive,
        sensitive_kinds=scan.kinds,
        references_claim_id=payload.references_claim_id,
    )
    db.add(message)
    audit.record(
        db, AuditAction.MESSAGE_SENT, property_id=prop.id, actor_role=role,
        actor_name=user.name if user else role.value,
        result="REDACTED" if scan.contained_sensitive else "OK",
        summary=(
            f"Message sent through the property relay."
            + (f" Redacted: {', '.join(scan.kinds)}." if scan.kinds else "")
        ),
        payload={"sensitive_kinds": scan.kinds},
    )
    if scan.contained_sensitive:
        pipeline.reassess(db, prop, actor_role=Role.ADMIN, actor_name="relay",
                          reason="Sensitive content detected in the relay")
    db.commit()
    users = {u.id: u for u in db.scalars(select(User)).all()}
    return {"message": message_out(message, role, users), "warning": scan.warning or None}


# ---------------------------------------------------------------------------
# Evidence assistant
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    property_id: str
    question: str = Field(..., min_length=2, max_length=500)


@router.get("/assistant/suggestions")
def assistant_suggestions():
    return {
        "questions": SUGGESTED_QUESTIONS,
        "contract": (
            "Every answer is derived from claim and contradiction records on this property's "
            "file and cites the document and page it came from. When no such record exists the "
            "assistant refuses rather than inferring."
        ),
    }


@router.post("/assistant/ask")
def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    prop = db.scalars(
        select(Property).where((Property.id == payload.property_id) |
                               (Property.reference == payload.property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found.")

    claims = list(db.scalars(select(Claim).where(Claim.property_id == prop.id)).all())
    documents = list(db.scalars(select(Document).where(Document.property_id == prop.id)).all())
    contradictions = list(db.scalars(
        select(Contradiction).where(Contradiction.property_id == prop.id)).all())
    events = list(db.scalars(
        select(OwnershipEvent).where(OwnershipEvent.property_id == prop.id)).all())

    ctx = pipeline.build_context(db, prop)
    risk = compute(ctx)
    plan = build_plan(ctx)

    result = answer(payload.question, claims, contradictions, documents, events,
                    ctx.outcome, risk, plan)

    db.add(
        AssistantQuery(
            property_id=prop.id,
            question=payload.question,
            intent=result.intent,
            answer_kind=result.kind.value,
            answer=result.text,
            confidence=result.confidence,
            evidence_refs=[e.dict() for e in result.evidence],
            backend=result.backend,
        )
    )
    audit.record(
        db,
        AuditAction.ASSISTANT_REFUSAL if result.kind is not AnswerKind.GROUNDED
        else AuditAction.ASSISTANT_QUERY,
        property_id=prop.id, actor_role=role, actor_name=role.value,
        result=result.kind.value,
        summary=f"Q: {payload.question[:160]} → {result.kind.value} "
                f"({len(result.evidence)} citation(s)).",
        commit=True,
    )
    return result.dict()


@router.get("/assistant/log")
def assistant_log(property_id: str | None = None, db: Session = Depends(get_db),
                  limit: int = 100):
    stmt = select(AssistantQuery)
    if property_id:
        prop = db.scalars(
            select(Property).where((Property.id == property_id) |
                                   (Property.reference == property_id))
        ).first()
        if prop:
            stmt = stmt.where(AssistantQuery.property_id == prop.id)
    rows = db.scalars(stmt.order_by(AssistantQuery.created_at.desc()).limit(limit)).all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": r.id, "property_id": r.property_id, "question": r.question,
                "intent": r.intent, "answer_kind": r.answer_kind, "answer": r.answer,
                "confidence": round(r.confidence, 3), "evidence": r.evidence_refs or [],
                "backend": r.backend, "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
    }
