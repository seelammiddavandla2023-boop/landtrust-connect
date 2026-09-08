"""Append-only audit ledger.

Every consequential action — an upload, an OCR run, a status change, a consent
decision, a risk recalculation, a hold, an assistant refusal — is written here with
the evidence it rests on, so any figure shown in the UI can be traced back to what
produced it.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain import AuditAction, Role
from ..models import AuditEvent


def record(
    db: Session,
    action: AuditAction | str,
    *,
    property_id: str | None = None,
    transaction_id: str | None = None,
    actor_role: Role | str = Role.ADMIN,
    actor_name: str = "system",
    result: str = "OK",
    summary: str = "",
    evidence_refs: list[dict] | None = None,
    payload: dict | None = None,
    commit: bool = False,
) -> AuditEvent:
    event = AuditEvent(
        property_id=property_id,
        transaction_id=transaction_id,
        actor_role=actor_role.value if hasattr(actor_role, "value") else str(actor_role),
        actor_name=actor_name,
        action=action.value if hasattr(action, "value") else str(action),
        result=result,
        summary=summary,
        evidence_refs=evidence_refs or [],
        payload=payload or {},
    )
    db.add(event)
    if commit:
        db.commit()
    return event
