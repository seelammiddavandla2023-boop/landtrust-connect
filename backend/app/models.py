"""
SQLAlchemy models for LandTrust Connect.

Design note (build brief §27): fields are typed columns, not opaque JSON.  JSON is
used only where the payload is genuinely heterogeneous — OCR bounding regions, rule
parameters and simulation snapshots.

Entity map
----------
User, Property, Document, DocumentPage, Claim, ClaimSupport, Contradiction,
OwnershipEvent, ConsentRequest, Message, Transaction, RiskAssessment, RiskFactor,
ResolutionAction, AuditEvent, AssistantQuery.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .domain import (
    ActionEffort,
    ActionStatus,
    ConsentStatus,
    ContradictionType,
    DocumentStatus,
    DocumentType,
    ExtractionMode,
    MatchType,
    OwnershipEventType,
    ResponsibleParty,
    RiskBand,
    RiskCategory,
    Role,
    Severity,
    TransactionState,
    VerificationStatus,
)


def _uuid() -> str:
    return uuid.uuid4().hex[:16]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------------------
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(32), default=Role.BUYER.value)
    organisation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Masked in every buyer-facing response; stored to demonstrate redaction.
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    identity_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    properties: Mapped[list["Property"]] = relationship(back_populates="owner")


# ---------------------------------------------------------------------------
class Property(Base, TimestampMixin):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(48), unique=True)  # e.g. LTC-PR-0001
    survey_number: Mapped[str] = mapped_column(String(64))
    district: Mapped[str] = mapped_column(String(120))
    village: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(120), default="Tamil Nadu")
    property_type: Mapped[str] = mapped_column(String(64), default="Residential Plot")
    claimed_area_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    guideline_value_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    asking_price_inr: Mapped[float | None] = mapped_column(Float, nullable=True)

    # What the *listing* asserts.  Deliberately separate from any verified claim —
    # a listing assertion has no evidential weight until documents support it.
    listed_owner_name: Mapped[str | None] = mapped_column(String(160), nullable=True)

    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    scenario_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scenario_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Risk rules closed by evidence that the platform cannot verify automatically —
    # a notarised affidavit, a registrar's confirmation. Each entry cites the action
    # and the document that closed it, so a closure is never anonymous.
    # [{rule_id, action_key, document_id, closed_at, note}]
    closed_rules: Mapped[list] = mapped_column(JSON, default=list)

    owner: Mapped[User | None] = relationship(back_populates="properties")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    contradictions: Mapped[list["Contradiction"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    ownership_events: Mapped[list["OwnershipEvent"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    doc_type: Mapped[str] = mapped_column(String(48), default=DocumentType.UNKNOWN.value)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classification_signals: Mapped[dict] = mapped_column(JSON, default=dict)

    # Attributes OF the document rather than of the parcel. A certificate's own number
    # and date are not facts about the land, so they are stored here instead of in the
    # claim store — otherwise the contradiction engine would compare an encumbrance
    # certificate's number against a deed's number and report a conflict between two
    # values that were never describing the same thing.
    reference_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    instrument_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=DocumentStatus.UPLOADED.value)
    extraction_mode: Mapped[str] = mapped_column(String(16), default=ExtractionMode.DEMO.value)
    ocr_engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    processing_ms: Mapped[int] = mapped_column(Integer, default=0)

    # Authenticity / quality indicators — indicators only, never legal conclusions.
    issued_on: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False)
    integrity_flags: Mapped[list] = mapped_column(JSON, default=list)
    quality_score: Mapped[float] = mapped_column(Float, default=1.0)
    is_duplicate_of: Mapped[str | None] = mapped_column(String(32), nullable=True)

    uploaded_by_role: Mapped[str] = mapped_column(String(32), default=Role.OWNER.value)
    # For the resolution simulator: a document staged but not yet "obtained".
    is_pending_evidence: Mapped[bool] = mapped_column(Boolean, default=False)

    property: Mapped[Property] = relationship(back_populates="documents")
    pages: Mapped[list["DocumentPage"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    ocr_confidence: Mapped[float] = mapped_column(Float, default=1.0)
    width: Mapped[float] = mapped_column(Float, default=595.0)
    height: Mapped[float] = mapped_column(Float, default=842.0)
    layout_blocks: Mapped[list] = mapped_column(JSON, default=list)

    document: Mapped[Document] = relationship(back_populates="pages")


# ---------------------------------------------------------------------------
class Claim(Base, TimestampMixin):
    """
    A single land detail asserted by a single document.

    `verification_status` is NEVER set by the extractor.  It is written only by
    services.verification.resolver, from the cross-document evidence set.
    """

    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)

    claim_type: Mapped[str] = mapped_column(String(48), index=True)
    value: Mapped[str] = mapped_column(String(512))
    normalized_value: Mapped[str] = mapped_column(String(512), default="")
    numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_page: Mapped[int] = mapped_column(Integer, default=1)
    source_span: Mapped[str | None] = mapped_column(Text, nullable=True)  # snippet of source text
    source_region: Mapped[dict] = mapped_column(JSON, default=dict)  # {x,y,w,h} normalised 0..1
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    extraction_method: Mapped[str] = mapped_column(String(32), default=ExtractionMode.DEMO.value)

    verification_status: Mapped[str] = mapped_column(
        String(32), default=VerificationStatus.UNVERIFIED.value
    )
    status_explanation: Mapped[str] = mapped_column(Text, default="")
    sensitivity: Mapped[str] = mapped_column(String(16), default="PUBLIC")
    is_owner_declared: Mapped[bool] = mapped_column(Boolean, default=False)
    superseded: Mapped[bool] = mapped_column(Boolean, default=False)

    property: Mapped[Property] = relationship(back_populates="claims")
    document: Mapped[Document | None] = relationship(back_populates="claims")


class ClaimSupport(Base):
    """
    A directed evidence relation between two claims of the same type.

    match_type records HOW the two values relate — the material that both the
    verification resolver and the Claim-Evidence Matrix render.
    """

    __tablename__ = "claim_supports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    related_claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    match_type: Mapped[str] = mapped_column(String(32), default=MatchType.EXACT_MATCH.value)
    is_supporting: Mapped[bool] = mapped_column(Boolean, default=True)
    similarity: Mapped[float] = mapped_column(Float, default=1.0)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
class Contradiction(Base, TimestampMixin):
    __tablename__ = "contradictions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    contradiction_type: Mapped[str] = mapped_column(String(48))
    claim_type: Mapped[str] = mapped_column(String(48))
    severity: Mapped[str] = mapped_column(String(16), default=Severity.MEDIUM.value)

    left_claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    right_claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    left_value: Mapped[str] = mapped_column(String(512), default="")
    right_value: Mapped[str] = mapped_column(String(512), default="")
    left_source: Mapped[str] = mapped_column(String(255), default="")
    right_source: Mapped[str] = mapped_column(String(255), default="")
    difference: Mapped[str] = mapped_column(String(255), default="")
    magnitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    explanation: Mapped[str] = mapped_column(Text, default="")
    detection_rule: Mapped[str] = mapped_column(String(64), default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_note: Mapped[str] = mapped_column(Text, default="")

    property: Mapped[Property] = relationship(back_populates="contradictions")


# ---------------------------------------------------------------------------
class OwnershipEvent(Base):
    """A node/edge source for the temporal ownership graph."""

    __tablename__ = "ownership_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    event_type: Mapped[str] = mapped_column(String(48))
    occurred_on: Mapped[datetime] = mapped_column(DateTime)
    from_party: Mapped[str | None] = mapped_column(String(160), nullable=True)
    to_party: Mapped[str | None] = mapped_column(String(160), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. lender
    amount_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True
    )
    evidence_page: Mapped[int] = mapped_column(Integer, default=1)
    is_disputed: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    property: Mapped[Property] = relationship(back_populates="ownership_events")


# ---------------------------------------------------------------------------
class ConsentRequest(Base, TimestampMixin):
    __tablename__ = "consent_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    requester_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    items: Mapped[list] = mapped_column(JSON, default=list)  # DisclosureItem values
    purpose: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default=ConsentStatus.REQUESTED.value)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    granted_items: Mapped[list] = mapped_column(JSON, default=list)
    denied_items: Mapped[list] = mapped_column(JSON, default=list)
    decision_note: Mapped[str] = mapped_column(Text, default="")


# ---------------------------------------------------------------------------
class Message(Base):
    """Property-scoped relay message.  Contact details are never carried here."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    sender_role: Mapped[str] = mapped_column(String(32))
    sender_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    redacted_body: Mapped[str] = mapped_column(Text, default="")
    contained_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    sensitive_kinds: Mapped[list] = mapped_column(JSON, default=list)
    references_claim_id: Mapped[str | None] = mapped_column(ForeignKey("claims.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Roles that have opened the thread since this message arrived. A list rather
    # than a single flag because the same message is unread for the owner and the
    # buyer independently, and a relay with more than two parties on it should not
    # need a schema change.
    read_by: Mapped[list] = mapped_column(JSON, default=list)


# ---------------------------------------------------------------------------
class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    reference: Mapped[str] = mapped_column(String(48), unique=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    buyer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default=TransactionState.WARN.value)
    state_reason: Mapped[str] = mapped_column(Text, default="")
    state_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    consideration_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    stage: Mapped[str] = mapped_column(String(48), default="DUE_DILIGENCE")
    blocked_actions: Mapped[list] = mapped_column(JSON, default=list)

    property: Mapped[Property] = relationship(back_populates="transactions")
    assessments: Mapped[list["RiskAssessment"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    band: Mapped[str] = mapped_column(String(16), default=RiskBand.LOW.value)
    state: Mapped[str] = mapped_column(String(32), default=TransactionState.PROCEED.value)
    state_reason: Mapped[str] = mapped_column(Text, default="")
    category_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    engine_version: Mapped[str] = mapped_column(String(32), default="rules-1.0")
    is_simulation: Mapped[bool] = mapped_column(Boolean, default=False)
    simulation_label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    transaction: Mapped[Transaction | None] = relationship(back_populates="assessments")
    factors: Mapped[list["RiskFactor"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class RiskFactor(Base):
    """One triggered rule.  Every score is reconstructable from these rows."""

    __tablename__ = "risk_factors"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(ForeignKey("risk_assessments.id"))
    rule_id: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32), default=RiskCategory.DOCUMENT.value)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(16), default=Severity.MEDIUM.value)
    title: Mapped[str] = mapped_column(String(200), default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    is_mitigation: Mapped[bool] = mapped_column(Boolean, default=False)

    assessment: Mapped[RiskAssessment] = relationship(back_populates="factors")


# ---------------------------------------------------------------------------
class ResolutionAction(Base, TimestampMixin):
    __tablename__ = "resolution_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    action_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    required_evidence: Mapped[str] = mapped_column(String(255), default="")
    responsible_party: Mapped[str] = mapped_column(
        String(32), default=ResponsibleParty.OWNER.value
    )
    authority_required: Mapped[str] = mapped_column(String(200), default="")
    effort: Mapped[str] = mapped_column(String(16), default=ActionEffort.MEDIUM.value)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    resolves_rules: Mapped[list] = mapped_column(JSON, default=list)
    risk_before: Mapped[float] = mapped_column(Float, default=0.0)
    risk_after: Mapped[float] = mapped_column(Float, default=0.0)
    state_after: Mapped[str] = mapped_column(String(32), default=TransactionState.HOLD.value)
    status: Mapped[str] = mapped_column(String(32), default=ActionStatus.RECOMMENDED.value)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(32), default=Role.ADMIN.value)
    actor_name: Mapped[str] = mapped_column(String(160), default="system")
    action: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(64), default="OK")
    summary: Mapped[str] = mapped_column(Text, default="")
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


# ---------------------------------------------------------------------------
class AssistantQuery(Base):
    """Every assistant exchange is logged so grounding behaviour is measurable."""

    __tablename__ = "assistant_queries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str | None] = mapped_column(ForeignKey("properties.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(64), default="UNKNOWN")
    answer_kind: Mapped[str] = mapped_column(String(32), default="REFUSED")
    answer: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list)
    backend: Mapped[str] = mapped_column(String(32), default="deterministic")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------------------
class VerificationAssignment(Base, TimestampMixin):
    """
    A property placed on a named verifier's desk.

    The platform derives a verification *status* from evidence, and nothing here
    changes that. What an assignment adds is accountability for the human work
    around it: who onboarded this property, who is responsible for examining the
    documents the machine flagged, and whether that examination has happened.

    `onboarded_by_verifier` records that this verifier brought the property onto
    the platform, which is a different contribution from reviewing it and is
    counted separately in the supervisor's figures.
    """

    __tablename__ = "verification_assignments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    verifier_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="ASSIGNED", index=True)
    onboarded_by_verifier: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # The transaction state when the verifier signed the property off. Comparing
    # it with the state now is how "did their sign-off hold up?" is measured.
    state_at_signoff: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_at_signoff: Mapped[float | None] = mapped_column(Float, nullable=True)

    property: Mapped["Property"] = relationship()
    verifier: Mapped["User"] = relationship()


class VerifierFinding(Base):
    """
    A verifier's recorded examination of a flagged document.

    This is deliberately **evidence, not approval**. A verifier does not decide
    that a claim is verified — the resolver does that from the evidence set. What
    a verifier can establish is a fact the platform cannot compute from the file
    alone: whether the physical document matches the original held by the issuing
    office. That fact then feeds the same machinery as any other evidence.

    An `agrees_with_platform` value is stored at write time by comparing the
    finding with the integrity indicators the pipeline computed. It is the basis
    of the accuracy figure a supervisor sees, and it is recorded rather than
    recomputed so that a later change to the rules cannot silently rewrite a
    person's record.
    """

    __tablename__ = "verifier_findings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("verification_assignments.id"), nullable=True, index=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    verifier_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True)
    outcome: Mapped[str] = mapped_column(String(48))
    note: Mapped[str] = mapped_column(Text, default="")
    agrees_with_platform: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    property: Mapped["Property"] = relationship()
    document: Mapped["Document"] = relationship()
    verifier: Mapped["User"] = relationship()


class EscalationDetermination(Base):
    """
    A legal reviewer's decision on a case the platform refused to decide.

    The state controller escalates rather than guessing when seller authority
    cannot be established. Until now that escalation had no destination: the case
    said "refer to a legal reviewer" and nothing further happened. This is where
    it lands, and the determination is recorded with its reasoning in the audit
    trail rather than silently changing a score.
    """

    __tablename__ = "escalation_determinations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    outcome: Mapped[str] = mapped_column(String(48))
    reasoning: Mapped[str] = mapped_column(Text, default="")
    state_at_review: Mapped[str] = mapped_column(String(32), default="")
    risk_at_review: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    property: Mapped["Property"] = relationship()
    reviewer: Mapped["User"] = relationship()
