"""
Extraction-mode registry.

    DEMO  → text-layer acquisition (PyMuPDF).  No OCR engine, no model, no API key.
    OCR   → Tesseract at 200 dpi with per-word confidences.
    LLM   → reserved for LLM-assisted extraction; falls back with a clear reason
            when no key is configured (build brief §26: must work without keys).

Selection is per-call, so a single deployment can process one document with the
text layer and the next with OCR — which is exactly what the evaluation harness does
to compare the two backends.
"""
from __future__ import annotations

from pathlib import Path

from ...config import settings
from ...domain import ExtractionMode
from .base import DocumentText, TextAcquisition
from .ocr import OcrAcquisition
from .text_layer import TextLayerAcquisition

_TEXT_LAYER = TextLayerAcquisition()
_OCR = OcrAcquisition()


def available_modes() -> dict[str, dict]:
    return {
        ExtractionMode.DEMO.value: {
            "engine": _TEXT_LAYER.name,
            "available": _TEXT_LAYER.available(),
            "description": "Embedded text-layer extraction. Deterministic, no external "
                           "dependencies. Default mode for the Review-2 demonstration.",
        },
        ExtractionMode.OCR.value: {
            "engine": _OCR.name,
            "available": _OCR.available(),
            "description": "Tesseract OCR over rasterised pages. Used automatically when a "
                           "document has no text layer (scans and photographs).",
        },
        ExtractionMode.LLM.value: {
            "engine": settings.llm_model or "not configured",
            "available": bool(settings.llm_api_key),
            "description": "Reserved for LLM-assisted extraction of unstructured deeds. "
                           "Configure LLM_API_KEY and LLM_MODEL to enable (Review-3).",
        },
    }


def _resolve(mode: ExtractionMode | str | None) -> ExtractionMode:
    if mode is None:
        mode = settings.extraction_mode
    if isinstance(mode, str):
        try:
            mode = ExtractionMode(mode.upper())
        except ValueError:
            mode = ExtractionMode.DEMO
    return mode


def acquire(path: Path, mode: ExtractionMode | str | None = None) -> DocumentText:
    """
    Acquire page text for a file under the requested mode, with graceful degradation:

      * LLM requested but unconfigured  → DEMO
      * OCR requested but unavailable   → DEMO
      * DEMO produced no usable text    → OCR (the file is a scan)
    """
    resolved = _resolve(mode)
    strategy: TextAcquisition = _TEXT_LAYER

    if resolved is ExtractionMode.OCR and _OCR.available():
        strategy = _OCR
    elif resolved is ExtractionMode.LLM:
        strategy = _TEXT_LAYER  # LLM assists structuring, not acquisition

    text = strategy.read(path)
    if not text.full_text.strip() and strategy is _TEXT_LAYER and _OCR.available():
        text = _OCR.read(path)
    return text


# ---------------------------------------------------------------------------
# LLM integration seam (Review-3)
# ---------------------------------------------------------------------------
class LLMExtractorAdapter:
    """
    Integration interface for an LLM-assisted extractor.

    Implement `structure()` against any provider.  The rest of the system is
    unaffected because the return type is the same list[ExtractedClaim] the
    deterministic grammar produces, and verification remains a separate stage —
    an LLM is never allowed to declare a claim verified.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def structure(self, text: str, doc_type: str) -> list:  # pragma: no cover - Review-3
        if not self.configured:
            raise RuntimeError(
                "LLM extraction is not configured. Set LLM_API_KEY and LLM_MODEL, or use "
                "EXTRACTION_MODE=DEMO / OCR, both of which run with no external services."
            )
        raise NotImplementedError(
            "Review-3 scope: bind this method to a provider SDK. Return list[ExtractedClaim] "
            "with page numbers and character spans so claim-level provenance is preserved."
        )
