"""
Populate the database from the synthetic corpus.

    python -m app.seed.seed            # generate documents if needed, then seed
    python -m app.seed.seed --reset    # drop and rebuild everything

Seeding runs the *real* pipeline over the *real* generated PDFs: classification,
extraction, provenance, contradiction detection, verification, risk, state control
and resolution planning all execute exactly as they would for an uploaded file.
Nothing here writes a verification status or a risk score directly.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal, init_db, reset_db
from ..domain import (
    AuditAction,
    ConsentStatus,
    DisclosureItem,
    DocumentType,
    Role,
)
from ..models import (
    ConsentRequest,
    Document,
    Message,
    Property,
    Transaction,
    User,
)
from ..services import audit, pipeline
from ..services.privacy.redaction import scan_message
from .generate import generate
from .scenarios import all_scenarios


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_corpus() -> dict:
    gt_path = settings.synthetic_dir / "ground_truth.json"
    if not gt_path.exists():
        return generate()
    return json.loads(gt_path.read_text("utf-8"))


# ---------------------------------------------------------------------------
DEMO_USERS = [
    dict(name="Ananya Iyer", email="buyer@landtrust.demo", role=Role.BUYER,
         organisation="Individual buyer", phone="9840777001",
         identity_number="XXXX XXXX 1102"),
    dict(name="R. Vasanth", email="verifier@landtrust.demo", role=Role.VERIFIER,
         organisation="LandTrust Verification Desk", phone="9840777002",
         identity_number=None),
    dict(name="Adv. Kavitha Menon", email="legal@landtrust.demo", role=Role.LEGAL_REVIEWER,
         organisation="Menon & Associates", phone="9840777003", identity_number=None),
    dict(name="Platform Administrator", email="admin@landtrust.demo", role=Role.ADMIN,
         organisation="LandTrust Connect", phone=None, identity_number=None),
]


def seed(db: Session, reset: bool = False) -> dict:
    ground_truth = ensure_corpus()
    scenarios = all_scenarios()

    users: dict[str, User] = {}
    for spec in DEMO_USERS:
        user = User(
            name=spec["name"], email=spec["email"], role=spec["role"].value,
            organisation=spec["organisation"], phone=spec["phone"],
            identity_number=spec["identity_number"],
        )
        db.add(user)
        users[spec["role"].value] = user
    db.flush()
    buyer = users[Role.BUYER.value]

    summary = {"properties": 0, "documents": 0, "claims": 0}

    for index, plan in enumerate(scenarios, start=1):
        owner = User(
            name=plan.owner_name,
            email=plan.owner_email,
            role=Role.OWNER.value,
            organisation="Individual owner",
            phone=plan.owner_phone,
            identity_number=plan.owner_identity,
        )
        db.add(owner)
        db.flush()

        prop = Property(
            reference=plan.reference,
            survey_number=plan.survey_number,
            district=plan.district,
            village=plan.village,
            property_type=plan.property_type,
            claimed_area_sqft=plan.claimed_area_sqft,
            guideline_value_inr=plan.guideline_value_inr,
            asking_price_inr=plan.asking_price_inr,
            listed_owner_name=plan.listed_owner_name,
            owner_id=owner.id,
            scenario_key=plan.key,
            scenario_label=plan.label,
            closed_rules=[],
        )
        db.add(prop)
        db.flush()

        txn = Transaction(
            reference=f"TXN-{plan.reference.split('-')[-1]}",
            property_id=prop.id,
            buyer_id=buyer.id,
            consideration_inr=plan.asking_price_inr,
        )
        db.add(txn)
        db.flush()

        prop_dir = settings.synthetic_dir / plan.reference
        for doc_plan in plan.documents:
            src = prop_dir / doc_plan.spec.filename
            if not src.exists():
                continue
            result = pipeline.ingest_document(
                db, prop, src, doc_plan.spec.filename,
                uploaded_by_role=Role.OWNER, actor_name=plan.owner_name,
            )
            summary["documents"] += 1
            summary["claims"] += len(result.claims)
        db.flush()

        _seed_interactions(db, prop, owner, buyer, plan)
        pipeline.reassess(db, prop, actor_role=Role.ADMIN, actor_name="seed",
                          reason="Initial evidence set ingested")
        summary["properties"] += 1

    audit.record(
        db, AuditAction.DEMO_RESET, actor_role=Role.ADMIN, actor_name="seed",
        summary=f"Demo corpus seeded: {summary['properties']} properties, "
                f"{summary['documents']} documents, {summary['claims']} claims.",
        commit=True,
    )
    return summary


def _seed_interactions(db: Session, prop: Property, owner: User, buyer: User, plan) -> None:
    """Consent requests and relay messages that make the portals look lived-in."""
    if plan.key == "clean_title":
        req = ConsentRequest(
            property_id=prop.id, requester_id=buyer.id, owner_id=owner.id,
            items=[DisclosureItem.FULL_OWNER_NAME.value, DisclosureItem.LATEST_EC.value,
                   DisclosureItem.SURVEY_RECORD.value, DisclosureItem.IDENTITY_DOCUMENT.value],
            purpose="Pre-agreement due diligence on the title chain.",
            status=ConsentStatus.APPROVED_TIME_LIMITED.value,
            granted_items=[DisclosureItem.FULL_OWNER_NAME.value, DisclosureItem.LATEST_EC.value,
                           DisclosureItem.SURVEY_RECORD.value],
            denied_items=[DisclosureItem.IDENTITY_DOCUMENT.value],
            decided_at=_now() - timedelta(hours=2),
            expires_at=_now() + timedelta(hours=22),
            decision_note="Approved for 24 hours. Identity document is never shared.",
        )
        db.add(req)
        _message(db, prop, Role.BUYER, buyer,
                 "Thank you for sharing the encumbrance certificate. The chain looks complete "
                 "to me — could you confirm the mortgage released in 2025 was the only charge?")
        _message(db, prop, Role.OWNER, owner,
                 "Yes, that was a home-improvement loan. The release letter from the bank is "
                 "already in the file, and the 2026 certificate shows nil.")

    elif plan.key == "area_conflict_active_mortgage":
        db.add(ConsentRequest(
            property_id=prop.id, requester_id=buyer.id, owner_id=owner.id,
            items=[DisclosureItem.LATEST_EC.value, DisclosureItem.SURVEY_RECORD.value,
                   DisclosureItem.MORTGAGE_DETAIL.value],
            purpose="Need a current EC and the certified extent to resolve the 150 sq.ft "
                    "discrepancy and the outstanding charge.",
            status=ConsentStatus.REQUESTED.value,
        ))
        _message(db, prop, Role.BUYER, buyer,
                 "I would like clarification on the area mismatch detected between the sale deed "
                 "and the encumbrance certificate. The deed says 1800 sq.ft and the EC says "
                 "1650 sq.ft.")
        _message(db, prop, Role.OWNER, owner,
                 "The 1650 figure predates the boundary re-fixing. I have applied for a fresh "
                 "measurement from the taluk survey office and will upload it as soon as it is "
                 "issued, along with the lender's release letter.")

    elif plan.key == "possible_impersonation":
        db.add(ConsentRequest(
            property_id=prop.id, requester_id=buyer.id, owner_id=owner.id,
            items=[DisclosureItem.FULL_OWNER_NAME.value, DisclosureItem.SALE_DEED_COPY.value],
            purpose="The listing name does not match the deed. Requesting the deed and the "
                    "registered owner's name.",
            status=ConsentStatus.DENIED.value,
            denied_items=[DisclosureItem.FULL_OWNER_NAME.value,
                          DisclosureItem.SALE_DEED_COPY.value],
            decided_at=_now() - timedelta(days=1),
            decision_note="Declined by the listing party.",
        ))
        db.add(ConsentRequest(
            property_id=prop.id, requester_id=buyer.id, owner_id=owner.id,
            items=[DisclosureItem.SURVEY_RECORD.value],
            purpose="Requesting the survey record to confirm the pattadar name.",
            status=ConsentStatus.REQUESTED.value,
            created_at=_now() - timedelta(days=6),
        ))
        _message(db, prop, Role.BUYER, buyer,
                 "The documents name Mohan Reddy but the listing is under your name. Could you "
                 "share the instrument that transfers the property to you?")
        _message(db, prop, Role.OWNER, owner,
                 "The paperwork is with my advocate. Easier if we settle this directly - reach me "
                 "on 9445567788 or arjun.reddy@example.in and I will send the token account "
                 "details.")

    elif plan.key == "joint_ownership_missing_ec":
        db.add(ConsentRequest(
            property_id=prop.id, requester_id=buyer.id, owner_id=owner.id,
            items=[DisclosureItem.LATEST_EC.value],
            purpose="No encumbrance certificate is on file.",
            status=ConsentStatus.REQUESTED.value,
            created_at=_now() - timedelta(days=1),
        ))
        _message(db, prop, Role.BUYER, buyer,
                 "There is no encumbrance certificate in the file. Could you obtain one covering "
                 "the period since 2020?")

    elif plan.key == "document_modification":
        _message(db, prop, Role.BUYER, buyer,
                 "The extent in the deed does not match the survey record. Before I go further "
                 "I would like a certified copy of the deed from the sub-registrar.")


def _message(db: Session, prop: Property, role: Role, sender: User, body: str) -> None:
    scan = scan_message(body)
    db.add(
        Message(
            property_id=prop.id,
            sender_role=role.value,
            sender_id=sender.id,
            body=body,
            redacted_body=scan.redacted,
            contained_sensitive=scan.contained_sensitive,
            sensitive_kinds=scan.kinds,
        )
    )


def run(reset: bool = True) -> dict:
    if reset:
        reset_db()
    else:
        init_db()
    db = SessionLocal()
    try:
        existing = db.scalar(select(Property).limit(1))
        if existing and not reset:
            return {"skipped": True, "reason": "database already populated"}
        result = seed(db, reset=reset)
        db.commit()
        return result
    finally:
        db.close()


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Seed the LandTrust Connect demo database.")
    parser.add_argument("--reset", action="store_true", help="drop and rebuild all tables")
    parser.add_argument("--keep", action="store_true", help="seed only if empty")
    args = parser.parse_args()
    out = run(reset=not args.keep)
    print(json.dumps(out, indent=2))
