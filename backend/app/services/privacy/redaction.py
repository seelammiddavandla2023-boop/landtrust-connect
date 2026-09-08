"""
Redaction and selective disclosure.

Two jobs:

1. **Masking** — turn a stored value into the form a given role is allowed to see.
   Identity numbers, phone numbers and addresses are never emitted in full to a
   buyer, with or without consent (domain.NEVER_DISCLOSED); names are masked to
   initials until the owner approves disclosure.

2. **Outbound scanning** — detect identity numbers, card numbers, phone numbers and
   e-mail addresses in relay messages so they can be redacted before delivery and
   flagged to the risk engine.  Moving a negotiation off the audited channel is
   itself a risk signal.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ...domain import (
    NEVER_DISCLOSED,
    ClaimType,
    DisclosureItem,
    Role,
    Sensitivity,
    sensitivity_of,
)

# --- masking ---------------------------------------------------------------

def mask_name(name: str) -> str:
    """'Ravi Kumar' → 'R*** K****' — enough to check a reference, not to identify."""
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts:
        return "—"
    return " ".join(p[0].upper() + "*" * max(1, len(p) - 1) for p in parts)


def mask_identity(value: str) -> str:
    """Aadhaar/PAN style: reveal only the last four characters."""
    digits = re.sub(r"\s+", "", value or "")
    if len(digits) <= 4:
        return "XXXX"
    tail = digits[-4:]
    return f"XXXX XXXX {tail}"


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return f"+91 XXXXX X{digits[-4:]}" if len(digits) >= 4 else "XXXXXXXXXX"


def mask_address(value: str) -> str:
    parts = [p.strip() for p in re.split(r"[,\n]", value or "") if p.strip()]
    if not parts:
        return "Restricted"
    return f"{parts[-1]} (locality only)"


def mask_money(value: str) -> str:
    return "Disclosed on request"


_MASKERS = {
    ClaimType.OWNER_NAME.value: mask_name,
    ClaimType.SELLER_NAME.value: mask_name,
    ClaimType.BUYER_NAME.value: mask_name,
    ClaimType.TAXPAYER_NAME.value: mask_name,
    ClaimType.POA_HOLDER.value: mask_name,
    ClaimType.POA_GRANTOR.value: mask_name,
    ClaimType.IDENTITY_NUMBER.value: mask_identity,
    ClaimType.OWNER_PHONE.value: mask_phone,
    ClaimType.OWNER_ADDRESS.value: mask_address,
    ClaimType.CONSIDERATION_VALUE.value: mask_money,
    ClaimType.MORTGAGE_AMOUNT.value: mask_money,
    ClaimType.DOCUMENT_NUMBER.value: lambda v: (v[:4] + "…" + v[-3:]) if len(v) > 9 else "…",
}

# Which consent grant unlocks which claim type.
UNLOCKED_BY = {
    ClaimType.OWNER_NAME.value: DisclosureItem.FULL_OWNER_NAME,
    ClaimType.SELLER_NAME.value: DisclosureItem.FULL_OWNER_NAME,
    ClaimType.TAXPAYER_NAME.value: DisclosureItem.FULL_OWNER_NAME,
    ClaimType.POA_HOLDER.value: DisclosureItem.FULL_OWNER_NAME,
    ClaimType.POA_GRANTOR.value: DisclosureItem.FULL_OWNER_NAME,
    ClaimType.MORTGAGE_AMOUNT.value: DisclosureItem.MORTGAGE_DETAIL,
    ClaimType.CONSIDERATION_VALUE.value: DisclosureItem.MORTGAGE_DETAIL,
    ClaimType.DOCUMENT_NUMBER.value: DisclosureItem.SALE_DEED_COPY,
    ClaimType.OWNER_PHONE.value: DisclosureItem.CONTACT_NUMBER,
    ClaimType.OWNER_ADDRESS.value: DisclosureItem.FULL_ADDRESS,
    ClaimType.IDENTITY_NUMBER.value: DisclosureItem.IDENTITY_DOCUMENT,
}


@dataclass
class Disclosure:
    value: str
    masked: bool
    reason: str
    unlockable_by: str | None = None


def disclose(claim_type: str, value: str, role: Role, granted: set[str]) -> Disclosure:
    """
    Return the value as this role may see it.

    Owners, verifiers, legal reviewers and admins see their own file in full.  Buyers
    see masked values unless the owner has granted the corresponding disclosure item —
    and identity documents are refused even then.
    """
    sens = sensitivity_of(claim_type)
    if role in {Role.OWNER, Role.VERIFIER, Role.LEGAL_REVIEWER, Role.ADMIN}:
        return Disclosure(value, False, "Full value visible to this role.")

    if sens is Sensitivity.PUBLIC:
        return Disclosure(value, False, "Non-personal detail; disclosed once evidence supports it.")

    item = UNLOCKED_BY.get(claim_type)
    masker = _MASKERS.get(claim_type, lambda v: "Restricted")

    if item and item in NEVER_DISCLOSED:
        return Disclosure(
            masker(value),
            True,
            "Identity documents are never disclosed through this platform, with or without "
            "owner consent. Verification is performed on the platform's side and only the "
            "outcome is shared.",
            None,
        )

    if item and item.value in granted:
        return Disclosure(value, False, "Disclosed under an active owner consent grant.")

    if sens is Sensitivity.RESTRICTED:
        return Disclosure(
            masker(value),
            True,
            "Restricted detail. The owner may release it through a time-limited consent grant.",
            item.value if item else None,
        )

    return Disclosure(
        masker(value),
        True,
        "Masked by default. Request access from the owner to see the full value.",
        item.value if item else None,
    )


# --- outbound scanning -----------------------------------------------------
PATTERNS: list[tuple[str, str, str]] = [
    ("AADHAAR", r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", "[identity number redacted]"),
    ("PAN", r"\b[A-Z]{5}\d{4}[A-Z]\b", "[PAN redacted]"),
    ("CARD", r"\b(?:\d[ -]?){13,16}\b", "[card number redacted]"),
    ("PHONE", r"(?:\+?91[\s-]?)?\b[6-9]\d{9}\b", "[phone number redacted]"),
    ("EMAIL", r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b", "[email redacted]"),
    ("BANK_ACCOUNT", r"\b(?:a/?c|account)\s*(?:no\.?|number)?\s*[:#-]?\s*\d{9,18}\b",
     "[account number redacted]"),
    ("UPI", r"\b[\w.-]{3,}@(?:okaxis|oksbi|okhdfcbank|ybl|paytm|upi)\b", "[UPI id redacted]"),
    ("OFF_PLATFORM", r"\b(?:whatsapp|telegram|call me on|message me at)\b",
     "[off-platform contact suggestion]"),
]


@dataclass
class ScanResult:
    redacted: str
    kinds: list[str]
    contained_sensitive: bool
    warning: str = ""


def scan_message(body: str) -> ScanResult:
    redacted = body or ""
    kinds: list[str] = []
    for kind, pattern, replacement in PATTERNS:
        if re.search(pattern, redacted, re.IGNORECASE):
            kinds.append(kind)
            redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    warning = ""
    if kinds:
        warning = (
            "This message contained details that the relay does not carry ("
            + ", ".join(k.replace("_", " ").lower() for k in kinds)
            + "). They have been removed. Sharing identity or payment details outside the "
              "platform removes the audit trail and the consent controls that protect both "
              "parties."
        )
    return ScanResult(redacted, kinds, bool(kinds), warning)
