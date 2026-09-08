"""
Claim extraction grammar.

A label-driven key–value grammar that maps document text onto ClaimTypes.  The same
grammar runs over both text-layer output and OCR output, so switching acquisition
mode does not change what the system understands — only how well it reads.

`doc_types=None` means the pattern applies to every document type; otherwise the
pattern is only considered for the listed types.  This is what lets "Name:" mean
*taxpayer* on a tax receipt and *purchaser* on a sale deed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...domain import ClaimType, DocumentType

VALUE_TAIL = r"[:\-–]\s*(?P<value>[^\n\r]{1,160})"


@dataclass
class FieldPattern:
    claim_type: ClaimType
    labels: tuple[str, ...]
    doc_types: tuple[DocumentType, ...] | None = None
    base_confidence: float = 0.95
    value_regex: str | None = None
    transform: str | None = None
    priority: int = 5
    _compiled: list[re.Pattern] = field(default_factory=list, repr=False)

    def compiled(self) -> list[re.Pattern]:
        if not self._compiled:
            for label in self.labels:
                self._compiled.append(
                    re.compile(rf"(?P<label>{label})\s*{self.value_regex or VALUE_TAIL}",
                               re.IGNORECASE)
                )
        return self._compiled


# ---------------------------------------------------------------------------
PATTERNS: list[FieldPattern] = [
    # --- ownership -----------------------------------------------------------
    FieldPattern(
        ClaimType.OWNER_NAME,
        (r"present\s+owner", r"current\s+owner", r"owner\s*name", r"owner\s*/\s*holder",
         r"registered\s+owner", r"name\s+of\s+(?:the\s+)?owner", r"pattadar\s*name",
         r"khatadar", r"title\s*holder"),
        priority=1,
    ),
    FieldPattern(
        ClaimType.OWNER_NAME,
        (r"purchaser\s*/\s*transferee", r"purchaser", r"vendee", r"transferee",
         r"buyer\s*\(purchaser\)"),
        doc_types=(DocumentType.SALE_DEED,),
        base_confidence=0.96,
        priority=2,
    ),
    FieldPattern(
        ClaimType.SELLER_NAME,
        (r"vendor\s*/\s*transferor", r"vendor", r"seller", r"transferor", r"executant"),
        doc_types=(DocumentType.SALE_DEED, DocumentType.POWER_OF_ATTORNEY),
        base_confidence=0.94,
    ),
    FieldPattern(
        ClaimType.TAXPAYER_NAME,
        (r"assessee", r"taxpayer\s*name", r"taxpayer", r"name\s+of\s+assessee",
         r"paid\s+by"),
        doc_types=(DocumentType.TAX_RECEIPT,),
        base_confidence=0.93,
    ),
    FieldPattern(
        ClaimType.OWNER_NAME,
        (r"claimant", r"property\s+holder", r"holder\s+name"),
        doc_types=(DocumentType.ENCUMBRANCE_CERTIFICATE, DocumentType.SURVEY_RECORD),
        base_confidence=0.92,
        priority=3,
    ),
    # --- parcel identity -----------------------------------------------------
    FieldPattern(
        ClaimType.SURVEY_NUMBER,
        (r"survey\s*(?:no|number)", r"s\.?\s*no", r"resurvey\s*(?:no|number)",
         r"old\s+survey\s*(?:no|number)", r"plot\s*/\s*survey"),
        base_confidence=0.97,
        priority=1,
    ),
    FieldPattern(
        ClaimType.PROPERTY_AREA,
        (r"extent\s*/\s*area", r"total\s+extent", r"extent", r"area\s+of\s+(?:the\s+)?(?:land|plot|property)",
         r"measured\s+area", r"plot\s+area", r"land\s+area", r"area"),
        base_confidence=0.95,
        priority=1,
    ),
    FieldPattern(
        ClaimType.PROPERTY_TYPE,
        (r"classification", r"land\s+use", r"property\s+type", r"nature\s+of\s+property"),
        base_confidence=0.9,
    ),
    FieldPattern(
        ClaimType.DISTRICT,
        (r"district", r"revenue\s+district"),
        base_confidence=0.93,
    ),
    FieldPattern(
        ClaimType.VILLAGE,
        (r"village", r"revenue\s+village", r"locality"),
        base_confidence=0.92,
    ),
    FieldPattern(
        ClaimType.BOUNDARY_DESCRIPTION,
        (r"boundaries", r"schedule\s+of\s+boundaries", r"bounded\s+by"),
        base_confidence=0.85,
    ),
    # --- registration --------------------------------------------------------
    FieldPattern(
        ClaimType.REGISTRATION_DATE,
        (r"date\s+of\s+registration", r"registration\s+date", r"registered\s+on",
         r"date\s+of\s+execution", r"deed\s+date"),
        base_confidence=0.96,
        priority=1,
    ),
    FieldPattern(
        ClaimType.DOCUMENT_NUMBER,
        (r"document\s*(?:no|number)", r"deed\s*(?:no|number)", r"registration\s*(?:no|number)",
         r"certificate\s*(?:no|number)", r"receipt\s*(?:no|number)", r"instrument\s*(?:no|number)"),
        base_confidence=0.96,
    ),
    FieldPattern(
        ClaimType.CONSIDERATION_VALUE,
        (r"sale\s+consideration", r"consideration", r"transaction\s+value",
         r"market\s+value"),
        doc_types=(DocumentType.SALE_DEED,),
        base_confidence=0.92,
    ),
    # --- encumbrance ---------------------------------------------------------
    FieldPattern(
        ClaimType.MORTGAGE_STATUS,
        (r"encumbrance\s+status", r"mortgage\s+status", r"charge\s+status",
         r"encumbrances?\s+found", r"status\s+of\s+encumbrance", r"lien\s+status"),
        base_confidence=0.95,
        priority=1,
    ),
    FieldPattern(
        ClaimType.MORTGAGE_AMOUNT,
        (r"mortgage\s+amount", r"loan\s+amount", r"secured\s+amount",
         r"outstanding\s+amount", r"charge\s+amount"),
        base_confidence=0.93,
    ),
    FieldPattern(
        ClaimType.MORTGAGE_LENDER,
        (r"mortgagee", r"lender", r"financial\s+institution", r"charge\s+holder",
         r"bank\s+name"),
        base_confidence=0.92,
    ),
    FieldPattern(
        ClaimType.ENCUMBRANCE_PERIOD,
        (r"search\s+period", r"period\s+of\s+search", r"encumbrance\s+period",
         r"period\s+covered"),
        doc_types=(DocumentType.ENCUMBRANCE_CERTIFICATE,),
        base_confidence=0.94,
    ),
    # --- tax -----------------------------------------------------------------
    FieldPattern(
        ClaimType.TAX_STATUS,
        (r"payment\s+status", r"tax\s+status", r"dues\s+status", r"status\s+of\s+payment"),
        doc_types=(DocumentType.TAX_RECEIPT,),
        base_confidence=0.94,
    ),
    # --- authorisation -------------------------------------------------------
    FieldPattern(
        ClaimType.POA_HOLDER,
        (r"attorney\s+holder", r"power\s+holder", r"agent\s+name", r"holder\s+of\s+power",
         r"attorney"),
        doc_types=(DocumentType.POWER_OF_ATTORNEY,),
        base_confidence=0.94,
    ),
    FieldPattern(
        ClaimType.POA_GRANTOR,
        (r"principal", r"grantor", r"donor\s+of\s+power", r"executed\s+by"),
        doc_types=(DocumentType.POWER_OF_ATTORNEY,),
        base_confidence=0.94,
    ),
    FieldPattern(
        ClaimType.AUTHORIZATION_EXPIRY,
        (r"valid\s+until", r"valid\s+up\s*to", r"expiry\s+date", r"date\s+of\s+expiry",
         r"authorisation\s+valid\s+till", r"valid\s+till"),
        base_confidence=0.95,
    ),
    # --- identity (restricted) ----------------------------------------------
    FieldPattern(
        ClaimType.IDENTITY_NUMBER,
        (r"aadhaar\s*(?:no|number)?", r"identity\s*(?:no|number)", r"id\s*number",
         r"pan\s*(?:no|number)?", r"passport\s*(?:no|number)?"),
        base_confidence=0.9,
    ),
    FieldPattern(
        ClaimType.OWNER_PHONE,
        (r"mobile", r"phone", r"contact\s*(?:no|number)"),
        base_confidence=0.88,
    ),
    FieldPattern(
        ClaimType.OWNER_ADDRESS,
        (r"residing\s+at", r"address", r"postal\s+address"),
        base_confidence=0.85,
    ),
]


def patterns_for(doc_type: str) -> list[FieldPattern]:
    """Patterns applicable to a document type, most specific first."""
    try:
        dt = DocumentType(doc_type)
    except ValueError:
        dt = DocumentType.UNKNOWN
    selected = [
        p for p in PATTERNS
        if p.doc_types is None or dt in p.doc_types
    ]
    return sorted(selected, key=lambda p: (p.priority, 0 if p.doc_types else 1))


# ---------------------------------------------------------------------------
# Value cleaning
# ---------------------------------------------------------------------------
_TRAILING_JUNK = re.compile(r"[\s\.,;:|]+$")
_LEADING_JUNK = re.compile(r"^[\s\.,;:|\-]+")
# Stop a captured value at the next label on the same line ("Area: 2400 sq.ft  District: Vellore")
_NEXT_LABEL = re.compile(
    r"\s{2,}(?=[A-Z][A-Za-z /]{2,30}\s*[:\-])"
)


def clean_value(raw: str) -> str:
    value = _NEXT_LABEL.split(raw, maxsplit=1)[0]
    value = _LEADING_JUNK.sub("", value)
    value = _TRAILING_JUNK.sub("", value)
    return re.sub(r"\s+", " ", value).strip()


def plausible(claim_type: ClaimType, value: str) -> bool:
    """Cheap sanity gate so obvious garbage never becomes a claim."""
    if not value or len(value) < 1:
        return False
    if len(value) > 160:
        return False
    if claim_type in {ClaimType.PROPERTY_AREA, ClaimType.MORTGAGE_AMOUNT,
                      ClaimType.CONSIDERATION_VALUE}:
        return bool(re.search(r"\d", value))
    if claim_type in {ClaimType.REGISTRATION_DATE, ClaimType.AUTHORIZATION_EXPIRY}:
        return bool(re.search(r"\d{2}", value))
    if claim_type in {ClaimType.OWNER_NAME, ClaimType.SELLER_NAME, ClaimType.BUYER_NAME,
                      ClaimType.TAXPAYER_NAME, ClaimType.POA_HOLDER, ClaimType.POA_GRANTOR}:
        return bool(re.search(r"[A-Za-z]{2}", value)) and not re.fullmatch(r"[\d\W]+", value)
    return True
