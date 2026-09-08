"""Document Intelligence — upload, pipeline telemetry, page rendering."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..domain import DOCUMENT_TYPE_LABELS, DocumentType, PIPELINE_ORDER, Role
from ..models import Document, Property, RiskAssessment, RiskFactor
from ..serializers import assessment_out, claim_out, document_out
from ..services import pipeline
from ..services.extractor.registry import available_modes
from .deps import current_role, get_property, granted_items

router = APIRouter(prefix="/api/documents", tags=["documents"])

ACCEPTED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt"}
MAX_BYTES = 25 * 1024 * 1024


@router.get("/modes")
def extraction_modes():
    """Which extraction backends this deployment can actually use right now."""
    return {
        "modes": available_modes(),
        "pipeline_stages": [s.value for s in PIPELINE_ORDER],
        "supported_categories": [
            {"value": d.value, "label": DOCUMENT_TYPE_LABELS[d]}
            for d in DocumentType if d is not DocumentType.UNKNOWN
        ],
        "accepted_extensions": sorted(ACCEPTED),
        "max_bytes": MAX_BYTES,
    }


@router.post("/upload")
async def upload(
    property_id: str = Form(...),
    file: UploadFile = File(...),
    mode: str | None = Form(default=None),
    db: Session = Depends(get_db),
    role: Role = Depends(current_role),
):
    """
    Upload a real file and run the real pipeline over it.

    Returns the stage-by-stage telemetry, the classified document, the extracted
    claims and the recomputed risk assessment — so the UI can animate the pipeline
    with what actually happened rather than a scripted sequence.
    """
    prop = db.scalars(
        select(Property).where((Property.id == property_id) |
                               (Property.reference == property_id))
    ).first()
    if prop is None:
        raise HTTPException(404, f"Property '{property_id}' not found.")

    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in ACCEPTED:
        raise HTTPException(
            415,
            f"'{suffix or 'no extension'}' is not an accepted format. "
            f"Accepted: {', '.join(sorted(ACCEPTED))}.",
        )
    payload = await file.read()
    if not payload:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(payload) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds the {MAX_BYTES // (1024 * 1024)} MB limit.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)

    try:
        result = pipeline.ingest_document(
            db, prop, tmp_path, file.filename or tmp_path.name, mode=mode,
            uploaded_by_role=role, actor_name=role.value,
        )
        db.flush()
        assessment = pipeline.reassess(
            db, prop, actor_role=role, actor_name=role.value,
            reason=f"New evidence uploaded: {file.filename}",
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    granted = granted_items(db, prop, role)
    factors = db.scalars(
        select(RiskFactor).where(RiskFactor.assessment_id == assessment.id)).all()

    stages = [
        {"stage": s.stage, "status": s.status, "detail": s.detail, "duration_ms": s.duration_ms}
        for s in result.stages
    ]
    stages.append({
        "stage": "CROSS_DOCUMENT_VALIDATION", "status": "OK",
        "detail": "Claims compared against every other document on file; verification statuses "
                  "re-derived from the combined evidence.",
        "duration_ms": 0,
    })
    stages.append({
        "stage": "RISK_UPDATE", "status": "OK",
        "detail": f"Composite risk {assessment.overall_score:.0f}/100 ({assessment.band}); "
                  f"transaction state {assessment.state}.",
        "duration_ms": 0,
    })
    stages.append({"stage": "COMPLETE", "status": "OK", "detail": "Pipeline finished.",
                   "duration_ms": 0})

    return {
        "document": document_out(result.document),
        "claims": [claim_out(c, role, granted, result.document) for c in result.claims],
        "stages": stages,
        "assessment": assessment_out(assessment, list(factors)),
    }


@router.get("/{document_id}/file")
def download(document_id: str, db: Session = Depends(get_db)):
    """Serve the stored PDF so the document viewer can render the real page."""
    doc = db.get(Document, document_id)
    if doc is None or not doc.storage_path:
        raise HTTPException(404, "Document file not available.")
    path = Path(doc.storage_path)
    if not path.exists():
        raise HTTPException(404, "Stored file is missing from the workspace.")
    return FileResponse(path, media_type=doc.mime_type, filename=doc.filename)


@router.get("/{document_id}/pipeline")
def replay_pipeline(document_id: str, db: Session = Depends(get_db)):
    """
    Stream this document's processing stages as server-sent events.

    Used by the Document Intelligence screen to replay how a seeded document was
    processed, with the same stage list a live upload produces.
    """
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found.")

    detail = {
        "UPLOADING": f"Received {doc.filename} ({doc.size_bytes / 1024:.0f} KB).",
        "FILE_VALIDATION": f"{doc.mime_type}, {doc.page_count} page(s), checksum "
                           f"{(doc.checksum or '')[:12]}.",
        "CLASSIFICATION": f"{doc.doc_type} at {doc.classification_confidence:.0%} confidence.",
        "OCR": f"{doc.ocr_engine} in {doc.extraction_mode} mode.",
        "LAYOUT_ANALYSIS": f"{sum(len(p.layout_blocks or []) for p in doc.pages)} layout blocks.",
        "CLAIM_EXTRACTION": f"{len(doc.claims)} claim(s) extracted.",
        "EVIDENCE_LINKING": f"{sum(1 for c in doc.claims if c.source_region)} claim(s) anchored "
                            "to a page region.",
        "CROSS_DOCUMENT_VALIDATION": "Compared against every other document on this property.",
        "RISK_UPDATE": "Composite risk and transaction state recomputed.",
        "COMPLETE": f"Processed in {doc.processing_ms} ms.",
    }

    def events():
        for index, stage in enumerate(PIPELINE_ORDER):
            payload = {
                "stage": stage.value,
                "index": index,
                "total": len(PIPELINE_ORDER),
                "status": "OK",
                "detail": detail.get(stage.value, ""),
            }
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
