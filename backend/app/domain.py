"""
LandTrust Connect — canonical domain vocabulary.

This module is the single source of truth for every enumerated value used by the
backend, the evaluation harness and (mirrored in `frontend/lib/domain.ts`) the UI.

Research note
-------------
The central claim of LandTrust Connect is that a *claim* (a single land detail such
as "owner name" or "area") is a first-class object which carries its own evidence
and its own verification status.  A claim is therefore never a bare string: it is a
(value, provenance, confidence, status) tuple.  The enums below encode the state
space of that tuple.
"""
from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String-valued enum so values serialise directly to JSON."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
class Role(StrEnum):
    OWNER = "OWNER"
    BUYER = "BUYER"
    VERIFIER = "VERIFIER"
    LEGAL_REVIEWER = "LEGAL_REVIEWER"
    ADMIN = "ADMIN"


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
class DocumentType(StrEnum):
    SALE_DEED = "SALE_DEED"
    ENCUMBRANCE_CERTIFICATE = "ENCUMBRANCE_CERTIFICATE"
    SURVEY_RECORD = "SURVEY_RECORD"
    TAX_RECEIPT = "TAX_RECEIPT"
    IDENTITY_PROOF = "IDENTITY_PROOF"
    POWER_OF_ATTORNEY = "POWER_OF_ATTORNEY"
    MORTGAGE_DOCUMENT = "MORTGAGE_DOCUMENT"
    BANK_NOC = "BANK_NOC"
    OWNER_DECLARATION = "OWNER_DECLARATION"
    AFFIDAVIT = "AFFIDAVIT"
    UNKNOWN = "UNKNOWN"


DOCUMENT_TYPE_LABELS = {
    DocumentType.SALE_DEED: "Sale Deed",
    DocumentType.ENCUMBRANCE_CERTIFICATE: "Encumbrance Certificate",
    DocumentType.SURVEY_RECORD: "Survey Record",
    DocumentType.TAX_RECEIPT: "Tax Receipt",
    DocumentType.IDENTITY_PROOF: "Identity Proof",
    DocumentType.POWER_OF_ATTORNEY: "Power of Attorney",
    DocumentType.MORTGAGE_DOCUMENT: "Mortgage Document",
    DocumentType.BANK_NOC: "Bank NOC / Release Letter",
    DocumentType.OWNER_DECLARATION: "Owner Declaration (self-reported)",
    DocumentType.AFFIDAVIT: "Sworn Affidavit",
    DocumentType.UNKNOWN: "Unclassified Document",
}


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"


class PipelineStage(StrEnum):
    """Ordered stages shown by the Document Intelligence pipeline UI."""

    UPLOADING = "UPLOADING"
    FILE_VALIDATION = "FILE_VALIDATION"
    CLASSIFICATION = "CLASSIFICATION"
    OCR = "OCR"
    LAYOUT_ANALYSIS = "LAYOUT_ANALYSIS"
    CLAIM_EXTRACTION = "CLAIM_EXTRACTION"
    EVIDENCE_LINKING = "EVIDENCE_LINKING"
    CROSS_DOCUMENT_VALIDATION = "CROSS_DOCUMENT_VALIDATION"
    RISK_UPDATE = "RISK_UPDATE"
    COMPLETE = "COMPLETE"


PIPELINE_ORDER = [
    PipelineStage.UPLOADING,
    PipelineStage.FILE_VALIDATION,
    PipelineStage.CLASSIFICATION,
    PipelineStage.OCR,
    PipelineStage.LAYOUT_ANALYSIS,
    PipelineStage.CLAIM_EXTRACTION,
    PipelineStage.EVIDENCE_LINKING,
    PipelineStage.CROSS_DOCUMENT_VALIDATION,
    PipelineStage.RISK_UPDATE,
    PipelineStage.COMPLETE,
]


class ExtractionMode(StrEnum):
    """The extraction service is modular: DEMO works with no models or API keys."""

    DEMO = "DEMO"          # deterministic template-driven parse of synthetic documents
    OCR = "OCR"            # real text-layer / Tesseract OCR extraction
    LLM = "LLM"            # reserved: LLM-assisted extraction when a key is configured


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------
class ClaimType(StrEnum):
    OWNER_NAME = "owner_name"
    SELLER_NAME = "seller_name"
    BUYER_NAME = "buyer_name"
    SURVEY_NUMBER = "survey_number"
    PROPERTY_AREA = "property_area"
    PROPERTY_TYPE = "property_type"
    DISTRICT = "district"
    VILLAGE = "village"
    REGISTRATION_DATE = "registration_date"
    DOCUMENT_NUMBER = "document_number"
    MORTGAGE_STATUS = "mortgage_status"
    MORTGAGE_AMOUNT = "mortgage_amount"
    MORTGAGE_LENDER = "mortgage_lender"
    ENCUMBRANCE_PERIOD = "encumbrance_period"
    TAXPAYER_NAME = "taxpayer_name"
    TAX_STATUS = "tax_status"
    POA_HOLDER = "poa_holder"
    POA_GRANTOR = "poa_grantor"
    AUTHORIZATION_EXPIRY = "authorization_expiry"
    CONSIDERATION_VALUE = "consideration_value"
    BOUNDARY_DESCRIPTION = "boundary_description"
    IDENTITY_NUMBER = "identity_number"
    OWNER_PHONE = "owner_phone"
    OWNER_ADDRESS = "owner_address"
    # An assertion that two name forms denote the same person. Sworn separately
    # and treated as evidence about the *relationship between two names*, which is
    # what reconciles a variant rather than merely asserting one form is right.
    NAME_EQUIVALENCE = "name_equivalence"


CLAIM_TYPE_LABELS = {
    ClaimType.OWNER_NAME: "Owner Name",
    ClaimType.SELLER_NAME: "Seller Name",
    ClaimType.BUYER_NAME: "Buyer Name",
    ClaimType.SURVEY_NUMBER: "Survey Number",
    ClaimType.PROPERTY_AREA: "Property Area",
    ClaimType.PROPERTY_TYPE: "Property Type",
    ClaimType.DISTRICT: "District",
    ClaimType.VILLAGE: "Village",
    ClaimType.REGISTRATION_DATE: "Registration Date",
    ClaimType.DOCUMENT_NUMBER: "Document Number",
    ClaimType.MORTGAGE_STATUS: "Mortgage / Encumbrance Status",
    ClaimType.MORTGAGE_AMOUNT: "Mortgage Amount",
    ClaimType.MORTGAGE_LENDER: "Mortgage Lender",
    ClaimType.ENCUMBRANCE_PERIOD: "Encumbrance Search Period",
    ClaimType.TAXPAYER_NAME: "Taxpayer Name",
    ClaimType.TAX_STATUS: "Property Tax Status",
    ClaimType.POA_HOLDER: "Power of Attorney Holder",
    ClaimType.POA_GRANTOR: "Power of Attorney Grantor",
    ClaimType.AUTHORIZATION_EXPIRY: "Authorization Expiry",
    ClaimType.CONSIDERATION_VALUE: "Consideration Value",
    ClaimType.BOUNDARY_DESCRIPTION: "Boundary Description",
    ClaimType.IDENTITY_NUMBER: "Identity Document Number",
    ClaimType.OWNER_PHONE: "Owner Phone",
    ClaimType.OWNER_ADDRESS: "Owner Address",
    ClaimType.NAME_EQUIVALENCE: "Name Equivalence (sworn)",
}


class ValueKind(StrEnum):
    """Drives normalisation and comparison strategy in the contradiction engine."""

    PERSON_NAME = "PERSON_NAME"
    IDENTIFIER = "IDENTIFIER"
    NUMERIC = "NUMERIC"
    AREA = "AREA"
    MONEY = "MONEY"
    DATE = "DATE"
    CATEGORICAL = "CATEGORICAL"
    TEXT = "TEXT"


CLAIM_VALUE_KIND = {
    ClaimType.OWNER_NAME: ValueKind.PERSON_NAME,
    ClaimType.SELLER_NAME: ValueKind.PERSON_NAME,
    ClaimType.BUYER_NAME: ValueKind.PERSON_NAME,
    ClaimType.TAXPAYER_NAME: ValueKind.PERSON_NAME,
    ClaimType.POA_HOLDER: ValueKind.PERSON_NAME,
    ClaimType.POA_GRANTOR: ValueKind.PERSON_NAME,
    ClaimType.MORTGAGE_LENDER: ValueKind.TEXT,
    ClaimType.SURVEY_NUMBER: ValueKind.IDENTIFIER,
    ClaimType.DOCUMENT_NUMBER: ValueKind.IDENTIFIER,
    ClaimType.IDENTITY_NUMBER: ValueKind.IDENTIFIER,
    ClaimType.PROPERTY_AREA: ValueKind.AREA,
    ClaimType.MORTGAGE_AMOUNT: ValueKind.MONEY,
    ClaimType.CONSIDERATION_VALUE: ValueKind.MONEY,
    ClaimType.REGISTRATION_DATE: ValueKind.DATE,
    ClaimType.AUTHORIZATION_EXPIRY: ValueKind.DATE,
    ClaimType.MORTGAGE_STATUS: ValueKind.CATEGORICAL,
    ClaimType.TAX_STATUS: ValueKind.CATEGORICAL,
    ClaimType.PROPERTY_TYPE: ValueKind.CATEGORICAL,
    ClaimType.DISTRICT: ValueKind.TEXT,
    ClaimType.VILLAGE: ValueKind.TEXT,
    ClaimType.ENCUMBRANCE_PERIOD: ValueKind.TEXT,
    ClaimType.BOUNDARY_DESCRIPTION: ValueKind.TEXT,
    ClaimType.OWNER_PHONE: ValueKind.IDENTIFIER,
    ClaimType.OWNER_ADDRESS: ValueKind.TEXT,
    ClaimType.NAME_EQUIVALENCE: ValueKind.TEXT,
}


class VerificationStatus(StrEnum):
    """
    Derived — never written by the extractor.

    The extractor produces claims with provenance and confidence only.  The
    VerificationResolver assigns these statuses from the *evidence graph*.  This
    separation is the mechanism that stops a single uploaded document from making a
    claim look officially verified.
    """

    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    CONFLICTING = "CONFLICTING"
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"
    OWNER_PROVIDED = "OWNER_PROVIDED"
    UNVERIFIED = "UNVERIFIED"


# Ordering used for "verification level" roll-ups (higher = stronger).
VERIFICATION_RANK = {
    VerificationStatus.VERIFIED: 6,
    VerificationStatus.PARTIALLY_VERIFIED: 5,
    VerificationStatus.EXPIRED: 4,
    VerificationStatus.OWNER_PROVIDED: 3,
    VerificationStatus.PENDING: 2,
    VerificationStatus.UNVERIFIED: 1,
    VerificationStatus.CONFLICTING: 0,
}


class Sensitivity(StrEnum):
    """Disclosure class — drives the evidence-gated profile and redaction layer."""

    PUBLIC = "PUBLIC"        # visible to any buyer once evidence-supported
    GATED = "GATED"          # visible masked; full value requires owner consent
    RESTRICTED = "RESTRICTED"  # never shown to a buyer in this prototype


CLAIM_SENSITIVITY = {
    ClaimType.IDENTITY_NUMBER: Sensitivity.RESTRICTED,
    ClaimType.OWNER_PHONE: Sensitivity.RESTRICTED,
    ClaimType.OWNER_ADDRESS: Sensitivity.RESTRICTED,
    ClaimType.OWNER_NAME: Sensitivity.GATED,
    ClaimType.SELLER_NAME: Sensitivity.GATED,
    ClaimType.TAXPAYER_NAME: Sensitivity.GATED,
    ClaimType.POA_HOLDER: Sensitivity.GATED,
    ClaimType.POA_GRANTOR: Sensitivity.GATED,
    ClaimType.BUYER_NAME: Sensitivity.RESTRICTED,
    ClaimType.CONSIDERATION_VALUE: Sensitivity.GATED,
    ClaimType.MORTGAGE_AMOUNT: Sensitivity.GATED,
    ClaimType.DOCUMENT_NUMBER: Sensitivity.GATED,
}


def sensitivity_of(claim_type: str) -> Sensitivity:
    return CLAIM_SENSITIVITY.get(ClaimType(claim_type), Sensitivity.PUBLIC)


# Attributes that describe the *document* rather than the *parcel*.  Each is a fact
# about one instrument, so the value is meaningful only in the context of the
# instrument type listed here; claims of these types coming from any other document
# type are stored as document metadata instead of entering the claim store.
#
# Without this distinction, a sale deed's registration date and a mortgage deed's
# registration date look like two answers to one question, and the contradiction
# engine reports a conflict between two facts that were never about the same thing.
INSTRUMENT_SCOPE = {
    ClaimType.DOCUMENT_NUMBER.value: DocumentType.SALE_DEED.value,
    ClaimType.REGISTRATION_DATE.value: DocumentType.SALE_DEED.value,
    ClaimType.CONSIDERATION_VALUE.value: DocumentType.SALE_DEED.value,
    ClaimType.ENCUMBRANCE_PERIOD.value: DocumentType.ENCUMBRANCE_CERTIFICATE.value,
}


def is_parcel_claim(claim_type: str, doc_type: str | None) -> bool:
    """True when this claim belongs in the parcel's claim store."""
    scope = INSTRUMENT_SCOPE.get(claim_type)
    return scope is None or scope == doc_type


# Claim types the system expects for a complete land file.  Absence of an expected
# claim yields PENDING rather than silence — "missing evidence" is itself evidence.
CORE_CLAIM_TYPES = [
    ClaimType.OWNER_NAME,
    ClaimType.SURVEY_NUMBER,
    ClaimType.PROPERTY_AREA,
    ClaimType.REGISTRATION_DATE,
    ClaimType.MORTGAGE_STATUS,
    ClaimType.TAX_STATUS,
]


# ---------------------------------------------------------------------------
# Cross-document comparison
# ---------------------------------------------------------------------------
class MatchType(StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"
    EXPIRED = "EXPIRED"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SEVERITY_RANK = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class ContradictionType(StrEnum):
    OWNER_IDENTITY = "OWNER_IDENTITY"
    SURVEY_IDENTITY = "SURVEY_IDENTITY"
    AREA_DISCREPANCY = "AREA_DISCREPANCY"
    DATE_CHRONOLOGY = "DATE_CHRONOLOGY"
    ENCUMBRANCE_DISCLOSURE = "ENCUMBRANCE_DISCLOSURE"
    AUTHORIZATION_EXPIRY = "AUTHORIZATION_EXPIRY"
    DOCUMENT_INTEGRITY = "DOCUMENT_INTEGRITY"
    TAXPAYER_MISMATCH = "TAXPAYER_MISMATCH"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"


# ---------------------------------------------------------------------------
# Risk & transaction control
# ---------------------------------------------------------------------------
class RiskCategory(StrEnum):
    OWNERSHIP = "OWNERSHIP"
    DOCUMENT = "DOCUMENT"
    ENCUMBRANCE = "ENCUMBRANCE"
    SURVEY = "SURVEY"
    VALUATION = "VALUATION"
    PAYMENT = "PAYMENT"
    INTERACTION = "INTERACTION"


RISK_CATEGORY_LABELS = {
    RiskCategory.OWNERSHIP: "Ownership Risk",
    RiskCategory.DOCUMENT: "Document Risk",
    RiskCategory.ENCUMBRANCE: "Encumbrance Risk",
    RiskCategory.SURVEY: "Land / Survey Risk",
    RiskCategory.VALUATION: "Valuation Risk",
    RiskCategory.PAYMENT: "Payment Risk",
    RiskCategory.INTERACTION: "Interaction Risk",
}


class RiskBand(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransactionState(StrEnum):
    PROCEED = "PROCEED"
    WARN = "WARN"
    HOLD = "HOLD"
    ESCALATE = "ESCALATE"
    REJECT = "REJECT"


TRANSACTION_STATE_RANK = {
    TransactionState.PROCEED: 0,
    TransactionState.WARN: 1,
    TransactionState.HOLD: 2,
    TransactionState.ESCALATE: 3,
    TransactionState.REJECT: 4,
}

# Score → state thresholds, as half-open intervals [lo, hi) so no score falls
# between bands (documented in docs/ARCHITECTURE.md §Risk).
STATE_THRESHOLDS = [
    (0.0, 25.0, TransactionState.PROCEED, RiskBand.LOW),
    (25.0, 50.0, TransactionState.WARN, RiskBand.MODERATE),
    (50.0, 75.0, TransactionState.HOLD, RiskBand.HIGH),
    (75.0, 100.01, TransactionState.ESCALATE, RiskBand.CRITICAL),
]


# ---------------------------------------------------------------------------
# Consent / privacy
# ---------------------------------------------------------------------------
class ConsentStatus(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    APPROVED_TIME_LIMITED = "APPROVED_TIME_LIMITED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class DisclosureItem(StrEnum):
    """Discrete things a buyer may request from an owner."""

    FULL_OWNER_NAME = "FULL_OWNER_NAME"
    LATEST_EC = "LATEST_EC"
    SURVEY_RECORD = "SURVEY_RECORD"
    SALE_DEED_COPY = "SALE_DEED_COPY"
    TAX_RECEIPT = "TAX_RECEIPT"
    MORTGAGE_DETAIL = "MORTGAGE_DETAIL"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    CONTACT_NUMBER = "CONTACT_NUMBER"
    FULL_ADDRESS = "FULL_ADDRESS"


DISCLOSURE_LABELS = {
    DisclosureItem.FULL_OWNER_NAME: "Full owner name",
    DisclosureItem.LATEST_EC: "Latest encumbrance certificate",
    DisclosureItem.SURVEY_RECORD: "Certified survey record",
    DisclosureItem.SALE_DEED_COPY: "Sale deed copy",
    DisclosureItem.TAX_RECEIPT: "Property tax receipt",
    DisclosureItem.MORTGAGE_DETAIL: "Mortgage / loan detail",
    DisclosureItem.IDENTITY_DOCUMENT: "Identity document",
    DisclosureItem.CONTACT_NUMBER: "Direct contact number",
    DisclosureItem.FULL_ADDRESS: "Full postal address",
}

# Items that the prototype refuses to disclose regardless of owner consent, because
# disclosing them would defeat the privacy-first design.  Section 32 of the build
# brief: do not fake identity verification, do not over-expose identity documents.
NEVER_DISCLOSED = {DisclosureItem.IDENTITY_DOCUMENT}


# ---------------------------------------------------------------------------
# Ownership graph
# ---------------------------------------------------------------------------
class NodeType(StrEnum):
    PERSON = "PERSON"
    PROPERTY = "PROPERTY"
    DEED = "DEED"
    MORTGAGE = "MORTGAGE"
    POWER_OF_ATTORNEY = "POWER_OF_ATTORNEY"
    TAX_RECORD = "TAX_RECORD"
    TRANSACTION = "TRANSACTION"
    SURVEY_RECORD = "SURVEY_RECORD"


class EdgeType(StrEnum):
    OWNS = "OWNS"
    OWNED = "OWNED"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    AUTHORIZED = "AUTHORIZED"
    MORTGAGED_TO = "MORTGAGED_TO"
    SUPPORTED_BY = "SUPPORTED_BY"
    CONTRADICTS = "CONTRADICTS"
    RECORDED_IN = "RECORDED_IN"
    RELEASED = "RELEASED"


class OwnershipEventType(StrEnum):
    ORIGINAL_GRANT = "ORIGINAL_GRANT"
    TRANSFER = "TRANSFER"
    SALE_DEED_REGISTERED = "SALE_DEED_REGISTERED"
    MORTGAGE_CREATED = "MORTGAGE_CREATED"
    MORTGAGE_RELEASED = "MORTGAGE_RELEASED"
    POA_GRANTED = "POA_GRANTED"
    POA_EXPIRED = "POA_EXPIRED"
    TAX_PAID = "TAX_PAID"
    VERIFICATION_RUN = "VERIFICATION_RUN"
    PARTITION = "PARTITION"


# ---------------------------------------------------------------------------
# Resolution planning
# ---------------------------------------------------------------------------
class ActionEffort(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ResponsibleParty(StrEnum):
    OWNER = "OWNER"
    BUYER = "BUYER"
    LENDER = "LENDER"
    SURVEYOR = "SURVEYOR"
    REGISTRAR = "REGISTRAR"
    LEGAL_REVIEWER = "LEGAL_REVIEWER"


class ActionStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
class AuditAction(StrEnum):
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_CLASSIFIED = "DOCUMENT_CLASSIFIED"
    OCR_EXECUTED = "OCR_EXECUTED"
    CLAIM_EXTRACTED = "CLAIM_EXTRACTED"
    CLAIM_STATUS_CHANGED = "CLAIM_STATUS_CHANGED"
    CONTRADICTION_DETECTED = "CONTRADICTION_DETECTED"
    CONTRADICTION_RESOLVED = "CONTRADICTION_RESOLVED"
    CONSENT_REQUESTED = "CONSENT_REQUESTED"
    CONSENT_APPROVED = "CONSENT_APPROVED"
    CONSENT_DENIED = "CONSENT_DENIED"
    CONSENT_EXPIRED = "CONSENT_EXPIRED"
    DISCLOSURE_VIEWED = "DISCLOSURE_VIEWED"
    RISK_RECALCULATED = "RISK_RECALCULATED"
    TRANSACTION_HELD = "TRANSACTION_HELD"
    TRANSACTION_RELEASED = "TRANSACTION_RELEASED"
    TRANSACTION_ESCALATED = "TRANSACTION_ESCALATED"
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    RESOLUTION_PLAN_GENERATED = "RESOLUTION_PLAN_GENERATED"
    RESOLUTION_ACTION_APPLIED = "RESOLUTION_ACTION_APPLIED"
    MESSAGE_SENT = "MESSAGE_SENT"
    ASSISTANT_QUERY = "ASSISTANT_QUERY"
    ASSISTANT_REFUSAL = "ASSISTANT_REFUSAL"
    DEMO_RESET = "DEMO_RESET"


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------
class AnswerKind(StrEnum):
    GROUNDED = "GROUNDED"      # answer supported by retrieved claim/contradiction records
    REFUSED = "REFUSED"        # insufficient evidence — refusal is the correct output
    OUT_OF_SCOPE = "OUT_OF_SCOPE"  # question outside what a land-evidence file can answer


DISCLAIMER = (
    "Research prototype — decision-support only. LandTrust Connect does not replace "
    "official land records, registrar verification or legal advice."
)

# ---------------------------------------------------------------------------
# The human side of verification.
#
# The platform derives a claim's status from evidence and always will. These
# enums describe the work people do *around* that: who is responsible for a
# property, what a verifier can establish that the file cannot, and what a legal
# reviewer decides about a case the machine deliberately refused to decide.


class AssignmentStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"


ASSIGNMENT_STATUS_LABELS = {
    AssignmentStatus.ASSIGNED.value: "Awaiting review",
    AssignmentStatus.IN_REVIEW.value: "Under review",
    AssignmentStatus.COMPLETED.value: "Signed off",
    AssignmentStatus.ESCALATED.value: "Escalated to legal",
}


class FindingOutcome(StrEnum):
    """
    What a verifier can establish by examining the original document.

    Each of these is a statement about the *document*, never about whether a
    claim is true. The resolver decides that, from the whole evidence set.
    """

    CONSISTENT_WITH_ORIGINAL = "CONSISTENT_WITH_ORIGINAL"
    CONFIRMED_ALTERED = "CONFIRMED_ALTERED"
    ORIGINAL_UNAVAILABLE = "ORIGINAL_UNAVAILABLE"
    INCONCLUSIVE = "INCONCLUSIVE"


FINDING_OUTCOME_LABELS = {
    FindingOutcome.CONSISTENT_WITH_ORIGINAL.value:
        "Examined — consistent with the issuing office's copy",
    FindingOutcome.CONFIRMED_ALTERED.value:
        "Examined — differs from the issuing office's copy",
    FindingOutcome.ORIGINAL_UNAVAILABLE.value:
        "The issuing office could not produce an original",
    FindingOutcome.INCONCLUSIVE.value:
        "Examined — could not be established either way",
}

#: Which outcomes agree with the platform having raised an integrity indicator.
#: A verifier who confirms an alteration agrees with the machine; one who finds
#: the document clean disagrees with it. Neither is punished — the point of the
#: figure is to show a supervisor where human and automated judgement diverge.
FINDING_CONFIRMS_INDICATOR = {
    FindingOutcome.CONFIRMED_ALTERED.value: True,
    FindingOutcome.CONSISTENT_WITH_ORIGINAL.value: False,
}


class EscalationOutcome(StrEnum):
    RELEASED_TO_PROCEED = "RELEASED_TO_PROCEED"
    REFERRED_TO_REGISTRAR = "REFERRED_TO_REGISTRAR"
    REFUSED = "REFUSED"
    AWAITING_EVIDENCE = "AWAITING_EVIDENCE"


ESCALATION_OUTCOME_LABELS = {
    EscalationOutcome.RELEASED_TO_PROCEED.value:
        "Authority established — released for normal diligence",
    EscalationOutcome.REFERRED_TO_REGISTRAR.value:
        "Referred to the sub-registrar for official confirmation",
    EscalationOutcome.REFUSED.value:
        "Refused — the file cannot support a transaction",
    EscalationOutcome.AWAITING_EVIDENCE.value:
        "Held pending specific evidence requested from the owner",
}
