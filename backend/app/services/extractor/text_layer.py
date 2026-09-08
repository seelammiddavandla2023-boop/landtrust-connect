"""
DEMO / text-layer acquisition.

Reads the embedded text layer of a PDF (or a plain text file) with word-level
geometry, using PyMuPDF.  This is the default mode: it requires no OCR engine, no
model download and no API key, yet it is a *real* read of a *real* uploaded file —
the pipeline is genuinely end-to-end, not mocked.
"""
from __future__ import annotations

import time
from pathlib import Path

from ...domain import ExtractionMode
from .base import DocumentText, PageText, TextAcquisition, WordBox

try:  # pragma: no cover - import guard
    import pymupdf  # type: ignore
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf  # type: ignore
    except ImportError:
        pymupdf = None  # type: ignore


class TextLayerAcquisition(TextAcquisition):
    name = "pymupdf-textlayer"

    def available(self) -> bool:
        return pymupdf is not None

    def read(self, path: Path) -> DocumentText:
        started = time.perf_counter()
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            body = path.read_text(encoding="utf-8", errors="replace")
            pages = [PageText(1, body, 595.0, 842.0, [], 1.0)]
        elif pymupdf is None:
            pages = []
        else:
            pages = self._read_pdf(path)
        return DocumentText(
            pages=pages,
            engine=self.name,
            mode=ExtractionMode.DEMO,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def _read_pdf(self, path: Path) -> list[PageText]:
        pages: list[PageText] = []
        with pymupdf.open(path) as doc:  # type: ignore[union-attr]
            for index, page in enumerate(doc, start=1):
                rect = page.rect
                words_raw = page.get_text("words")  # x0,y0,x1,y1,word,block,line,word_no
                words = [
                    WordBox(w[4], w[0], w[1], w[2], w[3], 1.0)
                    for w in words_raw
                ]
                blocks = [
                    {
                        "x": round(b[0] / rect.width, 4),
                        "y": round(b[1] / rect.height, 4),
                        "w": round((b[2] - b[0]) / rect.width, 4),
                        "h": round((b[3] - b[1]) / rect.height, 4),
                        "kind": "text",
                    }
                    for b in page.get_text("blocks")[:60]
                ]
                pages.append(
                    PageText(
                        page_number=index,
                        text=page.get_text("text"),
                        width=rect.width,
                        height=rect.height,
                        words=words,
                        # A native text layer is a lossless read; confidence is 1.0 by
                        # construction, and the pipeline reports it as such rather than
                        # inventing a plausible-looking OCR score.
                        ocr_confidence=1.0,
                        layout_blocks=blocks,
                    )
                )
        return pages
