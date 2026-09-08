"""
Capability authorisation.

Disclosure has always been enforced for real on this platform: what a role may
*see* is decided server-side by the redaction and consent layers. What a role may
*do* was not — document upload, reassessment and the demonstration reset accepted
any caller, and the interface papered over the gap by sending "OWNER" on consent
decisions and resolution steps regardless of who was actually acting. Switching
role therefore changed what you saw and nothing about what you could do, which is
not how the platform is described and not how a land transaction works: a buyer
does not add evidence to someone else's file, and an owner does not request
access to their own.

This module is the single table of who may do what. Routes ask it; the API at
`/api/roles` publishes it, so the interface disables a control for exactly the
reason the server would refuse it, rather than keeping a private second copy of
the rules that can drift out of step.

The table encodes the parties' real positions:

* Only the **owner** adds evidence to their own property. Corroborating a claim
  is the whole point of the evidence gate, and a buyer who could upload the
  document that clears a doubt about the seller's title would defeat it.
* Only the **buyer** attempts to transact. The state controller exists to refuse
  those attempts; letting anyone press the button makes the refusal a slogan.
* Only the **owner** decides disclosure — and cannot request it from themselves.
* An **administrator** may do most things, because it operates the platform.
* A **legal reviewer** examines an escalated case and does not clear it. That is
  the point of an escalation.
"""
from __future__ import annotations

from fastapi import HTTPException

from ..domain import Role


class Capability:
    """String constants, so a typo is a name error rather than a silent allow."""

    UPLOAD_EVIDENCE = "UPLOAD_EVIDENCE"
    REASSESS = "REASSESS"
    APPLY_RESOLUTION = "APPLY_RESOLUTION"
    SIMULATE_RESOLUTION = "SIMULATE_RESOLUTION"
    REQUEST_CONSENT = "REQUEST_CONSENT"
    DECIDE_CONSENT = "DECIDE_CONSENT"
    ATTEMPT_TRANSACTION = "ATTEMPT_TRANSACTION"
    SEND_MESSAGE = "SEND_MESSAGE"
    ASK_ASSISTANT = "ASK_ASSISTANT"
    RESET_DEMO = "RESET_DEMO"


#: capability -> the roles permitted to exercise it.
CAPABILITIES: dict[str, set[Role]] = {
    # Adding evidence to a property is the owner's act. A verifier examines what
    # is on file and an administrator operates the platform; neither is the
    # source of a property's paperwork.
    Capability.UPLOAD_EVIDENCE: {Role.OWNER, Role.ADMIN},
    # Recomputing is read-only in effect — it derives the current position from
    # the current evidence — but it writes assessment rows, so a buyer browsing
    # a listing should not be able to trigger it.
    Capability.REASSESS: {Role.OWNER, Role.VERIFIER, Role.LEGAL_REVIEWER, Role.ADMIN},
    # A legal reviewer is deliberately absent: an escalated case is theirs to
    # examine, not to clear.
    Capability.APPLY_RESOLUTION: {Role.OWNER, Role.VERIFIER, Role.ADMIN},
    # Simulation writes nothing, so anyone may run it — a buyer seeing what would
    # clear a hold is exactly the transparency the platform is arguing for.
    Capability.SIMULATE_RESOLUTION: set(Role),
    # An owner cannot request access to their own property.
    Capability.REQUEST_CONSENT: {Role.BUYER, Role.VERIFIER, Role.LEGAL_REVIEWER},
    Capability.DECIDE_CONSENT: {Role.OWNER, Role.ADMIN},
    # The state controller exists to refuse a buyer's attempt to progress.
    Capability.ATTEMPT_TRANSACTION: {Role.BUYER, Role.ADMIN},
    Capability.SEND_MESSAGE: set(Role),
    Capability.ASK_ASSISTANT: set(Role),
    Capability.RESET_DEMO: {Role.ADMIN},
}

#: Why each capability is restricted, in the words the user is shown when a
#: control is disabled. Kept beside the table so the two cannot drift.
REASONS: dict[str, str] = {
    Capability.UPLOAD_EVIDENCE: (
        "Only the land owner adds evidence to a property. A buyer who could upload the "
        "document that settles a doubt about the seller's title would defeat the point of "
        "the evidence gate."
    ),
    Capability.REASSESS: (
        "Recomputing an assessment is for the owner or a reviewer. A buyer sees the current "
        "position; they do not drive it."
    ),
    Capability.APPLY_RESOLUTION: (
        "A resolution step is applied by the owner or a verifier. A legal reviewer examines "
        "an escalated case rather than clearing it."
    ),
    Capability.REQUEST_CONSENT: (
        "An owner does not request access to their own property. Switch to Buyer to ask for "
        "a disclosure."
    ),
    Capability.DECIDE_CONSENT: (
        "Only the owner decides what is disclosed. Switch to Land Owner to approve, limit or "
        "revoke access."
    ),
    Capability.ATTEMPT_TRANSACTION: (
        "The buyer is the party who attempts to progress a transaction. Switch to Buyer to "
        "see the state controller permit or refuse the action."
    ),
    Capability.RESET_DEMO: (
        "Rebuilding the demonstration database is an administrator action."
    ),
}


def allows(role: Role, capability: str) -> bool:
    return role in CAPABILITIES.get(capability, set())


def require(role: Role, capability: str) -> None:
    """Raise 403 unless the role holds the capability."""
    if allows(role, capability):
        return
    permitted = ", ".join(sorted(r.value.replace("_", " ").title()
                                 for r in CAPABILITIES.get(capability, set())))
    reason = REASONS.get(capability, "")
    raise HTTPException(
        status_code=403,
        detail=(
            f"{reason} Permitted roles: {permitted or 'none'}. "
            "Use the role selector in the top bar to switch."
        ).strip(),
    )


def matrix() -> dict[str, dict]:
    """
    The whole table, for `/api/roles`.

    Returned per role rather than per capability, because that is the shape the
    interface needs: given the active role, which controls are live.
    """
    return {
        role.value: {
            "capabilities": sorted(
                cap for cap, roles in CAPABILITIES.items() if role in roles
            ),
            "denied": {
                cap: REASONS.get(cap, "")
                for cap, roles in CAPABILITIES.items()
                if role not in roles
            },
        }
        for role in Role
    }
