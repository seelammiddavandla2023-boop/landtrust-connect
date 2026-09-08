"""
Transaction state control and the autonomous resolution planner.

`/simulate` answers "what would happen if…" without changing anything.
`/apply` performs the corrective step for real: it ingests the evidence the action
produces, re-runs the whole assessment, and lets the score fall on its own.  The new
risk figure is never written by this endpoint — it is whatever the engine computes
from the enlarged evidence set.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..domain import ActionStatus, AuditAction, Role, TransactionState
from ..models import Property, ResolutionAction, RiskFactor, Transaction
from ..serializers import assessment_out, resolution_out, transaction_out
from ..services import audit, pipeline
from ..services.resolution_planner.planner import CATALOGUE, CATALOGUE_BY_KEY
from ..services.resolution_planner.planner import plan as build_plan
from ..services.risk_engine.engine import BLOCKED_ACTIONS, STATE_BANNER, compute
from ..services.risk_engine.rules import RULE_CATALOGUE
from .deps import current_role, get_property

router = APIRouter(prefix="/api", tags=["control"])


# Actions completed entirely inside the platform, which therefore produce no document
# to cite. Everything else must supply evidence before a factor can be closed.
IN_PLATFORM_ACTIONS = {"RESPOND_TO_ACCESS_REQUESTS", "CLARIFY_TAXPAYER", "EXPLAIN_VALUATION"}


def _manifest() -> dict:
    path = settings.synthetic_dir / "pending" / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError:
        return {}


# ---------------------------------------------------------------------------
@router.get("/transactions")
def list_transactions(db: Session = Depends(get_db)):
    rows = db.scalars(select(Transaction)).all()
    props = {p.id: p for p in db.scalars(select(Property)).all()}
    return {
        "count": len(rows),
        "items": [
            {
                **transaction_out(t),
                "property_reference": props[t.property_id].reference if t.property_id in props
                else None,
                "scenario_label": props[t.property_id].scenario_label if t.property_id in props
                else None,
                "banner": STATE_BANNER.get(TransactionState(t.state), ""),
            }
            for t in rows
        ],
    }


@router.get("/transactions/states")
def state_reference():
    """The state machine, its thresholds and what each state blocks."""
    from ..domain import STATE_THRESHOLDS

    return {
        "thresholds": [
            {"from": lo, "to": hi, "state": state.value, "band": band.value}
            for lo, hi, state, band in STATE_THRESHOLDS
        ],
        "states": [
            {
                "state": s.value,
                "banner": STATE_BANNER.get(s, ""),
                "blocked_actions": BLOCKED_ACTIONS.get(s, []),
            }
            for s in TransactionState
        ],
        "rules": [
            {"rule_id": rule_id, "weight": weight,
             "is_mitigation": isinstance(weight, (int, float)) and weight < 0,
             "computed": isinstance(weight, str)}
            for rule_id, weight in sorted(
                RULE_CATALOGUE.items(),
                key=lambda kv: -(abs(kv[1]) if isinstance(kv[1], (int, float)) else 30.0),
            )
        ],
        "note": (
            "Scores map to states by threshold, but categorical failures override the "
            "arithmetic: if seller authority cannot be established the case escalates whatever "
            "the score says. Overrides can only make a state stricter, never more permissive."
        ),
    }


@router.post("/transactions/{property_id}/attempt/{action}")
def attempt_action(
    action: str,
    prop: Property = Depends(get_property),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    """
    Try to perform a transaction action. Blocked actions are refused with the reason.

    Demonstration only — no payment is ever processed by this prototype.
    """
    txn = db.scalars(select(Transaction).where(Transaction.property_id == prop.id)).first()
    if txn is None:
        raise HTTPException(404, "No transaction exists for this property.")
    blocked = txn.blocked_actions or []
    if action.upper() in blocked:
        audit.record(
            db, AuditAction.TRANSACTION_HELD, property_id=prop.id, transaction_id=txn.id,
            actor_role=role, actor_name=role.value, result="BLOCKED",
            summary=f"Attempt to '{action}' refused while the transaction is in state "
                    f"{txn.state}.",
            commit=True,
        )
        return {
            "allowed": False,
            "state": txn.state,
            "action": action.upper(),
            "reason": txn.state_reason,
            "banner": STATE_BANNER.get(TransactionState(txn.state), ""),
            "note": "This prototype never processes payments. The block is the demonstration.",
        }
    audit.record(
        db, AuditAction.TRANSACTION_RELEASED, property_id=prop.id, transaction_id=txn.id,
        actor_role=role, actor_name=role.value, result="ALLOWED",
        summary=f"'{action}' permitted in state {txn.state}.", commit=True,
    )
    return {
        "allowed": True,
        "state": txn.state,
        "action": action.upper(),
        "reason": txn.state_reason,
        "note": "Permitted in the current state. No payment is processed by this prototype.",
    }


# ---------------------------------------------------------------------------
@router.get("/resolution/catalogue")
def action_catalogue():
    return {
        "actions": [
            {
                "key": a.key,
                "title": a.title,
                "description": a.description,
                "required_evidence": a.required_evidence,
                "resolves": sorted(a.resolves),
                "grants": sorted(a.grants),
                "responsible_party": a.responsible.value,
                "authority_required": a.authority,
                "effort": a.effort.value,
                "produces_document": a.produces_document,
            }
            for a in CATALOGUE
        ]
    }


class SimulateRequest(BaseModel):
    property_id: str
    action_keys: list[str]


@router.post("/resolution/simulate")
def simulate(payload: SimulateRequest, db: Session = Depends(get_db)):
    """
    Counterfactual: what the score and state would be if these actions were completed.

    Nothing is written. The result comes from re-running the same scorer with the
    named rules suppressed, which is why the numbers here match what actually happens
    when the evidence arrives.
    """
    prop = db.scalars(
        select(Property).where((Property.id == payload.property_id) |
                               (Property.reference == payload.property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found.")

    unknown = [k for k in payload.action_keys if k not in CATALOGUE_BY_KEY]
    if unknown:
        raise HTTPException(400, f"Unknown action(s): {', '.join(unknown)}")

    ctx = pipeline.build_context(db, prop)
    before = compute(ctx)

    suppressed = set(ctx.suppressed)
    granted = set(ctx.granted)
    for key in payload.action_keys:
        action = CATALOGUE_BY_KEY[key]
        suppressed |= set(action.resolves)
        granted |= set(action.grants)
    ctx.suppressed = suppressed
    ctx.granted = granted
    after = compute(ctx)

    return {
        "before": {
            "overall_score": before.overall, "band": before.band.value,
            "state": before.state.value, "category_scores": before.category_scores(),
        },
        "after": {
            "overall_score": after.overall, "band": after.band.value,
            "state": after.state.value, "category_scores": after.category_scores(),
        },
        "delta": round(before.overall - after.overall, 1),
        "resolved_rules": sorted(
            before.triggered_rule_ids() - after.triggered_rule_ids()
        ),
        "actions": [
            {"key": k, "title": CATALOGUE_BY_KEY[k].title} for k in payload.action_keys
        ],
    }


class ApplyRequest(BaseModel):
    property_id: str
    action_key: str
    note: str = ""


@router.post("/resolution/apply")
def apply_action(
    payload: ApplyRequest,
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    """
    Perform a corrective step for real.

    Where the action produces a document, the corresponding evidence file is ingested
    through the ordinary pipeline — classification, extraction, provenance and all.
    Where it produces evidence the platform cannot itself verify (a notarised
    affidavit, a registrar's written confirmation), the rule is *closed* against that
    document, and the closure is recorded with the document that produced it so it is
    never an anonymous suppression.

    Either way, the resulting score is computed, not asserted.
    """
    # Applying a step changes the evidence set and can move a held transaction toward
    # PROCEED, so it is a privileged operation — not something a buyer, or an
    # unauthenticated caller defaulting to the buyer role, may perform on someone
    # else's file.
    if role not in {Role.OWNER, Role.ADMIN, Role.VERIFIER}:
        raise HTTPException(
            403,
            "Only the owner, a verifier or an administrator may apply a resolution step. "
            "Switch role using the selector in the top bar.",
        )

    prop = db.scalars(
        select(Property).where((Property.id == payload.property_id) |
                               (Property.reference == payload.property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, "Property not found.")
    action = CATALOGUE_BY_KEY.get(payload.action_key)
    if action is None:
        raise HTTPException(400, f"Unknown action '{payload.action_key}'.")

    ctx = pipeline.build_context(db, prop)
    before = compute(ctx)

    manifest = _manifest().get(prop.reference, {})
    filename = manifest.get(action.key)
    ingested = None

    if filename:
        path = settings.synthetic_dir / "pending" / prop.reference / filename
        if path.exists():
            result = pipeline.ingest_document(
                db, prop, path, filename,
                uploaded_by_role=role, actor_name=f"{role.value} (resolution step)",
            )
            ingested = result.document
            db.flush()
            audit.record(
                db, AuditAction.EVIDENCE_ADDED, property_id=prop.id, actor_role=role,
                actor_name=role.value,
                summary=f"Evidence obtained for '{action.title}': {filename}.",
                evidence_refs=[{"kind": "document", "id": ingested.id, "label": filename,
                                "page": 1}],
            )

    # Recompute the whole picture BEFORE deciding what is still outstanding. The new
    # document may clear a factor by re-derivation — a certified survey settles an
    # extent discrepancy, a lender's release settles a charge — and asking the question
    # against a stale assessment would close factors the evidence had already resolved,
    # turning derivation into suppression without anyone noticing.
    pipeline.reassess(
        db, prop, actor_role=role, actor_name=role.value,
        reason=f"Evidence supplied for: {action.title}",
    )

    # Whatever survives that recomputation may be *closed* against the new document —
    # but only when a document was actually ingested to cite, and only for actions
    # whose evidence the platform cannot verify automatically. A closure with nothing
    # to point at would be an untraceable reduction in risk, which is precisely what
    # this system exists not to do.
    after_ingest = compute(pipeline.build_context(db, prop))
    still_open = action.resolves & after_ingest.triggered_rule_ids()
    closures = list(prop.closed_rules or [])
    uncloseable: list[str] = []

    if still_open:
        if ingested is not None or action.key in IN_PLATFORM_ACTIONS:
            now = datetime.now(timezone.utc).isoformat()
            for rule_id in sorted(still_open):
                closures.append({
                    "rule_id": rule_id,
                    "action_key": action.key,
                    "document_id": ingested.id if ingested else None,
                    "document_name": (
                        ingested.filename if ingested
                        else f"{action.title} (completed in-platform)"
                    ),
                    "closed_at": now,
                    "note": payload.note or (
                        f"Closed by completing '{action.title}'. The platform cannot verify this "
                        f"evidence automatically, so the factor is closed against the document "
                        f"cited here rather than cleared by re-derivation."
                        if ingested else
                        f"Closed by completing '{action.title}' within the platform."
                    ),
                })
            prop.closed_rules = closures
        else:
            # No document, no in-platform completion, no closure. The step is recorded
            # as attempted and the factor stays on the file.
            uncloseable = sorted(still_open)
    if still_open and not uncloseable:
        audit.record(
            db, AuditAction.CONTRADICTION_RESOLVED, property_id=prop.id, actor_role=role,
            actor_name=role.value,
            summary=(
                f"Risk factor(s) {', '.join(sorted(still_open))} closed for '{action.title}' "
                + (f"against {ingested.filename}." if ingested
                   else "on completion within the platform.")
            ),
            payload={"rules": sorted(still_open), "action": action.key,
                     "document_id": ingested.id if ingested else None},
        )

    assessment = pipeline.reassess(
        db, prop, actor_role=role, actor_name=role.value,
        reason=f"Resolution step applied: {action.title}",
    )

    row = db.scalars(
        select(ResolutionAction).where(
            ResolutionAction.property_id == prop.id,
            ResolutionAction.action_key == action.key,
        )
    ).first()
    if row:
        row.status = ActionStatus.COMPLETED.value
        row.applied_at = datetime.now(timezone.utc)
    audit.record(
        db, AuditAction.RESOLUTION_ACTION_APPLIED, property_id=prop.id, actor_role=role,
        actor_name=role.value, result=assessment.state,
        summary=f"'{action.title}' completed. Composite risk {before.overall:.0f} → "
                f"{assessment.overall_score:.0f}; state {before.state.value} → "
                f"{assessment.state}.",
        commit=True,
    )

    factors = db.scalars(
        select(RiskFactor).where(RiskFactor.assessment_id == assessment.id)).all()
    remaining = db.scalars(
        select(ResolutionAction)
        .where(ResolutionAction.property_id == prop.id)
        .order_by(ResolutionAction.priority)
    ).all()

    return {
        "action": {"key": action.key, "title": action.title},
        "document": {"id": ingested.id, "filename": ingested.filename} if ingested else None,
        "before": {"overall_score": before.overall, "state": before.state.value,
                   "band": before.band.value},
        "after": {"overall_score": round(assessment.overall_score, 1),
                  "state": assessment.state, "band": assessment.band},
        "delta": round(before.overall - assessment.overall_score, 1),
        "assessment": assessment_out(assessment, list(factors)),
        "remaining_steps": [resolution_out(a) for a in remaining],
        "closed_rules": prop.closed_rules or [],
        "uncloseable_rules": uncloseable,
        "notice": (
            "No document was supplied for this step, so "
            f"{', '.join(uncloseable)} remains on the file. Upload the required evidence to "
            "clear it." if uncloseable else None
        ),
    }
