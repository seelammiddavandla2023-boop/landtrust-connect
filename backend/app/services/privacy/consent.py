"""
Consent lifecycle and the evidence-gated property profile.

Two rules govern what a buyer sees:

  * **Evidence gate** — a field is presented as verified only if the verification
    resolver said so.  Owner-entered text with no supporting document appears in a
    visibly separate "owner provided" section, never mixed in with verified facts.
  * **Consent gate** — personal values are masked until the owner grants the
    matching disclosure item, and grants can be time-limited and expire on their own.

The two gates are independent: a claim can be fully verified and still masked, and a
value the owner has consented to share is still labelled with its evidence status.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from ...domain import (
    CLAIM_TYPE_LABELS,
    DISCLOSURE_LABELS,
    NEVER_DISCLOSED,
    ClaimType,
    ConsentStatus,
    DisclosureItem,
    Role,
    Sensitivity,
    VerificationStatus,
    sensitivity_of,
)
from .redaction import disclose

TIME_LIMITED_HOURS = 24


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def expire_stale(requests: list) -> list:
    """Mark time-limited grants whose window has closed. Returns the ones that changed."""
    changed = []
    now = utcnow()
    for r in requests:
        if r.status != ConsentStatus.APPROVED_TIME_LIMITED.value:
            continue
        expires = _aware(r.expires_at)
        if expires and expires <= now:
            r.status = ConsentStatus.EXPIRED.value
            r.granted_items = []
            changed.append(r)
    return changed


def active_grants(requests: list, requester_id: str | None = None) -> set[str]:
    """Disclosure items currently released to a requester."""
    expire_stale(requests)
    granted: set[str] = set()
    for r in requests:
        if requester_id and r.requester_id != requester_id:
            continue
        if r.status not in {
            ConsentStatus.APPROVED.value, ConsentStatus.APPROVED_TIME_LIMITED.value
        }:
            continue
        expires = _aware(r.expires_at)
        if expires and expires <= utcnow():
            continue
        granted.update(r.granted_items or [])
    return granted - {i.value for i in NEVER_DISCLOSED}


def decide(request, approve: bool, items: list[str] | None = None,
           time_limited: bool = False, note: str = "") -> None:
    """Record an owner's decision on a consent request."""
    request.decided_at = utcnow()
    request.decision_note = note
    requested = set(request.items or [])
    never = {i.value for i in NEVER_DISCLOSED}

    if not approve:
        request.status = ConsentStatus.DENIED.value
        request.granted_items = []
        request.denied_items = sorted(requested)
        return

    chosen = set(items) & requested if items else requested
    granted = sorted(chosen - never)
    request.granted_items = granted
    request.denied_items = sorted(requested - set(granted))
    if time_limited:
        request.status = ConsentStatus.APPROVED_TIME_LIMITED.value
        request.expires_at = utcnow() + timedelta(hours=TIME_LIMITED_HOURS)
    else:
        request.status = ConsentStatus.APPROVED.value
        request.expires_at = None


def revoke(request, note: str = "") -> None:
    request.status = ConsentStatus.REVOKED.value
    request.granted_items = []
    request.decision_note = note or "Access revoked by the owner."
    request.decided_at = utcnow()


# ---------------------------------------------------------------------------
# Evidence-gated profile
# ---------------------------------------------------------------------------
PROFILE_FIELDS = [
    ClaimType.SURVEY_NUMBER,
    ClaimType.PROPERTY_AREA,
    ClaimType.PROPERTY_TYPE,
    ClaimType.DISTRICT,
    ClaimType.VILLAGE,
    ClaimType.OWNER_NAME,
    ClaimType.REGISTRATION_DATE,
    ClaimType.MORTGAGE_STATUS,
    ClaimType.MORTGAGE_AMOUNT,
    ClaimType.TAX_STATUS,
    ClaimType.BOUNDARY_DESCRIPTION,
    ClaimType.DOCUMENT_NUMBER,
    ClaimType.OWNER_PHONE,
    ClaimType.OWNER_ADDRESS,
    ClaimType.IDENTITY_NUMBER,
]

SECTION_FOR_STATUS = {
    VerificationStatus.VERIFIED: "verified",
    VerificationStatus.PARTIALLY_VERIFIED: "partially_verified",
    VerificationStatus.CONFLICTING: "conflicting",
    VerificationStatus.EXPIRED: "partially_verified",
    VerificationStatus.OWNER_PROVIDED: "owner_provided",
    VerificationStatus.PENDING: "pending",
    VerificationStatus.UNVERIFIED: "owner_provided",
}


@dataclass
class ProfileField:
    claim_type: str
    label: str
    value: str
    raw_available: bool
    masked: bool
    mask_reason: str
    verification_status: str
    explanation: str
    sensitivity: str
    section: str
    supporting_documents: int = 0
    conflicting_documents: int = 0
    unlockable_by: str | None = None


@dataclass
class GatedProfile:
    property_reference: str
    fields: list[ProfileField] = field(default_factory=list)
    restricted_items: list[dict] = field(default_factory=list)
    granted_items: list[str] = field(default_factory=list)
    verification_level: float = 0.0
    disclaimer: str = ""

    def by_section(self) -> dict[str, list[ProfileField]]:
        out: dict[str, list[ProfileField]] = {}
        for f in self.fields:
            out.setdefault(f.section, []).append(f)
        return out


def build_profile(
    property_obj,
    claims: list,
    outcome,
    role: Role,
    granted: set[str],
) -> GatedProfile:
    """
    Assemble what a given role may see about a property.

    Note the ordering: the *status* is decided first (by the evidence), then the
    *visibility* (by consent).  A buyer therefore always learns whether a fact is
    supported, even when they are not permitted to see its value.
    """
    profile = GatedProfile(
        property_reference=property_obj.reference,
        granted_items=sorted(granted),
        verification_level=outcome.verification_level(),
        disclaimer=(
            "Statuses describe agreement between the documents uploaded to this platform. They "
            "are not a certification of legal title and do not replace official records or "
            "professional advice."
        ),
    )

    best_claim: dict[str, object] = {}
    for c in claims:
        if c.superseded:
            continue
        current = best_claim.get(c.claim_type)
        if current is None or c.confidence > current.confidence:
            best_claim[c.claim_type] = c

    for claim_type in PROFILE_FIELDS:
        key = claim_type.value
        group = outcome.per_type.get(key)
        claim = best_claim.get(key)
        sens = sensitivity_of(key)

        if claim is None:
            if group is None:
                continue
            profile.fields.append(
                ProfileField(
                    claim_type=key,
                    label=CLAIM_TYPE_LABELS.get(claim_type, key),
                    value="Not evidenced",
                    raw_available=False,
                    masked=False,
                    mask_reason="",
                    verification_status=group.status.value,
                    explanation=group.explanation,
                    sensitivity=sens.value,
                    section="pending",
                )
            )
            continue

        status = group.status if group else VerificationStatus.UNVERIFIED
        d = disclose(key, claim.value, role, granted)
        profile.fields.append(
            ProfileField(
                claim_type=key,
                label=CLAIM_TYPE_LABELS.get(claim_type, key),
                value=d.value,
                raw_available=not d.masked,
                masked=d.masked,
                mask_reason=d.reason,
                verification_status=status.value,
                explanation=group.explanation if group else "",
                sensitivity=sens.value,
                section=SECTION_FOR_STATUS.get(status, "owner_provided"),
                supporting_documents=len(group.supporting_document_ids) if group else 0,
                conflicting_documents=len(group.conflicting_document_ids) if group else 0,
                unlockable_by=d.unlockable_by,
            )
        )

    profile.restricted_items = [
        {
            "item": item.value,
            "label": DISCLOSURE_LABELS[item],
            "policy": (
                "Never disclosed through this platform, with or without consent."
                if item in NEVER_DISCLOSED else
                "Available only under an explicit owner consent grant."
            ),
            "requestable": item not in NEVER_DISCLOSED,
        }
        for item in DisclosureItem
    ]
    return profile
