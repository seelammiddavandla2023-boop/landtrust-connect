"""
Temporal claim scoping.

A land file is a record of *successive* states, not a set of simultaneous
assertions.  A 2017 deed naming one purchaser and a 2021 deed naming another are
not in contradiction — they are a chain of title.  A 2023 mortgage deed and a 2026
encumbrance certificate reporting "nil" are not in contradiction either — the charge
was discharged in between.

Without this step the contradiction engine would fire on every historical document
and every property with a history would look fraudulent.  With it, only claims that
are *currently* in force are compared, while the superseded ones remain in the
database to build the ownership graph and the timeline.

This is why `Claim.superseded` exists, and why the ownership graph is built from all
claims while verification is computed from live ones only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ...domain import ClaimType, DocumentType
from ..normalization import parse_date

# claim type → the document types that succeed one another for that attribute.
# A claim asserted by an older document of one of these types is superseded by the
# same claim type asserted by a newer one.
SUCCESSION: dict[str, set[str]] = {
    ClaimType.MORTGAGE_STATUS.value: {
        DocumentType.ENCUMBRANCE_CERTIFICATE.value,
        DocumentType.MORTGAGE_DOCUMENT.value,
        DocumentType.BANK_NOC.value,
    },
    ClaimType.MORTGAGE_AMOUNT.value: {
        DocumentType.ENCUMBRANCE_CERTIFICATE.value,
        DocumentType.MORTGAGE_DOCUMENT.value,
        DocumentType.BANK_NOC.value,
    },
    ClaimType.MORTGAGE_LENDER.value: {
        DocumentType.ENCUMBRANCE_CERTIFICATE.value,
        DocumentType.MORTGAGE_DOCUMENT.value,
        DocumentType.BANK_NOC.value,
    },
    ClaimType.ENCUMBRANCE_PERIOD.value: {DocumentType.ENCUMBRANCE_CERTIFICATE.value},
    ClaimType.TAX_STATUS.value: {DocumentType.TAX_RECEIPT.value},
    ClaimType.TAXPAYER_NAME.value: {DocumentType.TAX_RECEIPT.value},
    # Instruments of transfer: only the most recent one states the *current* owner.
    ClaimType.OWNER_NAME.value: {DocumentType.SALE_DEED.value},
    ClaimType.SELLER_NAME.value: {DocumentType.SALE_DEED.value},
    ClaimType.REGISTRATION_DATE.value: {DocumentType.SALE_DEED.value},
    ClaimType.DOCUMENT_NUMBER.value: {DocumentType.SALE_DEED.value},
    ClaimType.CONSIDERATION_VALUE.value: {DocumentType.SALE_DEED.value},
    # Only the latest authorisation is operative.
    ClaimType.POA_HOLDER.value: {DocumentType.POWER_OF_ATTORNEY.value},
    ClaimType.POA_GRANTOR.value: {DocumentType.POWER_OF_ATTORNEY.value},
    ClaimType.AUTHORIZATION_EXPIRY.value: {DocumentType.POWER_OF_ATTORNEY.value},
}


@dataclass
class Supersession:
    claim_id: str
    superseded_by_document_id: str
    reason: str


def effective_date(document, claims: list) -> date:
    """
    When a document's statements became true.

    Preference order: the registration date it asserts, then its issue date, then the
    date it entered the system.  Instruments are dated by what they record, not by
    when someone happened to upload them.
    """
    for c in claims:
        if c.document_id != document.id:
            continue
        if c.claim_type in {ClaimType.REGISTRATION_DATE.value}:
            d = parse_date(c.value)
            if d:
                return d
    if document.issued_on:
        return document.issued_on.date() if isinstance(document.issued_on, datetime) \
            else document.issued_on
    created = getattr(document, "created_at", None)
    if created:
        return created.date() if isinstance(created, datetime) else created
    return date.min


def apply_supersession(claims: list, documents: list) -> list[Supersession]:
    """
    Mark superseded claims and clear the flag on claims that are current.

    Returns the supersessions applied, for the audit trail.
    """
    docs_by_id = {d.id: d for d in documents}
    dates = {d.id: effective_date(d, claims) for d in documents}
    applied: list[Supersession] = []

    # Start from a clean slate so re-running is idempotent.
    for c in claims:
        c.superseded = False

    for claim_type, doc_types in SUCCESSION.items():
        relevant = [
            c for c in claims
            if c.claim_type == claim_type
            and c.document_id in docs_by_id
            and docs_by_id[c.document_id].doc_type in doc_types
            and not docs_by_id[c.document_id].is_pending_evidence
        ]
        if len(relevant) < 2:
            continue
        latest = max(dates[c.document_id] for c in relevant)
        winners = [c for c in relevant if dates[c.document_id] == latest]
        winner_doc = docs_by_id[winners[0].document_id]
        for c in relevant:
            if dates[c.document_id] >= latest:
                continue
            c.superseded = True
            older = docs_by_id[c.document_id]
            applied.append(
                Supersession(
                    claim_id=c.id,
                    superseded_by_document_id=winner_doc.id,
                    reason=(
                        f"'{older.filename}' ({dates[c.document_id]:%d-%m-%Y}) is superseded for "
                        f"{claim_type.replace('_', ' ')} by '{winner_doc.filename}' "
                        f"({latest:%d-%m-%Y}). The earlier statement is retained as history and "
                        "excluded from current-state comparison."
                    ),
                )
            )
    return applied


def history_of(claims: list, documents: list, claim_type: str) -> list[dict]:
    """Chronological history of one attribute, superseded values included."""
    docs_by_id = {d.id: d for d in documents}
    dates = {d.id: effective_date(d, claims) for d in documents}
    rows = [
        {
            "claim_id": c.id,
            "value": c.value,
            "document": docs_by_id[c.document_id].filename if c.document_id in docs_by_id
            else "Owner declaration",
            "document_type": docs_by_id[c.document_id].doc_type if c.document_id in docs_by_id
            else "OWNER_DECLARATION",
            "effective_date": dates.get(c.document_id, date.min).isoformat(),
            "page": c.source_page,
            "superseded": c.superseded,
            "confidence": c.confidence,
        }
        for c in claims
        if c.claim_type == claim_type
    ]
    return sorted(rows, key=lambda r: r["effective_date"])
