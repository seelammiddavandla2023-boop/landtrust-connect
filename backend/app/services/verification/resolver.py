"""
Verification resolution — the evidence gate.

This is the module the whole research contribution turns on.  A claim's
verification status is a *derived property of the evidence set*, computed here and
nowhere else.  The extractor cannot write it; the UI cannot assume it; an LLM never
produces it.

Policy (in order of precedence)
-------------------------------
1. CONFLICTING       another document materially disagrees.
2. EXPIRED           every supporting document's validity period has lapsed.
3. OWNER_PROVIDED    the only source is the owner's own declaration.
4. VERIFIED          either (a) ≥2 independent documents agree by exact or
                     normalised match and their combined authority ≥ 0.90, or
                     (b) a single document that is the authority of record for that
                     attribute, unexpired and of adequate quality.
5. PARTIALLY_VERIFIED corroborated, but only approximately (initials, tolerance
                     bands), or supported by exactly one non-authoritative source.
6. PENDING           expected but no evidence at all.
7. UNVERIFIED        anything else.

Rule 5's single-source case is the direct answer to the brief's central
requirement: appearing in one uploaded document must not make a claim VERIFIED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..normalization import kind_for, normalise_name
from ...domain import (
    CORE_CLAIM_TYPES,
    VERIFICATION_RANK,
    ClaimType,
    DocumentType,
    MatchType,
    ValueKind,
    VerificationStatus,
    sensitivity_of,
)
from .authority import authority_of, combined_authority, is_authority_of_record

VERIFY_AUTHORITY_THRESHOLD = 0.90
MIN_CLAIM_CONFIDENCE = 0.55
MIN_DOCUMENT_QUALITY = 0.45


@dataclass
class ClaimResolution:
    claim_id: str
    claim_type: str
    status: VerificationStatus
    explanation: str
    supporting_document_ids: list[str] = field(default_factory=list)
    conflicting_document_ids: list[str] = field(default_factory=list)
    combined_authority: float = 0.0


@dataclass
class GroupResolution:
    claim_type: str
    status: VerificationStatus
    explanation: str
    claim_ids: list[str] = field(default_factory=list)
    supporting_document_ids: list[str] = field(default_factory=list)
    conflicting_document_ids: list[str] = field(default_factory=list)
    combined_authority: float = 0.0
    consensus_value: str | None = None


@dataclass
class ResolutionOutcome:
    per_claim: dict[str, ClaimResolution] = field(default_factory=dict)
    per_type: dict[str, GroupResolution] = field(default_factory=dict)
    pending_types: list[str] = field(default_factory=list)

    def status_of(self, claim_type: str) -> VerificationStatus:
        group = self.per_type.get(claim_type)
        return group.status if group else VerificationStatus.PENDING

    def verification_level(self) -> float:
        """Share of core claim types that reached VERIFIED (0..1)."""
        if not CORE_CLAIM_TYPES:
            return 0.0
        verified = sum(
            1 for ct in CORE_CLAIM_TYPES
            if self.status_of(ct.value) is VerificationStatus.VERIFIED
        )
        return round(verified / len(CORE_CLAIM_TYPES), 4)


def _doc_name(doc) -> str:
    return doc.filename if doc is not None else "Owner declaration"


def _fmt_list(names: list[str]) -> str:
    if not names:
        return "no documents"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + f" and {names[-1]}"


def _name_equivalences(claims: list, documents: list) -> set[frozenset[str]]:
    """
    Sworn statements that two name forms denote the same person.

    Returned as normalised unordered pairs. Only unexpired documents that are the
    authority of record for NAME_EQUIVALENCE count — in practice, a notarised
    affidavit. An owner simply asserting "those are both me" is not this.
    """
    from ..normalization import normalise_name

    docs = {d.id: d for d in documents}
    pairs: set[frozenset[str]] = set()
    for claim in claims:
        if claim.claim_type != ClaimType.NAME_EQUIVALENCE.value or claim.superseded:
            continue
        doc = docs.get(claim.document_id)
        if doc is None or doc.is_expired:
            continue
        if not is_authority_of_record(doc.doc_type, ClaimType.NAME_EQUIVALENCE.value):
            continue
        parts = [p.strip() for p in claim.value.split("||") if p.strip()]
        if len(parts) != 2:
            continue
        pairs.add(frozenset(normalise_name(p).text for p in parts))
    return pairs


def resolve(
    claims: list,
    documents: list,
    support_edges: list,
    contradictions: list,
    today: date | None = None,
) -> ResolutionOutcome:
    """
    Assign a verification status to every claim and to every claim *type*.

    `support_edges` are the SupportEdge records produced by the contradiction engine;
    `contradictions` are its ContradictionRecord objects.
    """
    today = today or date.today()
    outcome = ResolutionOutcome()
    docs_by_id = {d.id: d for d in documents}

    # Claim ids that participate in a material contradiction.
    conflicted: set[str] = set()
    conflict_note: dict[str, str] = {}
    for c in contradictions:
        for cid in (c.left_claim_id, c.right_claim_id):
            if cid:
                conflicted.add(cid)
                conflict_note.setdefault(cid, c.explanation)

    # Edge index: claim_id -> list of (related_claim_id, match_type, supporting)
    edges: dict[str, list] = {}
    for e in support_edges:
        edges.setdefault(e.claim_id, []).append(e)

    equivalences = _name_equivalences(claims, documents)

    by_type: dict[str, list] = {}
    for claim in claims:
        if claim.superseded:
            continue
        by_type.setdefault(claim.claim_type, []).append(claim)

    for claim_type, group in by_type.items():
        group_res = _resolve_group(
            claim_type, group, docs_by_id, edges, conflicted, conflict_note, today,
            equivalences,
        )
        outcome.per_type[claim_type] = group_res
        for claim in group:
            outcome.per_claim[claim.id] = ClaimResolution(
                claim_id=claim.id,
                claim_type=claim_type,
                status=group_res.status,
                explanation=group_res.explanation,
                supporting_document_ids=group_res.supporting_document_ids,
                conflicting_document_ids=group_res.conflicting_document_ids,
                combined_authority=group_res.combined_authority,
            )

    # Expected-but-absent claim types are PENDING, not silent.
    for claim_type in CORE_CLAIM_TYPES:
        if claim_type.value in outcome.per_type:
            continue
        outcome.pending_types.append(claim_type.value)
        outcome.per_type[claim_type.value] = GroupResolution(
            claim_type=claim_type.value,
            status=VerificationStatus.PENDING,
            explanation=(
                "No document on file asserts this detail, so it is held at PENDING. "
                "It is not shown to a buyer as absent-and-therefore-satisfactory."
            ),
        )
    return outcome


def _resolve_group(
    claim_type: str,
    group: list,
    docs_by_id: dict,
    edges: dict,
    conflicted: set[str],
    conflict_note: dict[str, str],
    today: date,
    equivalences: set[frozenset[str]] | None = None,
) -> GroupResolution:
    claim_ids = [c.id for c in group]
    doc_ids = [c.document_id for c in group if c.document_id]
    docs = [docs_by_id.get(d) for d in doc_ids]
    doc_names = [_doc_name(d) for d in docs]

    # --- 1. conflict -------------------------------------------------------
    conflicting_here = [c for c in group if c.id in conflicted]
    if conflicting_here:
        note = conflict_note.get(conflicting_here[0].id, "")
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.CONFLICTING,
            explanation=(
                f"Sources disagree on this detail, so it cannot be presented as verified. {note}"
            ).strip(),
            claim_ids=claim_ids,
            supporting_document_ids=[],
            conflicting_document_ids=[c.document_id for c in conflicting_here if c.document_id],
        )

    # --- 2. owner-declared only -------------------------------------------
    real_docs = [
        d for d in docs
        if d is not None and d.doc_type != DocumentType.OWNER_DECLARATION.value
    ]
    if not real_docs:
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.OWNER_PROVIDED,
            explanation=(
                "Stated by the owner with no supporting document. Shown as owner-provided "
                "information and never as verified."
            ),
            claim_ids=claim_ids,
        )

    # De-duplicate byte-identical documents: a duplicate is not a second witness.
    unique_docs, seen = [], set()
    for d in real_docs:
        key = d.checksum or d.id
        if key in seen:
            continue
        seen.add(key)
        unique_docs.append(d)

    # --- 3. expiry ---------------------------------------------------------
    live_docs = [d for d in unique_docs if not d.is_expired]
    if unique_docs and not live_docs:
        names = _fmt_list([d.filename for d in unique_docs])
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.EXPIRED,
            explanation=(
                f"The only evidence for this detail is {names}, whose validity period has "
                "lapsed. An expired document is not treated as current proof."
            ),
            claim_ids=claim_ids,
            supporting_document_ids=[d.id for d in unique_docs],
        )

    def _unimpeached(doc) -> bool:
        """
        A document showing indicators of post-issue modification is not a witness.

        Corroboration means two sources that independently attest to the same fact.
        A file that may have been altered attests to whatever the alteration says, so
        counting it as the second of two witnesses would let a single edit manufacture
        the corroboration the evidence gate exists to require.
        """
        return not any(f.get("severity") == "HIGH" for f in (doc.integrity_flags or []))

    quality_docs = [d for d in live_docs if d.quality_score >= MIN_DOCUMENT_QUALITY]
    impeached = [d for d in quality_docs if not _unimpeached(d)]
    usable_docs = [d for d in quality_docs if _unimpeached(d)]

    if impeached and not usable_docs:
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.PARTIALLY_VERIFIED,
            explanation=(
                f"The only evidence for this detail is "
                f"{_fmt_list([d.filename for d in impeached])}, which carries a high-severity "
                "integrity indicator. A document that may have been altered after issue cannot "
                "corroborate its own contents; a certified copy from the issuing authority is "
                "required."
            ),
            claim_ids=claim_ids,
            supporting_document_ids=[d.id for d in impeached],
        )

    if not usable_docs:
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.UNVERIFIED,
            explanation=(
                "Supporting documents did not meet the minimum quality threshold "
                f"({MIN_DOCUMENT_QUALITY:.0%}), so their contents are not relied upon."
            ),
            claim_ids=claim_ids,
            supporting_document_ids=[d.id for d in live_docs],
        )

    usable_ids = {d.id for d in usable_docs}
    usable_claims = [c for c in group if c.document_id in usable_ids]
    low_confidence = [c for c in usable_claims if c.confidence < MIN_CLAIM_CONFIDENCE]

    authorities = [authority_of(d.doc_type, claim_type) for d in usable_docs]
    combined = combined_authority(authorities)
    names = [d.filename for d in usable_docs]
    types = [d.doc_type.replace("_", " ").title() for d in usable_docs]

    # --- 4a. authority of record, single source ----------------------------
    authoritative = [d for d in usable_docs if is_authority_of_record(d.doc_type, claim_type)]
    if authoritative and not low_confidence:
        if len(usable_docs) == 1:
            d = authoritative[0]
            return GroupResolution(
                claim_type=claim_type,
                status=VerificationStatus.VERIFIED,
                explanation=(
                    f"Supported by {d.filename}, which is the authority of record for "
                    f"{claim_type.replace('_', ' ')}. A single source verifies only when it is "
                    "the issuing authority for that attribute."
                ),
                claim_ids=claim_ids,
                supporting_document_ids=[d.id for d in usable_docs],
                combined_authority=combined,
                consensus_value=usable_claims[0].value if usable_claims else None,
            )

    # --- 4b/5. corroboration quality ---------------------------------------
    match_types = set()
    for c in usable_claims:
        for e in edges.get(c.id, []):
            if e.related_claim_id in {x.id for x in usable_claims}:
                match_types.add(e.match_type)

    approximate = bool(match_types & {MatchType.PARTIAL_MATCH.value})
    reconciled_note = ""

    # A name variant is closed by evidence about the *relationship between the two
    # names*, not by anyone asserting that one of them is correct. Where a sworn
    # equivalence covers every differing pair in this group, the agreement is exact
    # in substance even though the strings differ.
    if approximate and equivalences and kind_for(claim_type) is ValueKind.PERSON_NAME:
        forms = {normalise_name(c.value).text for c in usable_claims}
        uncovered = [
            frozenset({a, b})
            for i, a in enumerate(sorted(forms))
            for b in sorted(forms)[i + 1:]
            if a != b and frozenset({a, b}) not in equivalences
        ]
        if not uncovered:
            approximate = False
            reconciled_note = (
                " The differing name forms are reconciled by a sworn equivalence on file, so "
                "they are treated as the same person rather than as an unexplained variant."
            )

    independent_sources = len(usable_docs)

    if independent_sources >= 2 and combined >= VERIFY_AUTHORITY_THRESHOLD and not approximate \
            and not low_confidence:
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.VERIFIED,
            explanation=(
                f"Consistent across {independent_sources} independent documents "
                f"({_fmt_list(types)}). Combined evidential authority {combined:.0%}, above the "
                f"{VERIFY_AUTHORITY_THRESHOLD:.0%} threshold required to present a claim as "
                f"verified.{reconciled_note}"
            ),
            claim_ids=claim_ids,
            supporting_document_ids=[d.id for d in usable_docs],
            combined_authority=combined,
            consensus_value=usable_claims[0].value if usable_claims else None,
        )

    if approximate and independent_sources >= 2:
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.PARTIALLY_VERIFIED,
            explanation=(
                f"{independent_sources} documents refer to the same detail but not in identical "
                "form (for example an abbreviated name component or a value within tolerance). "
                "The agreement is close enough to rule out a different subject, but not exact "
                "enough to certify."
            ),
            claim_ids=claim_ids,
            supporting_document_ids=[d.id for d in usable_docs],
            combined_authority=combined,
            consensus_value=usable_claims[0].value if usable_claims else None,
        )

    if independent_sources == 1:
        d = usable_docs[0]
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.PARTIALLY_VERIFIED,
            explanation=(
                f"Asserted only by {d.filename} ({d.doc_type.replace('_', ' ').title()}), which is "
                f"not the authority of record for {claim_type.replace('_', ' ')} "
                f"(authority {authorities[0]:.0%}). One uploaded document is not sufficient to "
                "present a claim as verified — independent corroboration is required."
            ),
            claim_ids=claim_ids,
            supporting_document_ids=[d.id],
            combined_authority=combined,
            consensus_value=usable_claims[0].value if usable_claims else None,
        )

    if low_confidence:
        return GroupResolution(
            claim_type=claim_type,
            status=VerificationStatus.PARTIALLY_VERIFIED,
            explanation=(
                f"Sources agree, but extraction confidence for at least one value is below "
                f"{MIN_CLAIM_CONFIDENCE:.0%}. The reading itself needs confirmation before the "
                "claim can be certified."
            ),
            claim_ids=claim_ids,
            supporting_document_ids=[d.id for d in usable_docs],
            combined_authority=combined,
        )

    return GroupResolution(
        claim_type=claim_type,
        status=VerificationStatus.PARTIALLY_VERIFIED,
        explanation=(
            f"Corroborated by {_fmt_list(names)}, but combined evidential authority is "
            f"{combined:.0%}, below the {VERIFY_AUTHORITY_THRESHOLD:.0%} threshold for a verified "
            "presentation."
        ),
        claim_ids=claim_ids,
        supporting_document_ids=[d.id for d in usable_docs],
        combined_authority=combined,
    )


def apply(claims: list, outcome: ResolutionOutcome) -> list[tuple[str, str, str]]:
    """
    Write resolved statuses onto Claim rows.

    Returns (claim_id, old_status, new_status) for every change, so the audit layer
    can record CLAIM_STATUS_CHANGED events with before/after values.
    """
    changes: list[tuple[str, str, str]] = []
    for claim in claims:
        res = outcome.per_claim.get(claim.id)
        if res is None:
            # A superseded claim is no longer part of the current position, so it must
            # not keep whatever status it held when it was. Leaving a stale VERIFIED on
            # the row would let a historical value be filtered and displayed as current.
            if claim.superseded and claim.verification_status != (
                VerificationStatus.UNVERIFIED.value
            ):
                changes.append(
                    (claim.id, claim.verification_status, VerificationStatus.UNVERIFIED.value)
                )
                claim.verification_status = VerificationStatus.UNVERIFIED.value
                claim.status_explanation = (
                    "Superseded by a later document. Retained as history and excluded from the "
                    "current position, so it carries no current verification status."
                )
            continue
        new_status = res.status.value
        if claim.verification_status != new_status:
            changes.append((claim.id, claim.verification_status, new_status))
        claim.verification_status = new_status
        claim.status_explanation = res.explanation
        claim.sensitivity = sensitivity_of(claim.claim_type).value
    return changes


def weakest_core_status(outcome: ResolutionOutcome) -> VerificationStatus:
    statuses = [outcome.status_of(ct.value) for ct in CORE_CLAIM_TYPES]
    return min(statuses, key=lambda s: VERIFICATION_RANK[s]) if statuses else \
        VerificationStatus.PENDING
