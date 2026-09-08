"""
Authenticity, completeness and tamper *indicators*.

Responsible-AI note (build brief §33): nothing in this module concludes that a
document is forged.  Each check emits an **indicator** with a plain-language
explanation, and downstream the risk engine treats indicators as evidence to be
reviewed by an authorised person — never as a legal finding.

The checks are computed from the file itself:
  * incremental-save count       — number of %%EOF markers in the PDF byte stream
  * metadata modification        — /ModDate later than /CreationDate
  * font discontinuity           — a value rendered in a different font/size from its label
  * page completeness            — "Page m of n" declarations vs actual page count
  * validity window              — declared expiry against the current date
  * text quality                 — mean acquisition confidence
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from .base import DocumentText

try:  # pragma: no cover
    import pymupdf  # type: ignore
except ImportError:  # pragma: no cover
    try:
        import fitz as pymupdf  # type: ignore
    except ImportError:
        pymupdf = None  # type: ignore


@dataclass
class Indicator:
    code: str
    label: str
    detail: str
    severity: str  # LOW | MEDIUM | HIGH
    page: int | None = None

    def dict(self) -> dict:
        return asdict(self)


# A font contributing no more than this many characters to the whole document, while
# appearing in a page body, is treated as an isolated insertion.
ISOLATED_FONT_MAX_CHARS = 40

PAGE_DECL = re.compile(r"page\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
VALID_UNTIL = re.compile(
    r"(?:valid\s+(?:until|up\s*to|till)|expiry\s+date|date\s+of\s+expiry)\s*[:\-]?\s*"
    r"([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
    re.IGNORECASE,
)
ISSUED_ON = re.compile(
    r"(?:issued\s+on|date\s+of\s+issue|issue\s+date)\s*[:\-]?\s*"
    r"([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
    re.IGNORECASE,
)


def _parse_dmy(text: str) -> date | None:
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _incremental_saves(path: Path) -> int:
    try:
        raw = path.read_bytes()
    except OSError:
        return 0
    return max(0, raw.count(b"%%EOF") - 1)


def _metadata_flags(path: Path) -> list[Indicator]:
    out: list[Indicator] = []
    if pymupdf is None or path.suffix.lower() != ".pdf":
        return out
    try:
        with pymupdf.open(path) as doc:  # type: ignore[union-attr]
            meta = doc.metadata or {}
    except Exception:
        return out
    created = (meta.get("creationDate") or "").strip()
    modified = (meta.get("modDate") or "").strip()
    if created and modified and modified > created:
        out.append(
            Indicator(
                "METADATA_MODIFIED",
                "Modified after creation",
                f"The PDF records a modification timestamp ({modified[2:16]}) later than its "
                f"creation timestamp ({created[2:16]}). Legitimate re-saves also produce this, "
                "so it is a prompt for review rather than a finding of tampering.",
                "MEDIUM",
            )
        )
    producer = (meta.get("producer") or "") + " " + (meta.get("creator") or "")
    if re.search(r"ghostscript|itext|pdftk|photoshop|gimp", producer, re.IGNORECASE):
        out.append(
            Indicator(
                "REWRITER_TOOL",
                "Rewritten by a general-purpose tool",
                f"The producer string ('{producer.strip()}') indicates the file passed through a "
                "generic PDF/image rewriter rather than an issuing authority's system.",
                "LOW",
            )
        )
    return out


def _font_discontinuity(path: Path) -> list[Indicator]:
    """
    Flag a font that appears in the body of the document for only a handful of
    characters and nowhere else in the file.

    Overtyping a single field inserts a short run of text in whatever font the editing
    tool used. That produces a font name with a tiny document-wide character count,
    sitting in the body of a page — a signature that ordinary typesetting does not
    produce, because a legitimate document reuses its own fonts throughout.

    Keying on the font *name* across the whole document (rather than per page, or per
    name+size) is what keeps this from firing on headers, footers and signature lines,
    which reuse the document's existing font family.
    """
    out: list[Indicator] = []
    if pymupdf is None or path.suffix.lower() != ".pdf":
        return out
    try:
        with pymupdf.open(path) as doc:  # type: ignore[union-attr]
            doc_font_chars: dict[str, int] = {}
            body_occurrence: dict[str, tuple[int, str, float]] = {}
            body_chars_total = 0

            for index, page in enumerate(doc, start=1):
                rect = page.rect
                for block in page.get_text("dict").get("blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = (span.get("text") or "").strip()
                            if not text:
                                continue
                            font = span.get("font", "?")
                            doc_font_chars[font] = doc_font_chars.get(font, 0) + len(text)
                            y = span.get("bbox", (0, 0, 0, 0))[1]
                            if rect.height * 0.16 <= y <= rect.height * 0.92:
                                body_chars_total += len(text)
                                body_occurrence.setdefault(
                                    font, (index, text, span.get("size", 0.0))
                                )

            if len(doc_font_chars) < 2 or body_chars_total < 120:
                return out

            for font, chars in sorted(doc_font_chars.items(), key=lambda kv: kv[1]):
                if chars > ISOLATED_FONT_MAX_CHARS or font not in body_occurrence:
                    continue
                page_no, sample, size = body_occurrence[font]
                out.append(
                    Indicator(
                        "FONT_DISCONTINUITY",
                        "Isolated font in document body",
                        f"On page {page_no} the text '{sample[:40]}' is set in {font} "
                        f"{size:.0f}pt. That font accounts for {chars} characters in the entire "
                        "file and is used nowhere else — the signature of a single field having "
                        "been overtyped after the document was produced. This is an indicator "
                        "requiring examination of the original, not a finding of forgery.",
                        "HIGH",
                        page=page_no,
                    )
                )
                break
    except Exception:
        return out
    return out


@dataclass
class QualityReport:
    indicators: list[Indicator]
    quality_score: float
    issued_on: date | None
    valid_until: date | None
    is_expired: bool
    declared_pages: int | None
    checksum: str

    def as_json(self) -> list[dict]:
        return [i.dict() for i in self.indicators]


def assess(path: Path, text: DocumentText, today: date | None = None) -> QualityReport:
    today = today or date.today()
    indicators: list[Indicator] = []
    full = text.full_text

    # --- completeness --------------------------------------------------------
    declared_pages = None
    m = PAGE_DECL.search(full)
    if m:
        declared_pages = int(m.group(2))
        actual = len(text.pages)
        if declared_pages > actual:
            indicators.append(
                Indicator(
                    "MISSING_PAGE",
                    "Incomplete document",
                    f"The document declares {declared_pages} pages but only {actual} "
                    f"{'page is' if actual == 1 else 'pages are'} present in the uploaded file.",
                    "HIGH",
                )
            )

    # --- validity window -----------------------------------------------------
    issued_on = valid_until = None
    m = ISSUED_ON.search(full)
    if m:
        issued_on = _parse_dmy(m.group(1))
    m = VALID_UNTIL.search(full)
    if m:
        valid_until = _parse_dmy(m.group(1))
    is_expired = bool(valid_until and valid_until < today)
    if is_expired:
        indicators.append(
            Indicator(
                "EXPIRED_DOCUMENT",
                "Validity period has ended",
                f"The document states it is valid until {valid_until:%d-%m-%Y}, which has passed. "
                "Claims resting solely on this document are marked EXPIRED rather than verified.",
                "HIGH",
            )
        )

    # --- integrity -----------------------------------------------------------
    saves = _incremental_saves(path)
    if saves >= 1:
        indicators.append(
            Indicator(
                "INCREMENTAL_SAVE",
                f"{saves} incremental save{'s' if saves > 1 else ''} after original write",
                f"The PDF byte stream contains {saves + 1} end-of-file markers, meaning content "
                "was appended or revised after the file was first written. Requires review of "
                "which fields changed.",
                "HIGH" if saves > 1 else "MEDIUM",
            )
        )
    indicators.extend(_metadata_flags(path))
    indicators.extend(_font_discontinuity(path))

    # --- acquisition quality -------------------------------------------------
    mean_conf = text.mean_confidence
    if mean_conf < 0.75:
        indicators.append(
            Indicator(
                "LOW_TEXT_QUALITY",
                "Low text-acquisition confidence",
                f"Mean text confidence is {mean_conf:.0%}. Extracted values from this document "
                "carry reduced confidence and should be corroborated.",
                "MEDIUM",
            )
        )
    if not full.strip():
        indicators.append(
            Indicator(
                "NO_TEXT_RECOVERED",
                "No readable text",
                "No text could be recovered from this file, so it contributes no claims.",
                "HIGH",
            )
        )

    weights = {"LOW": 0.05, "MEDIUM": 0.15, "HIGH": 0.3}
    penalty = sum(weights.get(i.severity, 0.1) for i in indicators)
    quality = round(max(0.0, min(1.0, (0.6 + 0.4 * mean_conf) - penalty)), 3)

    return QualityReport(
        indicators=indicators,
        quality_score=quality,
        issued_on=issued_on,
        valid_until=valid_until,
        is_expired=is_expired,
        declared_pages=declared_pages,
        checksum=file_checksum(path),
    )
