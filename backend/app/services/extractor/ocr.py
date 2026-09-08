"""
REAL OCR acquisition (Tesseract).

Used when EXTRACTION_MODE=OCR, or automatically as a fallback when an uploaded
document has no usable text layer (a scan or a photograph).  Word-level confidences
come from Tesseract itself, so the confidences displayed in the Claim-Evidence
Matrix are measured, not invented.
"""
from __future__ import annotations

import time
from pathlib import Path

from ...domain import ExtractionMode
from .base import DocumentText, PageText, TextAcquisition, WordBox

try:  # pragma: no cover
    import pymupdf  # type: ignore
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf  # type: ignore
    except ImportError:
        pymupdf = None  # type: ignore

try:  # pragma: no cover
    import pytesseract
    from PIL import Image
except ImportError:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore

RENDER_DPI = 200


class OcrAcquisition(TextAcquisition):
    name = "tesseract"

    def available(self) -> bool:
        if pytesseract is None:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:  # pragma: no cover - environment dependent
            return False

    def read(self, path: Path) -> DocumentText:
        started = time.perf_counter()
        pages: list[PageText] = []
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            pages.append(self._ocr_image(Image.open(path), 1))
        elif pymupdf is not None:
            import io

            with pymupdf.open(path) as doc:  # type: ignore[union-attr]
                for index, page in enumerate(doc, start=1):
                    pix = page.get_pixmap(dpi=RENDER_DPI)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    pages.append(self._ocr_image(img, index))
        return DocumentText(
            pages=pages,
            engine=f"{self.name}-{RENDER_DPI}dpi",
            mode=ExtractionMode.OCR,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    def _ocr_image(self, img, page_number: int) -> PageText:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        words: list[WordBox] = []
        confidences: list[float] = []
        lines: dict[tuple, list[str]] = {}
        for i, token in enumerate(data["text"]):
            token = (token or "").strip()
            if not token:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1.0
            if conf < 0:
                conf = 60.0
            confidences.append(conf / 100.0)
            x, y = float(data["left"][i]), float(data["top"][i])
            w, h = float(data["width"][i]), float(data["height"][i])
            words.append(WordBox(token, x, y, x + w, y + h, conf / 100.0))
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(token)
        text = "\n".join(" ".join(v) for _, v in sorted(lines.items()))
        return PageText(
            page_number=page_number,
            text=text,
            width=float(img.width),
            height=float(img.height),
            words=words,
            ocr_confidence=round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
            layout_blocks=[],
        )


def ocr_mode() -> ExtractionMode:
    return ExtractionMode.OCR
