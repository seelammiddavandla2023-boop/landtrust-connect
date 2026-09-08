"""
Document Intelligence orchestration.

    file → acquire text → classify → extract claims (+ provenance regions) → quality

The extractor's contract is narrow on purpose: it returns *what a document says*
and *where it says it*.  It never returns a verification status.  Deciding whether
a claim may be presented as verified is the job of the verification resolver, which
can only do so by looking across documents.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from ...domain import ClaimType, DocumentType, ExtractionMode
from .base import DocumentText, ExtractedClaim, PageText
from .classifier import Classification, classify
from .field_grammar import clean_value, patterns_for, plausible
from .quality import QualityReport, assess
from .registry import acquire


@dataclass
class DocumentAnalysis:
    text: DocumentText
    classification: Classification
    claims: list[ExtractedClaim]
    quality: QualityReport
    duration_ms: int


def _region_for(page: PageText, value: str, label: str = "") -> dict | None:
    """
    Locate the extracted value on the page and return a normalised bounding box.

    This is what makes claim-level provenance visible: clicking a claim in the UI can
    highlight the exact region of the source page the value came from.
    """
    if not page.words:
        return None
    targets = [t for t in re.split(r"\s+", value.strip()) if t][:8]
    if not targets:
        return None
    norm = [re.sub(r"[^\w./-]", "", t).lower() for t in targets]
    words = page.words
    n = len(norm)
    best: list = []
    for i in range(len(words)):
        window = words[i:i + n]
        if len(window) < n:
            break
        wtxt = [re.sub(r"[^\w./-]", "", w.text).lower() for w in window]
        hits = sum(1 for a, b in zip(wtxt, norm) if a and (a == b or b.startswith(a) or a.startswith(b)))
        if hits >= max(1, n - 1):
            best = window
            break
    if not best:
        # fall back to the first distinctive token
        for w in words:
            if re.sub(r"[^\w./-]", "", w.text).lower() == norm[0] and len(norm[0]) > 2:
                best = [w]
                break
    if not best:
        return None
    x0 = min(w.x0 for w in best)
    y0 = min(w.y0 for w in best)
    x1 = max(w.x1 for w in best)
    y1 = max(w.y1 for w in best)
    pad_x, pad_y = page.width * 0.004, page.height * 0.004
    return {
        "x": round(max(0.0, (x0 - pad_x) / page.width), 4),
        "y": round(max(0.0, (y0 - pad_y) / page.height), 4),
        "w": round(min(1.0, (x1 - x0 + 2 * pad_x) / page.width), 4),
        "h": round(min(1.0, (y1 - y0 + 2 * pad_y) / page.height), 4),
        "label": label,
    }


def _span_for(page_text: str, match_start: int, match_end: int) -> str:
    lo = max(0, match_start - 60)
    hi = min(len(page_text), match_end + 60)
    return re.sub(r"\s+", " ", page_text[lo:hi]).strip()


LABEL_ONLY = re.compile(r"^[\s]*$")


def _layout_value(page: PageText, label_tokens: list[str]) -> tuple[str, dict | None] | None:
    """
    Recover a value by geometry when the text flow does not carry it.

    A PDF whose fields have been overtyped after issue often appends the replacement
    at the end of the content stream, so "Extent / Area:" reads as a label with no
    value even though the page visibly shows one.  Reading the words positioned to
    the right of the label on the same baseline recovers it — and it is exactly the
    layout analysis the pipeline advertises, doing real work rather than decorating
    a progress bar.
    """
    if not page.words:
        return None
    norm = [re.sub(r"[^\w]", "", t).lower() for t in label_tokens if re.sub(r"[^\w]", "", t)]
    if not norm:
        return None
    words = page.words
    # Tokens carrying no alphanumerics ("/" in "Extent / Area:") are separators; the
    # anchor must align with the label's real words, and every aligned pair must match
    # — an empty token must never make the comparison pass vacuously.
    meaningful = [
        (i, re.sub(r"[^\w]", "", w.text).lower())
        for i, w in enumerate(words)
        if re.sub(r"[^\w]", "", w.text)
    ]

    anchor_indices: list[int] | None = None
    for start in range(len(meaningful)):
        window = meaningful[start:start + len(norm)]
        if len(window) < len(norm):
            break
        if all(t == n or t.startswith(n) or n.startswith(t) for (_, t), n in zip(window, norm)):
            anchor_indices = list(range(window[0][0], window[-1][0] + 1))
            break
    if not anchor_indices:
        return None
    anchor = [words[i] for i in anchor_indices]
    anchor_ids = set(anchor_indices)

    y0 = min(w.y0 for w in anchor)
    y1 = max(w.y1 for w in anchor)
    x_end = max(w.x1 for w in anchor)
    mid = (y0 + y1) / 2
    height = max(1.0, y1 - y0)

    same_line = [
        w for i, w in enumerate(words)
        if i not in anchor_ids
        and w.x0 >= x_end - 0.5
        and abs((w.y0 + w.y1) / 2 - mid) <= height * 0.7
    ]
    if not same_line:
        return None
    same_line.sort(key=lambda w: w.x0)
    # Stop at a run that looks like the next label ("District:").
    picked: list = []
    for w in same_line:
        if w.text.endswith(":") and picked:
            break
        picked.append(w)
    if not picked:
        return None
    value = clean_value(" ".join(w.text for w in picked))
    if not value:
        return None
    bx0 = min(w.x0 for w in picked)
    by0 = min(w.y0 for w in picked)
    bx1 = max(w.x1 for w in picked)
    by1 = max(w.y1 for w in picked)
    region = {
        "x": round(max(0.0, bx0 / page.width), 4),
        "y": round(max(0.0, by0 / page.height), 4),
        "w": round(min(1.0, (bx1 - bx0) / page.width), 4),
        "h": round(min(1.0, (by1 - by0) / page.height), 4),
        "label": " ".join(w.text for w in anchor),
        "recovered_by": "layout",
    }
    return value, region


def extract_claims(text: DocumentText, doc_type: str) -> list[ExtractedClaim]:
    """
    Run the field grammar over every page, keeping the best hit per claim type.

    Two passes:
      1. **Flow pass** — the label/value grammar over the page's reading order.
      2. **Layout pass** — for any field whose label is visible on the page but whose
         value the flow did not carry, recover the value by geometry.  This is not a
         nicety: a PDF edited after issue typically appends the replacement value to
         the end of the content stream, which breaks reading order while leaving the
         page visually intact.  Without this pass the platform would silently fail to
         read exactly the documents it most needs to scrutinise.
    """
    best: dict[str, ExtractedClaim] = {}
    patterns = patterns_for(doc_type)

    def offer(claim: ExtractedClaim) -> None:
        existing = best.get(claim.claim_type)
        if existing is None or claim.confidence > existing.confidence:
            best[claim.claim_type] = claim

    for page in text.pages:
        page_body = page.text
        if not page_body.strip():
            continue
        page_conf = page.ocr_confidence

        # ---- pass 1: reading-order grammar ---------------------------------
        for pattern in patterns:
            for regex in pattern.compiled():
                hit = None
                for m in regex.finditer(page_body):
                    value = clean_value(m.groupdict().get("value") or "")
                    if not plausible(pattern.claim_type, value):
                        continue
                    hit = (m, value)
                    break
                if hit is None:
                    continue
                m, value = hit
                # Confidence = grammar strength x acquisition quality, lightly
                # penalised for very long (likely over-captured) values.
                length_penalty = 0.0 if len(value) <= 60 else min(0.15, (len(value) - 60) / 400)
                offer(
                    ExtractedClaim(
                        claim_type=pattern.claim_type.value,
                        value=value,
                        page=page.page_number,
                        confidence=round(
                            max(0.05, min(0.995,
                                          pattern.base_confidence * page_conf - length_penalty)), 4
                        ),
                        source_span=_span_for(page_body, m.start(), m.end()),
                        region=_region_for(page, value, m.groupdict().get("label", "")),
                        method=text.mode.value,
                    )
                )
                break

        # ---- pass 2: geometric recovery -------------------------------------
        for pattern in patterns:
            if pattern.claim_type.value in best:
                continue
            for regex in pattern.compiled():
                label_hit = re.search(regex.pattern.split(r"\s*[:")[0], page_body, re.IGNORECASE) \
                    if r"\s*[:" in regex.pattern else None
                bare = re.search(rf"(?P<label>{pattern.labels[0]})\s*[:\-]", page_body,
                                 re.IGNORECASE)
                m = bare or label_hit
                if not m:
                    continue
                label_text = m.groupdict().get("label", m.group(0)).strip(" :-")
                recovered = _layout_value(page, re.split(r"\s+", label_text))
                if not recovered:
                    continue
                value, region = recovered
                if not plausible(pattern.claim_type, value):
                    continue
                offer(
                    ExtractedClaim(
                        claim_type=pattern.claim_type.value,
                        value=value,
                        page=page.page_number,
                        # Discounted: recovered by position rather than by the document's
                        # own reading order, which is itself a weaker signal.
                        confidence=round(
                            max(0.05, min(0.9, pattern.base_confidence * page_conf * 0.85)), 4
                        ),
                        source_span=_span_for(page_body, m.start(), m.end()),
                        region=region,
                        method=text.mode.value,
                    )
                )
                break

    claims = list(best.values())
    _augment_encumbrance(text, claims, doc_type)
    _augment_name_equivalence(text, claims, doc_type)
    return claims


NAME_EQUIVALENCE_PATTERNS = [
    r"['\"\u2018\u201c]?(?P<a>[A-Z][\w.]*(?:\s+[A-Z][\w.]*){0,3})['\"\u2019\u201d]?\s+and\s+"
    r"['\"\u2018\u201c]?(?P<b>[A-Z][\w.]*(?:\s+[A-Z][\w.]*){0,3})['\"\u2019\u201d]?\s+"
    r"refer\s+to\s+one\s+and\s+the\s+same\s+person",
    r"['\"\u2018\u201c]?(?P<a>[A-Z][\w.]*(?:\s+[A-Z][\w.]*){0,3})['\"\u2019\u201d]?\s+and\s+"
    r"['\"\u2018\u201c]?(?P<b>[A-Z][\w.]*(?:\s+[A-Z][\w.]*){0,3})['\"\u2019\u201d]?\s+"
    r"are\s+one\s+and\s+the\s+same",
]


def _augment_name_equivalence(text: DocumentText, claims: list[ExtractedClaim],
                              doc_type: str) -> None:
    """
    Read a sworn statement that two name forms denote the same person.

    A name variant across documents cannot be reconciled by asserting that one form
    is correct — both documents already say what they say. What resolves it is
    evidence about the *relationship between the two names*, which is exactly what a
    notarised affidavit provides. Extracting that relationship as its own claim lets
    the verification resolver upgrade the variant on evidence, rather than the
    platform simply agreeing to stop counting it.

    Restricted to sworn affidavits: an owner's unsworn say-so is not this.
    """
    if doc_type != DocumentType.AFFIDAVIT.value:
        return
    if any(c.claim_type == ClaimType.NAME_EQUIVALENCE.value for c in claims):
        return
    for page in text.pages:
        body = re.sub(r"\s+", " ", page.text)
        for pattern in NAME_EQUIVALENCE_PATTERNS:
            m = re.search(pattern, body, re.IGNORECASE)
            if not m:
                continue
            a, b = m.group("a").strip(), m.group("b").strip()
            if not a or not b or a.lower() == b.lower():
                continue
            claims.append(
                ExtractedClaim(
                    claim_type=ClaimType.NAME_EQUIVALENCE.value,
                    value=f"{a} || {b}",
                    page=page.page_number,
                    confidence=round(0.92 * page.ocr_confidence, 4),
                    source_span=_span_for(body, m.start(), m.end()),
                    region=_region_for(page, a),
                    method=text.mode.value,
                )
            )
            return


ENCUMBRANCE_AUTHORITIES = {
    DocumentType.ENCUMBRANCE_CERTIFICATE.value,
    DocumentType.MORTGAGE_DOCUMENT.value,
    DocumentType.BANK_NOC.value,
}


def _augment_encumbrance(text: DocumentText, claims: list[ExtractedClaim],
                         doc_type: str) -> None:
    """
    Encumbrance status is often expressed as prose ("No encumbrance was found...")
    rather than a labelled field.  Recover it so a clean EC still produces a claim —
    an absent claim would otherwise be indistinguishable from an undisclosed charge.

    Restricted to documents that *search for* encumbrances.  A sale deed's recital
    that the property is "free from all encumbrances" is the vendor's warranty, not a
    search of the register, and treating it as one would let a seller's own assurance
    stand in for the certificate that would test it.
    """
    if doc_type not in ENCUMBRANCE_AUTHORITIES:
        return
    if any(c.claim_type == ClaimType.MORTGAGE_STATUS.value for c in claims):
        return
    prose = [
        (r"no\s+encumbrances?\s+(?:were\s+)?(?:found|recorded|subsisting)", "None"),
        (r"nil\s+encumbrance", "None"),
        (r"encumbrances?\s*[:\-]?\s*nil", "None"),
        (r"free\s+from\s+all\s+encumbrances", "None"),
        (r"subsisting\s+mortgage", "Active"),
        (r"charge\s+is\s+subsisting", "Active"),
        (r"mortgage\s+(?:is\s+)?(?:currently\s+)?active", "Active"),
        (r"charge\s+(?:has\s+been\s+)?released", "Released"),
    ]
    for page in text.pages:
        for pattern, value in prose:
            m = re.search(pattern, page.text, re.IGNORECASE)
            if m:
                claims.append(
                    ExtractedClaim(
                        claim_type=ClaimType.MORTGAGE_STATUS.value,
                        value=value,
                        page=page.page_number,
                        confidence=round(0.88 * page.ocr_confidence, 4),
                        source_span=_span_for(page.text, m.start(), m.end()),
                        region=_region_for(page, m.group(0)[:40]),
                        method=text.mode.value,
                    )
                )
                return


def analyse(path: Path, mode: ExtractionMode | str | None = None,
            filename: str | None = None) -> DocumentAnalysis:
    """Full document-intelligence pass over one file."""
    started = time.perf_counter()
    text = acquire(path, mode)
    classification = classify(text.full_text, filename or path.name)
    doc_type = classification.doc_type.value if classification.confidence >= 0.25 \
        else DocumentType.UNKNOWN.value
    claims = extract_claims(text, doc_type)
    quality = assess(path, text)
    return DocumentAnalysis(
        text=text,
        classification=Classification(
            DocumentType(doc_type), classification.confidence,
            classification.signals, classification.runner_up,
        ),
        claims=claims,
        quality=quality,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
