"""
The human verification desk: assignments, findings, and the figures a supervisor
and the platform head are shown.

Three people-shaped jobs sit around the evidence engine, and none of them
overrides it:

* A **verifier** is responsible for named properties. They onboard some of them,
  and they examine the documents the pipeline flagged — establishing whether the
  paper matches the issuing office's copy, which is a fact the file cannot yield
  on its own. Their finding enters the system as evidence.
* A **legal reviewer** supervises a desk of verifiers and owns the cases the
  state controller escalated. Escalation previously had no destination; a
  determination recorded here is where it lands.
* An **administrator** sees the whole platform: every property, every verifier,
  and whether the desk as a whole is keeping up.

Every figure below is derived from stored rows at read time. None of them is a
counter that something increments, because a counter can drift from the events
it claims to summarise and there is no way to audit it afterwards.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain import (
    ASSIGNMENT_STATUS_LABELS,
    AssignmentStatus,
    FINDING_CONFIRMS_INDICATOR,
    FINDING_OUTCOME_LABELS,
    FindingOutcome,
    Role,
    TRANSACTION_STATE_RANK,
    TransactionState,
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

#: Transaction states that put a case on the legal reviewer's desk.
ESCALATED_STATES = {TransactionState.ESCALATE.value, TransactionState.REJECT.value}


def _has_high_integrity_indicator(doc: Document) -> bool:
    return any(f.get("severity") == "HIGH" for f in (doc.integrity_flags or []))


def flagged_documents(db: Session, property_id: str) -> list[Document]:
    """Documents on a property that the pipeline asked a human to examine."""
    docs = db.scalars(
        select(Document).where(Document.property_id == property_id)
    ).all()
    return [d for d in docs if _has_high_integrity_indicator(d)]


def evaluate_finding(db: Session, document_id: str | None, outcome: str) -> bool | None:
    """
    Did this finding agree with what the pipeline computed?

    Returns None where the question does not arise — an inconclusive examination,
    or a finding not tied to a specific document. Agreement is not a score of the
    verifier's competence: a disagreement is often the more valuable result,
    because it is where automated and human judgement diverge and a supervisor
    should look.
    """
    expected = FINDING_CONFIRMS_INDICATOR.get(outcome)
    if expected is None or not document_id:
        return None
    doc = db.get(Document, document_id)
    if doc is None:
        return None
    return _has_high_integrity_indicator(doc) is expected


# --------------------------------------------------------------------- metrics

def _state_of(db: Session, property_id: str) -> str | None:
    txn = db.scalars(
        select(Transaction).where(Transaction.property_id == property_id)
    ).first()
    return txn.state if txn else None


def verifier_record(db: Session, verifier: User) -> dict:
    """
    One verifier's record, as their supervisor sees it.

    The three figures that matter, and what each actually means:

    * **handled** — properties on their desk. Volume, nothing more.
    * **agreement** — of the findings where agreement is defined, the share that
      matched the pipeline's own reading of the document. Low agreement is a
      prompt to look, not a verdict; the human may well be right.
    * **regressions** — properties they signed off that have since moved to a
      *stricter* transaction state. This is the figure that speaks to the buyer's
      experience: a sign-off that later had to be walked back is exactly the
      trouble a buyer feels, and it is measured rather than asserted.
    """
    assignments = db.scalars(
        select(VerificationAssignment)
        .where(VerificationAssignment.verifier_id == verifier.id)
    ).all()
    findings = db.scalars(
        select(VerifierFinding).where(VerifierFinding.verifier_id == verifier.id)
    ).all()

    completed = [a for a in assignments if a.status == AssignmentStatus.COMPLETED.value]
    open_items = [a for a in assignments if a.status != AssignmentStatus.COMPLETED.value]
    onboarded = [a for a in assignments if a.onboarded_by_verifier]

    judged = [f for f in findings if f.agrees_with_platform is not None]
    agreed = [f for f in judged if f.agrees_with_platform]

    regressions = []
    for a in completed:
        if not a.state_at_signoff:
            continue
        now = _state_of(db, a.property_id)
        if now is None:
            continue
        if TRANSACTION_STATE_RANK.get(now, 0) > TRANSACTION_STATE_RANK.get(
            a.state_at_signoff, 0
        ):
            prop = db.get(Property, a.property_id)
            regressions.append({
                "property_id": a.property_id,
                "reference": prop.reference if prop else a.property_id,
                "signed_off_at": a.state_at_signoff,
                "state_now": now,
            })

    return {
        "verifier": {
            "id": verifier.id,
            "name": verifier.name,
            "email": verifier.email,
            "organisation": verifier.organisation,
        },
        "handled": len(assignments),
        "completed": len(completed),
        "open": len(open_items),
        "onboarded": len(onboarded),
        "findings": len(findings),
        "findings_judged": len(judged),
        "agreement_rate": round(100.0 * len(agreed) / len(judged), 1) if judged else None,
        "regressions": regressions,
        "regression_count": len(regressions),
        "clean_signoffs": len(completed) - len(regressions),
        "open_references": [
            {
                "reference": (db.get(Property, a.property_id).reference
                              if db.get(Property, a.property_id) else a.property_id),
                "status": a.status,
                "status_label": ASSIGNMENT_STATUS_LABELS.get(a.status, a.status),
            }
            for a in open_items
        ],
    }


def desk_summary(db: Session) -> dict:
    """Every verifier's record, plus the totals a supervisor is accountable for."""
    verifiers = db.scalars(
        select(User).where(User.role == Role.VERIFIER.value).order_by(User.name)
    ).all()
    records = [verifier_record(db, v) for v in verifiers]

    judged = sum(r["findings_judged"] for r in records)
    agreed = sum(
        round((r["agreement_rate"] or 0) / 100.0 * r["findings_judged"])
        for r in records
    )

    return {
        "verifiers": records,
        "totals": {
            "verifiers": len(records),
            "properties_handled": sum(r["handled"] for r in records),
            "properties_onboarded": sum(r["onboarded"] for r in records),
            "signed_off": sum(r["completed"] for r in records),
            "open": sum(r["open"] for r in records),
            "findings": sum(r["findings"] for r in records),
            "desk_agreement_rate": round(100.0 * agreed / judged, 1) if judged else None,
            "regressions": sum(r["regression_count"] for r in records),
        },
        "note": (
            "Agreement compares a verifier's examination of a document with the integrity "
            "indicators the pipeline computed from the same file. A disagreement is not an "
            "error — it is where human and automated judgement diverge, and is the first "
            "thing worth looking at. Regressions count properties signed off that have since "
            "moved to a stricter transaction state."
        ),
    }


def escalation_queue(db: Session) -> list[dict]:
    """
    Cases the state controller refused to decide, with any determination made.

    The platform escalates when seller authority cannot be established from the
    evidence. Somebody has to own that outcome; this is the list they own.
    """
    txns = db.scalars(
        select(Transaction).where(Transaction.state.in_(sorted(ESCALATED_STATES)))
    ).all()

    out = []
    for txn in txns:
        prop = db.get(Property, txn.property_id)
        if prop is None:
            continue
        determination = db.scalars(
            select(EscalationDetermination)
            .where(EscalationDetermination.property_id == prop.id)
            .order_by(EscalationDetermination.created_at.desc())
        ).first()
        assignment = db.scalars(
            select(VerificationAssignment)
            .where(VerificationAssignment.property_id == prop.id)
        ).first()
        verifier = db.get(User, assignment.verifier_id) if assignment else None
        assessment = db.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.property_id == prop.id)
            .order_by(RiskAssessment.created_at.desc())
        ).first()

        out.append({
            "property_id": prop.id,
            "reference": prop.reference,
            "survey_number": prop.survey_number,
            "village": prop.village,
            "district": prop.district,
            "scenario_label": prop.scenario_label,
            "state": txn.state,
            "state_reason": txn.state_reason,
            "risk_score": round(assessment.overall_score, 1) if assessment else None,
            "risk_band": assessment.band if assessment else None,
            "assigned_verifier": (
                {"id": verifier.id, "name": verifier.name} if verifier else None
            ),
            "determination": (
                {
                    "outcome": determination.outcome,
                    "reasoning": determination.reasoning,
                    "reviewer": (db.get(User, determination.reviewer_id).name
                                 if db.get(User, determination.reviewer_id) else "—"),
                    "created_at": determination.created_at,
                    "state_at_review": determination.state_at_review,
                }
                if determination else None
            ),
        })
    out.sort(key=lambda r: (r["determination"] is not None,
                            -(r["risk_score"] or 0)))
    return out


def platform_overview(db: Session) -> dict:
    """
    The head's view: the whole estate, and whether the desk is keeping up with it.

    Deliberately assembled from the same rows the other two views read, so the
    administrator and the supervisor can never be shown different numbers for the
    same question.
    """
    properties = db.scalars(select(Property)).all()
    assignments = db.scalars(select(VerificationAssignment)).all()
    assigned_ids = {a.property_id for a in assignments}

    by_state: dict[str, int] = defaultdict(int)
    for prop in properties:
        state = _state_of(db, prop.id) or "UNKNOWN"
        by_state[state] += 1

    desk = desk_summary(db)
    escalations = escalation_queue(db)
    undetermined = [e for e in escalations if e["determination"] is None]

    unassigned = [
        {"reference": p.reference, "scenario_label": p.scenario_label}
        for p in properties if p.id not in assigned_ids
    ]

    return {
        "estate": {
            "properties": len(properties),
            "assigned": len(assigned_ids),
            "unassigned": len(unassigned),
            "documents": len(db.scalars(select(Document)).all()),
            "by_transaction_state": dict(by_state),
        },
        "desk": desk["totals"],
        "verifiers": desk["verifiers"],
        "escalations": {
            "total": len(escalations),
            "awaiting_determination": len(undetermined),
            "items": escalations,
        },
        "unassigned_properties": unassigned,
        "attention": _attention(desk, undetermined, unassigned),
    }


def _attention(desk: dict, undetermined: list, unassigned: list) -> list[dict]:
    """
    What the head should look at, worst first.

    A dashboard that only reports totals leaves the reader to work out what is
    wrong. These are the specific conditions worth acting on, and each says why.
    """
    items: list[dict] = []
    if undetermined:
        items.append({
            "severity": "HIGH",
            "title": f"{len(undetermined)} escalated case(s) with no determination",
            "detail": "The platform refused to decide these and nobody has yet recorded "
                      "what happens next. They are the oldest open question on the estate.",
        })
    if desk["totals"]["regressions"]:
        items.append({
            "severity": "HIGH",
            "title": f"{desk['totals']['regressions']} sign-off(s) since reversed",
            "detail": "A property was signed off and has since moved to a stricter state. "
                      "This is what a buyer experiences as the platform changing its mind.",
        })
    rate = desk["totals"]["desk_agreement_rate"]
    if rate is not None and rate < 80:
        items.append({
            "severity": "MEDIUM",
            "title": f"Desk agreement with the pipeline is {rate}%",
            "detail": "Human examination and the automated indicators are diverging often. "
                      "Either the indicators are firing where they should not, or the "
                      "examinations are missing something. Both are worth knowing.",
        })
    if unassigned:
        items.append({
            "severity": "MEDIUM",
            "title": f"{len(unassigned)} propert(y/ies) with no verifier",
            "detail": "Nobody is accountable for these files.",
        })
    if desk["totals"]["open"]:
        items.append({
            "severity": "LOW",
            "title": f"{desk['totals']['open']} assignment(s) still open",
            "detail": "Normal workload; listed so the queue depth is visible.",
        })
    if not items:
        items.append({
            "severity": "INFO",
            "title": "Nothing requires attention",
            "detail": "Every property is assigned, every escalation determined, and no "
                      "sign-off has been reversed.",
        })
    return items
