"""
Render the synthetic corpus to disk and write the ground-truth answer key.

    python -m app.seed.generate

Outputs
-------
data/synthetic/<property_reference>/*.pdf   the documents the pipeline will process
data/synthetic/pending/<ref>/*.pdf          evidence held back for the resolution demo
data/synthetic/ground_truth.json            the answer key the evaluation harness scores against
data/synthetic/pending/manifest.json        which held-back file each resolution action produces
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..config import settings
from .documents import render
from .scenarios import all_scenarios, resolution_evidence


def generate(out_dir: Path | None = None) -> dict:
    out_dir = out_dir or settings.synthetic_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    pending_root = out_dir / "pending"
    pending_root.mkdir(parents=True, exist_ok=True)

    ground_truth: dict = {
        "generated_for": "LandTrust Connect — Review-2 evaluation corpus",
        "note": (
            "All persons, survey numbers, document numbers and institutions are fictitious. "
            "This file is the answer key: app/eval/run_eval.py scores the pipeline against it."
        ),
        "properties": [],
    }
    manifest: dict[str, dict] = {}
    doc_count = 0
    claim_count = 0

    for plan in all_scenarios():
        prop_dir = out_dir / plan.reference
        prop_dir.mkdir(parents=True, exist_ok=True)
        documents = []
        for doc_plan in plan.documents:
            path = render(doc_plan.spec, prop_dir)
            doc_count += 1
            claim_count += len(doc_plan.expected_claims)
            documents.append(
                {
                    "filename": doc_plan.spec.filename,
                    "path": str(path.relative_to(out_dir)),
                    "expected_doc_type": doc_plan.spec.doc_type.value,
                    "expected_claims": doc_plan.expected_claims,
                    "anomalies": doc_plan.anomalies,
                    "pages": doc_plan.spec.pages,
                    "declared_pages": doc_plan.spec.declared_pages,
                    "tampered": doc_plan.spec.tamper is not None,
                }
            )

        pending = []
        evidence = resolution_evidence(plan.key)
        if evidence:
            pdir = pending_root / plan.reference
            pdir.mkdir(parents=True, exist_ok=True)
            for doc_plan in evidence:
                path = render(doc_plan.spec, pdir)
                pending.append(
                    {
                        "filename": doc_plan.spec.filename,
                        "path": str(path.relative_to(out_dir)),
                        "expected_doc_type": doc_plan.spec.doc_type.value,
                        "expected_claims": doc_plan.expected_claims,
                    }
                )
            manifest[plan.reference] = {
                "OBTAIN_CURRENT_EC": "Encumbrance_Certificate_2026_current.pdf",
                "OBTAIN_BANK_NOC": "Bank_NOC_2026.pdf",
                "OBTAIN_CERTIFIED_SURVEY": "Survey_Record_2026_certified.pdf",
                "RECONCILE_NAME_VARIANT": "Name_Discrepancy_Affidavit_2026.pdf",
            }

        ground_truth["properties"].append(
            {
                "reference": plan.reference,
                "scenario_key": plan.key,
                "label": plan.label,
                "summary": plan.summary,
                "demo_note": plan.demo_note,
                "listed_owner_name": plan.listed_owner_name,
                "survey_number": plan.survey_number,
                "documents": documents,
                "pending_evidence": pending,
                "expected_transaction_state": plan.expected_state.value,
                "expected_risk_band": plan.expected_risk_band,
                "expected_statuses": {k: v.value for k, v in plan.expected_statuses.items()},
                "expected_contradiction_types": plan.expected_contradiction_types,
                "injected_anomalies": plan.injected_anomalies,
                "expected_resolvable": plan.expected_resolvable,
            }
        )

    ground_truth["totals"] = {
        "properties": len(ground_truth["properties"]),
        "documents": doc_count,
        "expected_claims": claim_count,
        "injected_anomalies": sum(
            len(p["injected_anomalies"]) for p in ground_truth["properties"]
        ),
    }

    (out_dir / "ground_truth.json").write_text(json.dumps(ground_truth, indent=2), "utf-8")
    (pending_root / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")
    return ground_truth


if __name__ == "__main__":  # pragma: no cover
    gt = generate()
    print(
        f"Generated {gt['totals']['documents']} documents across "
        f"{gt['totals']['properties']} properties "
        f"({gt['totals']['expected_claims']} expected claims, "
        f"{gt['totals']['injected_anomalies']} injected anomalies) in {settings.synthetic_dir}"
    )
