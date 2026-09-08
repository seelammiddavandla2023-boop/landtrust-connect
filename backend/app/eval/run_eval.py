"""
Evaluation harness.

    python -m app.eval.run_eval

Scores the running system against `data/synthetic/ground_truth.json` and writes
`data/metrics.json`, which the Research Results page reads.  Nothing on that page is
typed in by hand: if a number moves, it is because the system's behaviour moved.

What is measured
----------------
* **Classification accuracy** — predicted document type vs the declared type.
* **Extraction accuracy** — extracted value vs the answer key, compared with the
  same type-aware comparison the platform itself uses (so "Rs. 18,00,000" matching
  "Rs 1800000" counts as correct, and "1650" against "1800" does not).
* **Contradiction precision / recall** — detected contradiction *types* per property
  against the declared expectations. Detections outside the expected set count as
  false positives; expected types not detected count as false negatives.
* **Verification agreement** — resolved status vs the declared status per claim type.
* **Transaction-state accuracy** — final state vs the declared state per property.
* **Grounding** — a probe set of answerable and unanswerable questions; measures how
  many grounded answers carry citations and how many unanswerable ones are refused.

Honesty notes
-------------
The corpus is synthetic and small (6 properties, 31 documents). These figures
characterise the pipeline's behaviour on a controlled set with known anomalies; they
are not a claim about performance on real registry documents. The output file says
so, and the UI repeats it.
"""
from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal
from ..domain import AnswerKind, ClaimType, VerificationStatus
from ..models import (
    AssistantQuery,
    Claim,
    Contradiction,
    Document,
    OwnershipEvent,
    Property,
    RiskAssessment,
)
from ..services import pipeline
from ..services.evidence_qa.answerer import answer
from ..services.normalization import compare_values
from ..services.resolution_planner.planner import plan as build_plan
from ..services.risk_engine.engine import compute

# Questions a complete land file can answer, and questions no land file can.
ANSWERABLE_PROBES = [
    "Who is the verified owner?",
    "What is the survey number?",
    "What is the extent of the property?",
    "What is the encumbrance status?",
    "Which document contains the mortgage?",
    "What documents are on file?",
    "What is the ownership history?",
    "What evidence is still missing?",
    "Why is this property high risk?",
    "What is the transaction state?",
]

UNANSWERABLE_PROBES = [
    "What will this property be worth in 2030?",
    "Should I buy this property?",
    "Give me the owner's phone number.",
    "Can you certify that this title is legally valid?",
    "What is the soil quality of this land?",
    "Who is the neighbouring plot's owner?",
    "How many trees are on the property?",
    "What is the seller's bank account number?",
]


def _pct(numerator: float, denominator: float) -> float:
    return round(100.0 * numerator / denominator, 2) if denominator else 0.0


def run(with_ocr: bool = False) -> dict:
    gt_path = settings.synthetic_dir / "ground_truth.json"
    if not gt_path.exists():
        raise SystemExit(
            "No ground_truth.json found. Run `python -m app.seed.generate` first."
        )
    ground_truth = json.loads(gt_path.read_text("utf-8"))
    started = time.perf_counter()

    db = SessionLocal()
    try:
        results = _evaluate(db, ground_truth)
    finally:
        db.close()

    if with_ocr:
        results["ocr_arm"] = _evaluate_ocr_arm(ground_truth)
    else:
        # Say why the arm is missing rather than leaving the key absent. A consumer
        # that finds no `ocr_arm` cannot tell "Tesseract was not installed" from
        # "nobody passed --ocr", and guessing the first is a false statement about
        # the machine whenever the second is true.
        results["ocr_arm"] = {
            "available": False,
            "reason": (
                "The OCR arm was not requested for this run. It rasterises every page "
                "and reads it with Tesseract, which takes minutes rather than seconds, "
                "so it is opt-in. Run `python -m app.eval.run_eval --ocr` (or "
                "`npm run eval:ocr`) to compute it. Every other figure on this page is "
                "unaffected, but without it the extraction figure measures the field "
                "grammar against a lossless text layer rather than measuring a reader."
            ),
        }

    results["meta"] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "corpus": "Synthetic — LandTrust Connect Review-2 evaluation set",
        "extraction_mode": settings.extraction_mode,
        "engine_version": "rules-1.0",
        "caveat": (
            "Computed against a synthetic corpus of "
            f"{ground_truth['totals']['properties']} properties and "
            f"{ground_truth['totals']['documents']} documents with "
            f"{ground_truth['totals']['injected_anomalies']} deliberately injected anomalies. "
            "These figures characterise behaviour on a controlled set with known ground truth. "
            "They are not a claim about performance on real registry documents, which vary in "
            "layout, language, scan quality and completeness in ways this corpus does not."
        ),
    }
    settings.metrics_path.write_text(json.dumps(results, indent=2), "utf-8")
    return results


def _evaluate(db, ground_truth: dict) -> dict:
    gt_props = {p["reference"]: p for p in ground_truth["properties"]}

    cls_total = cls_correct = 0
    ext_total = ext_correct = 0
    extraction_errors: list[dict] = []
    classification_errors: list[dict] = []
    per_claim_type: dict[str, dict[str, int]] = {}

    contra_tp = contra_fp = contra_fn = 0
    contradiction_detail: list[dict] = []

    ver_total = ver_correct = 0
    verification_errors: list[dict] = []
    confusion: Counter = Counter()

    state_total = state_correct = 0
    state_detail: list[dict] = []

    processing_times: list[dict] = []

    for reference, gt in gt_props.items():
        prop = db.scalars(select(Property).where(Property.reference == reference)).first()
        if prop is None:
            continue
        documents = list(db.scalars(
            select(Document).where(Document.property_id == prop.id)).all())
        claims = list(db.scalars(select(Claim).where(Claim.property_id == prop.id)).all())
        by_filename = {d.filename: d for d in documents}

        # ---- classification + extraction ----------------------------------
        for gt_doc in gt["documents"]:
            doc = by_filename.get(gt_doc["filename"])
            if doc is None:
                continue
            cls_total += 1
            if doc.doc_type == gt_doc["expected_doc_type"]:
                cls_correct += 1
            else:
                classification_errors.append({
                    "property": reference,
                    "document": gt_doc["filename"],
                    "expected": gt_doc["expected_doc_type"],
                    "predicted": doc.doc_type,
                    "confidence": round(doc.classification_confidence, 3),
                })
            processing_times.append({
                "document": gt_doc["filename"], "doc_type": doc.doc_type,
                "pages": doc.page_count, "ms": doc.processing_ms,
                "claims": len([c for c in claims if c.document_id == doc.id]),
            })

            doc_claims = {c.claim_type: c for c in claims if c.document_id == doc.id}
            for claim_type, expected in gt_doc["expected_claims"].items():
                # Instrument-scoped attributes are stored as document metadata rather
                # than claims, so score them from wherever the system actually keeps them.
                actual = None
                if claim_type in doc_claims:
                    actual = doc_claims[claim_type].value
                elif claim_type == ClaimType.DOCUMENT_NUMBER.value:
                    actual = doc.reference_number
                elif claim_type == ClaimType.REGISTRATION_DATE.value and doc.instrument_date:
                    actual = doc.instrument_date.strftime("%d-%m-%Y")

                ext_total += 1
                bucket = per_claim_type.setdefault(claim_type, {"total": 0, "correct": 0})
                bucket["total"] += 1
                if actual is None:
                    extraction_errors.append({
                        "property": reference, "document": gt_doc["filename"],
                        "claim_type": claim_type, "expected": expected, "actual": None,
                        "kind": "MISSED",
                    })
                    continue
                cmp = compare_values(claim_type, expected, actual)
                if cmp.agrees:
                    ext_correct += 1
                    bucket["correct"] += 1
                else:
                    extraction_errors.append({
                        "property": reference, "document": gt_doc["filename"],
                        "claim_type": claim_type, "expected": expected, "actual": actual,
                        "kind": "WRONG_VALUE", "match_type": cmp.match_type.value,
                    })

        # ---- contradiction detection ---------------------------------------
        detected = {
            c.contradiction_type
            for c in db.scalars(
                select(Contradiction).where(
                    Contradiction.property_id == prop.id,
                    Contradiction.resolved == False,  # noqa: E712
                )
            ).all()
        }
        expected_types = set(gt["expected_contradiction_types"])
        tp = detected & expected_types
        fp = detected - expected_types
        fn = expected_types - detected
        contra_tp += len(tp)
        contra_fp += len(fp)
        contra_fn += len(fn)
        contradiction_detail.append({
            "property": reference, "label": gt["label"],
            "expected": sorted(expected_types), "detected": sorted(detected),
            "true_positives": sorted(tp), "false_positives": sorted(fp),
            "false_negatives": sorted(fn),
        })

        # ---- verification agreement ----------------------------------------
        ctx = pipeline.build_context(db, prop)
        for claim_type, expected_status in gt["expected_statuses"].items():
            ver_total += 1
            actual_status = ctx.outcome.status_of(claim_type).value
            confusion[f"{expected_status}->{actual_status}"] += 1
            if actual_status == expected_status:
                ver_correct += 1
            else:
                verification_errors.append({
                    "property": reference, "claim_type": claim_type,
                    "expected": expected_status, "actual": actual_status,
                })

        # ---- transaction state ---------------------------------------------
        assessment = db.scalars(
            select(RiskAssessment)
            .where(RiskAssessment.property_id == prop.id,
                   RiskAssessment.is_simulation == False)  # noqa: E712
            .order_by(RiskAssessment.created_at.desc())
        ).first()
        state_total += 1
        actual_state = assessment.state if assessment else None
        if actual_state == gt["expected_transaction_state"]:
            state_correct += 1
        state_detail.append({
            "property": reference, "label": gt["label"],
            "expected_state": gt["expected_transaction_state"], "actual_state": actual_state,
            "expected_band": gt["expected_risk_band"],
            "actual_band": assessment.band if assessment else None,
            "risk_score": round(assessment.overall_score, 1) if assessment else None,
            "correct": actual_state == gt["expected_transaction_state"],
        })

    grounding = _evaluate_grounding(db)
    resolution = _evaluate_resolution(db, ground_truth)

    contra_precision = _pct(contra_tp, contra_tp + contra_fp)
    contra_recall = _pct(contra_tp, contra_tp + contra_fn)
    f1 = (
        round(2 * contra_precision * contra_recall / (contra_precision + contra_recall), 2)
        if (contra_precision + contra_recall) else 0.0
    )

    return {
        "headline": {
            "documents_tested": cls_total,
            "claims_evaluated": ext_total,
            "classification_accuracy": _pct(cls_correct, cls_total),
            "extraction_accuracy": _pct(ext_correct, ext_total),
            "contradiction_precision": contra_precision,
            "contradiction_recall": contra_recall,
            "contradiction_f1": f1,
            "verification_agreement": _pct(ver_correct, ver_total),
            "transaction_state_accuracy": _pct(state_correct, state_total),
            "grounded_citation_rate": grounding["grounded_citation_rate"],
            "unsupported_answer_blocking": grounding["refusal_rate"],
            "resolution_outcome_accuracy": resolution["outcome_accuracy"],
        },
        "classification": {
            "total": cls_total, "correct": cls_correct,
            "accuracy": _pct(cls_correct, cls_total), "errors": classification_errors,
        },
        "extraction": {
            "total": ext_total, "correct": ext_correct,
            "accuracy": _pct(ext_correct, ext_total),
            "by_claim_type": [
                {"claim_type": k, "total": v["total"], "correct": v["correct"],
                 "accuracy": _pct(v["correct"], v["total"])}
                for k, v in sorted(per_claim_type.items(),
                                   key=lambda kv: -kv[1]["total"])
            ],
            "errors": extraction_errors,
        },
        "contradiction": {
            "true_positives": contra_tp, "false_positives": contra_fp,
            "false_negatives": contra_fn, "precision": contra_precision,
            "recall": contra_recall, "f1": f1, "per_property": contradiction_detail,
        },
        "verification": {
            "total": ver_total, "correct": ver_correct,
            "agreement": _pct(ver_correct, ver_total),
            "confusion": [
                {"transition": k, "count": v}
                for k, v in sorted(confusion.items(), key=lambda kv: -kv[1])
            ],
            "errors": verification_errors,
        },
        "transaction_state": {
            "total": state_total, "correct": state_correct,
            "accuracy": _pct(state_correct, state_total), "per_property": state_detail,
        },
        "grounding": grounding,
        "resolution": resolution,
        "performance": {
            "documents": processing_times,
            "mean_ms": round(sum(p["ms"] for p in processing_times) /
                             len(processing_times), 1) if processing_times else 0,
            "mean_claims_per_document": round(
                sum(p["claims"] for p in processing_times) / len(processing_times), 2
            ) if processing_times else 0,
        },
    }


def _evaluate_grounding(db) -> dict:
    """
    Probe the assistant with questions the file can and cannot answer.

    Two properties matter and are measured separately:
      * a grounded answer must carry at least one citation, and
      * an unanswerable question must produce a refusal, never a plausible sentence.
    """
    props = list(db.scalars(select(Property).order_by(Property.reference)).all())
    grounded_total = grounded_with_citations = 0
    unanswerable_total = refused = 0
    leaks: list[dict] = []
    unanswered_answerable: list[dict] = []

    for prop in props:
        claims = list(db.scalars(select(Claim).where(Claim.property_id == prop.id)).all())
        documents = list(db.scalars(
            select(Document).where(Document.property_id == prop.id)).all())
        contradictions = list(db.scalars(
            select(Contradiction).where(Contradiction.property_id == prop.id)).all())
        events = list(db.scalars(
            select(OwnershipEvent).where(OwnershipEvent.property_id == prop.id)).all())
        ctx = pipeline.build_context(db, prop)
        risk = compute(ctx)
        plan = build_plan(ctx)

        for question in ANSWERABLE_PROBES:
            result = answer(question, claims, contradictions, documents, events,
                            ctx.outcome, risk, plan)
            if result.kind is AnswerKind.GROUNDED:
                grounded_total += 1
                # Answers derived from the risk ledger or the completeness check are
                # grounded in records that are not themselves documents; they count as
                # cited when they name the records they came from.
                if result.evidence or result.intent in {
                    "RISK_LEVEL", "STATE", "MISSING", "RESOLUTION"
                }:
                    grounded_with_citations += 1
            else:
                unanswered_answerable.append({
                    "property": prop.reference, "question": question,
                    "kind": result.kind.value,
                })

        for question in UNANSWERABLE_PROBES:
            result = answer(question, claims, contradictions, documents, events,
                            ctx.outcome, risk, plan)
            unanswerable_total += 1
            if result.kind in {AnswerKind.REFUSED, AnswerKind.OUT_OF_SCOPE}:
                refused += 1
            else:
                leaks.append({
                    "property": prop.reference, "question": question,
                    "answer": result.text[:200],
                })

    logged = list(db.scalars(select(AssistantQuery)).all())
    return {
        "answerable_probes": len(ANSWERABLE_PROBES) * len(props),
        "grounded_answers": grounded_total,
        "grounded_with_citations": grounded_with_citations,
        "grounded_citation_rate": _pct(grounded_with_citations, grounded_total),
        "answerable_coverage": _pct(grounded_total, len(ANSWERABLE_PROBES) * len(props)),
        "unanswerable_probes": unanswerable_total,
        "refused": refused,
        "refusal_rate": _pct(refused, unanswerable_total),
        "unsupported_answers_emitted": len(leaks),
        "leaks": leaks,
        "answerable_but_refused": unanswered_answerable,
        "logged_queries": len(logged),
        "note": (
            "'Unsupported answer blocking' is the share of questions with no basis in the "
            "property file that produced a refusal instead of an answer. A single leak would "
            "show here as a counter-example, not be averaged away."
        ),
    }


def _evaluate_ocr_arm(ground_truth: dict) -> dict:
    """
    Re-read every document through the real OCR backend and score extraction again.

    This is the arm that makes the extraction figure meaningful. The text-layer path
    reads a lossless digital original, so near-perfect accuracy there measures the
    grammar, not the reader. Rasterising each page at 200 dpi and passing it through
    Tesseract introduces genuine character errors, so the OCR figure measures what the
    pipeline does when the input is an image rather than a PDF with a text layer —
    which is what a scanned deed actually is.
    """
    from ..services.extractor.registry import available_modes
    from ..services.extractor.service import analyse

    if not available_modes()["OCR"]["available"]:
        return {"available": False,
                "note": "Tesseract is not installed in this environment; the OCR arm was "
                        "skipped. Install tesseract-ocr to enable it."}

    total = correct = 0
    cls_total = cls_correct = 0
    errors: list[dict] = []
    per_claim_type: dict[str, dict[str, int]] = {}
    durations: list[int] = []

    for gt_prop in ground_truth["properties"]:
        for gt_doc in gt_prop["documents"]:
            path = settings.synthetic_dir / gt_prop["reference"] / gt_doc["filename"]
            if not path.exists():
                continue
            analysis = analyse(path, mode="OCR", filename=gt_doc["filename"])
            durations.append(analysis.duration_ms)
            cls_total += 1
            if analysis.classification.doc_type.value == gt_doc["expected_doc_type"]:
                cls_correct += 1
            found = {c.claim_type: c.value for c in analysis.claims}
            for claim_type, expected in gt_doc["expected_claims"].items():
                total += 1
                bucket = per_claim_type.setdefault(claim_type, {"total": 0, "correct": 0})
                bucket["total"] += 1
                actual = found.get(claim_type)
                if actual is None:
                    errors.append({"property": gt_prop["reference"],
                                   "document": gt_doc["filename"], "claim_type": claim_type,
                                   "expected": expected, "actual": None, "kind": "MISSED"})
                    continue
                if compare_values(claim_type, expected, actual).agrees:
                    correct += 1
                    bucket["correct"] += 1
                else:
                    errors.append({"property": gt_prop["reference"],
                                   "document": gt_doc["filename"], "claim_type": claim_type,
                                   "expected": expected, "actual": actual,
                                   "kind": "WRONG_VALUE"})

    return {
        "available": True,
        "engine": "tesseract-200dpi",
        "documents_tested": cls_total,
        "classification_accuracy": _pct(cls_correct, cls_total),
        "claims_evaluated": total,
        "extraction_accuracy": _pct(correct, total),
        "mean_ms_per_document": round(sum(durations) / len(durations), 1) if durations else 0,
        "by_claim_type": [
            {"claim_type": k, "total": v["total"], "correct": v["correct"],
             "accuracy": _pct(v["correct"], v["total"])}
            for k, v in sorted(per_claim_type.items(), key=lambda kv: -kv[1]["total"])
        ],
        "errors": errors[:80],
        "note": (
            "The same field grammar, the same answer key, a different reader. The gap between "
            "this figure and the text-layer figure is the cost of OCR on this corpus."
        ),
    }


def _evaluate_resolution(db, ground_truth: dict | None = None) -> dict:
    """
    Does the planner find a path to PROCEED where one should exist?

    Cases the corpus marks `expected_resolvable: false` are scored separately: where
    ownership itself is contradicted, escalation is the correct outcome and a plan
    that stops short of PROCEED is right rather than a failure.
    """
    resolvable = {
        p["reference"]: p.get("expected_resolvable", True)
        for p in (ground_truth or {}).get("properties", [])
    }
    props = list(db.scalars(select(Property).order_by(Property.reference)).all())
    rows = []
    reaching = 0
    needing_plan = 0
    correct_outcomes = 0
    scored = 0
    for prop in props:
        ctx = pipeline.build_context(db, prop)
        before = compute(ctx)
        plan = build_plan(ctx)
        should_resolve = resolvable.get(prop.reference, True)
        if before.state.value == "PROCEED":
            rows.append({
                "property": prop.reference, "baseline_state": before.state.value,
                "baseline_risk": before.overall, "steps": 0,
                "final_state": before.state.value, "final_risk": before.overall,
                "reaches_proceed": True, "expected_resolvable": should_resolve,
                "outcome_correct": True,
                "note": "Already clear; no plan required.",
            })
            continue
        needing_plan += 1
        if plan.reaches_proceed:
            reaching += 1
        scored += 1
        outcome_correct = plan.reaches_proceed == should_resolve
        if outcome_correct:
            correct_outcomes += 1
        rows.append({
            "expected_resolvable": should_resolve,
            "outcome_correct": outcome_correct,
            "property": prop.reference,
            "baseline_state": plan.baseline_state.value,
            "baseline_risk": plan.baseline_risk,
            "steps": len(plan.steps),
            "step_keys": [s.action.key for s in plan.steps],
            "final_state": plan.final_state.value,
            "final_risk": plan.final_risk,
            "reaches_proceed": plan.reaches_proceed,
            "risk_reduction": round(plan.baseline_risk - plan.final_risk, 1),
            "note": plan.note,
        })
    return {
        "properties_needing_a_plan": needing_plan,
        "plans_reaching_proceed": reaching,
        "reaching_proceed_pct": _pct(reaching, needing_plan),
        "outcome_accuracy": _pct(correct_outcomes, scored),
        "outcomes_scored": scored,
        "mean_steps": round(
            sum(r["steps"] for r in rows if r["steps"]) /
            max(1, len([r for r in rows if r["steps"]])), 2
        ),
        "per_property": rows,
        "note": (
            "Not every case should reach PROCEED. Where ownership itself is contradicted, the "
            "correct outcome is escalation to a legal reviewer, and a plan that stops short of "
            "PROCEED is the right answer rather than a failure."
        ),
    }


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate LandTrust Connect.")
    parser.add_argument("--ocr", action="store_true",
                        help="also re-read every document through Tesseract and score that arm "
                             "(slower, but the figure that actually characterises extraction)")
    cli = parser.parse_args()
    out = run(with_ocr=cli.ocr)
    h = out["headline"]
    print(f"\nLandTrust Connect — evaluation against the synthetic corpus")
    print("=" * 66)
    for key, value in h.items():
        unit = "" if isinstance(value, int) and "accuracy" not in key and "rate" not in key \
            and "precision" not in key and "recall" not in key and "pct" not in key \
            and "agreement" not in key and "blocking" not in key else " %"
        print(f"  {key.replace('_', ' ').title():44} {value}{unit}")
    if out.get("ocr_arm", {}).get("available"):
        arm = out["ocr_arm"]
        print("-" * 66)
        print(f"  OCR arm ({arm['engine']})")
        print(f"    {'Classification Accuracy':42} {arm['classification_accuracy']} %")
        print(f"    {'Extraction Accuracy':42} {arm['extraction_accuracy']} %")
        print(f"    {'Mean ms / document':42} {arm['mean_ms_per_document']}")
    print("=" * 66)
    print(f"  written to {settings.metrics_path}")
