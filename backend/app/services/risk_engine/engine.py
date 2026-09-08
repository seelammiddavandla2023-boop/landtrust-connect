"""
Risk aggregation and the transaction state controller.

Aggregation is deliberately *not* a plain weighted mean.  A mean lets six benign
categories dilute one critical one — exactly the failure mode that produces a
"medium risk" score for a property with an expired power of attorney.  Instead:

    category_sum   = Σ rule weights in that category (mitigations are negative)
    category_score = 100 · (1 − e^(−max(0, sum) / SATURATION))
    overall        = 100 · (1 − Π_c (1 − influence_c · category_score_c / 100))

The inner form is a saturating curve: the first serious problem in a category moves
the score a lot, the fifth moves it little.  The outer form is a noisy-OR: risks
combine as independent chances of the transaction being unsafe, so a single
critical category dominates while additional problems still add.  Both are monotone
in every rule weight, which is what makes the Resolution Planner's counterfactual
simulation meaningful.

Everything here is deterministic and reproducible.  `engine_version` is stored on
each assessment so a Review-3 learned scorer can coexist with these results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import exp

from ...domain import (
    RISK_CATEGORY_LABELS,
    STATE_THRESHOLDS,
    ContradictionType,
    RiskBand,
    RiskCategory,
    Severity,
    TransactionState,
    VerificationStatus,
)
from .rules import RiskContext, RuleHit, evaluate

ENGINE_VERSION = "rules-1.0"
SATURATION = 40.0

# How much a fully-saturated category can raise the overall score on its own.
CATEGORY_INFLUENCE = {
    RiskCategory.OWNERSHIP: 0.75,
    RiskCategory.ENCUMBRANCE: 0.62,
    RiskCategory.SURVEY: 0.55,
    RiskCategory.DOCUMENT: 0.55,
    RiskCategory.VALUATION: 0.30,
    RiskCategory.PAYMENT: 0.30,
    RiskCategory.INTERACTION: 0.35,
}


@dataclass
class CategoryScore:
    category: RiskCategory
    label: str
    raw_sum: float
    score: float
    influence: float
    factors: list[RuleHit] = field(default_factory=list)


@dataclass
class RiskResult:
    overall: float
    band: RiskBand
    state: TransactionState
    state_reason: str
    categories: dict[str, CategoryScore]
    hits: list[RuleHit]
    engine_version: str = ENGINE_VERSION
    hard_overrides: list[str] = field(default_factory=list)

    def category_scores(self) -> dict[str, float]:
        return {k: round(v.score, 1) for k, v in self.categories.items()}

    def triggered_rule_ids(self) -> set[str]:
        return {h.rule_id for h in self.hits if not h.is_mitigation}


def _category_score(raw_sum: float) -> float:
    positive = max(0.0, raw_sum)
    return round(100.0 * (1.0 - exp(-positive / SATURATION)), 2)


def compute(ctx: RiskContext) -> RiskResult:
    hits = evaluate(ctx)

    categories: dict[str, CategoryScore] = {}
    for category in RiskCategory:
        members = [h for h in hits if h.category is category]
        raw = sum(h.weight for h in members)
        categories[category.value] = CategoryScore(
            category=category,
            label=RISK_CATEGORY_LABELS[category],
            raw_sum=round(raw, 2),
            score=_category_score(raw),
            influence=CATEGORY_INFLUENCE[category],
            factors=sorted(members, key=lambda h: h.weight, reverse=True),
        )

    survival = 1.0
    for cs in categories.values():
        survival *= (1.0 - cs.influence * cs.score / 100.0)
    overall = round(min(100.0, max(0.0, 100.0 * (1.0 - survival))), 1)

    band, state = _band_and_state(overall)
    state, reason, overrides = _apply_overrides(ctx, hits, state, overall)

    return RiskResult(
        overall=overall,
        band=band,
        state=state,
        state_reason=reason,
        categories=categories,
        hits=hits,
        hard_overrides=overrides,
    )


def _band_and_state(score: float) -> tuple[RiskBand, TransactionState]:
    for lo, hi, state, band in STATE_THRESHOLDS:
        if lo <= score < hi:
            return band, state
    return RiskBand.CRITICAL, TransactionState.ESCALATE


# ---------------------------------------------------------------------------
# Transaction State Controller
# ---------------------------------------------------------------------------
# Some failures are categorical rather than quantitative: if the system cannot
# establish that the seller may sell, no arithmetic should let the transaction
# proceed.  These overrides can only ever move the state to a *stricter* value.
HARD_OVERRIDES = [
    (
        {"UNVERIFIED_SELLER_AUTHORITY"},
        TransactionState.ESCALATE,
        "Seller authority could not be established from the available evidence. The case is "
        "escalated to a legal reviewer rather than resolved automatically.",
    ),
    (
        {"EXPIRED_POA", "OWNER_CONTRADICTION"},
        TransactionState.ESCALATE,
        "An expired authorisation combined with an ownership contradiction means no party on "
        "file is evidenced as entitled to transact.",
    ),
    (
        {"SUSPICIOUS_EDIT", "OWNER_CONTRADICTION"},
        TransactionState.REJECT,
        "Ownership is contradicted and a supporting document shows indicators of post-issue "
        "modification. The transaction is refused pending examination by an authorised "
        "verifier; this is a decision about the evidence, not a legal finding.",
    ),
    (
        {"OWNER_CONTRADICTION"},
        TransactionState.HOLD,
        "Documents disagree about who owns this property, so progression is held until the "
        "contradiction is resolved.",
    ),
    (
        {"ACTIVE_MORTGAGE"},
        TransactionState.HOLD,
        "An active encumbrance is recorded; the transaction is held until a release or "
        "lender no-objection is provided.",
    ),
]


def _apply_overrides(
    ctx: RiskContext, hits: list[RuleHit], state: TransactionState, score: float
) -> tuple[TransactionState, str, list[str]]:
    from ...domain import TRANSACTION_STATE_RANK

    triggered = {h.rule_id for h in hits if not h.is_mitigation}
    reasons: list[str] = []
    applied: list[str] = []
    final = state

    for required, forced, message in HARD_OVERRIDES:
        if not required.issubset(triggered):
            continue
        if TRANSACTION_STATE_RANK[forced] > TRANSACTION_STATE_RANK[final]:
            final = forced
            reasons.append(message)
            applied.append("+".join(sorted(required)))
        elif TRANSACTION_STATE_RANK[forced] == TRANSACTION_STATE_RANK[final]:
            reasons.append(message)
            applied.append("+".join(sorted(required)))

    if not reasons:
        reasons.append(_score_reason(final, score, hits))
    return final, " ".join(reasons), applied


def _score_reason(state: TransactionState, score: float, hits: list[RuleHit]) -> str:
    top = sorted(
        (h for h in hits if not h.is_mitigation and h.weight > 0),
        key=lambda h: h.weight,
        reverse=True,
    )[:3]
    drivers = "; ".join(h.title.lower() for h in top) or "residual verification risk only"
    if state is TransactionState.PROCEED:
        return (
            f"Composite risk {score:.0f}/100. No unresolved contradiction or encumbrance blocks "
            f"progression. Remaining exposure: {drivers}."
        )
    if state is TransactionState.WARN:
        return (
            f"Composite risk {score:.0f}/100. The file may progress, but the buyer should be "
            f"shown the open items before committing: {drivers}."
        )
    if state is TransactionState.HOLD:
        return (
            f"Composite risk {score:.0f}/100 exceeds the hold threshold of 50. Progression to "
            f"agreement or payment is blocked until the driving issues are resolved: {drivers}."
        )
    if state is TransactionState.ESCALATE:
        return (
            f"Composite risk {score:.0f}/100. The case requires review by a legal reviewer or "
            f"authorised verifier before any further step: {drivers}."
        )
    return (
        f"Composite risk {score:.0f}/100. The evidence does not support proceeding: {drivers}."
    )


BLOCKED_ACTIONS = {
    TransactionState.PROCEED: [],
    TransactionState.WARN: [],
    TransactionState.HOLD: ["INITIATE_PAYMENT", "PROCEED_TO_AGREEMENT", "SHARE_IDENTITY"],
    TransactionState.ESCALATE: [
        "INITIATE_PAYMENT", "PROCEED_TO_AGREEMENT", "SHARE_IDENTITY", "TOKEN_ADVANCE",
    ],
    TransactionState.REJECT: [
        "INITIATE_PAYMENT", "PROCEED_TO_AGREEMENT", "SHARE_IDENTITY", "TOKEN_ADVANCE",
        "SITE_VISIT_BOOKING",
    ],
}

STATE_BANNER = {
    TransactionState.PROCEED: "Evidence supports progression. Continue with normal diligence.",
    TransactionState.WARN: "Open items exist. Review them before committing funds.",
    TransactionState.HOLD: (
        "Transaction temporarily held because unresolved evidence creates a high-risk condition."
    ),
    TransactionState.ESCALATE: (
        "Escalated for review by a legal reviewer or authorised verifier before any further step."
    ),
    TransactionState.REJECT: (
        "Progression refused on the current evidence. Authorised examination is required."
    ),
}


def blocked_actions(state: TransactionState) -> list[str]:
    return list(BLOCKED_ACTIONS.get(state, []))
