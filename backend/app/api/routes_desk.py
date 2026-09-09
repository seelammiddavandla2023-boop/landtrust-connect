"""
The verification desk: a verifier's queue, a supervisor's team view, and the
platform head's overview.

Three roles, three surfaces, one set of rows underneath — so the administrator
and the supervisor can never be shown different answers to the same question.

Nothing here can make a claim verified. A verifier records what they established
by examining a document; the resolver still decides what the evidence set
supports. That separation is the point, and it is why this module writes findings
rather than statuses.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..domain import (
    ASSIGNMENT_STATUS_LABELS,
    AssignmentStatus,
    AuditAction,
    ESCALATION_OUTCOME_LABELS,
    EscalationOutcome,
    FINDING_OUTCOME_LABELS,
    FindingOutcome,
    Role,
)
from ..models import (
    Document,
    EscalationDetermination,
    Property,
    RiskAssessment,
    Transaction,
    User,
    VerificationAssignment,
    VerifierFinding,
)
from ..services import audit, authz, verification_desk
from .deps import current_role, current_user, get_property

router = APIRouter(prefix="/api", tags=["desk"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)



def _seller_of(db: Session, prop: Property) -> dict:
    """The party who listed the property, as the verifier needs to see them."""
    owner = db.get(User, prop.owner_id) if prop.owner_id else None
    return {
        "listed_owner_name": prop.listed_owner_name,
        "account_name": owner.name if owner else None,
        "email": owner.email if owner else None,
        "phone": owner.phone if owner else None,
        "organisation": owner.organisation if owner else None,
        "note": (
            "The listed name is what the seller asserts. It is held separately from any "
            "owner name the documents establish, which is what allows the two to be "
            "compared."
        ),
    }


def _latest_upload(db: Session, property_id: str) -> dict | None:
    doc = db.scalars(
        select(Document)
        .where(Document.property_id == property_id)
        .order_by(Document.created_at.desc())
    ).first()
    if doc is None:
        return None
    return {
        "filename": doc.filename,
        "doc_type": doc.doc_type,
        "uploaded_by_role": doc.uploaded_by_role,
        "created_at": doc.created_at,
    }


# --------------------------------------------------------------- the verifier

@router.get("/desk/queue")
def my_queue(
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    user: User | None = Depends(current_user),
):
    """The properties on this verifier's desk, and what each still needs."""
    authz.require(role, authz.Capability.RECORD_FINDING)
    if user is None:
        raise HTTPException(400, "No demo user is configured for this role.")

    assignments = db.scalars(
        select(VerificationAssignment)
        .where(VerificationAssignment.verifier_id == user.id)
        .order_by(VerificationAssignment.assigned_at)
    ).all()

    items = []
    for a in assignments:
        prop = db.get(Property, a.property_id)
        if prop is None:
            continue
        txn = db.scalars(
            select(Transaction).where(Transaction.property_id == prop.id)
        ).first()
        assessment = db.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.property_id == prop.id)
            .order_by(RiskAssessment.created_at.desc())
        ).first()
        flagged = verification_desk.flagged_documents(db, prop.id)
        findings = db.scalars(
            select(VerifierFinding)
            .where(VerifierFinding.assignment_id == a.id)
            .order_by(VerifierFinding.created_at.desc())
        ).all()
        examined = {f.document_id for f in findings if f.document_id}

        items.append({
            "assignment_id": a.id,
            "status": a.status,
            "status_label": ASSIGNMENT_STATUS_LABELS.get(a.status, a.status),
            "onboarded_by_me": a.onboarded_by_verifier,
            "assigned_at": a.assigned_at,
            "completed_at": a.completed_at,
            "property": {
                "id": prop.id,
                "reference": prop.reference,
                "survey_number": prop.survey_number,
                "village": prop.village,
                "district": prop.district,
                "scenario_label": prop.scenario_label,
                "claimed_area_sqft": prop.claimed_area_sqft,
                "asking_price_inr": prop.asking_price_inr,
            },
            # Who put this file on the platform, and what the listing asserts.
            # A verifier examining a document needs to know who supplied it, and
            # the listed name is deliberately shown as a claim rather than a fact:
            # it is exactly the value an impersonation would falsify.
            "seller": _seller_of(db, prop),
            "documents_on_file": len(db.scalars(
                select(Document).where(Document.property_id == prop.id)).all()),
            "latest_upload": _latest_upload(db, prop.id),
            "transaction_state": txn.state if txn else None,
            "risk_score": round(assessment.overall_score, 1) if assessment else None,
            "risk_band": assessment.band if assessment else None,
            "documents_to_examine": [
                {
                    "id": d.id,
                    "filename": d.filename,
                    "indicators": [
                        f.get("code") for f in (d.integrity_flags or [])
                        if f.get("severity") == "HIGH"
                    ],
                    "examined": d.id in examined,
                }
                for d in flagged
            ],
            "outstanding": len([d for d in flagged if d.id not in examined]),
            "findings": [
                {
                    "id": f.id,
                    "outcome": f.outcome,
                    "outcome_label": FINDING_OUTCOME_LABELS.get(f.outcome, f.outcome),
                    "note": f.note,
                    "document_id": f.document_id,
                    "agrees_with_platform": f.agrees_with_platform,
                    "created_at": f.created_at,
                }
                for f in findings
            ],
        })

    return {
        "verifier": {"id": user.id, "name": user.name,
                     "organisation": user.organisation},
        "assignments": items,
        "outcomes": [
            {"key": o.value, "label": FINDING_OUTCOME_LABELS[o.value]}
            for o in FindingOutcome
        ],
        "note": (
            "A finding records what you established by examining the original document. It "
            "is evidence, not approval: the platform still derives every claim's status from "
            "the evidence set, and your examination becomes part of that set."
        ),
    }


class FindingCreate(BaseModel):
    property_id: str
    document_id: str | None = None
    outcome: str
    note: str = Field(default="", max_length=2000)


@router.post("/desk/findings")
def record_finding(
    payload: FindingCreate,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    user: User | None = Depends(current_user),
):
    authz.require(role, authz.Capability.RECORD_FINDING)
    if user is None:
        raise HTTPException(400, "No demo user is configured for this role.")
    if payload.outcome not in {o.value for o in FindingOutcome}:
        raise HTTPException(400, f"Unknown outcome '{payload.outcome}'.")

    prop = db.scalars(
        select(Property).where((Property.id == payload.property_id) |
                               (Property.reference == payload.property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found.")

    assignment = db.scalars(
        select(VerificationAssignment).where(
            (VerificationAssignment.property_id == prop.id) &
            (VerificationAssignment.verifier_id == user.id)
        )
    ).first()
    if assignment is None:
        raise HTTPException(403, "This property is not on your desk.")

    finding = VerifierFinding(
        assignment_id=assignment.id,
        property_id=prop.id,
        verifier_id=user.id,
        document_id=payload.document_id,
        outcome=payload.outcome,
        note=payload.note,
        agrees_with_platform=verification_desk.evaluate_finding(
            db, payload.document_id, payload.outcome),
    )
    db.add(finding)

    if assignment.status == AssignmentStatus.ASSIGNED.value:
        assignment.status = AssignmentStatus.IN_REVIEW.value

    audit.record(
        db, AuditAction.EVIDENCE_ADDED, property_id=prop.id, actor_role=role,
        actor_name=user.name, result=payload.outcome,
        summary=f"Verifier examination recorded: "
                f"{FINDING_OUTCOME_LABELS.get(payload.outcome, payload.outcome)}.",
        payload={"document_id": payload.document_id,
                 "agrees_with_platform": finding.agrees_with_platform},
        commit=True,
    )
    return {"finding_id": finding.id,
            "agrees_with_platform": finding.agrees_with_platform,
            "assignment_status": assignment.status}


@router.post("/desk/assignments/{assignment_id}/sign-off")
def sign_off(
    assignment_id: str,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    user: User | None = Depends(current_user),
):
    """
    Close an assignment, recording the state it was closed in.

    The state is stored because that is what makes a later reversal visible: if
    the property moves to a stricter state afterwards, the supervisor's view
    counts it as a regression against this sign-off. Without the snapshot there
    would be nothing to compare against and the figure would be an assertion.
    """
    authz.require(role, authz.Capability.RECORD_FINDING)
    assignment = db.get(VerificationAssignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "Assignment not found.")
    if user is None or assignment.verifier_id != user.id:
        raise HTTPException(403, "This property is not on your desk.")

    flagged = verification_desk.flagged_documents(db, assignment.property_id)
    examined = {
        f.document_id for f in db.scalars(
            select(VerifierFinding)
            .where(VerifierFinding.assignment_id == assignment.id)
        ).all() if f.document_id
    }
    outstanding = [d for d in flagged if d.id not in examined]
    if outstanding:
        raise HTTPException(
            400,
            f"{len(outstanding)} flagged document(s) have not been examined: "
            + ", ".join(d.filename for d in outstanding[:3])
            + ". Record a finding for each before signing off.",
        )

    txn = db.scalars(
        select(Transaction).where(Transaction.property_id == assignment.property_id)
    ).first()
    assessment = db.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.property_id == assignment.property_id)
        .order_by(RiskAssessment.created_at.desc())
    ).first()

    assignment.status = AssignmentStatus.COMPLETED.value
    assignment.completed_at = _utcnow()
    assignment.state_at_signoff = txn.state if txn else None
    assignment.risk_at_signoff = assessment.overall_score if assessment else None

    audit.record(
        db, AuditAction.CONTRADICTION_RESOLVED, property_id=assignment.property_id,
        actor_role=role, actor_name=user.name, result=assignment.state_at_signoff or "OK",
        summary=f"Verifier signed the file off in state {assignment.state_at_signoff}.",
        commit=True,
    )
    return {"status": assignment.status,
            "state_at_signoff": assignment.state_at_signoff,
            "risk_at_signoff": assignment.risk_at_signoff}


# ------------------------------------------------------- the legal reviewer

@router.get("/desk/team")
def team(db: Session = Depends(get_db), role: Role = Depends(current_role)):
    """Every verifier's record, for the reviewer who supervises the desk."""
    authz.require(role, authz.Capability.SUPERVISE_DESK)
    return verification_desk.desk_summary(db)


@router.get("/desk/escalations")
def escalations(db: Session = Depends(get_db), role: Role = Depends(current_role)):
    """Cases the state controller refused to decide."""
    authz.require(role, authz.Capability.SUPERVISE_DESK)
    return {
        "items": verification_desk.escalation_queue(db),
        "outcomes": [
            {"key": o.value, "label": ESCALATION_OUTCOME_LABELS[o.value]}
            for o in EscalationOutcome
        ],
        "note": (
            "The platform escalates rather than guessing when authority cannot be "
            "established from the evidence. A determination recorded here does not change "
            "the risk score — it records what a qualified person decided about a case the "
            "machine declined to decide, and why."
        ),
    }


class DeterminationCreate(BaseModel):
    property_id: str
    outcome: str
    reasoning: str = Field(default="", max_length=4000)


@router.post("/desk/escalations/determination")
def record_determination(
    payload: DeterminationCreate,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
    user: User | None = Depends(current_user),
):
    authz.require(role, authz.Capability.SUPERVISE_DESK)
    if user is None:
        raise HTTPException(400, "No demo user is configured for this role.")
    if payload.outcome not in {o.value for o in EscalationOutcome}:
        raise HTTPException(400, f"Unknown outcome '{payload.outcome}'.")

    prop = db.scalars(
        select(Property).where((Property.id == payload.property_id) |
                               (Property.reference == payload.property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found.")

    txn = db.scalars(
        select(Transaction).where(Transaction.property_id == prop.id)
    ).first()
    if txn is None or txn.state not in verification_desk.ESCALATED_STATES:
        raise HTTPException(
            400,
            "This property is not escalated. A determination is recorded only for a case "
            "the platform declined to decide.",
        )
    assessment = db.scalars(
        select(RiskAssessment)
        .where(RiskAssessment.property_id == prop.id)
        .order_by(RiskAssessment.created_at.desc())
    ).first()

    determination = EscalationDetermination(
        property_id=prop.id,
        reviewer_id=user.id,
        outcome=payload.outcome,
        reasoning=payload.reasoning,
        state_at_review=txn.state,
        risk_at_review=assessment.overall_score if assessment else 0.0,
    )
    db.add(determination)
    audit.record(
        db, AuditAction.TRANSACTION_ESCALATED, property_id=prop.id, transaction_id=txn.id,
        actor_role=role, actor_name=user.name, result=payload.outcome,
        summary=f"Legal determination recorded on an escalated case: "
                f"{ESCALATION_OUTCOME_LABELS.get(payload.outcome, payload.outcome)}.",
        payload={"reasoning": payload.reasoning, "state_at_review": txn.state},
        commit=True,
    )
    return {"determination_id": determination.id, "outcome": determination.outcome}


# ------------------------------------------------------- the administrator

@router.get("/desk/overview")
def overview(db: Session = Depends(get_db), role: Role = Depends(current_role)):
    """The whole estate and the whole desk, for the platform head."""
    authz.require(role, authz.Capability.PLATFORM_OVERSIGHT)
    return verification_desk.platform_overview(db)
