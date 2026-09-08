"""
Shared dependencies.

Authentication is deliberately minimal (build brief §34: do not over-engineer auth
for a university prototype).  The active role travels in the `X-Demo-Role` header so
the UI can switch roles instantly during a review demonstration.  *Authorisation*,
by contrast, is not simulated: the redaction and consent layers apply for real, and
a buyer request genuinely cannot retrieve a masked value.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..domain import Role
from ..models import ConsentRequest, Property, User
from ..services.privacy import consent as consent_service


def current_role(x_demo_role: str | None = Header(default=None)) -> Role:
    if not x_demo_role:
        return Role.BUYER
    try:
        return Role(x_demo_role.upper())
    except ValueError:
        return Role.BUYER


def current_user(
    db: Session = Depends(get_db), role: Role = Depends(current_role)
) -> User | None:
    return db.scalars(select(User).where(User.role == role.value)).first()


def get_property(property_id: str, db: Session = Depends(get_db)) -> Property:
    prop = db.scalars(
        select(Property).where(
            (Property.id == property_id) | (Property.reference == property_id)
        )
    ).first()
    if prop is None:
        raise HTTPException(status_code=404, detail=f"Property '{property_id}' not found.")
    return prop


def granted_items(db: Session, prop: Property, role: Role) -> set[str]:
    """Disclosure items currently released to the viewing role."""
    if role in {Role.OWNER, Role.ADMIN, Role.VERIFIER, Role.LEGAL_REVIEWER}:
        from ..domain import DisclosureItem, NEVER_DISCLOSED

        return {i.value for i in DisclosureItem} - {i.value for i in NEVER_DISCLOSED}
    requests = db.scalars(
        select(ConsentRequest).where(ConsentRequest.property_id == prop.id)
    ).all()
    changed = consent_service.expire_stale(list(requests))
    if changed:
        db.commit()
    return consent_service.active_grants(list(requests))
