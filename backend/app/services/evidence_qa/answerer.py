"""
Evidence-grounded property assistant.

The contract, from the research proposal: **every answer is either supported by
retrieved evidence records or it is a refusal.**  There is no third option and no
"best guess".  Concretely:

  * The answerer receives only records retrieved from this property's file.
  * Every sentence it produces is generated from those records, and the records are
    returned alongside as citations (document, page, confidence).
  * If retrieval is empty, the answerer returns `AnswerKind.REFUSED` with
    "Insufficient evidence available to answer this question."
  * Questions that no land-evidence file can answer — legal advice, price
    forecasts, requests for personal contact details, requests to certify title —
    return `AnswerKind.OUT_OF_SCOPE` with a reason, rather than an evasive answer.

This module is deliberately deterministic.  `llm_adapter.py` documents how an LLM
can be introduced *without* weakening the guarantee: the LLM may only rephrase text
derived from retrieved records, and the citation set is computed before generation.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...domain import DISCLAIMER, AnswerKind, ClaimType, VerificationStatus
from .retriever import EvidenceRef, Retrieval, label_for, refs_from_claims, retrieve

REFUSAL = "Insufficient evidence available to answer this question."

OUT_OF_SCOPE_MESSAGES = {
    "LEGAL_ADVICE": (
        "This is a legal question, and LandTrust Connect is a decision-support system rather "
        "than a legal adviser. What the platform can tell you is which claims the uploaded "
        "evidence supports and which it does not; whether to transact on that basis is a "
        "decision for you and a qualified advocate."
    ),
    "VALUATION_FORECAST": (
        "The platform does not forecast property values. It reasons about ownership evidence, "
        "encumbrances and transaction risk, and it has no market model to answer this from."
    ),
    "PERSONAL_CONTACT": (
        "Personal contact and identity details are not disclosed through the assistant. Contact "
        "with the owner runs through the property relay, and identity documents are never "
        "released to a counterparty, with or without consent."
    ),
    "OTHER_PARCEL": (
        "This assistant answers only about the property whose file is open. It holds no evidence "
        "about neighbouring or adjacent parcels, and answering from this property's documents "
        "would be answering a different question from the one you asked."
    ),
    "NOT_IN_FILE": (
        "That detail is not something a land-evidence file records. This platform reasons about "
        "ownership documents, extents, encumbrances and transaction risk; it holds no data on "
        "banking, site conditions, amenities or construction."
    ),
    "OFFICIAL_CERTIFICATION": (
        "The platform cannot certify title. Its statuses describe agreement between the documents "
        "uploaded here; they are not confirmation from the land registry, and no result produced "
        "here should be presented as an official verification."
    ),
}


@dataclass
class Answer:
    kind: AnswerKind
    text: str
    confidence: float
    intent: str
    evidence: list[EvidenceRef] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    backend: str = "deterministic-grounded"

    def dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "answer": self.text,
            "confidence": round(self.confidence, 4),
            "intent": self.intent,
            "evidence": [e.dict() for e in self.evidence],
            "caveats": self.caveats,
            "backend": self.backend,
            "disclaimer": DISCLAIMER,
        }


STATUS_PHRASE = {
    VerificationStatus.VERIFIED: "verified against independent or authoritative evidence",
    VerificationStatus.PARTIALLY_VERIFIED: "only partially verified",
    VerificationStatus.CONFLICTING: "in conflict between sources",
    VerificationStatus.PENDING: "not evidenced at all",
    VerificationStatus.EXPIRED: "supported only by expired evidence",
    VerificationStatus.OWNER_PROVIDED: "stated by the owner with no supporting document",
    VerificationStatus.UNVERIFIED: "unverified",
}


def answer(
    question: str,
    claims: list,
    contradictions: list,
    documents: list,
    events: list,
    outcome,
    risk=None,
    plan=None,
) -> Answer:
    r = retrieve(question, claims, contradictions, documents, events)

    if r.out_of_scope:
        return Answer(
            AnswerKind.OUT_OF_SCOPE,
            OUT_OF_SCOPE_MESSAGES.get(r.out_of_scope, REFUSAL),
            1.0,
            r.intent,
        )

    handler = {
        "OWNER": _owner,
        "RISK_WHY": _risk_why,
        "RISK_LEVEL": _risk_level,
        "STATE": _state,
        "MORTGAGE_SOURCE": _mortgage_source,
        "CONFLICT_WHY": _conflict_why,
        "MISSING": _missing,
        "RESOLUTION": _resolution,
        "DOCUMENTS": _documents,
        "HISTORY": _history,
        "VERIFICATION": _claim_value,
        "CLAIM_VALUE": _claim_value,
        "UNKNOWN": _claim_value,
    }.get(r.intent, _claim_value)

    result = handler(r, claims, contradictions, documents, events, outcome, risk, plan)
    return result or _refuse(r.intent)


def _refuse(intent: str, extra: str = "") -> Answer:
    return Answer(
        AnswerKind.REFUSED,
        (REFUSAL + (" " + extra if extra else "")),
        0.0,
        intent,
        caveats=[
            "The assistant answers only from claims extracted from documents on this property's "
            "file. When no such record exists it refuses rather than inferring."
        ],
    )


# ---------------------------------------------------------------------------
def _owner(r, claims, contradictions, documents, events, outcome, risk, plan):
    group = outcome.per_type.get(ClaimType.OWNER_NAME.value)
    owner_claims = [c for c in claims if c.claim_type == ClaimType.OWNER_NAME.value
                    and not c.superseded]
    if not owner_claims or group is None:
        return _refuse("OWNER", "No document on file states an owner for this property.")

    refs = refs_from_claims(owner_claims, documents)
    status = group.status
    values = sorted({c.value for c in owner_claims})

    if status is VerificationStatus.CONFLICTING:
        text = (
            "Ownership cannot be established from the evidence on file. The documents name "
            + " and ".join(f"'{v}'" for v in values)
            + ", and those references have not been reconciled. Until they are, no party is shown "
              "as the verified owner."
        )
        confidence = 0.9
    elif status is VerificationStatus.VERIFIED:
        text = (
            f"The current evidence identifies {values[0]} as the supported owner. {group.explanation}"
        )
        confidence = min(0.99, group.combined_authority or 0.9)
    else:
        text = (
            f"The evidence points to {values[0]} as the owner, but this is "
            f"{STATUS_PHRASE[status]}. {group.explanation}"
        )
        confidence = 0.65

    return Answer(
        AnswerKind.GROUNDED, text, confidence, "OWNER", refs,
        caveats=["Ownership here means agreement between uploaded documents, not confirmation "
                 "from the land registry."],
    )


def _risk_why(r, claims, contradictions, documents, events, outcome, risk, plan):
    if risk is None:
        return _refuse("RISK_WHY", "No risk assessment has been computed for this property yet.")
    drivers = [h for h in risk.hits if not h.is_mitigation and h.weight > 0]
    drivers.sort(key=lambda h: h.weight, reverse=True)
    if not drivers:
        return Answer(
            AnswerKind.GROUNDED,
            f"No risk factors are currently triggered beyond the baseline. The composite score is "
            f"{risk.overall:.0f}/100 and the transaction state is {risk.state.value}.",
            0.9, "RISK_WHY",
        )
    top = drivers[:4]
    lines = [
        f"This property scores {risk.overall:.0f}/100 ({risk.band.value} risk) and the transaction "
        f"state is {risk.state.value}. The score is driven by:"
    ]
    for h in top:
        lines.append(f"• {h.title} (+{h.weight:.0f}, {h.category.value.lower()}): {h.explanation}")
    refs: list[EvidenceRef] = []
    docs_by_id = {d.id: d for d in documents}
    for h in top:
        for ref in h.evidence_refs[:2]:
            doc = docs_by_id.get(ref.get("document_id") or ref.get("id"))
            refs.append(
                EvidenceRef("risk_factor", doc.id if doc else None,
                            doc.filename if doc else ref.get("label", h.rule_id),
                            ref.get("page"), 1.0, h.title)
            )
    return Answer(AnswerKind.GROUNDED, "\n".join(lines), 0.92, "RISK_WHY", refs[:6])


def _risk_level(r, claims, contradictions, documents, events, outcome, risk, plan):
    if risk is None:
        return _refuse("RISK_LEVEL")
    parts = [f"{v.label}: {v.score:.0f}/100" for v in risk.categories.values() if v.score > 0]
    text = (
        f"The composite transaction risk is {risk.overall:.0f}/100, band {risk.band.value}, "
        f"state {risk.state.value}. Category breakdown — " + "; ".join(parts) + "."
    )
    return Answer(AnswerKind.GROUNDED, text, 0.95, "RISK_LEVEL")


def _state(r, claims, contradictions, documents, events, outcome, risk, plan):
    if risk is None:
        return _refuse("STATE")
    text = f"The transaction state is {risk.state.value}. {risk.state_reason}"
    if risk.state.value in {"HOLD", "ESCALATE", "REJECT"}:
        text += (
            " Progression to agreement or payment is disabled while this state holds. "
            "The Resolution Plan tab lists the evidence that would release it."
        )
    return Answer(AnswerKind.GROUNDED, text, 0.95, "STATE")


def _mortgage_source(r, claims, contradictions, documents, events, outcome, risk, plan):
    relevant = [c for c in claims
                if c.claim_type in {ClaimType.MORTGAGE_STATUS.value,
                                    ClaimType.MORTGAGE_AMOUNT.value,
                                    ClaimType.MORTGAGE_LENDER.value}
                and not c.superseded]
    if not relevant:
        return _refuse("MORTGAGE_SOURCE",
                       "No document on file records an encumbrance or mortgage entry.")
    docs_by_id = {d.id: d for d in documents}
    lines = ["The encumbrance information comes from:"]
    for c in relevant:
        doc = docs_by_id.get(c.document_id)
        lines.append(
            f"• {label_for(c.claim_type)} = '{c.value}' — {doc.filename if doc else 'owner declaration'}, "
            f"page {c.source_page}, extraction confidence {c.confidence:.0%}."
        )
    return Answer(AnswerKind.GROUNDED, "\n".join(lines), 0.93, "MORTGAGE_SOURCE",
                  refs_from_claims(relevant, documents))


def _conflict_why(r, claims, contradictions, documents, events, outcome, risk, plan):
    targets = r.target_claim_types
    pool = [c for c in contradictions if not c.resolved]
    if targets:
        scoped = [c for c in pool if c.claim_type in targets]
        pool = scoped or pool
    if not pool:
        return _refuse("CONFLICT_WHY", "No unresolved contradiction is recorded for this property.")
    c = max(pool, key=lambda x: {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1,
                                 "INFO": 0}.get(x.severity, 0))
    text = (
        f"{label_for(c.claim_type)} is marked {c.severity.lower()}-severity "
        f"{c.contradiction_type.replace('_', ' ').lower()}. {c.explanation}"
    )
    refs = [
        EvidenceRef("contradiction", None, c.left_source, None, 1.0, c.left_value),
        EvidenceRef("contradiction", None, c.right_source, None, 1.0, c.right_value),
    ]
    return Answer(AnswerKind.GROUNDED, text, 0.94, "CONFLICT_WHY",
                  [e for e in refs if e.document_name])


def _missing(r, claims, contradictions, documents, events, outcome, risk, plan):
    gaps = [c for c in contradictions
            if c.contradiction_type == "MISSING_EVIDENCE" and not c.resolved]
    pending = outcome.pending_types
    if not gaps and not pending:
        return Answer(
            AnswerKind.GROUNDED,
            "No required document or core claim is missing from this file. Every core claim has "
            "at least one supporting document.",
            0.9, "MISSING",
        )
    lines = ["The following evidence is not on file:"]
    for g in gaps:
        lines.append(f"• {g.explanation}")
    for p in pending:
        if not any(p in g.left_value for g in gaps):
            lines.append(f"• No value is evidenced for {label_for(p)}.")
    return Answer(AnswerKind.GROUNDED, "\n".join(lines), 0.9, "MISSING")


def _resolution(r, claims, contradictions, documents, events, outcome, risk, plan):
    if plan is None or not plan.steps:
        if risk is not None and risk.state.value == "PROCEED":
            return Answer(
                AnswerKind.GROUNDED,
                "No corrective action is outstanding — the evidence on file supports progression.",
                0.9, "RESOLUTION",
            )
        return _refuse("RESOLUTION", "No resolution plan has been generated for this property.")
    lines = [
        f"Current risk {plan.baseline_risk:.0f}/100 ({plan.baseline_state.value}). "
        f"The minimum evidence path is:"
    ]
    for step in plan.steps:
        lines.append(
            f"{step.priority}. {step.action.title} — required: {step.action.required_evidence}. "
            f"Responsible: {step.action.responsible.value.title()}. "
            f"Expected risk {step.risk_before:.0f} → {step.risk_after:.0f} "
            f"({step.state_before.value} → {step.state_after.value})."
        )
    lines.append(plan.note)
    return Answer(AnswerKind.GROUNDED, "\n".join(lines), 0.9, "RESOLUTION")


def _documents(r, claims, contradictions, documents, events, outcome, risk, plan):
    live = [d for d in documents if not d.is_pending_evidence]
    if not live:
        return _refuse("DOCUMENTS", "No documents have been uploaded for this property.")
    lines = [f"{len(live)} document(s) are on file:"]
    for d in live:
        extra = []
        if d.is_expired:
            extra.append("expired")
        if d.integrity_flags:
            extra.append(f"{len(d.integrity_flags)} integrity indicator(s)")
        suffix = f" — {', '.join(extra)}" if extra else ""
        lines.append(
            f"• {d.filename}: classified as {d.doc_type.replace('_', ' ').title()} "
            f"({d.classification_confidence:.0%} confidence), {d.page_count} page(s){suffix}."
        )
    refs = [EvidenceRef("document", d.id, d.filename, 1, d.classification_confidence)
            for d in live]
    return Answer(AnswerKind.GROUNDED, "\n".join(lines), 0.95, "DOCUMENTS", refs)


def _history(r, claims, contradictions, documents, events, outcome, risk, plan):
    if not events:
        return _refuse("HISTORY",
                       "No ownership events could be derived from the documents on file.")
    docs_by_id = {d.id: d for d in documents}
    ordered = sorted(events, key=lambda e: e.occurred_on)
    lines = ["Ownership history derived from the evidence on file:"]
    refs: list[EvidenceRef] = []
    for e in ordered:
        doc = docs_by_id.get(e.evidence_document_id)
        detail = e.description or (f"{e.from_party} → {e.to_party}" if e.from_party else e.to_party)
        lines.append(
            f"• {e.occurred_on:%d-%m-%Y} — {e.event_type.replace('_', ' ').title()}: {detail}"
            + (f" (source: {doc.filename} p{e.evidence_page})" if doc else "")
        )
        if doc:
            refs.append(EvidenceRef("event", doc.id, doc.filename, e.evidence_page,
                                    e.confidence, detail or ""))
    return Answer(AnswerKind.GROUNDED, "\n".join(lines), 0.88, "HISTORY", refs[:6])


def _claim_value(r, claims, contradictions, documents, events, outcome, risk, plan):
    targets = r.target_claim_types
    if not targets:
        return _refuse(
            r.intent,
            "The question does not map onto a land detail this file holds. Try asking about the "
            "owner, survey number, extent, registration date, encumbrance status, tax status, "
            "risk, or missing evidence.",
        )
    claim_type = targets[0]
    group = outcome.per_type.get(claim_type)
    matching = [c for c in claims if c.claim_type == claim_type and not c.superseded]
    if not matching or group is None:
        return _refuse(
            r.intent,
            f"No document on file asserts a value for {label_for(claim_type)}.",
        )
    values = sorted({c.value for c in matching})
    status = group.status
    if status is VerificationStatus.CONFLICTING:
        text = (
            f"{label_for(claim_type)} is in conflict: the documents state "
            + " and ".join(f"'{v}'" for v in values)
            + f". {group.explanation}"
        )
        confidence = 0.85
    else:
        text = (
            f"{label_for(claim_type)} is recorded as '{values[0]}', which is "
            f"{STATUS_PHRASE[status]}. {group.explanation}"
        )
        confidence = max(c.confidence for c in matching)
    return Answer(AnswerKind.GROUNDED, text, confidence, r.intent,
                  refs_from_claims(matching, documents))


SUGGESTED_QUESTIONS = [
    "Who is the verified owner?",
    "Why is this property high risk?",
    "Which document contains the mortgage?",
    "Why is the area marked conflicting?",
    "What evidence is still missing?",
    "What is the ownership history?",
    "How do I resolve the open issues?",
    "What documents are on file?",
]
