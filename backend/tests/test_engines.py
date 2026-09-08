"""
Unit tests for the reasoning engines.

These test the *policies* rather than the plumbing: that a name variant is not a
different person, that 150 sq.ft on 1800 is material while 4 sq.ft is not, that a
chain of title is not a contradiction, and that the risk aggregation refuses to let
six benign categories dilute one critical one.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.domain import ClaimType, MatchType, RiskCategory, Severity, TransactionState
from app.services.normalization import (
    compare_values,
    normalise,
    parse_area_sqft,
    parse_money_inr,
)
from app.services.risk_engine.engine import _category_score, compute
from app.services.verification.authority import (
    authority_of,
    combined_authority,
    is_authority_of_record,
)


# ---------------------------------------------------------------------------
# Name comparison
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("Ravi Kumar", "Ravi Kumar", MatchType.EXACT_MATCH),
        ("Ravi Kumar", "ravi  kumar", MatchType.NORMALIZED_MATCH),
        ("Ravi Kumar", "Mr. Ravi Kumar", MatchType.NORMALIZED_MATCH),
        ("Priya Sharma", "Priya S. Sharma", MatchType.PARTIAL_MATCH),
        ("Ravi Kumar", "R. Kumar", MatchType.PARTIAL_MATCH),
        ("Mohan Reddy", "Arjun Reddy", MatchType.MISMATCH),
        ("Ravi Kumar", "Fatima Begum", MatchType.MISMATCH),
    ],
)
def test_name_comparison(a, b, expected):
    assert compare_values(ClaimType.OWNER_NAME.value, a, b).match_type is expected


def test_a_shared_surname_is_a_weaker_mismatch_than_no_relation():
    related = compare_values(ClaimType.OWNER_NAME.value, "Mohan Reddy", "Arjun Reddy")
    unrelated = compare_values(ClaimType.OWNER_NAME.value, "Mohan Reddy", "Fatima Begum")
    assert related.similarity > unrelated.similarity
    # Both are still mismatches: a shared surname is not evidence of the same person.
    assert related.is_material_conflict and unrelated.is_material_conflict
    assert related.severity is Severity.HIGH
    assert unrelated.severity is Severity.CRITICAL


# ---------------------------------------------------------------------------
# Area comparison
# ---------------------------------------------------------------------------
def test_area_units_are_converted_before_comparison():
    assert parse_area_sqft("2400 sq.ft") == 2400
    assert parse_area_sqft("223 sq.m") == pytest.approx(2400.35, abs=1)
    assert parse_area_sqft("1 acre") == 43560
    # A parcel quoted in square metres agrees with the same parcel in square feet.
    assert compare_values(ClaimType.PROPERTY_AREA.value, "2400 sq.ft", "223 sq.m").agrees


@pytest.mark.parametrize(
    "a,b,material",
    [
        ("1800 sq.ft", "1800 sq.ft", False),
        ("1800 sq.ft", "1805 sq.ft", False),   # within surveying tolerance
        ("1800 sq.ft", "1830 sq.ft", False),   # 1.7% — variance, flagged not material
        ("1800 sq.ft", "1650 sq.ft", True),    # 8.3% — the acceptance case
        ("2000 sq.ft", "5000 sq.ft", True),
    ],
)
def test_area_materiality(a, b, material):
    assert compare_values(ClaimType.PROPERTY_AREA.value, a, b).is_material_conflict is material


def test_area_difference_is_quantified():
    cmp = compare_values(ClaimType.PROPERTY_AREA.value, "1800 sq.ft", "1650 sq.ft")
    assert cmp.magnitude == pytest.approx(150.0)
    assert "150" in cmp.difference and "8.3" in cmp.difference


# ---------------------------------------------------------------------------
# Identifiers, money, dates, categories
# ---------------------------------------------------------------------------
def test_survey_subdivision_is_a_material_difference():
    cmp = compare_values(ClaimType.SURVEY_NUMBER.value, "142/3A", "142/3B")
    assert cmp.is_material_conflict
    assert "sub-division" in cmp.note.lower()


def test_survey_separator_normalisation():
    assert compare_values(ClaimType.SURVEY_NUMBER.value, "142/3A", "142-3a").agrees


def test_indian_money_notation():
    assert parse_money_inr("Rs. 18,00,000") == 1800000
    assert parse_money_inr("₹18 lakh") == 1800000
    assert parse_money_inr("1.5 crore") == 15000000
    assert compare_values(ClaimType.MORTGAGE_AMOUNT.value, "Rs. 18,00,000", "₹18 lakh").agrees


def test_encumbrance_synonyms_resolve_to_the_same_status():
    assert compare_values(ClaimType.MORTGAGE_STATUS.value, "NIL", "None").agrees
    assert compare_values(ClaimType.MORTGAGE_STATUS.value, "Active", "Subsisting").agrees
    assert compare_values(
        ClaimType.MORTGAGE_STATUS.value, "NIL", "Active"
    ).is_material_conflict


def test_registration_and_execution_dates_within_a_month_are_not_a_conflict():
    assert not compare_values(
        ClaimType.REGISTRATION_DATE.value, "15-06-2021", "02-07-2021"
    ).is_material_conflict
    assert compare_values(
        ClaimType.REGISTRATION_DATE.value, "15-06-2021", "15-06-2019"
    ).is_material_conflict


def test_normalisation_produces_a_canonical_stored_form():
    assert normalise(ClaimType.PROPERTY_AREA.value, "223 sq.m").number == pytest.approx(2400.35, abs=1)
    assert normalise(ClaimType.OWNER_NAME.value, "Mr. Ravi  Kumar").text == "ravi kumar"
    assert normalise(ClaimType.REGISTRATION_DATE.value, "15-06-2021").text == "2021-06-15"


# ---------------------------------------------------------------------------
# Evidential authority
# ---------------------------------------------------------------------------
def test_authority_of_record_is_attribute_specific():
    # The survey office determines extent; a tax receipt merely quotes it.
    assert is_authority_of_record("SURVEY_RECORD", ClaimType.PROPERTY_AREA.value)
    assert not is_authority_of_record("TAX_RECEIPT", ClaimType.PROPERTY_AREA.value)
    # The encumbrance certificate determines encumbrance; the deed merely warrants it.
    assert is_authority_of_record("ENCUMBRANCE_CERTIFICATE", ClaimType.MORTGAGE_STATUS.value)
    assert not is_authority_of_record("SALE_DEED", ClaimType.MORTGAGE_STATUS.value)


def test_an_owner_declaration_carries_almost_no_weight():
    assert authority_of("OWNER_DECLARATION", ClaimType.OWNER_NAME.value) <= 0.25


def test_independent_evidence_combines_without_reaching_certainty():
    one = combined_authority([0.8])
    two = combined_authority([0.8, 0.8])
    many_weak = combined_authority([0.2] * 20)
    assert two > one
    assert two < 1.0, "no finite amount of evidence should reach certainty"
    assert many_weak < 0.99, "twenty weak witnesses must not become an authority"


# ---------------------------------------------------------------------------
# Risk aggregation
# ---------------------------------------------------------------------------
def test_category_score_saturates():
    """The first serious problem should move a category far more than the fifth."""
    first = _category_score(30) - _category_score(0)
    fifth = _category_score(150) - _category_score(120)
    assert first > fifth * 3
    assert _category_score(0) == 0
    assert _category_score(-40) == 0, "mitigations must not produce a negative category"


def test_aggregation_does_not_dilute_a_single_critical_category():
    """
    A weighted mean would let six benign categories average away one critical one.
    The noisy-OR combination must not, and this is the property the whole risk model
    depends on.
    """
    from app.services.risk_engine.engine import CATEGORY_INFLUENCE

    critical_only = 1.0
    for category, influence in CATEGORY_INFLUENCE.items():
        score = 95.0 if category is RiskCategory.OWNERSHIP else 0.0
        critical_only *= 1 - influence * score / 100
    overall = 100 * (1 - critical_only)
    assert overall > 65, (
        f"one saturated ownership category alone should carry the file into hold "
        f"territory; got {overall:.1f}"
    )


def test_state_bands_have_no_gaps():
    """A score must never fall between two bands."""
    from app.domain import STATE_THRESHOLDS
    from app.services.risk_engine.engine import _band_and_state

    for score in [x / 2 for x in range(0, 201)]:
        band, state = _band_and_state(score)
        assert isinstance(state, TransactionState)
    # The boundaries themselves
    assert _band_and_state(24.9)[1] is TransactionState.PROCEED
    assert _band_and_state(25.0)[1] is TransactionState.WARN
    assert _band_and_state(49.9)[1] is TransactionState.WARN
    assert _band_and_state(50.0)[1] is TransactionState.HOLD
    assert _band_and_state(74.9)[1] is TransactionState.HOLD
    assert _band_and_state(75.0)[1] is TransactionState.ESCALATE
