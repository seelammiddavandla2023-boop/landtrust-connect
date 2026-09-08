"""
Scenario-level tests: every property in the corpus lands where the ground truth says.

These are the assertions behind the Research Results page. If a scenario stops
matching its declared expectation, this suite fails *before* the metrics quietly
change.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.domain import ClaimType, TransactionState, VerificationStatus
from app.models import Claim, Contradiction, Document, Property
from app.services import pipeline
from app.services.resolution_planner.planner import plan as build_plan
from app.services.risk_engine.engine import compute


@pytest.fixture(scope="module")
def ground_truth():
    path = settings.synthetic_dir / "ground_truth.json"
    assert path.exists(), "run `python -m app.seed.generate` first"
    return json.loads(path.read_text("utf-8"))


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


def _gt(ground_truth, reference):
    return next(p for p in ground_truth["properties"] if p["reference"] == reference)


REFERENCES = [f"LTC-PR-{i:04d}" for i in range(1, 7)]


@pytest.mark.parametrize("reference", REFERENCES)
def test_transaction_state_matches_ground_truth(db, ground_truth, reference):
    gt = _gt(ground_truth, reference)
    prop = db.scalars(select(Property).where(Property.reference == reference)).first()
    assert prop is not None
    risk = compute(pipeline.build_context(db, prop))
    assert risk.state.value == gt["expected_transaction_state"], (
        f"{reference} ({gt['label']}) scored {risk.overall}/100 → {risk.state.value}, "
        f"expected {gt['expected_transaction_state']}"
    )
    assert risk.band.value == gt["expected_risk_band"]


@pytest.mark.parametrize("reference", REFERENCES)
def test_verification_statuses_match_ground_truth(db, ground_truth, reference):
    gt = _gt(ground_truth, reference)
    prop = db.scalars(select(Property).where(Property.reference == reference)).first()
    outcome = pipeline.build_context(db, prop).outcome
    for claim_type, expected in gt["expected_statuses"].items():
        actual = outcome.status_of(claim_type).value
        assert actual == expected, (
            f"{reference}: {claim_type} resolved to {actual}, expected {expected} — "
            f"{outcome.per_type.get(claim_type).explanation if claim_type in outcome.per_type else ''}"
        )


@pytest.mark.parametrize("reference", REFERENCES)
def test_expected_contradiction_types_are_all_detected(db, ground_truth, reference):
    gt = _gt(ground_truth, reference)
    prop = db.scalars(select(Property).where(Property.reference == reference)).first()
    detected = {
        c.contradiction_type
        for c in db.scalars(
            select(Contradiction).where(
                Contradiction.property_id == prop.id,
                Contradiction.resolved == False,  # noqa: E712
            )
        ).all()
    }
    missing = set(gt["expected_contradiction_types"]) - detected
    assert not missing, f"{reference}: failed to detect {sorted(missing)}"


# ---------------------------------------------------------------------------
# Behaviours that only appear in specific scenarios
# ---------------------------------------------------------------------------
def test_clean_title_treats_history_as_history_not_contradiction(db):
    """
    LTC-PR-0001 has two prior owners and a mortgage created in 2023 and released in
    2025. None of that is a contradiction, and the current position must be clean.
    """
    prop = db.scalars(select(Property).where(Property.reference == "LTC-PR-0001")).first()
    ctx = pipeline.build_context(db, prop)

    assert ctx.outcome.status_of(ClaimType.OWNER_NAME.value) is VerificationStatus.VERIFIED
    assert ctx.outcome.status_of(ClaimType.MORTGAGE_STATUS.value) is VerificationStatus.VERIFIED

    # The mortgage-status claim in force must be the released one, not the 2023 charge.
    live = [
        c for c in ctx.claims
        if c.claim_type == ClaimType.MORTGAGE_STATUS.value and not c.superseded
    ]
    assert live, "the encumbrance position must be evidenced"
    assert not any("active" in c.value.lower() for c in live), (
        "a discharged mortgage must not be reported as active"
    )

    # And the superseded historical claims must still exist, for the graph.
    superseded = [
        c for c in ctx.claims
        if c.claim_type == ClaimType.MORTGAGE_STATUS.value and c.superseded
    ]
    assert superseded, "history must be retained, not deleted"


def test_impersonation_case_escalates_without_accusing_anyone(db):
    prop = db.scalars(select(Property).where(Property.reference == "LTC-PR-0003")).first()
    ctx = pipeline.build_context(db, prop)
    risk = compute(ctx)

    assert risk.state is TransactionState.ESCALATE
    assert "UNVERIFIED_SELLER_AUTHORITY" in risk.triggered_rule_ids()
    assert "EXPIRED_POA" in risk.triggered_rule_ids()

    # Responsible-AI requirement: the wording must describe the evidence, not the person.
    text = " ".join(h.explanation for h in risk.hits).lower()
    for forbidden in ["fraud", "fraudster", "criminal", "impostor", "guilty", "forger"]:
        assert forbidden not in text, (
            f"risk explanations must not accuse anyone; found '{forbidden}'"
        )
    assert "cannot establish" in text or "unverified" in text


def test_modified_document_is_rejected_and_forfeits_its_authority(db):
    prop = db.scalars(select(Property).where(Property.reference == "LTC-PR-0005")).first()
    ctx = pipeline.build_context(db, prop)
    risk = compute(ctx)

    assert risk.state is TransactionState.REJECT
    assert "SUSPICIOUS_EDIT" in risk.triggered_rule_ids()

    deed = next(
        d for d in ctx.documents if d.filename == "Sale_Deed_2018_modified.pdf"
    )
    codes = {f["code"] for f in (deed.integrity_flags or [])}
    assert "FONT_DISCONTINUITY" in codes, "the overtyped field must be detected"
    assert "INCREMENTAL_SAVE" in codes, "the post-issue save must be detected"

    # The tampered deed's inflated area must not be reconciled away by the survey record.
    assert ctx.outcome.status_of(ClaimType.PROPERTY_AREA.value) is (
        VerificationStatus.CONFLICTING
    )

    # Explanations must still be indicators, not findings of forgery.
    text = " ".join(h.explanation for h in risk.hits).lower()
    assert "forged" not in text or "not a finding" in text


def test_owner_declaration_alone_never_verifies(db):
    """LTC-PR-0004 declares 'no encumbrance' with no certificate to back it."""
    prop = db.scalars(select(Property).where(Property.reference == "LTC-PR-0004")).first()
    ctx = pipeline.build_context(db, prop)
    assert ctx.outcome.status_of(ClaimType.MORTGAGE_STATUS.value) is (
        VerificationStatus.OWNER_PROVIDED
    )
    explanation = ctx.outcome.per_type[ClaimType.MORTGAGE_STATUS.value].explanation.lower()
    assert "never shown as verified" in explanation or "no supporting document" in explanation


def test_missing_evidence_is_recorded_not_ignored(db):
    prop = db.scalars(select(Property).where(Property.reference == "LTC-PR-0004")).first()
    contradictions = db.scalars(
        select(Contradiction).where(
            Contradiction.property_id == prop.id,
            Contradiction.contradiction_type == "MISSING_EVIDENCE",
        )
    ).all()
    assert any("ENCUMBRANCE" in c.left_value for c in contradictions), (
        "an absent encumbrance certificate must be recorded explicitly; absence of "
        "evidence is not evidence of absence"
    )


def test_cases_needing_authorised_review_do_not_pretend_to_resolve(db, ground_truth):
    """
    Where ownership itself is contradicted, a plan that stops short of PROCEED is the
    right answer. The planner must not manufacture a path that does not exist.
    """
    for reference in ["LTC-PR-0003", "LTC-PR-0005"]:
        gt = _gt(ground_truth, reference)
        assert gt["expected_resolvable"] is False
        prop = db.scalars(select(Property).where(Property.reference == reference)).first()
        plan = build_plan(pipeline.build_context(db, prop))
        assert not plan.reaches_proceed, (
            f"{reference} should not reach PROCEED by uploading documents alone"
        )
        assert "legal reviewer" in plan.note.lower() or "authorised" in plan.note.lower()


def test_every_property_has_a_full_audit_trail(db):
    from app.models import AuditEvent

    for reference in REFERENCES:
        prop = db.scalars(select(Property).where(Property.reference == reference)).first()
        events = db.scalars(
            select(AuditEvent).where(AuditEvent.property_id == prop.id)).all()
        actions = {e.action for e in events}
        for required in [
            "DOCUMENT_UPLOADED",
            "DOCUMENT_CLASSIFIED",
            "OCR_EXECUTED",
            "CLAIM_EXTRACTED",
            "RISK_RECALCULATED",
        ]:
            assert required in actions, f"{reference} is missing {required} in its audit trail"
