"""
Autonomous resolution planner — the minimum-evidence path.

Detecting a problem is the easy half.  The research contribution here is answering
*"what is the smallest set of additional evidence that would make this transaction
safe to progress?"*

Method
------
Each candidate action declares which risk rules it would neutralise and which
mitigations it would grant.  Because the risk aggregation is monotone in every rule
weight, the effect of an action can be evaluated exactly by re-running the scorer
with that rule set suppressed — a genuine counterfactual, not a stored estimate.

The planner then runs a greedy search over the counterfactuals, at each step taking
the action with the best risk-reduction-per-unit-effort, until the transaction state
reaches PROCEED or no candidate improves the score.  Greedy is appropriate because
the aggregation is submodular in practice (each additional fix helps less), and it
keeps the plan explainable: every step shows the score it moves from and to.
"""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass, field

from ...domain import (
    ActionEffort,
    DocumentType,
    ResponsibleParty,
    TransactionState,
)
from ..risk_engine.engine import compute
from ..risk_engine.rules import RiskContext

EFFORT_COST = {ActionEffort.LOW: 1.0, ActionEffort.MEDIUM: 2.0, ActionEffort.HIGH: 3.5}


@dataclass(frozen=True)
class CandidateAction:
    key: str
    title: str
    description: str
    required_evidence: str
    resolves: frozenset[str]
    grants: frozenset[str] = frozenset()
    responsible: ResponsibleParty = ResponsibleParty.OWNER
    authority: str = ""
    effort: ActionEffort = ActionEffort.MEDIUM
    produces_document: str | None = None


CATALOGUE: list[CandidateAction] = [
    CandidateAction(
        key="OBTAIN_CURRENT_EC",
        title="Obtain a current encumbrance certificate",
        description=(
            "Apply for a fresh EC covering the period up to the present date. This replaces "
            "an out-of-date certificate and evidences whether any charge has been created since "
            "the last search."
        ),
        required_evidence="Encumbrance Certificate issued within the last 30 days",
        resolves=frozenset({"STALE_EC", "MISSING_EC", "EXPIRED_DOCUMENT"}),
        responsible=ResponsibleParty.OWNER,
        authority="Sub-Registrar's office (online EC portal or counter application)",
        effort=ActionEffort.LOW,
        produces_document=DocumentType.ENCUMBRANCE_CERTIFICATE.value,
    ),
    CandidateAction(
        key="OBTAIN_BANK_NOC",
        title="Obtain lender no-objection / mortgage release",
        description=(
            "Request a no-objection certificate or release letter from the charge holder "
            "confirming the loan position and, where applicable, that the charge has been "
            "discharged."
        ),
        required_evidence="Bank NOC or registered release of mortgage",
        resolves=frozenset({"ACTIVE_MORTGAGE", "ENCUMBRANCE_DISCLOSURE_CONFLICT"}),
        grants=frozenset({"BANK_NOC_PRESENT"}),
        responsible=ResponsibleParty.LENDER,
        authority="Charge holder (lending institution) — owner must initiate the request",
        effort=ActionEffort.MEDIUM,
        produces_document=DocumentType.BANK_NOC.value,
    ),
    CandidateAction(
        key="OBTAIN_CERTIFIED_SURVEY",
        title="Obtain a certified survey record / FMB sketch",
        description=(
            "Commission a certified measurement from the survey authority. The survey record is "
            "the authority of record for extent, so it settles an area discrepancy rather than "
            "adding another opinion to it."
        ),
        required_evidence="Certified survey record (FMB sketch / patta extract) for the parcel",
        resolves=frozenset({"AREA_MISMATCH", "MISSING_SURVEY_RECORD", "SURVEY_MISMATCH"}),
        responsible=ResponsibleParty.SURVEYOR,
        authority="Taluk survey office / licensed surveyor",
        effort=ActionEffort.HIGH,
        produces_document=DocumentType.SURVEY_RECORD.value,
    ),
    CandidateAction(
        key="RECONCILE_NAME_VARIANT",
        title="Reconcile the owner-name variation",
        description=(
            "Provide an affidavit, gazette notification or bank record establishing that the "
            "differing name forms refer to the same person, so ownership can move from "
            "partially verified to verified."
        ),
        required_evidence="Name-discrepancy affidavit or official record linking both name forms",
        resolves=frozenset({"OWNER_NAME_VARIANT"}),
        responsible=ResponsibleParty.OWNER,
        authority="Notary / issuing authority of the supporting record",
        effort=ActionEffort.LOW,
    ),
    CandidateAction(
        key="ESTABLISH_SELLER_AUTHORITY",
        title="Establish the seller's authority to transact",
        description=(
            "Produce either a currently valid power of attorney executed by the evidenced owner, "
            "or a registered instrument transferring title to the listing party. Until one exists, "
            "no other evidence makes the sale safe."
        ),
        required_evidence="Valid, unexpired power of attorney or a registered transfer deed",
        resolves=frozenset(
            {"UNVERIFIED_SELLER_AUTHORITY", "OWNER_CONTRADICTION", "EXPIRED_POA",
             "OWNER_DECLARED_ONLY", "CHRONOLOGY_VIOLATION"}
        ),
        responsible=ResponsibleParty.LEGAL_REVIEWER,
        authority="Sub-Registrar (registration) — reviewed by a legal professional",
        effort=ActionEffort.HIGH,
        produces_document=DocumentType.POWER_OF_ATTORNEY.value,
    ),
    CandidateAction(
        key="CORROBORATE_OWNERSHIP",
        title="Add an independent document corroborating ownership",
        description=(
            "Supply a second, independent document naming the owner — a registered deed, a "
            "patta/khata extract or an encumbrance certificate — so ownership no longer rests on "
            "a single source."
        ),
        required_evidence="A second independent ownership document",
        resolves=frozenset({"SINGLE_SOURCE_OWNER"}),
        responsible=ResponsibleParty.OWNER,
        authority="Revenue office / Sub-Registrar",
        effort=ActionEffort.MEDIUM,
    ),
    CandidateAction(
        key="SUBMIT_COMPLETE_DOCUMENT",
        title="Re-submit the incomplete document in full",
        description=(
            "Upload every page of the document flagged as incomplete, including the schedule and "
            "signature pages, so no material term is missing from the evidence set."
        ),
        required_evidence="Complete, unbroken copy of the flagged document",
        resolves=frozenset({"MISSING_PAGE"}),
        responsible=ResponsibleParty.OWNER,
        authority="Original issuing office if the owner's copy is incomplete",
        effort=ActionEffort.LOW,
    ),
    CandidateAction(
        key="CERTIFIED_COPY_FOR_EDITED_DOC",
        title="Replace the flagged document with a certified copy",
        description=(
            "Obtain a certified true copy directly from the issuing authority for the document "
            "showing modification indicators. A copy issued at source removes the question "
            "without anyone having to adjudicate the original."
        ),
        required_evidence="Certified true copy from the issuing authority",
        resolves=frozenset({"SUSPICIOUS_EDIT", "DUPLICATE_DOCUMENT"}),
        responsible=ResponsibleParty.REGISTRAR,
        authority="Sub-Registrar / issuing department",
        effort=ActionEffort.HIGH,
    ),
    CandidateAction(
        key="CLEAR_TAX_ARREARS",
        title="Clear outstanding property tax and upload the receipt",
        description=(
            "Settle municipal dues and provide the current receipt, which also corroborates who "
            "the municipality treats as the holder of the property."
        ),
        required_evidence="Current property tax receipt showing nil arrears",
        resolves=frozenset({"TAX_DEFAULT", "MISSING_TAX_RECEIPT"}),
        responsible=ResponsibleParty.OWNER,
        authority="Municipal corporation / panchayat",
        effort=ActionEffort.LOW,
        produces_document=DocumentType.TAX_RECEIPT.value,
    ),
    CandidateAction(
        key="EXPLAIN_VALUATION",
        title="Document the reason for the price variance",
        description=(
            "Record why the asking price departs from the guideline value — condition, litigation "
            "history, distress sale or an outdated guideline rate — so the variance is explained "
            "rather than unexplained."
        ),
        required_evidence="Valuation note or independent valuer's report",
        resolves=frozenset({"VALUATION_OUTLIER"}),
        responsible=ResponsibleParty.BUYER,
        authority="Registered valuer (optional)",
        effort=ActionEffort.MEDIUM,
    ),
    CandidateAction(
        key="CLARIFY_TAXPAYER",
        title="Clarify why tax is paid by a different person",
        description=(
            "Provide the relationship or authorisation under which another party pays the "
            "property tax."
        ),
        required_evidence="Owner statement or authorisation covering the tax payer",
        resolves=frozenset({"TAXPAYER_MISMATCH"}),
        responsible=ResponsibleParty.OWNER,
        authority="",
        effort=ActionEffort.LOW,
    ),
    CandidateAction(
        key="RESPOND_TO_ACCESS_REQUESTS",
        title="Respond to the buyer's outstanding evidence requests",
        description=(
            "Approve or decline the open access requests. Time-limited approval is available and "
            "is recorded in the audit trail."
        ),
        required_evidence="Owner decision on each open consent request",
        resolves=frozenset({"UNANSWERED_ACCESS_REQUEST", "EVIDENCE_ACCESS_DENIED"}),
        responsible=ResponsibleParty.OWNER,
        authority="",
        effort=ActionEffort.LOW,
    ),
]

CATALOGUE_BY_KEY = {a.key: a for a in CATALOGUE}


@dataclass
class PlannedStep:
    action: CandidateAction
    priority: int
    risk_before: float
    risk_after: float
    state_before: TransactionState
    state_after: TransactionState
    resolved_rules: list[str]
    delta: float = 0.0


@dataclass
class ResolutionPlan:
    baseline_risk: float
    baseline_state: TransactionState
    steps: list[PlannedStep] = field(default_factory=list)
    final_risk: float = 0.0
    final_state: TransactionState = TransactionState.HOLD
    unaddressed: list[str] = field(default_factory=list)
    reaches_proceed: bool = False
    note: str = ""


def _simulate(ctx: RiskContext, suppressed: set[str], granted: set[str]):
    sim = copy(ctx)
    sim.suppressed = set(ctx.suppressed) | suppressed
    sim.granted = set(ctx.granted) | granted
    return compute(sim)


def plan(ctx: RiskContext, max_steps: int = 6) -> ResolutionPlan:
    """Compute the minimum-evidence path from the current state toward PROCEED."""
    from ...domain import TRANSACTION_STATE_RANK

    baseline = compute(ctx)
    result = ResolutionPlan(
        baseline_risk=baseline.overall,
        baseline_state=baseline.state,
        final_risk=baseline.overall,
        final_state=baseline.state,
    )

    open_rules = baseline.triggered_rule_ids()
    applicable = [a for a in CATALOGUE if a.resolves & open_rules]
    if not applicable:
        result.reaches_proceed = baseline.state is TransactionState.PROCEED
        result.note = (
            "No corrective evidence is outstanding. The residual score reflects the absence of "
            "official registry confirmation, which no uploaded document can remove."
            if result.reaches_proceed else
            "No catalogued action addresses the open items; refer the case to a legal reviewer."
        )
        return result

    suppressed: set[str] = set()
    granted: set[str] = set()
    current = baseline
    remaining = list(applicable)
    priority = 1

    while remaining and priority <= max_steps:
        best = None
        for action in remaining:
            trial = _simulate(ctx, suppressed | set(action.resolves), granted | set(action.grants))
            delta = current.overall - trial.overall
            state_gain = (
                TRANSACTION_STATE_RANK[current.state] - TRANSACTION_STATE_RANK[trial.state]
            )
            if delta <= 0.05 and state_gain <= 0:
                continue
            # Value per unit of effort, with a bonus for actually unblocking the state.
            value = (delta + 12.0 * state_gain) / EFFORT_COST[action.effort]
            if best is None or value > best[0]:
                best = (value, action, trial, delta)
        if best is None:
            break

        _, action, trial, delta = best
        result.steps.append(
            PlannedStep(
                action=action,
                priority=priority,
                risk_before=current.overall,
                risk_after=trial.overall,
                state_before=current.state,
                state_after=trial.state,
                resolved_rules=sorted(action.resolves & open_rules),
                delta=round(delta, 1),
            )
        )
        suppressed |= set(action.resolves)
        granted |= set(action.grants)
        current = trial
        remaining = [a for a in remaining if a.key != action.key and (a.resolves & (open_rules - suppressed))]
        priority += 1
        if current.state is TransactionState.PROCEED:
            break

    result.final_risk = current.overall
    result.final_state = current.state
    result.reaches_proceed = current.state is TransactionState.PROCEED
    result.unaddressed = sorted(current.triggered_rule_ids() - suppressed)

    if result.reaches_proceed:
        result.note = (
            f"Completing {len(result.steps)} action(s) is sufficient to move this transaction "
            f"from {baseline.state.value} to PROCEED, reducing composite risk from "
            f"{baseline.overall:.0f} to {current.overall:.0f}. No further evidence is required "
            "for the platform to release the hold."
        )
    else:
        result.note = (
            f"The catalogued actions reduce composite risk from {baseline.overall:.0f} to "
            f"{current.overall:.0f}, ending at {current.state.value}. The remaining exposure "
            "cannot be cleared by uploading further evidence and requires an authorised verifier "
            "or legal reviewer."
        )
    return result
