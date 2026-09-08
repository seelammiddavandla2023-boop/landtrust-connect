"""
The Review-2 acceptance test.

This is the demonstration the project is judged on, executed as an assertion:

    A property whose sale deed records 1800 sq.ft, whose encumbrance certificate
    records 1650 sq.ft, and against which an ₹18,00,000 charge is subsisting, must

      1.  extract and display both area claims,
      2.  bind each claim to its document and page,
      3.  detect the area contradiction,
      4.  identify the active encumbrance,
      5.  mark the affected claims CONFLICTING,
      6.  compute HIGH risk,
      7.  move the transaction to HOLD,
      8.  explain why,
      9.  recommend the additional evidence required,
     10.  ingest that evidence when it is supplied,
     11.  recompute the risk,
     12.  show a reduced score, and
     13.  move the transaction toward PROCEED once the evidence is sufficient.

Nothing here is stubbed. The pipeline runs over the generated PDFs, and every figure
asserted is one the engines produced.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.domain import ClaimType, TransactionState, VerificationStatus
from app.models import Claim, Contradiction, Document, Property, ResolutionAction
from app.services import pipeline
from app.services.resolution_planner.planner import CATALOGUE_BY_KEY
from app.services.risk_engine.engine import compute

REFERENCE = "LTC-PR-0002"


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def prop(db):
    row = db.scalars(select(Property).where(Property.reference == REFERENCE)).first()
    assert row is not None, (
        f"{REFERENCE} is not in the database. Run `python -m app.seed.seed --reset` first."
    )
    return row


def _claims(db, prop, claim_type: ClaimType, include_superseded: bool = False):
    rows = db.scalars(
        select(Claim).where(
            Claim.property_id == prop.id, Claim.claim_type == claim_type.value
        )
    ).all()
    return [c for c in rows if include_superseded or not c.superseded]


# ---------------------------------------------------------------------------
# 1–2. Both area claims exist, each bound to its document and page.
# ---------------------------------------------------------------------------
def test_both_area_claims_are_extracted_with_provenance(db, prop):
    areas = _claims(db, prop, ClaimType.PROPERTY_AREA)
    values = {c.value for c in areas}
    assert "1800 sq.ft" in values, f"expected the deed's 1800 sq.ft, got {values}"
    assert "1650 sq.ft" in values, f"expected the certificate's 1650 sq.ft, got {values}"

    docs = {d.id: d for d in db.scalars(
        select(Document).where(Document.property_id == prop.id)).all()}
    for claim in areas:
        assert claim.document_id in docs, "every claim must name the document it came from"
        assert claim.source_page >= 1, "every claim must name the page it came from"
        assert claim.confidence > 0, "every claim must carry an extraction confidence"
        assert claim.source_span, "every claim must retain the text it was read from"
        # Provenance is not merely a filename: the claim knows where on the page it sat.
        assert claim.source_region.get("w"), "every claim must anchor to a page region"


# ---------------------------------------------------------------------------
# 3. The area contradiction is detected, with the magnitude computed.
# ---------------------------------------------------------------------------
def test_area_contradiction_is_detected(db, prop):
    rows = db.scalars(
        select(Contradiction).where(
            Contradiction.property_id == prop.id,
            Contradiction.contradiction_type == "AREA_DISCREPANCY",
        )
    ).all()
    assert rows, "the 150 sq.ft disagreement must be recorded as a contradiction"
    c = rows[0]
    assert c.severity in {"HIGH", "CRITICAL"}
    assert c.magnitude == pytest.approx(150.0), f"expected a 150 sq.ft gap, got {c.magnitude}"
    assert "1800" in f"{c.left_value}{c.right_value}"
    assert "1650" in f"{c.left_value}{c.right_value}"
    # The explanation must name both sources — an unexplained flag is not evidence.
    assert "Sale_Deed" in c.left_source or "Sale_Deed" in c.right_source
    assert "Encumbrance" in c.left_source or "Encumbrance" in c.right_source


# ---------------------------------------------------------------------------
# 4. The active encumbrance is identified.
# ---------------------------------------------------------------------------
def test_active_encumbrance_is_identified(db, prop):
    statuses = _claims(db, prop, ClaimType.MORTGAGE_STATUS)
    assert statuses, "the encumbrance certificate must yield a mortgage-status claim"
    assert any("active" in c.value.lower() for c in statuses)

    amounts = _claims(db, prop, ClaimType.MORTGAGE_AMOUNT)
    assert any("18,00,000" in c.value for c in amounts), "the charge amount must be extracted"


# ---------------------------------------------------------------------------
# 5. The affected claims are CONFLICTING; unaffected ones are not dragged down.
# ---------------------------------------------------------------------------
def test_verification_statuses_reflect_the_evidence(db, prop):
    ctx = pipeline.build_context(db, prop)
    outcome = ctx.outcome

    assert outcome.status_of(ClaimType.PROPERTY_AREA.value) is VerificationStatus.CONFLICTING

    # The survey number agrees across three documents, so the area conflict must not
    # contaminate it. Contradiction is per-attribute, not per-file.
    assert outcome.status_of(ClaimType.SURVEY_NUMBER.value) is VerificationStatus.VERIFIED

    # "Priya Sharma" vs "Priya S. Sharma" is a name variant, not a different person:
    # partially verified, never verified, never conflicting.
    assert outcome.status_of(ClaimType.OWNER_NAME.value) is (
        VerificationStatus.PARTIALLY_VERIFIED
    )


def test_a_single_document_never_verifies_a_claim_on_its_own(db, prop):
    """The central research requirement, asserted directly."""
    ctx = pipeline.build_context(db, prop)
    docs = {d.id: d for d in ctx.documents}

    for claim_type, group in ctx.outcome.per_type.items():
        if group.status is not VerificationStatus.VERIFIED:
            continue
        sources = [docs[d] for d in group.supporting_document_ids if d in docs]
        if len(sources) >= 2:
            continue
        # A lone source is permitted to verify only when it is the authority of record
        # for that attribute — that is the single documented exception.
        from app.services.verification.authority import is_authority_of_record

        assert sources and is_authority_of_record(sources[0].doc_type, claim_type), (
            f"{claim_type} is VERIFIED from a single non-authoritative document "
            f"({[s.filename for s in sources]}) — a claim must never be verified "
            "merely because it appeared once."
        )


# ---------------------------------------------------------------------------
# 6–8. HIGH risk, HOLD state, with an explanation.
# ---------------------------------------------------------------------------
def test_risk_is_high_and_transaction_is_held(db, prop):
    ctx = pipeline.build_context(db, prop)
    risk = compute(ctx)

    assert risk.band.value == "HIGH", f"expected HIGH band, got {risk.band.value} at {risk.overall}"
    assert 50 <= risk.overall < 75, f"HOLD band is [50, 75); got {risk.overall}"
    assert risk.state is TransactionState.HOLD

    triggered = risk.triggered_rule_ids()
    assert "ACTIVE_MORTGAGE" in triggered
    assert "AREA_MISMATCH" in triggered

    assert risk.state_reason, "a held transaction must say why it is held"
    assert len(risk.state_reason) > 60, "the reason must be an explanation, not a label"


def test_unsafe_actions_are_blocked_while_held(db, prop):
    from app.services.risk_engine.engine import blocked_actions

    ctx = pipeline.build_context(db, prop)
    risk = compute(ctx)
    blocked = blocked_actions(risk.state)
    assert "INITIATE_PAYMENT" in blocked
    assert "PROCEED_TO_AGREEMENT" in blocked


# ---------------------------------------------------------------------------
# 9. A minimum-evidence path is recommended.
# ---------------------------------------------------------------------------
def test_resolution_plan_reaches_proceed(db, prop):
    from app.services.resolution_planner.planner import plan as build_plan

    ctx = pipeline.build_context(db, prop)
    resolution = build_plan(ctx)

    assert resolution.steps, "a held transaction must be given a way out"
    assert resolution.reaches_proceed, (
        f"the plan ends at {resolution.final_state.value} "
        f"({resolution.final_risk}); it should reach PROCEED"
    )

    keys = {s.action.key for s in resolution.steps}
    assert "OBTAIN_BANK_NOC" in keys, "the active charge must be addressed"
    assert "OBTAIN_CERTIFIED_SURVEY" in keys, "the extent discrepancy must be addressed"

    # Each step must strictly reduce risk, and the predicted scores must chain.
    previous = resolution.baseline_risk
    for step in resolution.steps:
        assert step.risk_before == pytest.approx(previous, abs=0.11), (
            "each step must start from the previous step's outcome"
        )
        assert step.risk_after < step.risk_before, (
            f"{step.action.key} does not reduce risk ({step.risk_before} → {step.risk_after})"
        )
        previous = step.risk_after


# ---------------------------------------------------------------------------
# 10–13. Applying the evidence for real reduces the risk and releases the hold.
# ---------------------------------------------------------------------------
def test_applying_evidence_reduces_risk_and_releases_the_hold(db, prop):
    """
    The end-to-end sequence.

    The steps applied are the ones the *planner* recommends, not a list written here —
    a hardcoded sequence would let the test pass while the plan on screen said
    something else.

    Each step ingests a real PDF through the ordinary pipeline, and the score that
    comes out is whatever the engine computes from the enlarged evidence set. Where a
    step supplies evidence the platform cannot verify by re-derivation — a notarised
    affidavit is the case here — the corresponding factor is *closed against that
    document*, and the closure is recorded with the document that produced it. The
    assertions below distinguish the two, because the difference matters.
    """
    import json

    from app.config import settings
    from app.services import audit
    from app.domain import AuditAction, Role

    manifest_path = settings.synthetic_dir / "pending" / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")).get(REFERENCE, {})
    assert manifest, "the corrective evidence for this scenario must be generated"

    from app.services.resolution_planner.planner import plan as build_plan

    ctx = pipeline.build_context(db, prop)
    start = compute(ctx)
    assert start.state is TransactionState.HOLD

    initial_plan = build_plan(ctx)
    planned = [s.action.key for s in initial_plan.steps]
    plan_final = initial_plan.final_risk
    assert planned, "the planner must recommend something for a held transaction"

    trace = [(None, start.overall, start.state.value)]
    closures_used: list[str] = []

    for action_key in planned:
        action = CATALOGUE_BY_KEY[action_key]
        filename = manifest.get(action_key)
        if filename:
            path = settings.synthetic_dir / "pending" / REFERENCE / filename
            assert path.exists(), f"missing corrective evidence file: {path}"
            pipeline.ingest_document(
                db, prop, path, filename, uploaded_by_role=Role.OWNER, actor_name="test",
            )
            db.flush()

        # Mirror /resolution/apply: recompute first, so a factor the new evidence
        # clears by re-derivation is never closed administratively instead.
        pipeline.reassess(
            db, prop, actor_role=Role.OWNER, actor_name="test",
            reason=f"acceptance: evidence for {action_key}",
        )
        after_ingest = compute(pipeline.build_context(db, prop))
        still_open = action.resolves & after_ingest.triggered_rule_ids()
        if still_open:
            assert filename, (
                f"{action_key} left {sorted(still_open)} open with no document to cite. "
                "A factor may only be closed against evidence that was actually supplied."
            )
            closures = list(prop.closed_rules or [])
            for rule_id in sorted(still_open):
                closures_used.append(f"{rule_id}<-{filename}")
                closures.append({
                    "rule_id": rule_id, "action_key": action.key,
                    "document_id": None, "document_name": filename,
                    "closed_at": "test",
                    "note": f"closed against {filename} by the acceptance test",
                })
            prop.closed_rules = closures
            db.flush()

        assessment = pipeline.reassess(
            db, prop, actor_role=Role.OWNER, actor_name="test",
            reason=f"acceptance test: {action_key}",
        )
        trace.append((action_key, assessment.overall_score, assessment.state))

        if assessment.state == TransactionState.PROCEED.value:
            break

    readable = " → ".join(
        f"{key or 'start'}: {score:.1f}/{state}" for key, score, state in trace
    )

    # 11–12. Risk fell.
    assert trace[-1][1] < start.overall, f"risk did not fall: {readable}"

    # 13. And the hold was released.
    assert trace[-1][2] == TransactionState.PROCEED.value, (
        f"the transaction did not reach PROCEED: {readable}"
    )

    # The reduction must be substantial, not cosmetic.
    assert start.overall - trace[-1][1] > 40, (
        f"expected a large reduction once the evidence was supplied: {readable}"
    )

    # Predictions must never overstate the improvement. Suppressing an action's rules
    # models what it removes but not what the evidence additionally earns, so the
    # applied score should land at or below the planned one — under-promising is the
    # safe direction for a system that decides whether a transaction may proceed.
    assert trace[-1][1] <= plan_final + 0.11, (
        f"the applied score ({trace[-1][1]}) is worse than the plan predicted "
        f"({plan_final}); a counterfactual must be a lower bound on the improvement"
    )

    print(f"\nAcceptance sequence: {readable}")
    print(f"Factors closed against a document rather than re-derived: "
          f"{closures_used or 'none — every step cleared by recomputation'}")


def test_the_sworn_affidavit_reconciles_the_name_by_evidence(db, prop):
    """
    The name variant must be closed by *evidence*, not by agreeing to stop counting it.

    An affidavit swearing that two name forms denote the same person is evidence about
    the relationship between the two names — which is the thing in question. This test
    exists because the alternative (suppressing the rule and calling it resolved) would
    make the final step of the acceptance sequence a presentational trick.
    """
    import json

    from app.config import settings
    from app.domain import Role
    from app.services.verification.resolver import _name_equivalences

    # The corpus reaches PROCEED during the previous test; work from a clean file.
    from app.seed.seed import run

    db.close()
    run(reset=True)

    fresh = SessionLocal()
    try:
        reloaded = fresh.scalars(
            select(Property).where(Property.reference == REFERENCE)).first()
        before = fresh.scalars(  # noqa: F841 - readability
            select(Claim).where(Claim.property_id == reloaded.id)).all()
        ctx = pipeline.build_context(fresh, reloaded)
        assert ctx.outcome.status_of(ClaimType.OWNER_NAME.value) is (
            VerificationStatus.PARTIALLY_VERIFIED
        )
        assert not _name_equivalences(ctx.claims, ctx.documents)

        manifest = json.loads(
            (settings.synthetic_dir / "pending" / "manifest.json").read_text("utf-8")
        )[REFERENCE]
        path = settings.synthetic_dir / "pending" / REFERENCE / manifest["RECONCILE_NAME_VARIANT"]
        result = pipeline.ingest_document(
            fresh, reloaded, path, path.name, uploaded_by_role=Role.OWNER, actor_name="test",
        )
        fresh.flush()

        # The affidavit must be recognised as a sworn instrument, not a self-declaration.
        assert result.document.doc_type == "AFFIDAVIT"
        assert any(
            c.claim_type == ClaimType.NAME_EQUIVALENCE.value for c in result.claims
        ), "the sworn equivalence must be extracted as its own claim"

        pipeline.reassess(fresh, reloaded, actor_role=Role.OWNER, actor_name="test",
                          reason="acceptance: affidavit")

        after = pipeline.build_context(fresh, reloaded)
        assert _name_equivalences(after.claims, after.documents), (
            "the equivalence must be available to the resolver"
        )
        assert after.outcome.status_of(ClaimType.OWNER_NAME.value) is (
            VerificationStatus.VERIFIED
        ), (
            "a sworn equivalence covering every differing name form should reconcile the "
            "variant on evidence: "
            + after.outcome.per_type[ClaimType.OWNER_NAME.value].explanation
        )
        assert "sworn equivalence" in (
            after.outcome.per_type[ClaimType.OWNER_NAME.value].explanation
        )
        # And it must have been derived, not suppressed.
        assert not reloaded.closed_rules, (
            "the name variant should be resolved by evidence, with nothing suppressed"
        )
    finally:
        fresh.close()


# ---------------------------------------------------------------------------
# Guard: the demonstration must be repeatable.
# ---------------------------------------------------------------------------
def test_reseed_restores_the_starting_state(db, prop):
    """The previous test mutated the file; confirm a reset returns it to HOLD."""
    from app.seed.seed import run

    db.close()
    run(reset=True)

    fresh = SessionLocal()
    try:
        reloaded = fresh.scalars(
            select(Property).where(Property.reference == REFERENCE)).first()
        risk = compute(pipeline.build_context(fresh, reloaded))
        assert risk.state is TransactionState.HOLD
        assert 50 <= risk.overall < 75
    finally:
        fresh.close()
