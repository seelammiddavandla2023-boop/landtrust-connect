"""
Evidential authority of a document type for a given claim type.

The verification policy rests on one idea from the research proposal: *not every
document is an equally good witness for every fact*.  A survey record is the
authority of record for extent; a tax receipt merely corroborates it.  An owner's
own declaration is evidence of what the owner says, not of what is true.

authority ∈ [0, 1]:
    1.00  authority of record for this attribute — may verify on its own
    0.80  strong corroborating evidence
    0.50  weak corroboration
    0.20  self-reported, no independent weight
"""
from __future__ import annotations

from ...domain import ClaimType, DocumentType

DEFAULT_AUTHORITY = 0.45

AUTHORITY: dict[DocumentType, dict[str, float]] = {
    DocumentType.SALE_DEED: {
        ClaimType.OWNER_NAME.value: 0.95,
        ClaimType.SELLER_NAME.value: 0.95,
        ClaimType.BUYER_NAME.value: 0.95,
        ClaimType.REGISTRATION_DATE.value: 1.00,   # authority for its own registration
        ClaimType.DOCUMENT_NUMBER.value: 1.00,
        ClaimType.CONSIDERATION_VALUE.value: 0.95,
        ClaimType.SURVEY_NUMBER.value: 0.90,
        ClaimType.PROPERTY_AREA.value: 0.85,
        ClaimType.BOUNDARY_DESCRIPTION.value: 0.85,
        ClaimType.DISTRICT.value: 0.85,
        ClaimType.VILLAGE.value: 0.85,
        "_default": 0.75,
    },
    DocumentType.SURVEY_RECORD: {
        ClaimType.SURVEY_NUMBER.value: 1.00,       # authority of record for the parcel
        ClaimType.PROPERTY_AREA.value: 1.00,
        ClaimType.BOUNDARY_DESCRIPTION.value: 1.00,
        ClaimType.PROPERTY_TYPE.value: 0.95,
        ClaimType.OWNER_NAME.value: 0.85,
        ClaimType.DISTRICT.value: 0.95,
        ClaimType.VILLAGE.value: 0.95,
        "_default": 0.65,
    },
    DocumentType.ENCUMBRANCE_CERTIFICATE: {
        ClaimType.MORTGAGE_STATUS.value: 1.00,     # authority of record for encumbrances
        ClaimType.MORTGAGE_AMOUNT.value: 0.95,
        ClaimType.MORTGAGE_LENDER.value: 0.95,
        ClaimType.ENCUMBRANCE_PERIOD.value: 1.00,
        ClaimType.SURVEY_NUMBER.value: 0.90,
        ClaimType.OWNER_NAME.value: 0.80,
        ClaimType.PROPERTY_AREA.value: 0.75,
        ClaimType.REGISTRATION_DATE.value: 0.85,
        ClaimType.DOCUMENT_NUMBER.value: 0.85,
        "_default": 0.60,
    },
    DocumentType.TAX_RECEIPT: {
        ClaimType.TAX_STATUS.value: 1.00,          # authority for whether tax was paid
        ClaimType.TAXPAYER_NAME.value: 0.80,
        ClaimType.OWNER_NAME.value: 0.55,          # the payer need not be the owner
        ClaimType.SURVEY_NUMBER.value: 0.70,
        ClaimType.PROPERTY_AREA.value: 0.60,
        "_default": 0.45,
    },
    DocumentType.MORTGAGE_DOCUMENT: {
        ClaimType.MORTGAGE_STATUS.value: 0.95,
        ClaimType.MORTGAGE_AMOUNT.value: 1.00,
        ClaimType.MORTGAGE_LENDER.value: 1.00,
        ClaimType.OWNER_NAME.value: 0.80,
        ClaimType.SURVEY_NUMBER.value: 0.80,
        "_default": 0.60,
    },
    DocumentType.BANK_NOC: {
        ClaimType.MORTGAGE_STATUS.value: 1.00,     # the lender is authoritative on release
        ClaimType.MORTGAGE_LENDER.value: 1.00,
        ClaimType.OWNER_NAME.value: 0.70,
        "_default": 0.55,
    },
    DocumentType.POWER_OF_ATTORNEY: {
        ClaimType.POA_HOLDER.value: 1.00,
        ClaimType.POA_GRANTOR.value: 1.00,
        ClaimType.AUTHORIZATION_EXPIRY.value: 1.00,
        ClaimType.OWNER_NAME.value: 0.55,
        "_default": 0.50,
    },
    DocumentType.IDENTITY_PROOF: {
        ClaimType.IDENTITY_NUMBER.value: 0.90,
        ClaimType.OWNER_NAME.value: 0.60,
        ClaimType.OWNER_ADDRESS.value: 0.70,
        "_default": 0.40,
    },
    DocumentType.OWNER_DECLARATION: {
        "_default": 0.20,                          # self-reported: never verifies alone
    },
    DocumentType.AFFIDAVIT: {
        # A sworn, notarised statement is authoritative about the *relationship between
        # two names* — that is what a name-discrepancy affidavit exists to establish.
        # It says nothing authoritative about who owns the land, so everything else
        # stays at declaration weight.
        ClaimType.NAME_EQUIVALENCE.value: 1.00,
        "_default": 0.25,
    },
    DocumentType.UNKNOWN: {
        "_default": 0.25,
    },
}


def authority_of(doc_type: str | None, claim_type: str) -> float:
    """How much weight a document of this type carries for this claim type."""
    if not doc_type:
        return 0.20
    try:
        dt = DocumentType(doc_type)
    except ValueError:
        dt = DocumentType.UNKNOWN
    table = AUTHORITY.get(dt, {})
    return table.get(claim_type, table.get("_default", DEFAULT_AUTHORITY))


def is_authority_of_record(doc_type: str | None, claim_type: str) -> bool:
    """
    True when a single document of this type is, on its own, sufficient to verify
    this claim type.  Everything else requires independent corroboration.
    """
    return authority_of(doc_type, claim_type) >= 0.999


def combined_authority(authorities: list[float]) -> float:
    """
    Independent-evidence combination (noisy-OR).  Two 0.8 witnesses are stronger than
    one, but never reach certainty; twenty weak witnesses do not become an authority.
    """
    product = 1.0
    for a in authorities:
        product *= (1.0 - max(0.0, min(1.0, a)))
    return round(1.0 - product, 4)
