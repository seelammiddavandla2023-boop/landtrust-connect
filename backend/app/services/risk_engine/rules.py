"""
Transaction risk rules.

Every rule is a pure function of the evidence context that returns zero or more
`RuleHit`s.  A hit carries its weight, its category, a human explanation and the
evidence it was derived from — so a score is never a number without a reason, and
the Resolution Planner can reason about *which* hits a given piece of evidence
would remove.

Rule-based by design for Review-2 (build brief §19): the weights are inspectable and
the behaviour is reproducible.  `engine.py` keeps the aggregation separate from the
rules so a learned scorer can replace or augment this file in Review-3 without
changing anything else.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ...domain import (
    ClaimType,
    ContradictionType,
    DocumentType,
    RiskCategory,
    Severity,
    VerificationStatus,
)
from ..normalization import normalise_categorical, parse_date, parse_money_inr


@dataclass
class RuleHit:
    rule_id: str
    category: RiskCategory
    weight: float
    severity: Severity
    title: str
    explanation: str
    evidence_refs: list[dict] = field(default_factory=list)
    is_mitigation: bool = False


@dataclass
class RiskContext:
    property: object
    claims: list
    documents: list
    contradictions: list
    outcome: object              # verification.resolver.ResolutionOutcome
    transaction: object | None = None
    messages: list = field(default_factory=list)
    consent_requests: list = field(default_factory=list)
    today: date = field(default_factory=date.today)
    # Rule ids the caller wants suppressed — used by the resolution simulator to ask
    # "what would the score be if this issue were resolved?"
    suppressed: set[str] = field(default_factory=set)
    # Extra rule ids to force on (mitigations granted by a simulated action).
    granted: set[str] = field(default_factory=set)

    # -- convenience ---------------------------------------------------------
    def claims_of(self, claim_type) -> list:
        ct = claim_type.value if hasattr(claim_type, "value") else claim_type
        return [c for c in self.claims if c.claim_type == ct and not c.superseded]

    def status_of(self, claim_type) -> VerificationStatus:
        ct = claim_type.value if hasattr(claim_type, "value") else claim_type
        return self.outcome.status_of(ct)

    def docs_of(self, doc_type) -> list:
        dt = doc_type.value if hasattr(doc_type, "value") else doc_type
        return [d for d in self.documents if d.doc_type == dt and not d.is_pending_evidence]

    def has_doc(self, doc_type) -> bool:
        return bool(self.docs_of(doc_type))

    def contradictions_of(self, ctype) -> list:
        cv = ctype.value if hasattr(ctype, "value") else ctype
        return [c for c in self.contradictions if c.contradiction_type == cv and not c.resolved]

    def doc_ref(self, doc, page: int = 1) -> dict:
        return {"kind": "document", "id": doc.id, "label": doc.filename, "page": page}

    def claim_ref(self, claim) -> dict:
        return {
            "kind": "claim",
            "id": claim.id,
            "label": f"{claim.claim_type} = {claim.value}",
            "page": claim.source_page,
            "document_id": claim.document_id,
        }

    def contradiction_ref(self, c) -> dict:
        return {"kind": "contradiction", "id": c.id, "label": c.detection_rule,
                "page": None}


RULES: list = []


def rule(fn):
    RULES.append(fn)
    return fn


# ===========================================================================
# Baseline
# ===========================================================================
@rule
def r_baseline(ctx: RiskContext) -> list[RuleHit]:
    """
    Residual risk that no amount of uploaded paper removes.

    LandTrust Connect verifies claims against *supplied evidence*, not against the
    government register.  Stating that plainly as a scored factor is more honest
    than presenting a fully-evidenced file as zero-risk.
    """
    return [
        RuleHit(
            "BASELINE_NO_OFFICIAL_CONFIRMATION",
            RiskCategory.DOCUMENT,
            18.0,
            Severity.LOW,
            "No official registry confirmation",
            "Verification in this prototype is performed against the documents supplied, not "
            "against the government land register. A residual risk therefore remains on every "
            "transaction until an authorised source confirms the record.",
        )
    ]


# ===========================================================================
# Ownership
# ===========================================================================
@rule
def r_owner_contradiction(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for c in ctx.contradictions_of(ContradictionType.OWNER_IDENTITY):
        hits.append(
            RuleHit(
                "OWNER_CONTRADICTION",
                RiskCategory.OWNERSHIP,
                30.0,
                Severity.CRITICAL,
                "Ownership contradiction between sources",
                c.explanation,
                [ctx.contradiction_ref(c)],
            )
        )
    return hits[:1]  # one hit per property; the ledger keeps the detail


@rule
def r_owner_partial(ctx: RiskContext) -> list[RuleHit]:
    if ctx.status_of(ClaimType.OWNER_NAME) is not VerificationStatus.PARTIALLY_VERIFIED:
        return []
    group = ctx.outcome.per_type.get(ClaimType.OWNER_NAME.value)
    # With a single source there is no variation *between* documents to report;
    # SINGLE_SOURCE_OWNER covers that case, and firing both would double-count one
    # weakness and label it wrongly.
    if group and len(group.supporting_document_ids) < 2:
        return []
    return [
        RuleHit(
            "OWNER_NAME_VARIANT",
            RiskCategory.OWNERSHIP,
            8.0,
            Severity.MEDIUM,
            "Owner name not identical across documents",
            (group.explanation if group else "")
            + " Name variants are common and usually benign, but they leave the identity of the "
              "titleholder short of certified.",
            [ctx.claim_ref(c) for c in ctx.claims_of(ClaimType.OWNER_NAME)][:3],
        )
    ]


@rule
def r_owner_single_source(ctx: RiskContext) -> list[RuleHit]:
    group = ctx.outcome.per_type.get(ClaimType.OWNER_NAME.value)
    if not group or len(group.supporting_document_ids) != 1:
        return []
    if group.status is VerificationStatus.VERIFIED:
        return []
    return [
        RuleHit(
            "SINGLE_SOURCE_OWNER",
            RiskCategory.OWNERSHIP,
            12.0,
            Severity.MEDIUM,
            "Ownership rests on a single document",
            "Only one document asserts who owns this property. A single source cannot be "
            "cross-checked, so an error or a forgery in that one document would not be visible "
            "to this system.",
            [{"kind": "document", "id": group.supporting_document_ids[0],
              "label": "sole ownership source", "page": 1}],
        )
    ]


@rule
def r_owner_provided_only(ctx: RiskContext) -> list[RuleHit]:
    if ctx.status_of(ClaimType.OWNER_NAME) is not VerificationStatus.OWNER_PROVIDED:
        return []
    return [
        RuleHit(
            "OWNER_DECLARED_ONLY",
            RiskCategory.OWNERSHIP,
            26.0,
            Severity.HIGH,
            "Ownership is self-declared",
            "The owner's identity is stated by the owner and supported by no document. Nothing "
            "in this file distinguishes a genuine owner from any other party making the same "
            "statement.",
        )
    ]


@rule
def r_expired_poa(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for c in ctx.contradictions_of(ContradictionType.AUTHORIZATION_EXPIRY):
        hits.append(
            RuleHit(
                "EXPIRED_POA",
                RiskCategory.OWNERSHIP,
                35.0,
                Severity.CRITICAL,
                "Authorisation has expired",
                c.explanation,
                [ctx.contradiction_ref(c)],
            )
        )
    return hits[:1]


@rule
def r_unverified_seller_authority(ctx: RiskContext) -> list[RuleHit]:
    """
    The listing party is neither the evidenced owner nor a currently-authorised agent.
    This is the impersonation signature: it needs both halves to fire.
    """
    listed = (ctx.property.listed_owner_name or "").strip()
    if not listed:
        return []
    owner_conflict = bool(ctx.contradictions_of(ContradictionType.OWNER_IDENTITY))
    poa_ok = False
    for claim in ctx.claims_of(ClaimType.POA_HOLDER):
        expiry_claims = [
            c for c in ctx.claims_of(ClaimType.AUTHORIZATION_EXPIRY)
            if c.document_id == claim.document_id
        ]
        expiry = parse_date(expiry_claims[0].value) if expiry_claims else None
        if expiry and expiry >= ctx.today:
            poa_ok = True
    if owner_conflict and not poa_ok:
        return [
            RuleHit(
                "UNVERIFIED_SELLER_AUTHORITY",
                RiskCategory.OWNERSHIP,
                28.0,
                Severity.CRITICAL,
                "Seller's authority to transact is unverified",
                f"'{listed}' is offering this property, but the evidence names a different owner "
                "and no unexpired authorisation connects the two. On the available evidence the "
                "system cannot establish that this party may sell. This is a statement about the "
                "evidence, not an accusation against any individual.",
            )
        ]
    return []


@rule
def r_verified_owner(ctx: RiskContext) -> list[RuleHit]:
    if ctx.status_of(ClaimType.OWNER_NAME) is not VerificationStatus.VERIFIED:
        return []
    group = ctx.outcome.per_type.get(ClaimType.OWNER_NAME.value)
    return [
        RuleHit(
            "VERIFIED_OWNER",
            RiskCategory.OWNERSHIP,
            -10.0,
            Severity.INFO,
            "Ownership corroborated across independent documents",
            group.explanation if group else "Owner name is consistent across sources.",
            is_mitigation=True,
        )
    ]


# ===========================================================================
# Survey / land
# ===========================================================================
@rule
def r_area_mismatch(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for c in ctx.contradictions_of(ContradictionType.AREA_DISCREPANCY):
        # Weight scales with how large the discrepancy is.
        magnitude = c.magnitude or 0.0
        areas = [
            float(x) for x in
            (getattr(ctx.property, "claimed_area_sqft", None) or magnitude or 1,)
        ]
        base = max(areas) or 1.0
        rel = min(1.0, magnitude / base) if base else 0.0
        weight = round(14.0 + 22.0 * min(1.0, rel / 0.15), 1)
        hits.append(
            RuleHit(
                "AREA_MISMATCH",
                RiskCategory.SURVEY,
                weight,
                Severity(c.severity),
                "Recorded extent differs between documents",
                c.explanation
                + " Extent drives price, stamp duty and the boundary that will actually be "
                  "conveyed, so an unreconciled difference is material.",
                [ctx.contradiction_ref(c)],
            )
        )
    return hits[:1]


@rule
def r_survey_mismatch(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for c in ctx.contradictions_of(ContradictionType.SURVEY_IDENTITY):
        hits.append(
            RuleHit(
                "SURVEY_MISMATCH",
                RiskCategory.SURVEY,
                25.0,
                Severity.CRITICAL,
                "Documents reference different parcels",
                c.explanation
                + " If the documents describe different parcels, evidence from one of them does "
                  "not apply to the property being sold at all.",
                [ctx.contradiction_ref(c)],
            )
        )
    return hits[:1]


@rule
def r_missing_survey_record(ctx: RiskContext) -> list[RuleHit]:
    if ctx.has_doc(DocumentType.SURVEY_RECORD):
        return []
    return [
        RuleHit(
            "MISSING_SURVEY_RECORD",
            RiskCategory.SURVEY,
            15.0,
            Severity.MEDIUM,
            "No certified survey record",
            "The authority of record for extent and boundaries is absent, so area is being taken "
            "from documents that only quote it. Any disagreement about extent cannot be settled "
            "from this file.",
        )
    ]


# ===========================================================================
# Encumbrance
# ===========================================================================
def _encumbrance_state(ctx: RiskContext) -> tuple[str, list]:
    claims = ctx.claims_of(ClaimType.MORTGAGE_STATUS)
    if not claims:
        return "unknown", []
    # The most authoritative live statement wins for reporting purposes.
    order = {
        DocumentType.BANK_NOC.value: 4,
        DocumentType.ENCUMBRANCE_CERTIFICATE.value: 3,
        DocumentType.MORTGAGE_DOCUMENT.value: 2,
    }
    docs = {d.id: d for d in ctx.documents}
    ranked = sorted(
        claims,
        key=lambda c: (
            order.get(getattr(docs.get(c.document_id), "doc_type", ""), 1),
            getattr(docs.get(c.document_id), "issued_on", None) or ctx.today,
        ),
        reverse=True,
    )
    return normalise_categorical(ranked[0].value).text, ranked


@rule
def r_active_mortgage(ctx: RiskContext) -> list[RuleHit]:
    state, claims = _encumbrance_state(ctx)
    if state != "active":
        return []
    amount_claims = ctx.claims_of(ClaimType.MORTGAGE_AMOUNT)
    lender_claims = ctx.claims_of(ClaimType.MORTGAGE_LENDER)
    amount = parse_money_inr(amount_claims[0].value) if amount_claims else None
    lender = lender_claims[0].value if lender_claims else "the lender of record"
    detail = f" of approximately ₹{amount:,.0f}" if amount else ""
    return [
        RuleHit(
            "ACTIVE_MORTGAGE",
            RiskCategory.ENCUMBRANCE,
            30.0,
            Severity.HIGH,
            "Active encumbrance on the property",
            f"A subsisting charge{detail} in favour of {lender} is recorded against this "
            "property. Until it is discharged or a release is produced, the property cannot be "
            "conveyed free of encumbrance.",
            [ctx.claim_ref(c) for c in claims[:2]],
        )
    ]


@rule
def r_missing_ec(ctx: RiskContext) -> list[RuleHit]:
    if ctx.has_doc(DocumentType.ENCUMBRANCE_CERTIFICATE):
        return []
    return [
        RuleHit(
            "MISSING_EC",
            RiskCategory.ENCUMBRANCE,
            20.0,
            Severity.HIGH,
            "No encumbrance certificate on file",
            "Without an encumbrance certificate there is no evidence either way about mortgages, "
            "liens or attachments. An absent certificate is not the same as a clear one.",
        )
    ]


@rule
def r_stale_ec(ctx: RiskContext) -> list[RuleHit]:
    """
    Only the *most recent* certificate matters.

    Judging every certificate on file would mean a two-year-old EC kept this factor
    alive forever, so obtaining a fresh one could never clear it — and a resolution
    step that cannot succeed is worse than no step at all.
    """
    certificates = ctx.docs_of(DocumentType.ENCUMBRANCE_CERTIFICATE)
    dated = [
        d for d in certificates
        if (d.issued_on.date() if hasattr(d.issued_on, "date") else d.issued_on)
    ]
    if not dated:
        return []
    latest = max(
        dated,
        key=lambda d: d.issued_on.date() if hasattr(d.issued_on, "date") else d.issued_on,
    )
    hits = []
    for doc in [latest]:
        issued = doc.issued_on.date() if hasattr(doc.issued_on, "date") else doc.issued_on
        age_days = (ctx.today - issued).days
        if age_days <= 180:
            continue
        hits.append(
            RuleHit(
                "STALE_EC",
                RiskCategory.ENCUMBRANCE,
                10.0,
                Severity.MEDIUM,
                "Encumbrance certificate is out of date",
                f"The most recent encumbrance certificate on file, '{doc.filename}', was issued "
                f"{age_days} days ago ({issued:%d-%m-%Y}). Charges created after that date would "
                "not appear in it, so it cannot evidence the current position.",
                [ctx.doc_ref(doc)],
            )
        )
    return hits[:1]


@rule
def r_undisclosed_encumbrance(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for c in ctx.contradictions_of(ContradictionType.ENCUMBRANCE_DISCLOSURE):
        hits.append(
            RuleHit(
                "ENCUMBRANCE_DISCLOSURE_CONFLICT",
                RiskCategory.ENCUMBRANCE,
                24.0,
                Severity.HIGH,
                "Encumbrance status disclosed inconsistently",
                c.explanation
                + " A difference between what is declared and what is certified is the pattern "
                  "an undisclosed charge produces.",
                [ctx.contradiction_ref(c)],
            )
        )
    return hits[:1]


@rule
def r_clear_encumbrance(ctx: RiskContext) -> list[RuleHit]:
    state, claims = _encumbrance_state(ctx)
    if state not in {"none", "released"}:
        return []
    if ctx.status_of(ClaimType.MORTGAGE_STATUS) not in {
        VerificationStatus.VERIFIED, VerificationStatus.PARTIALLY_VERIFIED
    }:
        return []
    # A mitigation may never rest on a document the platform has itself flagged. An
    # incomplete certificate is exactly the case where the missing pages might carry
    # the encumbrance entry, so reading it as evidence of a clear position would
    # credit the file for the part that is absent.
    docs = {d.id: d for d in ctx.documents}
    sources = [docs.get(c.document_id) for c in claims[:1]]
    if any(
        d is not None and any(f.get("severity") == "HIGH" for f in (d.integrity_flags or []))
        for d in sources
    ):
        return []
    return [
        RuleHit(
            "CLEAR_ENCUMBRANCE",
            RiskCategory.ENCUMBRANCE,
            -8.0,
            Severity.INFO,
            "Encumbrance position evidenced as clear",
            "The encumbrance authority of record reports no subsisting charge for the period "
            "searched.",
            [ctx.claim_ref(c) for c in claims[:1]],
            is_mitigation=True,
        )
    ]


@rule
def r_bank_noc(ctx: RiskContext) -> list[RuleHit]:
    if not ctx.has_doc(DocumentType.BANK_NOC) and "BANK_NOC_PRESENT" not in ctx.granted:
        return []
    docs = ctx.docs_of(DocumentType.BANK_NOC)
    return [
        RuleHit(
            "BANK_NOC_PRESENT",
            RiskCategory.ENCUMBRANCE,
            -20.0,
            Severity.INFO,
            "Lender release on file",
            "A no-objection / release letter from the charge holder is on file, evidencing that "
            "the lender's interest has been discharged.",
            [ctx.doc_ref(d) for d in docs[:1]],
            is_mitigation=True,
        )
    ]


# ===========================================================================
# Document integrity
# ===========================================================================
@rule
def r_suspicious_edit(ctx: RiskContext) -> list[RuleHit]:
    """
    Post-issue modification indicators, weighted by how many independently agree.

    An incremental save on its own is common and innocuous — any re-save produces one.
    An isolated font in the body is a strong signal on its own. The two together are
    what overtyping a field actually leaves behind, and are scored accordingly, so the
    combination is worth more than either alone rather than one silently doing all the
    work.
    """
    hits = []
    for doc in ctx.documents:
        codes = {f.get("code") for f in (doc.integrity_flags or [])}
        strong = codes & {"FONT_DISCONTINUITY", "INCREMENTAL_SAVE", "METADATA_MODIFIED"}
        if "FONT_DISCONTINUITY" not in codes:
            continue  # the isolated-font signal is required; the others corroborate it
        corroborating = len(strong) - 1
        weight = 24.0 + 6.0 * min(corroborating, 2)
        details = "; ".join(
            f.get("detail", "") for f in (doc.integrity_flags or [])
            if f.get("code") in strong
        )
        hits.append(
            RuleHit(
                "SUSPICIOUS_EDIT",
                RiskCategory.DOCUMENT,
                weight,
                Severity.CRITICAL,
                f"Possible post-issue modification — {doc.filename}"
                + (f" ({len(strong)} independent indicators)" if corroborating else ""),
                details + " These are indicators requiring authorised examination, not a finding "
                          "that the document is forged.",
                [ctx.doc_ref(doc)],
            )
        )
    return hits[:2]


@rule
def r_missing_page(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for doc in ctx.documents:
        for f in (doc.integrity_flags or []):
            if f.get("code") == "MISSING_PAGE":
                hits.append(
                    RuleHit(
                        "MISSING_PAGE",
                        RiskCategory.DOCUMENT,
                        12.0,
                        Severity.HIGH,
                        f"Incomplete document — {doc.filename}",
                        f.get("detail", "")
                        + " Pages that are absent may contain the schedule, the encumbrance entry "
                          "or the signature page.",
                        [ctx.doc_ref(doc)],
                    )
                )
    return hits[:2]


@rule
def r_duplicate_document(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for c in ctx.contradictions:
        if c.detection_rule != "DUPLICATE_DOCUMENT" or c.resolved:
            continue
        hits.append(
            RuleHit(
                "DUPLICATE_DOCUMENT",
                RiskCategory.DOCUMENT,
                10.0,
                Severity.MEDIUM,
                "Duplicate document submitted",
                c.explanation,
                [ctx.contradiction_ref(c)],
            )
        )
    return hits[:1]


@rule
def r_expired_document(ctx: RiskContext) -> list[RuleHit]:
    expired = [d for d in ctx.documents if d.is_expired and not d.is_pending_evidence]
    if not expired:
        return []
    return [
        RuleHit(
            "EXPIRED_DOCUMENT",
            RiskCategory.DOCUMENT,
            14.0,
            Severity.HIGH,
            "Expired documents in the evidence set",
            "The following documents are past their stated validity and are not relied upon as "
            "current proof: " + ", ".join(d.filename for d in expired[:3]) + ".",
            [ctx.doc_ref(d) for d in expired[:3]],
        )
    ]


@rule
def r_chronology(ctx: RiskContext) -> list[RuleHit]:
    hits = []
    for c in ctx.contradictions_of(ContradictionType.DATE_CHRONOLOGY):
        hits.append(
            RuleHit(
                "CHRONOLOGY_VIOLATION",
                RiskCategory.DOCUMENT,
                18.0,
                Severity.HIGH,
                "Ownership chronology does not hold",
                c.explanation,
                [ctx.contradiction_ref(c)],
            )
        )
    return hits[:1]


@rule
def r_all_core_verified(ctx: RiskContext) -> list[RuleHit]:
    level = ctx.outcome.verification_level()
    if level < 1.0:
        return []
    return [
        RuleHit(
            "ALL_CORE_CLAIMS_VERIFIED",
            RiskCategory.DOCUMENT,
            -6.0,
            Severity.INFO,
            "Every core claim is evidence-verified",
            "All six core claims — owner, survey number, extent, registration date, encumbrance "
            "status and tax status — reached VERIFIED against independent or authoritative "
            "sources.",
            is_mitigation=True,
        )
    ]


# ===========================================================================
# Valuation
# ===========================================================================
@rule
def r_tax_default(ctx: RiskContext) -> list[RuleHit]:
    claims = ctx.claims_of(ClaimType.TAX_STATUS)
    for c in claims:
        if normalise_categorical(c.value).text == "unpaid":
            return [
                RuleHit(
                    "TAX_DEFAULT",
                    RiskCategory.VALUATION,
                    12.0,
                    Severity.MEDIUM,
                    "Property tax in arrears",
                    "Outstanding municipal dues transfer with the property in most jurisdictions "
                    "and can obstruct mutation of the record after sale.",
                    [ctx.claim_ref(c)],
                )
            ]
    if not ctx.has_doc(DocumentType.TAX_RECEIPT):
        return [
            RuleHit(
                "MISSING_TAX_RECEIPT",
                RiskCategory.VALUATION,
                8.0,
                Severity.LOW,
                "No property tax receipt",
                "Tax receipts corroborate possession and the identity of the person treated by "
                "the municipality as the holder. None is on file.",
            )
        ]
    return []


@rule
def r_valuation_outlier(ctx: RiskContext) -> list[RuleHit]:
    prop = ctx.property
    guideline = getattr(prop, "guideline_value_inr", None)
    asking = getattr(prop, "asking_price_inr", None)
    if not guideline or not asking or guideline <= 0:
        return []
    ratio = asking / guideline
    if 0.75 <= ratio <= 1.6:
        return []
    direction = "below" if ratio < 1 else "above"
    return [
        RuleHit(
            "VALUATION_OUTLIER",
            RiskCategory.VALUATION,
            12.0,
            Severity.MEDIUM,
            f"Asking price is well {direction} guideline value",
            f"The asking price is {ratio:.0%} of the guideline value for this locality. Prices "
            f"far {direction} the guideline are associated with disputed title, distress sales or "
            "under-declaration, and warrant explanation.",
        )
    ]


# ===========================================================================
# Payment
# ===========================================================================
@rule
def r_payment_exposure(ctx: RiskContext) -> list[RuleHit]:
    txn = ctx.transaction
    value = getattr(txn, "consideration_inr", None) or getattr(
        ctx.property, "asking_price_inr", None
    )
    hits = [
        RuleHit(
            "NO_ESCROW_CONFIGURED",
            RiskCategory.PAYMENT,
            5.0,
            Severity.LOW,
            "No escrow arrangement recorded",
            "No escrow or staged-payment arrangement is recorded for this transaction. Payment "
            "protection is out of scope for this prototype (Review-3) and is scored as residual "
            "exposure rather than simulated.",
        )
    ]
    if value and value >= 1_00_00_000:
        hits.append(
            RuleHit(
                "HIGH_VALUE_TRANSACTION",
                RiskCategory.PAYMENT,
                6.0,
                Severity.LOW,
                "High-value transaction",
                f"A consideration of about ₹{value:,.0f} raises the consequence of any "
                "unresolved evidence issue.",
            )
        )
    return hits


# ===========================================================================
# Interaction
# ===========================================================================
@rule
def r_sensitive_share_attempt(ctx: RiskContext) -> list[RuleHit]:
    flagged = [m for m in ctx.messages if m.contained_sensitive]
    if not flagged:
        return []
    kinds = sorted({k for m in flagged for k in (m.sensitive_kinds or [])})
    return [
        RuleHit(
            "SENSITIVE_DATA_SHARE_ATTEMPT",
            RiskCategory.INTERACTION,
            10.0,
            Severity.MEDIUM,
            "Sensitive details attempted in the relay",
            f"{len(flagged)} message(s) contained content matching {', '.join(kinds) or 'sensitive'} "
            "patterns and were redacted before delivery. Moving a negotiation off the audited "
            "channel removes the protections this platform provides.",
        )
    ]


@rule
def r_unanswered_consent(ctx: RiskContext) -> list[RuleHit]:
    from ...domain import ConsentStatus

    pending = [
        r for r in ctx.consent_requests
        if r.status == ConsentStatus.REQUESTED.value
        and (ctx.today - (r.created_at.date() if hasattr(r.created_at, "date") else ctx.today)).days
        >= 3
    ]
    denied_material = [
        r for r in ctx.consent_requests
        if r.status == ConsentStatus.DENIED.value
    ]
    hits = []
    if pending:
        hits.append(
            RuleHit(
                "UNANSWERED_ACCESS_REQUEST",
                RiskCategory.INTERACTION,
                8.0,
                Severity.LOW,
                "Access request unanswered",
                f"{len(pending)} evidence-access request(s) have been open for three days or more "
                "without an owner decision.",
            )
        )
    if denied_material:
        hits.append(
            RuleHit(
                "EVIDENCE_ACCESS_DENIED",
                RiskCategory.INTERACTION,
                10.0,
                Severity.MEDIUM,
                "Owner declined to share evidence",
                "The owner declined a request for supporting evidence. Refusal is the owner's "
                "right under the consent model, and it also means the buyer proceeds on less "
                "evidence — both facts are recorded.",
            )
        )
    return hits


# ===========================================================================
def evaluate(ctx: RiskContext) -> list[RuleHit]:
    """Run every rule, honouring the simulator's suppression set."""
    hits: list[RuleHit] = []
    for fn in RULES:
        try:
            produced = fn(ctx) or []
        except Exception as exc:  # a broken rule must not take the platform down
            produced = [
                RuleHit(
                    f"RULE_ERROR::{fn.__name__}",
                    RiskCategory.DOCUMENT,
                    0.0,
                    Severity.INFO,
                    "Rule evaluation error",
                    f"{fn.__name__} raised {type(exc).__name__}: {exc}",
                )
            ]
        for hit in produced:
            if hit.rule_id in ctx.suppressed:
                continue
            hits.append(hit)
    return hits


RULE_CATALOGUE = {
    "BASELINE_NO_OFFICIAL_CONFIRMATION": 18.0,
    "OWNER_CONTRADICTION": 30.0,
    "OWNER_NAME_VARIANT": 8.0,
    "SINGLE_SOURCE_OWNER": 12.0,
    "OWNER_DECLARED_ONLY": 26.0,
    "EXPIRED_POA": 35.0,
    "UNVERIFIED_SELLER_AUTHORITY": 28.0,
    # Scaled by the size of the discrepancy: 14 at the materiality threshold,
    # rising to 36 for a difference of 15 % or more of the recorded extent.
    "AREA_MISMATCH": "14.0–36.0",
    "SURVEY_MISMATCH": 25.0,
    "MISSING_SURVEY_RECORD": 15.0,
    "ACTIVE_MORTGAGE": 30.0,
    "MISSING_EC": 20.0,
    "STALE_EC": 10.0,
    "ENCUMBRANCE_DISCLOSURE_CONFLICT": 24.0,
    # 24 for an isolated font alone, +6 per corroborating integrity indicator.
    "SUSPICIOUS_EDIT": "24.0–36.0",
    "MISSING_PAGE": 12.0,
    "DUPLICATE_DOCUMENT": 10.0,
    "EXPIRED_DOCUMENT": 14.0,
    "CHRONOLOGY_VIOLATION": 18.0,
    "TAX_DEFAULT": 12.0,
    "MISSING_TAX_RECEIPT": 8.0,
    "VALUATION_OUTLIER": 12.0,
    "NO_ESCROW_CONFIGURED": 5.0,
    "HIGH_VALUE_TRANSACTION": 6.0,
    "SENSITIVE_DATA_SHARE_ATTEMPT": 10.0,
    "UNANSWERED_ACCESS_REQUEST": 8.0,
    "EVIDENCE_ACCESS_DENIED": 10.0,
    "VERIFIED_OWNER": -10.0,
    "CLEAR_ENCUMBRANCE": -8.0,
    "BANK_NOC_PRESENT": -20.0,
    "ALL_CORE_CLAIMS_VERIFIED": -6.0,
}
