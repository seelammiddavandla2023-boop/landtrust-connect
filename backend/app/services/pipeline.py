"""
End-to-end orchestration.

    ingest_document()   file → Document + DocumentPage + Claim rows
    reassess()          claims → contradictions → verification → risk → state → plan

`reassess` is the heartbeat of the system: it runs after every upload, every
consent decision and every applied resolution action, and it recomputes the whole
evidence picture from scratch.  Recomputing rather than patching is what guarantees
that what the UI shows is always the current consequence of the current evidence.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..domain import (
    AuditAction,
    ClaimType,
    DocumentStatus,
    DocumentType,
    ExtractionMode,
    OwnershipEventType,
    PIPELINE_ORDER,
    Role,
    is_parcel_claim,
    TransactionState,
    sensitivity_of,
)
from ..models import (
    Claim,
    ClaimSupport,
    Contradiction,
    Document,
    DocumentPage,
    OwnershipEvent,
    Property,
    ResolutionAction,
    RiskAssessment,
    RiskFactor,
    Transaction,
    utcnow,
)
from . import audit
from .contradiction_engine.engine import detect
from .extractor.service import analyse
from .normalization import normalise, parse_date, parse_money_inr
from .privacy import consent as consent_service
from .resolution_planner.planner import plan as build_plan
from .risk_engine.engine import blocked_actions, compute
from .risk_engine.rules import RiskContext
from .verification import resolver as verification
from .verification import temporal


# ---------------------------------------------------------------------------
@dataclass
class StageLog:
    stage: str
    status: str
    detail: str
    duration_ms: int = 0


@dataclass
class IngestResult:
    document: Document
    claims: list[Claim]
    stages: list[StageLog] = field(default_factory=list)


def _store_file(src: Path, property_id: str, filename: str) -> Path:
    target_dir = settings.storage_dir / property_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    counter = 1
    while target.exists():
        target = target_dir / f"{Path(filename).stem}_{counter}{Path(filename).suffix}"
        counter += 1
    shutil.copyfile(src, target)
    return target


def ingest_document(
    db: Session,
    property_obj: Property,
    source_path: Path,
    filename: str | None = None,
    mode: str | None = None,
    uploaded_by_role: Role = Role.OWNER,
    actor_name: str = "owner",
    copy_file: bool = True,
) -> IngestResult:
    """Run the Document Intelligence pipeline over one file and persist the result."""
    filename = filename or source_path.name
    stages: list[StageLog] = []

    stored = _store_file(source_path, property_obj.id, filename) if copy_file else source_path
    stages.append(StageLog("UPLOADING", "OK", f"Stored as {stored.name}",))

    size = stored.stat().st_size
    if size == 0:
        stages.append(StageLog("FILE_VALIDATION", "FAILED", "File is empty."))
        raise ValueError("Uploaded file is empty.")
    stages.append(
        StageLog("FILE_VALIDATION", "OK",
                 f"{size / 1024:.0f} KB, extension {stored.suffix or 'none'} accepted.")
    )

    analysis = analyse(stored, mode, filename)
    stages.append(
        StageLog(
            "CLASSIFICATION", "OK",
            f"{analysis.classification.doc_type.value} "
            f"({analysis.classification.confidence:.0%} confidence)"
            + (f", runner-up {analysis.classification.runner_up.value}"
               if analysis.classification.runner_up else ""),
        )
    )
    stages.append(
        StageLog(
            "OCR", "OK",
            f"{analysis.text.engine}: {len(analysis.text.pages)} page(s), mean text confidence "
            f"{analysis.text.mean_confidence:.0%}",
            analysis.text.duration_ms,
        )
    )
    stages.append(
        StageLog(
            "LAYOUT_ANALYSIS", "OK",
            f"{sum(len(p.layout_blocks) for p in analysis.text.pages)} layout blocks, "
            f"{sum(len(p.words) for p in analysis.text.pages)} words positioned.",
        )
    )

    document = Document(
        property_id=property_obj.id,
        filename=filename,
        storage_path=str(stored),
        mime_type="application/pdf" if stored.suffix.lower() == ".pdf" else "application/octet-stream",
        size_bytes=size,
        checksum=analysis.quality.checksum,
        doc_type=analysis.classification.doc_type.value,
        classification_confidence=analysis.classification.confidence,
        classification_signals=analysis.classification.signals,
        status=DocumentStatus.PROCESSED.value,
        extraction_mode=analysis.text.mode.value,
        ocr_engine=analysis.text.engine,
        page_count=len(analysis.text.pages),
        processing_ms=analysis.duration_ms,
        issued_on=(
            datetime.combine(analysis.quality.issued_on, datetime.min.time())
            if analysis.quality.issued_on else None
        ),
        valid_until=(
            datetime.combine(analysis.quality.valid_until, datetime.min.time())
            if analysis.quality.valid_until else None
        ),
        is_expired=analysis.quality.is_expired,
        integrity_flags=analysis.quality.as_json(),
        quality_score=analysis.quality.quality_score,
        uploaded_by_role=uploaded_by_role.value,
    )
    db.add(document)
    db.flush()

    for page in analysis.text.pages:
        db.add(
            DocumentPage(
                document_id=document.id,
                page_number=page.page_number,
                text=page.text,
                ocr_confidence=page.ocr_confidence,
                width=page.width,
                height=page.height,
                layout_blocks=page.layout_blocks,
            )
        )

    created: list[Claim] = []
    for extracted in analysis.claims:
        # Document-scoped attributes are metadata about this instrument, not assertions
        # about the parcel. Routing them here keeps the claim store to facts that are
        # genuinely comparable across documents.
        if not is_parcel_claim(extracted.claim_type, document.doc_type):
            if extracted.claim_type == ClaimType.DOCUMENT_NUMBER.value:
                document.reference_number = extracted.value
            elif extracted.claim_type == ClaimType.REGISTRATION_DATE.value:
                d = parse_date(extracted.value)
                if d:
                    document.instrument_date = datetime.combine(d, datetime.min.time())
            continue

        norm = normalise(extracted.claim_type, extracted.value)
        claim = Claim(
            property_id=property_obj.id,
            document_id=document.id,
            claim_type=extracted.claim_type,
            value=extracted.value,
            normalized_value=norm.text,
            numeric_value=norm.number,
            source_page=extracted.page,
            source_span=extracted.source_span,
            source_region=extracted.region or {},
            confidence=extracted.confidence,
            extraction_method=extracted.method,
            sensitivity=sensitivity_of(extracted.claim_type).value,
            is_owner_declared=(
                document.doc_type == DocumentType.OWNER_DECLARATION.value
            ),
        )
        db.add(claim)
        created.append(claim)
        if extracted.claim_type == ClaimType.DOCUMENT_NUMBER.value:
            document.reference_number = extracted.value
        elif extracted.claim_type == ClaimType.REGISTRATION_DATE.value:
            d = parse_date(extracted.value)
            if d:
                document.instrument_date = datetime.combine(d, datetime.min.time())
    db.flush()

    stages.append(
        StageLog("CLAIM_EXTRACTION", "OK",
                 f"{len(created)} claim(s) extracted with page-level provenance.")
    )
    stages.append(
        StageLog("EVIDENCE_LINKING", "OK",
                 f"{sum(1 for c in created if c.source_region)} claim(s) anchored to a source "
                 "region on the page.")
    )

    _derive_ownership_events(db, property_obj, document, created)

    audit.record(
        db, AuditAction.DOCUMENT_UPLOADED,
        property_id=property_obj.id, actor_role=uploaded_by_role, actor_name=actor_name,
        summary=f"'{filename}' uploaded ({size / 1024:.0f} KB).",
        evidence_refs=[{"kind": "document", "id": document.id, "label": filename, "page": 1}],
        payload={"size_bytes": size},
    )
    audit.record(
        db, AuditAction.DOCUMENT_CLASSIFIED,
        property_id=property_obj.id, actor_role=Role.ADMIN, actor_name="classifier",
        summary=f"'{filename}' classified as {document.doc_type} at "
                f"{document.classification_confidence:.0%} confidence.",
        payload={"signals": document.classification_signals},
    )
    audit.record(
        db, AuditAction.OCR_EXECUTED,
        property_id=property_obj.id, actor_role=Role.ADMIN, actor_name=analysis.text.engine,
        summary=f"Text acquired from {len(analysis.text.pages)} page(s) in "
                f"{analysis.text.mode.value} mode at {analysis.text.mean_confidence:.0%} mean "
                "confidence.",
        payload={"engine": analysis.text.engine, "duration_ms": analysis.text.duration_ms},
    )
    for claim in created:
        audit.record(
            db, AuditAction.CLAIM_EXTRACTED,
            property_id=property_obj.id, actor_role=Role.ADMIN, actor_name="extractor",
            summary=f"{claim.claim_type} = '{claim.value}' from {filename} page "
                    f"{claim.source_page} at {claim.confidence:.0%} confidence.",
            evidence_refs=[{"kind": "claim", "id": claim.id, "label": claim.claim_type,
                            "page": claim.source_page, "document_id": document.id}],
        )

    return IngestResult(document=document, claims=created, stages=stages)


def _derive_ownership_events(db: Session, property_obj: Property, document: Document,
                             claims: list[Claim]) -> None:
    """Turn a processed document into temporal ownership-graph events."""
    by_type = {c.claim_type: c for c in claims}

    def value(ct: ClaimType) -> str | None:
        c = by_type.get(ct.value)
        return c.value if c else None

    reg = parse_date(value(ClaimType.REGISTRATION_DATE) or "")
    if reg is None and document.instrument_date:
        reg = document.instrument_date.date()
    issued = document.issued_on.date() if document.issued_on else None

    if document.doc_type == DocumentType.SALE_DEED.value:
        when = reg or issued
        if when:
            db.add(
                OwnershipEvent(
                    property_id=property_obj.id,
                    event_type=OwnershipEventType.SALE_DEED_REGISTERED.value,
                    occurred_on=datetime.combine(when, datetime.min.time()),
                    from_party=value(ClaimType.SELLER_NAME),
                    to_party=value(ClaimType.OWNER_NAME),
                    amount_inr=parse_money_inr(value(ClaimType.CONSIDERATION_VALUE) or ""),
                    description=f"Sale deed registered ({document.filename})",
                    evidence_document_id=document.id,
                    evidence_page=(by_type.get(ClaimType.REGISTRATION_DATE.value).source_page
                                   if by_type.get(ClaimType.REGISTRATION_DATE.value) else 1),
                    confidence=0.95,
                )
            )
    elif document.doc_type == DocumentType.MORTGAGE_DOCUMENT.value:
        when = reg or issued
        if when:
            db.add(
                OwnershipEvent(
                    property_id=property_obj.id,
                    event_type=OwnershipEventType.MORTGAGE_CREATED.value,
                    occurred_on=datetime.combine(when, datetime.min.time()),
                    counterparty=value(ClaimType.MORTGAGE_LENDER),
                    amount_inr=parse_money_inr(value(ClaimType.MORTGAGE_AMOUNT) or ""),
                    description=f"Charge created ({document.filename})",
                    evidence_document_id=document.id,
                    confidence=0.93,
                )
            )
    elif document.doc_type == DocumentType.BANK_NOC.value:
        when = issued or date.today()
        db.add(
            OwnershipEvent(
                property_id=property_obj.id,
                event_type=OwnershipEventType.MORTGAGE_RELEASED.value,
                occurred_on=datetime.combine(when, datetime.min.time()),
                counterparty=value(ClaimType.MORTGAGE_LENDER),
                description=f"Lender release recorded ({document.filename})",
                evidence_document_id=document.id,
                confidence=0.95,
            )
        )
    elif document.doc_type == DocumentType.POWER_OF_ATTORNEY.value:
        expiry = parse_date(value(ClaimType.AUTHORIZATION_EXPIRY) or "")
        granted_on = reg or issued
        if granted_on:
            db.add(
                OwnershipEvent(
                    property_id=property_obj.id,
                    event_type=OwnershipEventType.POA_GRANTED.value,
                    occurred_on=datetime.combine(granted_on, datetime.min.time()),
                    from_party=value(ClaimType.POA_GRANTOR),
                    to_party=value(ClaimType.POA_HOLDER),
                    description=f"Power of attorney granted ({document.filename})",
                    evidence_document_id=document.id,
                    confidence=0.92,
                )
            )
        if expiry and expiry < date.today():
            db.add(
                OwnershipEvent(
                    property_id=property_obj.id,
                    event_type=OwnershipEventType.POA_EXPIRED.value,
                    occurred_on=datetime.combine(expiry, datetime.min.time()),
                    from_party=value(ClaimType.POA_GRANTOR),
                    to_party=value(ClaimType.POA_HOLDER),
                    description="Authorisation lapsed",
                    evidence_document_id=document.id,
                    is_disputed=True,
                    confidence=0.95,
                )
            )
    elif document.doc_type == DocumentType.TAX_RECEIPT.value and issued:
        db.add(
            OwnershipEvent(
                property_id=property_obj.id,
                event_type=OwnershipEventType.TAX_PAID.value,
                occurred_on=datetime.combine(issued, datetime.min.time()),
                to_party=value(ClaimType.TAXPAYER_NAME),
                description=f"Property tax {value(ClaimType.TAX_STATUS) or 'recorded'}",
                evidence_document_id=document.id,
                confidence=0.9,
            )
        )


# ---------------------------------------------------------------------------
def build_context(db: Session, property_obj: Property, today: date | None = None) -> RiskContext:
    from ..models import ConsentRequest, Message

    claims = db.scalars(select(Claim).where(Claim.property_id == property_obj.id)).all()
    documents = db.scalars(select(Document).where(Document.property_id == property_obj.id)).all()
    contradictions = db.scalars(
        select(Contradiction).where(Contradiction.property_id == property_obj.id)
    ).all()
    messages = db.scalars(select(Message).where(Message.property_id == property_obj.id)).all()
    consents = db.scalars(
        select(ConsentRequest).where(ConsentRequest.property_id == property_obj.id)
    ).all()
    txn = db.scalars(
        select(Transaction).where(Transaction.property_id == property_obj.id)
    ).first()

    support_edges = db.scalars(
        select(ClaimSupport).where(ClaimSupport.property_id == property_obj.id)
    ).all()
    outcome = verification.resolve(list(claims), list(documents), list(support_edges),
                                   list(contradictions), today)
    return RiskContext(
        property=property_obj,
        claims=list(claims),
        documents=list(documents),
        contradictions=list(contradictions),
        outcome=outcome,
        transaction=txn,
        messages=list(messages),
        consent_requests=list(consents),
        today=today or date.today(),
        # Rules closed by evidence the platform cannot verify automatically (a notarised
        # affidavit, a registrar's written confirmation). Each closure names the document
        # that produced it — see Property.closed_rules and the audit trail.
        suppressed={e.get("rule_id") for e in (property_obj.closed_rules or []) if e.get("rule_id")},
    )


def reassess(
    db: Session,
    property_obj: Property,
    actor_role: Role = Role.ADMIN,
    actor_name: str = "system",
    reason: str = "Evidence set changed",
    today: date | None = None,
) -> RiskAssessment:
    """
    Recompute contradictions, verification statuses, risk, transaction state and the
    resolution plan for one property, and persist all of it.
    """
    today = today or date.today()
    claims = list(db.scalars(select(Claim).where(Claim.property_id == property_obj.id)).all())
    documents = list(
        db.scalars(select(Document).where(Document.property_id == property_obj.id)).all()
    )

    # --- 0. temporal scoping -------------------------------------------------
    # Decide which claims state the *current* position before anything compares them,
    # so a chain of title is not mistaken for a set of contradictions.
    supersessions = temporal.apply_supersession(claims, documents)
    db.flush()
    for s in supersessions:
        audit.record(
            db, AuditAction.CLAIM_STATUS_CHANGED,
            property_id=property_obj.id, actor_role=Role.ADMIN, actor_name="temporal-scoper",
            result="SUPERSEDED",
            summary=s.reason,
            evidence_refs=[{"kind": "claim", "id": s.claim_id, "label": "superseded",
                            "page": None, "document_id": s.superseded_by_document_id}],
        )

    # --- 1. contradictions ---------------------------------------------------
    previous_contradictions = db.scalars(
        select(Contradiction).where(Contradiction.property_id == property_obj.id)
    ).all()
    previous_keys = {(c.detection_rule, c.left_value, c.right_value)
                     for c in previous_contradictions}
    for c in previous_contradictions:
        db.delete(c)
    for s in db.scalars(
        select(ClaimSupport).where(ClaimSupport.property_id == property_obj.id)
    ).all():
        db.delete(s)
    db.flush()

    detection = detect(property_obj, list(claims), list(documents), today)

    for edge in detection.supports:
        db.add(
            ClaimSupport(
                property_id=property_obj.id,
                claim_id=edge.claim_id,
                related_claim_id=edge.related_claim_id,
                match_type=edge.match_type,
                is_supporting=edge.is_supporting,
                similarity=edge.similarity,
                note=edge.note,
            )
        )
    contradiction_rows: list[Contradiction] = []
    for rec in detection.contradictions:
        row = Contradiction(
            property_id=property_obj.id,
            contradiction_type=rec.contradiction_type,
            claim_type=rec.claim_type,
            severity=rec.severity,
            left_claim_id=rec.left_claim_id,
            right_claim_id=rec.right_claim_id,
            left_value=rec.left_value,
            right_value=rec.right_value,
            left_source=rec.left_source,
            right_source=rec.right_source,
            difference=rec.difference,
            magnitude=rec.magnitude,
            explanation=rec.explanation,
            detection_rule=rec.detection_rule,
        )
        db.add(row)
        contradiction_rows.append(row)
        key = (rec.detection_rule, rec.left_value, rec.right_value)
        if key not in previous_keys:
            audit.record(
                db, AuditAction.CONTRADICTION_DETECTED,
                property_id=property_obj.id, actor_role=Role.ADMIN,
                actor_name="contradiction-engine",
                result=rec.severity,
                summary=f"{rec.contradiction_type}: {rec.explanation[:280]}",
                payload={"rule": rec.detection_rule, "difference": rec.difference},
            )
    db.flush()

    # --- 2. verification -----------------------------------------------------
    support_edges = db.scalars(
        select(ClaimSupport).where(ClaimSupport.property_id == property_obj.id)
    ).all()
    outcome = verification.resolve(list(claims), list(documents), list(support_edges),
                                   contradiction_rows, today)
    changes = verification.apply(list(claims), outcome)
    for claim_id, old, new in changes:
        audit.record(
            db, AuditAction.CLAIM_STATUS_CHANGED,
            property_id=property_obj.id, actor_role=Role.ADMIN, actor_name="verification-resolver",
            result=new,
            summary=f"Claim {claim_id} moved {old} → {new}.",
            evidence_refs=[{"kind": "claim", "id": claim_id, "label": new, "page": None}],
        )
    db.flush()

    # --- 3. risk + state -----------------------------------------------------
    ctx = build_context(db, property_obj, today)
    ctx.outcome = outcome
    risk = compute(ctx)

    txn = ctx.transaction
    if txn is None:
        txn = Transaction(
            reference=f"TXN-{property_obj.reference.split('-')[-1]}",
            property_id=property_obj.id,
            consideration_inr=property_obj.asking_price_inr,
        )
        db.add(txn)
        db.flush()

    previous_state = txn.state
    txn.state = risk.state.value
    txn.state_reason = risk.state_reason
    txn.blocked_actions = blocked_actions(risk.state)
    if previous_state != txn.state:
        txn.state_changed_at = utcnow()

    assessment = RiskAssessment(
        property_id=property_obj.id,
        transaction_id=txn.id,
        overall_score=risk.overall,
        band=risk.band.value,
        state=risk.state.value,
        state_reason=risk.state_reason,
        category_scores=risk.category_scores(),
        engine_version=risk.engine_version,
    )
    db.add(assessment)
    db.flush()
    for hit in risk.hits:
        db.add(
            RiskFactor(
                assessment_id=assessment.id,
                rule_id=hit.rule_id,
                category=hit.category.value,
                weight=hit.weight,
                severity=hit.severity.value,
                title=hit.title,
                explanation=hit.explanation,
                evidence_refs=hit.evidence_refs,
                is_mitigation=hit.is_mitigation,
            )
        )

    audit.record(
        db, AuditAction.RISK_RECALCULATED,
        property_id=property_obj.id, transaction_id=txn.id,
        actor_role=actor_role, actor_name=actor_name,
        result=risk.band.value,
        summary=f"{reason}. Composite risk {risk.overall:.0f}/100 ({risk.band.value}); "
                f"{len(risk.triggered_rule_ids())} rule(s) triggered.",
        payload={"categories": risk.category_scores(),
                 "rules": sorted(risk.triggered_rule_ids())},
    )
    if previous_state != txn.state:
        action = {
            TransactionState.HOLD.value: AuditAction.TRANSACTION_HELD,
            TransactionState.ESCALATE.value: AuditAction.TRANSACTION_ESCALATED,
            TransactionState.REJECT.value: AuditAction.TRANSACTION_ESCALATED,
        }.get(txn.state, AuditAction.TRANSACTION_RELEASED)
        audit.record(
            db, action,
            property_id=property_obj.id, transaction_id=txn.id,
            actor_role=Role.ADMIN, actor_name="state-controller",
            result=txn.state,
            summary=f"Transaction state {previous_state} → {txn.state}. {risk.state_reason}",
            payload={"blocked_actions": txn.blocked_actions},
        )

    # --- 4. resolution plan --------------------------------------------------
    for old in db.scalars(
        select(ResolutionAction).where(ResolutionAction.property_id == property_obj.id)
    ).all():
        db.delete(old)
    db.flush()

    resolution = build_plan(ctx)
    for step in resolution.steps:
        db.add(
            ResolutionAction(
                property_id=property_obj.id,
                action_key=step.action.key,
                title=step.action.title,
                description=step.action.description,
                required_evidence=step.action.required_evidence,
                responsible_party=step.action.responsible.value,
                authority_required=step.action.authority,
                effort=step.action.effort.value,
                priority=step.priority,
                resolves_rules=step.resolved_rules,
                risk_before=step.risk_before,
                risk_after=step.risk_after,
                state_after=step.state_after.value,
            )
        )
    if resolution.steps:
        audit.record(
            db, AuditAction.RESOLUTION_PLAN_GENERATED,
            property_id=property_obj.id, transaction_id=txn.id,
            actor_role=Role.ADMIN, actor_name="resolution-planner",
            summary=f"{len(resolution.steps)}-step minimum-evidence path computed: "
                    f"{resolution.baseline_risk:.0f} → {resolution.final_risk:.0f} "
                    f"({resolution.baseline_state.value} → {resolution.final_state.value}).",
            payload={"steps": [s.action.key for s in resolution.steps],
                     "reaches_proceed": resolution.reaches_proceed},
        )

    db.commit()
    return assessment
