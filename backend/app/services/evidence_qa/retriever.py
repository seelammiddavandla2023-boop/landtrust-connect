"""
Evidence retrieval for the property assistant.

Retrieval is over *structured records* — claims, contradictions, risk factors,
resolution steps, ownership events — not over free text.  That is what makes
grounding checkable: an answer either cites claim records that exist in the
database, or there is nothing to answer from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...domain import CLAIM_TYPE_LABELS, ClaimType

# ---------------------------------------------------------------------------
# Intents
# ---------------------------------------------------------------------------
INTENT_PATTERNS: list[tuple[str, str]] = [
    ("OWNER", r"\b(who|whose)\b.*\b(own|owner|owns|title|holder|proprietor)\b"),
    ("OWNER", r"\bverified\s+owner\b|\bowner\s+name\b|\bwho\s+is\s+the\s+seller\b"),
    ("RISK_WHY", r"\bwhy\b.*\b(risk|risky|high[- ]risk|flagged|held|hold|blocked|escalat)"),
    ("RISK_LEVEL", r"\b(risk\s+score|how\s+risky|risk\s+level|overall\s+risk|what.*risk)\b"),
    ("STATE", r"\b(transaction\s+state|can\s+(?:i|we)\s+proceed|is\s+it\s+safe\s+to\s+proceed|"
              r"why\s+is\s+(?:the\s+)?transaction|payment\s+blocked)\b"),
    ("MORTGAGE_SOURCE", r"\b(which|what)\b.*\bdocument\b.*\b(mortgage|encumbrance|charge|loan)\b"),
    ("MORTGAGE_SOURCE", r"\bwhere\b.*\b(mortgage|encumbrance|charge)\b"),
    ("CONFLICT_WHY", r"\bwhy\b.*\b(conflict|conflicting|mismatch|discrepan|disagree|differ)\b"),
    ("CONFLICT_WHY", r"\b(area|extent)\b.*\b(conflict|mismatch|differ|discrepan)\b"),
    ("MISSING", r"\b(what|which)\b.*\b(evidence|document|missing|still\s+needed|required)\b"),
    ("MISSING", r"\bwhat\s+is\s+missing\b|\bwhat\s+else\s+do\s+(?:i|we)\s+need\b"),
    ("RESOLUTION", r"\b(how\s+(?:do|can)\s+(?:i|we)\s+(?:fix|resolve|clear)|resolution\s+plan|"
                   r"what\s+should\s+(?:i|we)\s+do|next\s+step)\b"),
    ("DOCUMENTS", r"\b(what|which|list)\b.*\bdocuments?\b.*\b(uploaded|available|on\s+file|have)\b"),
    ("DOCUMENTS", r"\blist\s+(?:the\s+)?documents\b"),
    ("HISTORY", r"\b(ownership\s+(?:history|chain)|previous\s+owner|chain\s+of\s+title|"
                r"who\s+owned|transfer\s+history)\b"),
    ("VERIFICATION", r"\b(is|was)\b.*\b(verified|confirmed)\b"),
    ("CLAIM_VALUE", r"\bwhat\s+is\s+the\b"),
]

# Subjects outside this property's file.  Checked *before* intent routing, because a
# question like "who owns the neighbouring plot?" contains every keyword that would
# otherwise route it to the owner handler — and answering it with this property's
# owner is exactly the failure mode the research identifies in existing assistants:
# a fluent answer to a question that was not asked.
FOREIGN_SUBJECT_PATTERNS: list[tuple[str, str]] = [
    ("OTHER_PARCEL", r"\b(neighbour|neighbor|neighbouring|neighboring|adjacent|adjoining|"
                     r"next\s+plot|next\s+door|nearby|surrounding|other\s+(?:plot|property|"
                     r"parcel)|another\s+(?:plot|property|parcel))\b"),
    ("NOT_IN_FILE", r"\b(bank\s+account|account\s+number|ifsc|upi|soil|tree|trees|water\s+"
                    r"table|borewell|electricity|power\s+supply|road\s+width|school|hospital|"
                    r"metro|distance\s+to|amenit|rent|tenant|vastu|facing|builder|"
                    r"construction\s+cost|carpet\s+area\s+ratio|fsi)\b"),
]

# Questions this system must refuse on principle, not for lack of data.
OUT_OF_SCOPE_PATTERNS: list[tuple[str, str]] = [
    ("LEGAL_ADVICE", r"\b(should\s+(?:i|we)\s+buy|is\s+(?:this|the)\s+title\s+legal|"
                     r"legally\s+(?:valid|safe)|will\s+(?:i|we)\s+win|sue|court\s+case\s+outcome|"
                     r"give\s+me\s+legal\s+advice)\b"),
    ("VALUATION_FORECAST", r"\b(worth\s+in\s+\d{4}|be\s+worth|price\s+forecast|future\s+value|"
                           r"good\s+investment|will\s+.{0,24}appreciate|resale\s+value|"
                           r"market\s+price|how\s+much\s+is\s+it\s+worth)\b"),
    ("PERSONAL_CONTACT", r"\b(phone\s+number|mobile\s+number|whatsapp|email\s+address|"
                         r"aadhaar\s+number|contact\s+details)\b"),
    ("OFFICIAL_CERTIFICATION", r"\b(certify|certificate\s+of\s+title|guarantee\s+(?:the\s+)?title|"
                               r"is\s+this\s+government\s+verified|official\s+confirmation)\b"),
]

CLAIM_KEYWORDS: dict[ClaimType, tuple[str, ...]] = {
    ClaimType.OWNER_NAME: ("owner", "owns", "title holder", "proprietor", "seller"),
    ClaimType.SURVEY_NUMBER: ("survey", "survey number", "parcel", "plot number"),
    ClaimType.PROPERTY_AREA: ("area", "extent", "size", "square feet", "sq.ft", "sqft"),
    ClaimType.REGISTRATION_DATE: ("registration date", "registered", "when was it registered"),
    ClaimType.DOCUMENT_NUMBER: ("document number", "deed number", "registration number"),
    ClaimType.MORTGAGE_STATUS: ("mortgage", "encumbrance", "charge", "loan", "lien"),
    ClaimType.MORTGAGE_AMOUNT: ("mortgage amount", "loan amount", "outstanding"),
    ClaimType.MORTGAGE_LENDER: ("lender", "bank", "mortgagee"),
    ClaimType.TAX_STATUS: ("tax", "property tax", "dues", "arrears"),
    ClaimType.TAXPAYER_NAME: ("taxpayer", "who pays tax"),
    ClaimType.POA_HOLDER: ("power of attorney", "attorney", "poa", "authorised", "authorized"),
    ClaimType.AUTHORIZATION_EXPIRY: ("expiry", "expired", "valid until", "authorisation"),
    ClaimType.DISTRICT: ("district",),
    ClaimType.VILLAGE: ("village", "locality"),
    ClaimType.PROPERTY_TYPE: ("property type", "classification", "land use"),
    ClaimType.BOUNDARY_DESCRIPTION: ("boundary", "boundaries", "bounded"),
    ClaimType.CONSIDERATION_VALUE: ("consideration", "sale price", "price paid"),
}


@dataclass
class EvidenceRef:
    kind: str
    document_id: str | None
    document_name: str
    page: int | None
    confidence: float
    excerpt: str = ""
    claim_id: str | None = None
    verification_status: str | None = None

    def dict(self) -> dict:
        return {
            "kind": self.kind,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "page": self.page,
            "confidence": round(self.confidence, 4),
            "excerpt": self.excerpt,
            "claim_id": self.claim_id,
            "verification_status": self.verification_status,
        }


@dataclass
class Retrieval:
    intent: str
    out_of_scope: str | None
    target_claim_types: list[str] = field(default_factory=list)
    claims: list = field(default_factory=list)
    contradictions: list = field(default_factory=list)
    documents: list = field(default_factory=list)
    events: list = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.claims or self.contradictions or self.documents or self.events)


def detect_intent(question: str) -> tuple[str, str | None]:
    q = (question or "").lower().strip()
    # Scope first: what the question is *about* outranks what it sounds like.
    for label, pattern in FOREIGN_SUBJECT_PATTERNS:
        if re.search(pattern, q):
            return "OUT_OF_SCOPE", label
    for label, pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, q):
            return "OUT_OF_SCOPE", label
    for intent, pattern in INTENT_PATTERNS:
        if re.search(pattern, q):
            return intent, None
    return "UNKNOWN", None


def detect_claim_types(question: str) -> list[str]:
    q = (question or "").lower()
    hits: list[tuple[int, str]] = []
    for claim_type, keywords in CLAIM_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                hits.append((len(kw), claim_type.value))
                break
    hits.sort(reverse=True)
    return [ct for _, ct in hits]


def retrieve(question: str, claims: list, contradictions: list, documents: list,
             events: list) -> Retrieval:
    intent, oos = detect_intent(question)
    targets = detect_claim_types(question)

    r = Retrieval(intent=intent, out_of_scope=oos, target_claim_types=targets)
    if oos:
        return r

    live_claims = [c for c in claims if not c.superseded]
    docs_by_id = {d.id: d for d in documents}

    if intent in {"OWNER", "VERIFICATION", "CLAIM_VALUE", "MORTGAGE_SOURCE"} or targets:
        wanted = targets or ([ClaimType.OWNER_NAME.value] if intent == "OWNER" else [])
        if intent == "MORTGAGE_SOURCE" and not wanted:
            wanted = [ClaimType.MORTGAGE_STATUS.value]
        r.claims = [c for c in live_claims if c.claim_type in wanted]
        r.documents = [docs_by_id[c.document_id] for c in r.claims
                       if c.document_id in docs_by_id]

    if intent in {"CONFLICT_WHY", "RISK_WHY", "STATE"}:
        if targets:
            r.contradictions = [c for c in contradictions
                                if c.claim_type in targets and not c.resolved]
            r.claims = [c for c in live_claims if c.claim_type in targets]
        if not r.contradictions:
            r.contradictions = [c for c in contradictions if not c.resolved]

    if intent == "MISSING":
        r.contradictions = [c for c in contradictions
                            if c.contradiction_type == "MISSING_EVIDENCE" and not c.resolved]
        r.documents = [d for d in documents if not d.is_pending_evidence]

    if intent in {"DOCUMENTS", "RESOLUTION", "RISK_LEVEL"}:
        r.documents = [d for d in documents if not d.is_pending_evidence]

    if intent == "HISTORY":
        r.events = list(events)
        r.documents = [d for d in documents if not d.is_pending_evidence]

    if intent == "UNKNOWN" and targets:
        r.claims = [c for c in live_claims if c.claim_type in targets]

    return r


def refs_from_claims(claims: list, documents: list, limit: int = 6) -> list[EvidenceRef]:
    docs_by_id = {d.id: d for d in documents}
    refs: list[EvidenceRef] = []
    for c in sorted(claims, key=lambda x: x.confidence, reverse=True)[:limit]:
        doc = docs_by_id.get(c.document_id)
        refs.append(
            EvidenceRef(
                kind="claim",
                document_id=c.document_id,
                document_name=doc.filename if doc else "Owner declaration",
                page=c.source_page,
                confidence=c.confidence,
                excerpt=(c.source_span or c.value)[:220],
                claim_id=c.id,
                verification_status=c.verification_status,
            )
        )
    return refs


def label_for(claim_type: str) -> str:
    try:
        return CLAIM_TYPE_LABELS[ClaimType(claim_type)]
    except (ValueError, KeyError):
        return claim_type.replace("_", " ").title()
