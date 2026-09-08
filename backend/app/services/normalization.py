"""
Value normalisation and typed comparison.

Cross-document contradiction detection is only meaningful if "Priya Sharma" and
"Priya S. Sharma" are recognised as *the same person written differently* while
"1800 sq.ft" and "1650 sq.ft" are recognised as a *material disagreement*.  This
module implements that distinction per ValueKind, and is the single place where
comparison policy lives.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from ..domain import CLAIM_VALUE_KIND, ClaimType, MatchType, Severity, ValueKind

# ---------------------------------------------------------------------------
# Tolerances (documented in docs/ARCHITECTURE.md §Contradiction detection)
# ---------------------------------------------------------------------------
AREA_EXACT_TOLERANCE = 0.005   # ≤0.5 % — rounding / unit conversion noise
AREA_PARTIAL_TOLERANCE = 0.02  # ≤2 %   — surveying variance, flagged but not material
MONEY_EXACT_TOLERANCE = 0.001
MONEY_PARTIAL_TOLERANCE = 0.05

NAME_TITLES = {
    "mr", "mrs", "ms", "miss", "dr", "shri", "sri", "smt", "kum", "thiru",
    "tmt", "selvi", "m/s", "messrs",
}

SQFT_PER_SQM = 10.7639
SQFT_PER_CENT = 435.6
SQFT_PER_ACRE = 43560.0

_AREA_UNITS = [
    (r"sq\.?\s*ft|sqft|square\s*feet|sft", 1.0),
    (r"sq\.?\s*m|sqm|square\s*met(?:re|er)s?", SQFT_PER_SQM),
    (r"cents?", SQFT_PER_CENT),
    (r"acres?", SQFT_PER_ACRE),
]

_MONEY_WORDS = [
    (r"crores?|cr\b", 1_00_00_000.0),
    (r"lakhs?|lacs?|lakh\b", 1_00_000.0),
    (r"thousand|k\b", 1_000.0),
]

_DATE_FORMATS = [
    "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y", "%d-%m-%y", "%m/%d/%Y",
]

_AFFIRMATIVE = {"yes", "true", "active", "present", "paid", "clear", "nil", "none", "no"}


# ---------------------------------------------------------------------------
@dataclass
class NormalisedValue:
    raw: str
    text: str                    # canonical text form
    number: float | None = None  # canonical numeric form where applicable
    kind: ValueKind = ValueKind.TEXT
    tokens: tuple[str, ...] = ()


@dataclass
class Comparison:
    match_type: MatchType
    similarity: float
    difference: str = ""
    magnitude: float | None = None
    severity: Severity = Severity.INFO
    note: str = ""

    @property
    def agrees(self) -> bool:
        return self.match_type in (
            MatchType.EXACT_MATCH,
            MatchType.NORMALIZED_MATCH,
            MatchType.PARTIAL_MATCH,
        )

    @property
    def is_material_conflict(self) -> bool:
        return self.match_type is MatchType.MISMATCH


# ---------------------------------------------------------------------------
def kind_for(claim_type: str) -> ValueKind:
    try:
        return CLAIM_VALUE_KIND.get(ClaimType(claim_type), ValueKind.TEXT)
    except ValueError:
        return ValueKind.TEXT


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


# --- names ------------------------------------------------------------------
def normalise_name(raw: str) -> NormalisedValue:
    text = _squash(raw).lower()
    text = re.sub(r"[^a-z0-9\s.]", " ", text)
    parts = [p.strip(" .") for p in text.split()]
    parts = [p for p in parts if p and p not in NAME_TITLES]
    canonical = " ".join(parts)
    return NormalisedValue(raw=raw, text=canonical, kind=ValueKind.PERSON_NAME,
                           tokens=tuple(parts))


def _name_tokens_compatible(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[bool, str]:
    """
    True when one token sequence is an initial-abbreviated form of the other,
    e.g. ('priya','sharma') vs ('priya','s','sharma').

    Returns (compatible, note).
    """
    long_, short_ = (a, b) if len(a) >= len(b) else (b, a)
    # Drop single-letter initials from the longer sequence and retry an exact compare.
    stripped = tuple(t for t in long_ if len(t) > 1)
    if stripped == short_:
        return True, "One source includes a middle initial the other omits."
    # Same surname + same first name, differing middle components.
    if long_ and short_ and long_[0] == short_[0] and long_[-1] == short_[-1]:
        return True, "First and last name agree; intermediate name components differ."
    # Initial expansion: 'r kumar' vs 'ravi kumar'
    if len(long_) == len(short_):
        expansions = 0
        for x, y in zip(long_, short_):
            if x == y:
                continue
            if (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y)):
                expansions += 1
                continue
            return False, ""
        if expansions:
            return True, "One source abbreviates a name component to an initial."
    return False, ""


def compare_names(a: str, b: str) -> Comparison:
    na, nb = normalise_name(a), normalise_name(b)
    if _squash(a) == _squash(b):
        return Comparison(MatchType.EXACT_MATCH, 1.0, severity=Severity.INFO)
    if na.text == nb.text:
        return Comparison(MatchType.NORMALIZED_MATCH, 0.98, severity=Severity.INFO,
                          note="Values agree after removing titles, case and punctuation.")
    ok, note = _name_tokens_compatible(na.tokens, nb.tokens)
    if ok:
        return Comparison(
            MatchType.PARTIAL_MATCH, 0.85,
            difference=f"'{_squash(a)}' vs '{_squash(b)}'",
            severity=Severity.LOW,
            note=note or "Name forms are compatible but not identical.",
        )
    # Shared surname only — weak signal, still a mismatch of identity.
    shared_surname = bool(na.tokens and nb.tokens and na.tokens[-1] == nb.tokens[-1])
    return Comparison(
        MatchType.MISMATCH,
        0.35 if shared_surname else 0.05,
        difference=f"'{_squash(a)}' vs '{_squash(b)}'",
        severity=Severity.CRITICAL if not shared_surname else Severity.HIGH,
        note=(
            "Different given names sharing a surname — possible related party or "
            "impersonation; cannot be treated as the same person."
            if shared_surname else
            "Names refer to different persons on the available evidence."
        ),
    )


# --- identifiers ------------------------------------------------------------
def normalise_identifier(raw: str) -> NormalisedValue:
    text = _squash(raw).upper()
    text = re.sub(r"[^A-Z0-9/\-]", "", text)
    text = text.replace("-", "/")
    return NormalisedValue(raw=raw, text=text, kind=ValueKind.IDENTIFIER)


def compare_identifiers(a: str, b: str) -> Comparison:
    ia, ib = normalise_identifier(a), normalise_identifier(b)
    if _squash(a) == _squash(b):
        return Comparison(MatchType.EXACT_MATCH, 1.0)
    if ia.text == ib.text:
        return Comparison(MatchType.NORMALIZED_MATCH, 0.97,
                          note="Identifiers agree after separator/case normalisation.")
    # Same parent survey, different sub-division (142/3A vs 142/3B) — material.
    pa, pb = ia.text.split("/")[0], ib.text.split("/")[0]
    if pa and pa == pb:
        return Comparison(
            MatchType.MISMATCH, 0.5,
            difference=f"{ia.text} vs {ib.text}",
            severity=Severity.HIGH,
            note="Same parent survey number but a different sub-division is referenced.",
        )
    return Comparison(
        MatchType.MISMATCH, 0.0,
        difference=f"{ia.text} vs {ib.text}",
        severity=Severity.CRITICAL,
        note="Documents reference different survey identifiers.",
    )


# --- area / money / numeric --------------------------------------------------
def parse_area_sqft(raw: str) -> float | None:
    text = _squash(raw).lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    value = float(m.group(1))
    for pattern, factor in _AREA_UNITS:
        if re.search(pattern, text):
            return round(value * factor, 2)
    return value  # assume sq.ft when unit is absent


def parse_money_inr(raw: str) -> float | None:
    text = _squash(raw).lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("inr", "")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    value = float(m.group(1))
    for pattern, factor in _MONEY_WORDS:
        if re.search(pattern, text):
            return value * factor
    return value


def _compare_numeric(
    a: str, b: str, parser, exact_tol: float, partial_tol: float, unit: str,
    kind: ValueKind,
) -> Comparison:
    va, vb = parser(a), parser(b)
    if va is None or vb is None:
        return Comparison(MatchType.MISSING, 0.0, severity=Severity.LOW,
                          note="One side could not be parsed as a number.")
    if va == vb:
        return Comparison(MatchType.EXACT_MATCH, 1.0)
    base = max(abs(va), abs(vb)) or 1.0
    rel = abs(va - vb) / base
    diff = abs(va - vb)
    diff_text = f"{diff:,.0f} {unit} ({rel * 100:.1f}%)"
    if rel <= exact_tol:
        return Comparison(MatchType.NORMALIZED_MATCH, 1.0 - rel, difference=diff_text,
                          magnitude=diff,
                          note="Difference is within rounding / unit-conversion tolerance.")
    if rel <= partial_tol:
        return Comparison(MatchType.PARTIAL_MATCH, 1.0 - rel, difference=diff_text,
                          magnitude=diff, severity=Severity.LOW,
                          note="Difference is small enough to be measurement variance.")
    severity = Severity.HIGH if rel <= 0.15 else Severity.CRITICAL
    return Comparison(
        MatchType.MISMATCH, max(0.0, 1.0 - rel), difference=diff_text, magnitude=diff,
        severity=severity,
        note=f"Sources disagree by {diff:,.0f} {unit}, beyond the {partial_tol * 100:.0f}% "
             f"tolerance for {kind.value.lower()} values.",
    )


def compare_areas(a: str, b: str) -> Comparison:
    return _compare_numeric(a, b, parse_area_sqft, AREA_EXACT_TOLERANCE,
                            AREA_PARTIAL_TOLERANCE, "sq.ft", ValueKind.AREA)


def compare_money(a: str, b: str) -> Comparison:
    return _compare_numeric(a, b, parse_money_inr, MONEY_EXACT_TOLERANCE,
                            MONEY_PARTIAL_TOLERANCE, "INR", ValueKind.MONEY)


# --- dates ------------------------------------------------------------------
def parse_date(raw: str) -> date | None:
    text = _squash(raw)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})", text)
    if m:
        try:
            return date(int(m.group(1)), 1, 1)
        except ValueError:
            return None
    return None


def compare_dates(a: str, b: str) -> Comparison:
    da, db = parse_date(a), parse_date(b)
    if da is None or db is None:
        return Comparison(MatchType.MISSING, 0.0, severity=Severity.LOW,
                          note="One side could not be parsed as a date.")
    if da == db:
        return Comparison(MatchType.EXACT_MATCH, 1.0)
    delta = abs((da - db).days)
    if delta <= 1:
        return Comparison(MatchType.NORMALIZED_MATCH, 0.99, difference=f"{delta} day",
                          magnitude=delta)
    if delta <= 31:
        return Comparison(MatchType.PARTIAL_MATCH, 0.8, difference=f"{delta} days",
                          magnitude=delta, severity=Severity.LOW,
                          note="Dates differ within one month (registration vs execution date).")
    return Comparison(
        MatchType.MISMATCH, max(0.0, 1 - delta / 3650), difference=f"{delta} days",
        magnitude=delta,
        severity=Severity.HIGH if delta > 365 else Severity.MEDIUM,
        note=f"Dates differ by {delta} days across sources.",
    )


# --- categorical / free text -------------------------------------------------
def normalise_categorical(raw: str) -> NormalisedValue:
    text = _squash(raw).lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    if text in {"nil", "none", "no", "clear", "not applicable", "na"}:
        text = "none"
    if text in {"active", "subsisting", "outstanding", "yes"}:
        text = "active"
    if text in {"released", "discharged", "closed", "cleared"}:
        text = "released"
    if text in {"paid", "settled", "up to date", "uptodate"}:
        text = "paid"
    if text in {"unpaid", "due", "arrears", "outstanding tax", "default"}:
        text = "unpaid"
    return NormalisedValue(raw=raw, text=text, kind=ValueKind.CATEGORICAL)


def compare_categorical(a: str, b: str) -> Comparison:
    ca, cb = normalise_categorical(a), normalise_categorical(b)
    if _squash(a).lower() == _squash(b).lower():
        return Comparison(MatchType.EXACT_MATCH, 1.0)
    if ca.text == cb.text:
        return Comparison(MatchType.NORMALIZED_MATCH, 0.97,
                          note="Equivalent terms for the same status.")
    # 'none' vs 'active' on encumbrance is the classic undisclosed-mortgage case.
    return Comparison(
        MatchType.MISMATCH, 0.0, difference=f"{ca.text or a} vs {cb.text or b}",
        severity=Severity.HIGH,
        note="Sources report different statuses for the same attribute.",
    )


def _token_set(text: str) -> set[str]:
    return {t for t in re.split(r"\W+", (text or "").lower()) if t}


def compare_text(a: str, b: str) -> Comparison:
    if _squash(a).lower() == _squash(b).lower():
        return Comparison(MatchType.EXACT_MATCH, 1.0)
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return Comparison(MatchType.MISSING, 0.0)
    jaccard = len(ta & tb) / len(ta | tb)
    if jaccard >= 0.9:
        return Comparison(MatchType.NORMALIZED_MATCH, jaccard)
    if jaccard >= 0.5:
        return Comparison(MatchType.PARTIAL_MATCH, jaccard, severity=Severity.LOW,
                          note="Descriptions overlap substantially but are not identical.")
    return Comparison(MatchType.MISMATCH, jaccard, difference=f"'{a}' vs '{b}'",
                      severity=Severity.MEDIUM,
                      note="Free-text descriptions differ materially.")


# ---------------------------------------------------------------------------
_COMPARERS = {
    ValueKind.PERSON_NAME: compare_names,
    ValueKind.IDENTIFIER: compare_identifiers,
    ValueKind.AREA: compare_areas,
    ValueKind.MONEY: compare_money,
    ValueKind.NUMERIC: compare_areas,
    ValueKind.DATE: compare_dates,
    ValueKind.CATEGORICAL: compare_categorical,
    ValueKind.TEXT: compare_text,
}


def compare_values(claim_type: str, a: str, b: str) -> Comparison:
    """Compare two raw claim values using the strategy for that claim type."""
    return _COMPARERS[kind_for(claim_type)](a or "", b or "")


def normalise(claim_type: str, raw: str) -> NormalisedValue:
    """Produce the canonical stored form for a claim value."""
    kind = kind_for(claim_type)
    if kind is ValueKind.PERSON_NAME:
        return normalise_name(raw)
    if kind is ValueKind.IDENTIFIER:
        return normalise_identifier(raw)
    if kind is ValueKind.AREA:
        n = parse_area_sqft(raw)
        return NormalisedValue(raw, f"{n:.0f} sq.ft" if n is not None else _squash(raw), n, kind)
    if kind is ValueKind.MONEY:
        n = parse_money_inr(raw)
        return NormalisedValue(raw, f"{n:.0f}" if n is not None else _squash(raw), n, kind)
    if kind is ValueKind.DATE:
        d = parse_date(raw)
        return NormalisedValue(raw, d.isoformat() if d else _squash(raw), None, kind)
    if kind is ValueKind.CATEGORICAL:
        return normalise_categorical(raw)
    return NormalisedValue(raw, _squash(raw).lower(), None, kind)
