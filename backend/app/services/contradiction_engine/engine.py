"""
Cross-document contradiction detection.

Three families of check:

1. **Intra-type comparison** — every pair of claims of the same type coming from
   different documents is compared with the type-appropriate strategy
   (services/normalization.py).  Agreements are recorded as ClaimSupport edges,
   disagreements as Contradiction rows.  Both directions matter: the Claim-Evidence
   Matrix needs "3 supporting / 1 conflicting" counts, not just a boolean.

2. **Cross-type semantic checks** — facts that only contradict when two *different*
   attributes are read together: taxpayer vs owner, listing owner vs deed owner,
   POA expiry vs the transaction date, declared encumbrance vs certified encumbrance.

3. **Absence checks** — an expected claim with no evidence at all.  Silence is not
   safety: a missing encumbrance certificate is recorded as MISSING_EVIDENCE so it
   can carry risk weight and appear in the resolution plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from ...domain import (
    CORE_CLAIM_TYPES,
    ClaimType,
    ContradictionType,
    DocumentType,
    MatchType,
    Severity,
)
from ..normalization import Comparison, compare_values, parse_date
from ..verification.authority import authority_of


@dataclass
class SupportEdge:
    claim_id: str
    related_claim_id: str
    match_type: str
    is_supporting: bool
    similarity: float
    note: str


@dataclass
class ContradictionRecord:
    contradiction_type: str
    claim_type: str
    severity: str
    left_claim_id: str | None
    right_claim_id: str | None
    left_value: str
    right_value: str
    left_source: str
    right_source: str
    difference: str
    magnitude: float | None
    explanation: str
    detection_rule: str


@dataclass
class DetectionResult:
    supports: list[SupportEdge] = field(default_factory=list)
    contradictions: list[ContradictionRecord] = field(default_factory=list)

    def conflicting_claim_ids(self) -> set[str]:
        ids: set[str] = set()
        for c in self.contradictions:
            if c.left_claim_id:
                ids.add(c.left_claim_id)
            if c.right_claim_id:
                ids.add(c.right_claim_id)
        return ids


CONTRADICTION_FOR_CLAIM = {
    ClaimType.OWNER_NAME.value: ContradictionType.OWNER_IDENTITY,
    ClaimType.SELLER_NAME.value: ContradictionType.OWNER_IDENTITY,
    ClaimType.TAXPAYER_NAME.value: ContradictionType.TAXPAYER_MISMATCH,
    ClaimType.SURVEY_NUMBER.value: ContradictionType.SURVEY_IDENTITY,
    ClaimType.PROPERTY_AREA.value: ContradictionType.AREA_DISCREPANCY,
    ClaimType.REGISTRATION_DATE.value: ContradictionType.DATE_CHRONOLOGY,
    ClaimType.MORTGAGE_STATUS.value: ContradictionType.ENCUMBRANCE_DISCLOSURE,
    ClaimType.MORTGAGE_AMOUNT.value: ContradictionType.ENCUMBRANCE_DISCLOSURE,
    ClaimType.AUTHORIZATION_EXPIRY.value: ContradictionType.AUTHORIZATION_EXPIRY,
}

# Claim types where a disagreement is genuinely material.  Free-text fields such as
# boundary descriptions vary in wording between offices and are reported as
# observations, not contradictions.
MATERIAL_CLAIM_TYPES = {
    ClaimType.OWNER_NAME.value,
    ClaimType.SELLER_NAME.value,
    ClaimType.SURVEY_NUMBER.value,
    ClaimType.PROPERTY_AREA.value,
    ClaimType.REGISTRATION_DATE.value,
    ClaimType.DOCUMENT_NUMBER.value,
    ClaimType.MORTGAGE_STATUS.value,
    ClaimType.MORTGAGE_AMOUNT.value,
    ClaimType.TAXPAYER_NAME.value,
    ClaimType.AUTHORIZATION_EXPIRY.value,
    ClaimType.TAX_STATUS.value,
}


def _doc_label(doc) -> str:
    if doc is None:
        return "Owner declaration"
    return doc.filename


def _effective(doc, today: date) -> date:
    if doc is None:
        return date.min
    if doc.issued_on:
        return doc.issued_on.date() if hasattr(doc.issued_on, "date") else doc.issued_on
    return today


def _authority_claim(claim_type: str, group: list, docs_by_id: dict, today: date):
    """
    The live claim, if any, coming from the authority of record for this attribute.

    Only unexpired, adequate-quality documents qualify, and where several exist the
    most recent one speaks.
    """
    from ..verification.authority import is_authority_of_record

    candidates = [
        c for c in group
        if c.document_id in docs_by_id
        and is_authority_of_record(docs_by_id[c.document_id].doc_type, claim_type)
        and not docs_by_id[c.document_id].is_expired
        and docs_by_id[c.document_id].quality_score >= 0.45
        and not any(f.get("severity") == "HIGH"
                    for f in (docs_by_id[c.document_id].integrity_flags or []))
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda c: _effective(docs_by_id[c.document_id], today))


def _reconcilable(claim_type, authority_claim, left, right, left_doc, right_doc,
                  docs_by_id) -> bool:
    """
    Whether a disagreement is settled by the authority of record rather than being a
    contradiction.

    This applies whether or not the authoritative document is one of the two being
    compared. Once the survey office has certified an extent, a disagreement *between*
    a deed and a certificate that merely quote that extent is equally settled — both
    were quoting, and the office has now measured. Requiring the authority to be one
    side of the pair would leave the original disagreement standing forever, so
    obtaining the certified measurement could never resolve it.

    Two guards keep this from becoming a way to explain problems away:

      * the authoritative document must **post-date** both documents it settles — a
        newer measurement supersedes an older quotation, never the reverse; and
      * a document carrying a HIGH integrity indicator is **never** reconciled away.
        A deed that shows signs of modification is escalated, not harmonised.
    """
    if authority_claim is None:
        return False
    auth_doc = docs_by_id.get(authority_claim.document_id)
    if auth_doc is None or left_doc is None or right_doc is None:
        return False

    def impeached(doc) -> bool:
        return any(f.get("severity") == "HIGH" for f in (doc.integrity_flags or []))

    if impeached(auth_doc) or impeached(left_doc) or impeached(right_doc):
        return False

    today = date.today()
    auth_date = _effective(auth_doc, today)
    # The authority settles only the documents it post-dates. A document issued after
    # the certified measurement is stating something newer, not quoting something older.
    for doc in (left_doc, right_doc):
        if doc.id == auth_doc.id:
            continue
        if auth_date <= _effective(doc, today):
            return False
    return True


def _explain(claim_type: str, left, right, left_doc, right_doc, cmp: Comparison) -> str:
    lt = _doc_label(left_doc)
    rt = _doc_label(right_doc)
    base = (
        f"{lt} (page {left.source_page}) states '{left.value}' while "
        f"{rt} (page {right.source_page}) states '{right.value}'."
    )
    if cmp.difference:
        base += f" Difference: {cmp.difference}."
    if cmp.note:
        base += f" {cmp.note}"
    la = authority_of(left_doc.doc_type if left_doc else None, claim_type)
    ra = authority_of(right_doc.doc_type if right_doc else None, claim_type)
    if abs(la - ra) >= 0.2:
        stronger = lt if la > ra else rt
        base += (
            f" {stronger} carries the higher evidential authority for this attribute, but the "
            "disagreement is not resolved automatically — an authorised source is required."
        )
    return base


# ---------------------------------------------------------------------------
def detect(
    property_obj,
    claims: list,
    documents: list,
    today: date | None = None,
) -> DetectionResult:
    today = today or date.today()
    result = DetectionResult()
    docs_by_id = {d.id: d for d in documents}

    by_type: dict[str, list] = {}
    for claim in claims:
        if claim.superseded:
            continue
        by_type.setdefault(claim.claim_type, []).append(claim)

    # ---- 1. intra-type pairwise comparison ---------------------------------
    for claim_type, group in by_type.items():
        authority_claim = _authority_claim(claim_type, group, docs_by_id, today)
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                left, right = group[i], group[j]
                if left.document_id and left.document_id == right.document_id:
                    continue  # same document cannot corroborate itself
                cmp = compare_values(claim_type, left.value, right.value)
                left_doc = docs_by_id.get(left.document_id)
                right_doc = docs_by_id.get(right.document_id)

                if cmp.match_type is MatchType.MISSING:
                    continue

                reconciled = _reconcilable(
                    claim_type, authority_claim, left, right, left_doc, right_doc,
                    docs_by_id,
                )
                if cmp.is_material_conflict and reconciled:
                    note = (
                        f"Reconciled to the authority of record: "
                        f"'{docs_by_id[authority_claim.document_id].filename}' certifies "
                        f"'{authority_claim.value}' and post-dates both documents, which quote "
                        "this attribute rather than determine it."
                    )
                    result.supports.append(
                        SupportEdge(left.id, right.id, MatchType.NORMALIZED_MATCH.value,
                                    True, 0.9, note)
                    )
                    result.supports.append(
                        SupportEdge(right.id, left.id, MatchType.NORMALIZED_MATCH.value,
                                    True, 0.9, note)
                    )
                    continue

                supporting = cmp.agrees
                note = cmp.note or (
                    "Values agree." if supporting else "Values disagree."
                )
                result.supports.append(
                    SupportEdge(left.id, right.id, cmp.match_type.value, supporting,
                                round(cmp.similarity, 4), note)
                )
                result.supports.append(
                    SupportEdge(right.id, left.id, cmp.match_type.value, supporting,
                                round(cmp.similarity, 4), note)
                )

                if not cmp.is_material_conflict:
                    continue
                if claim_type not in MATERIAL_CLAIM_TYPES:
                    continue

                result.contradictions.append(
                    ContradictionRecord(
                        contradiction_type=CONTRADICTION_FOR_CLAIM.get(
                            claim_type, ContradictionType.DOCUMENT_INTEGRITY
                        ).value,
                        claim_type=claim_type,
                        severity=cmp.severity.value,
                        left_claim_id=left.id,
                        right_claim_id=right.id,
                        left_value=left.value,
                        right_value=right.value,
                        left_source=f"{_doc_label(left_doc)} p{left.source_page}",
                        right_source=f"{_doc_label(right_doc)} p{right.source_page}",
                        difference=cmp.difference,
                        magnitude=cmp.magnitude,
                        explanation=_explain(claim_type, left, right, left_doc, right_doc, cmp),
                        detection_rule=f"PAIRWISE::{claim_type}",
                    )
                )

    # ---- 2. cross-type semantic checks -------------------------------------
    result.contradictions.extend(
        _listing_vs_evidence(property_obj, by_type, docs_by_id)
    )
    result.contradictions.extend(_taxpayer_vs_owner(by_type, docs_by_id))
    result.contradictions.extend(_authorisation_checks(by_type, docs_by_id, today))
    result.contradictions.extend(_chronology_checks(by_type, docs_by_id))
    result.contradictions.extend(_integrity_checks(documents))

    # ---- 3. absence checks --------------------------------------------------
    result.contradictions.extend(_absence_checks(by_type, documents))

    return result


# ---------------------------------------------------------------------------
def _listing_vs_evidence(property_obj, by_type, docs_by_id) -> list[ContradictionRecord]:
    """The name on the listing has no evidential weight until documents support it."""
    listed = (property_obj.listed_owner_name or "").strip()
    if not listed:
        return []
    out: list[ContradictionRecord] = []
    for claim in by_type.get(ClaimType.OWNER_NAME.value, []):
        doc = docs_by_id.get(claim.document_id)
        if doc and doc.doc_type == DocumentType.OWNER_DECLARATION.value:
            continue
        cmp = compare_values(ClaimType.OWNER_NAME.value, listed, claim.value)
        if not cmp.is_material_conflict:
            continue
        out.append(
            ContradictionRecord(
                contradiction_type=ContradictionType.OWNER_IDENTITY.value,
                claim_type=ClaimType.OWNER_NAME.value,
                severity=Severity.CRITICAL.value,
                left_claim_id=None,
                right_claim_id=claim.id,
                left_value=listed,
                right_value=claim.value,
                left_source="Listing (owner-entered)",
                right_source=f"{_doc_label(docs_by_id.get(claim.document_id))} p{claim.source_page}",
                difference=f"'{listed}' vs '{claim.value}'",
                magnitude=None,
                explanation=(
                    f"The property is listed under '{listed}', but the supporting evidence "
                    f"identifies '{claim.value}' as the owner. Ownership cannot be established "
                    "for the listing party from the documents provided. This does not by itself "
                    "prove impersonation; it means the seller's authority is unverified."
                ),
                detection_rule="LISTING_VS_EVIDENCE",
            )
        )
        break  # one contradiction per listing is enough
    return out


def _taxpayer_vs_owner(by_type, docs_by_id) -> list[ContradictionRecord]:
    owners = by_type.get(ClaimType.OWNER_NAME.value, [])
    payers = by_type.get(ClaimType.TAXPAYER_NAME.value, [])
    if not owners or not payers:
        return []
    out: list[ContradictionRecord] = []
    for payer in payers:
        agrees_with_any = False
        worst = None
        for owner in owners:
            cmp = compare_values(ClaimType.OWNER_NAME.value, owner.value, payer.value)
            if cmp.agrees:
                agrees_with_any = True
                break
            worst = (owner, cmp)
        if agrees_with_any or worst is None:
            continue
        owner, cmp = worst
        out.append(
            ContradictionRecord(
                contradiction_type=ContradictionType.TAXPAYER_MISMATCH.value,
                claim_type=ClaimType.TAXPAYER_NAME.value,
                severity=Severity.MEDIUM.value,
                left_claim_id=owner.id,
                right_claim_id=payer.id,
                left_value=owner.value,
                right_value=payer.value,
                left_source=f"{_doc_label(docs_by_id.get(owner.document_id))} p{owner.source_page}",
                right_source=f"{_doc_label(docs_by_id.get(payer.document_id))} p{payer.source_page}",
                difference=f"'{owner.value}' vs '{payer.value}'",
                magnitude=None,
                explanation=(
                    f"Property tax is recorded against '{payer.value}' while the ownership "
                    f"evidence names '{owner.value}'. A relative or agent may legitimately pay "
                    "tax, so this is an item to clarify rather than a defect in title."
                ),
                detection_rule="TAXPAYER_VS_OWNER",
            )
        )
    return out


def _authorisation_checks(by_type, docs_by_id, today: date) -> list[ContradictionRecord]:
    """A power of attorney that has lapsed cannot authorise a present-day sale."""
    out: list[ContradictionRecord] = []
    for claim in by_type.get(ClaimType.AUTHORIZATION_EXPIRY.value, []):
        expiry = parse_date(claim.value)
        if not expiry or expiry >= today:
            continue
        doc = docs_by_id.get(claim.document_id)
        holder = next(
            (c.value for c in by_type.get(ClaimType.POA_HOLDER.value, [])
             if c.document_id == claim.document_id),
            None,
        )
        out.append(
            ContradictionRecord(
                contradiction_type=ContradictionType.AUTHORIZATION_EXPIRY.value,
                claim_type=ClaimType.AUTHORIZATION_EXPIRY.value,
                severity=Severity.CRITICAL.value,
                left_claim_id=claim.id,
                right_claim_id=None,
                left_value=claim.value,
                right_value=f"today {today:%d-%m-%Y}",
                left_source=f"{_doc_label(doc)} p{claim.source_page}",
                right_source="System clock",
                difference=f"expired {(today - expiry).days} days ago",
                magnitude=float((today - expiry).days),
                explanation=(
                    f"The authorisation{f' held by {holder}' if holder else ''} expired on "
                    f"{expiry:%d-%m-%Y}, {(today - expiry).days} days ago. Any party acting under "
                    "it has no current authority on the evidence available, so the transaction "
                    "cannot proceed on this document alone."
                ),
                detection_rule="POA_EXPIRY",
            )
        )
    return out


def _chronology_checks(by_type, docs_by_id) -> list[ContradictionRecord]:
    """Registration must not predate the authority under which it was executed."""
    out: list[ContradictionRecord] = []
    regs = by_type.get(ClaimType.REGISTRATION_DATE.value, [])
    expiries = by_type.get(ClaimType.AUTHORIZATION_EXPIRY.value, [])
    for reg in regs:
        rd = parse_date(reg.value)
        if not rd:
            continue
        for exp in expiries:
            ed = parse_date(exp.value)
            if not ed or rd <= ed:
                continue
            out.append(
                ContradictionRecord(
                    contradiction_type=ContradictionType.DATE_CHRONOLOGY.value,
                    claim_type=ClaimType.REGISTRATION_DATE.value,
                    severity=Severity.HIGH.value,
                    left_claim_id=reg.id,
                    right_claim_id=exp.id,
                    left_value=reg.value,
                    right_value=exp.value,
                    left_source=f"{_doc_label(docs_by_id.get(reg.document_id))} p{reg.source_page}",
                    right_source=f"{_doc_label(docs_by_id.get(exp.document_id))} p{exp.source_page}",
                    difference=f"registered {(rd - ed).days} days after authority lapsed",
                    magnitude=float((rd - ed).days),
                    explanation=(
                        f"A registration dated {rd:%d-%m-%Y} post-dates the expiry of the "
                        f"authorisation on {ed:%d-%m-%Y}. The chronology of authority and "
                        "execution does not hold on the evidence supplied."
                    ),
                    detection_rule="CHRONOLOGY_AUTHORITY",
                )
            )
    return out


# Indicators that describe the *integrity* of a document, as distinct from its
# currency.  An expired certificate is not an integrity problem — it is handled by the
# verification resolver (EXPIRED status) and, for authorisations, by the dedicated
# expiry check.  Promoting it here as well would double-count one fact as two.
INTEGRITY_CODES = {
    "FONT_DISCONTINUITY",
    "INCREMENTAL_SAVE",
    "MISSING_PAGE",
    "METADATA_MODIFIED",
    "NO_TEXT_RECOVERED",
    "REWRITER_TOOL",
}


def _integrity_checks(documents) -> list[ContradictionRecord]:
    """Promote high-severity document *integrity* indicators into the ledger."""
    out: list[ContradictionRecord] = []
    seen_checksums: dict[str, str] = {}
    for doc in documents:
        for flag in (doc.integrity_flags or []):
            if flag.get("severity") != "HIGH" or flag.get("code") not in INTEGRITY_CODES:
                continue
            out.append(
                ContradictionRecord(
                    contradiction_type=ContradictionType.DOCUMENT_INTEGRITY.value,
                    claim_type="document_integrity",
                    severity=Severity.HIGH.value,
                    left_claim_id=None,
                    right_claim_id=None,
                    left_value=flag.get("label", flag.get("code", "")),
                    right_value="",
                    left_source=doc.filename,
                    right_source="",
                    difference=flag.get("code", ""),
                    magnitude=None,
                    explanation=flag.get("detail", ""),
                    detection_rule=f"INTEGRITY::{flag.get('code')}",
                )
            )
        if doc.checksum:
            if doc.checksum in seen_checksums and seen_checksums[doc.checksum] != doc.id:
                out.append(
                    ContradictionRecord(
                        contradiction_type=ContradictionType.DOCUMENT_INTEGRITY.value,
                        claim_type="document_integrity",
                        severity=Severity.MEDIUM.value,
                        left_claim_id=None,
                        right_claim_id=None,
                        left_value=doc.filename,
                        right_value=seen_checksums[doc.checksum],
                        left_source=doc.filename,
                        right_source="earlier upload",
                        difference="identical checksum",
                        magnitude=None,
                        explanation=(
                            f"'{doc.filename}' is byte-identical to a document already on file. "
                            "A duplicate upload adds no independent corroboration, so it is "
                            "excluded from the count of supporting sources."
                        ),
                        detection_rule="DUPLICATE_DOCUMENT",
                    )
                )
            else:
                seen_checksums[doc.checksum] = doc.id
    return out


REQUIRED_DOCUMENTS = {
    DocumentType.SALE_DEED: "Title evidence — establishes who acquired the property and when.",
    DocumentType.ENCUMBRANCE_CERTIFICATE: (
        "Encumbrance evidence — without it, an undisclosed mortgage cannot be ruled out."
    ),
    DocumentType.SURVEY_RECORD: "Extent evidence — the authority of record for area and boundaries.",
}


def _absence_checks(by_type, documents) -> list[ContradictionRecord]:
    out: list[ContradictionRecord] = []
    present_types = {d.doc_type for d in documents if not d.is_pending_evidence}

    for doc_type, why in REQUIRED_DOCUMENTS.items():
        if doc_type.value in present_types:
            continue
        out.append(
            ContradictionRecord(
                contradiction_type=ContradictionType.MISSING_EVIDENCE.value,
                claim_type="document_completeness",
                severity=(
                    Severity.HIGH.value
                    if doc_type is not DocumentType.SURVEY_RECORD
                    else Severity.MEDIUM.value
                ),
                left_claim_id=None,
                right_claim_id=None,
                left_value=doc_type.value,
                right_value="not provided",
                left_source="Evidence completeness check",
                right_source="",
                difference="missing",
                magnitude=None,
                explanation=(
                    f"No {doc_type.value.replace('_', ' ').title()} has been provided. {why} "
                    "Absence of evidence is recorded explicitly so it can be resolved, rather "
                    "than treated as an absence of risk."
                ),
                detection_rule=f"MISSING_DOCUMENT::{doc_type.value}",
            )
        )

    for claim_type in CORE_CLAIM_TYPES:
        if by_type.get(claim_type.value):
            continue
        out.append(
            ContradictionRecord(
                contradiction_type=ContradictionType.MISSING_EVIDENCE.value,
                claim_type=claim_type.value,
                severity=Severity.MEDIUM.value,
                left_claim_id=None,
                right_claim_id=None,
                left_value=claim_type.value,
                right_value="no evidence",
                left_source="Claim completeness check",
                right_source="",
                difference="missing",
                magnitude=None,
                explanation=(
                    f"No document on file asserts a value for "
                    f"'{claim_type.value.replace('_', ' ')}'. The claim is held at PENDING; it is "
                    "not displayed as unknown-but-fine."
                ),
                detection_rule=f"MISSING_CLAIM::{claim_type.value}",
            )
        )
    return out
