"""
Synthetic land-document generator.

Produces real, multi-page PDFs with a genuine text layer, so the Document
Intelligence pipeline processes them exactly as it would process a file a user
uploaded — classification, extraction, provenance regions and integrity checks all
run for real against these files.

Two documents are deliberately defective in ways the platform must catch:

  * a *tampered* deed, produced by writing the file, then re-opening it and
    overwriting a value in a different font and saving **incrementally**.  That
    leaves two %%EOF markers and an isolated font on the page — the two signals
    `services/extractor/quality.py` looks for.  The defect is manufactured by the
    same mechanism a real editor would use, not annotated in a side-channel.
  * an *incomplete* certificate that declares "Page 1 of 3" but ships two pages.

Ethics note: every person, survey number, document number and institution in this
corpus is invented.  No real land record is reproduced.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

from ..domain import DocumentType

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
LINE = 6.2 * mm


@dataclass
class Field:
    label: str
    value: str
    page: int = 1


@dataclass
class Para:
    text: str
    page: int = 1


@dataclass
class Tamper:
    page: int
    find: str
    replace: str
    note: str = ""


@dataclass
class DocSpec:
    filename: str
    doc_type: DocumentType
    title: str
    authority: str
    reference: str
    fields: list[Field] = field(default_factory=list)
    paragraphs: list[Para] = field(default_factory=list)
    pages: int = 2
    declared_pages: int | None = None
    issued_on: date | None = None
    valid_until: date | None = None
    tamper: Tamper | None = None
    seal_text: str = ""


# ---------------------------------------------------------------------------
def _header(c: pdfcanvas.Canvas, spec: DocSpec, page_no: int) -> float:
    y = PAGE_H - MARGIN
    c.setFillColor(colors.HexColor("#0B2545"))
    c.rect(MARGIN, y - 2 * mm, PAGE_W - 2 * MARGIN, 14 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(PAGE_W / 2, y + 4 * mm, spec.title)
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, y - 0.2 * mm, spec.authority)
    c.setFillColor(colors.HexColor("#111111"))

    y -= 12 * mm
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(colors.HexColor("#8A6D1F"))
    c.drawString(MARGIN, y, "SYNTHETIC RESEARCH DOCUMENT — LandTrust Connect prototype. "
                            "Not an official record. All particulars are fictitious.")
    c.setFillColor(colors.HexColor("#111111"))
    y -= 7 * mm

    c.setFont("Helvetica", 9)
    declared = spec.declared_pages or spec.pages
    c.drawRightString(PAGE_W - MARGIN, y, f"Page {page_no} of {declared}")
    c.drawString(MARGIN, y, f"Reference: {spec.reference}")
    y -= 4 * mm
    c.setStrokeColor(colors.HexColor("#C9D3E0"))
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    return y - 8 * mm


def _footer(c: pdfcanvas.Canvas, spec: DocSpec) -> None:
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#6B7A90"))
    parts = []
    if spec.issued_on:
        parts.append(f"Issued on: {spec.issued_on:%d-%m-%Y}")
    if spec.valid_until:
        parts.append(f"Valid until: {spec.valid_until:%d-%m-%Y}")
    c.drawString(MARGIN, MARGIN - 6 * mm, "   |   ".join(parts))
    c.drawRightString(PAGE_W - MARGIN, MARGIN - 6 * mm, spec.seal_text or "Digitally generated")
    c.setFillColor(colors.HexColor("#111111"))


def _wrap(text: str, width_chars: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if len(candidate) > width_chars:
            lines.append(current)
            current = w
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def render(spec: DocSpec, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / spec.filename
    c = pdfcanvas.Canvas(str(path), pagesize=A4)
    c.setTitle(spec.title)
    c.setAuthor(spec.authority)
    c.setSubject("Synthetic land document — LandTrust Connect research prototype")

    for page_no in range(1, spec.pages + 1):
        y = _header(c, spec, page_no)

        page_fields = [f for f in spec.fields if f.page == page_no]
        if page_fields:
            c.setFont("Helvetica-Bold", 9.5)
            c.setFillColor(colors.HexColor("#0B2545"))
            c.drawString(MARGIN, y, "PARTICULARS")
            c.setFillColor(colors.HexColor("#111111"))
            y -= LINE
            for f in page_fields:
                c.setFont("Helvetica-Bold", 9.5)
                c.drawString(MARGIN, y, f"{f.label}:")
                c.setFont("Helvetica", 9.5)
                label_w = c.stringWidth(f"{f.label}:", "Helvetica-Bold", 9.5)
                c.drawString(MARGIN + label_w + 3 * mm, y, f.value)
                y -= LINE
            y -= 3 * mm

        page_paras = [p for p in spec.paragraphs if p.page == page_no]
        for p in page_paras:
            c.setFont("Helvetica", 9.5)
            for line in _wrap(p.text, 108):
                if y < MARGIN + 22 * mm:
                    break
                c.drawString(MARGIN, y, line)
                y -= 5.2 * mm
            y -= 3 * mm

        if page_no == spec.pages:
            y = max(y, MARGIN + 26 * mm)
            c.setStrokeColor(colors.HexColor("#C9D3E0"))
            c.line(MARGIN, y, MARGIN + 55 * mm, y)
            c.setFont("Helvetica", 8.5)
            c.drawString(MARGIN, y - 5 * mm, "Authorised signatory")

        _footer(c, spec)
        c.showPage()
    c.save()

    if spec.tamper:
        _apply_tamper(path, spec.tamper)
    return path


def _apply_tamper(path: Path, tamper: Tamper) -> None:
    """
    Overwrite a value in a different font and save incrementally.

    This is how a document is actually altered after issue, and it produces the exact
    artefacts the quality checker looks for: an extra %%EOF marker (incremental save)
    and a span whose font appears nowhere else on the page.
    """
    try:
        import pymupdf
    except ImportError:  # pragma: no cover
        import fitz as pymupdf  # type: ignore

    doc = pymupdf.open(path)
    page = doc[tamper.page - 1]
    hits = page.search_for(tamper.find)
    if hits:
        rect = hits[0]
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()
        page.insert_text(
            (rect.x0, rect.y1 - 1.2),
            tamper.replace,
            fontname="tibo",          # Times-Bold: used nowhere else in these documents
            fontsize=10.5,
            color=(0.06, 0.06, 0.06),
        )
    doc.save(str(path), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    doc.close()


# ---------------------------------------------------------------------------
# Boilerplate text pools — vary the prose so the classifier is not matching on a
# single fixed template.
# ---------------------------------------------------------------------------
DEED_RECITALS = [
    "This Deed of Sale is executed on the date first written above between the Vendor of the "
    "one part and the Purchaser of the other part, whereby the Vendor doth hereby convey, "
    "transfer and assure unto the Purchaser the property described in the Schedule below, "
    "together with all rights, easements and appurtenances thereto.",
    "The Vendor declares that the schedule property is his absolute and self-acquired property, "
    "that he has good and marketable title thereto, and that the same is free from all "
    "encumbrances, attachments, court injunctions and prior agreements of sale, save as "
    "disclosed in this instrument.",
    "The Purchaser has this day paid the whole of the sale consideration and the Vendor "
    "acknowledges receipt of the same. Possession of the schedule property has been delivered "
    "to the Purchaser on the date of registration before the Sub-Registrar.",
]

EC_RECITALS = [
    "This certificate is issued on application under the Registration Act for the period stated "
    "above, following a search of the indexes maintained in this office in respect of the "
    "property described in the schedule.",
    "The particulars recorded below reflect the instruments registered in respect of the said "
    "property during the period of search. Entries relating to unregistered transactions, oral "
    "arrangements and instruments registered in other jurisdictions do not appear in this "
    "certificate.",
]

SURVEY_RECITALS = [
    "The extent recorded in this record is the measured extent as per the Field Measurement Book "
    "maintained by this office, and supersedes extents quoted in instruments of transfer where "
    "the two differ.",
    "The sub-division boundaries shown are as demarcated at the last survey. Any alteration to "
    "the sub-division requires a fresh application and re-measurement.",
]

TAX_RECITALS = [
    "This receipt evidences payment of property tax for the half-year stated and does not by "
    "itself confer or evidence title to the property assessed.",
]

POA_RECITALS = [
    "The Principal doth hereby nominate, constitute and appoint the Attorney named above to act "
    "for and on behalf of the Principal in respect of the schedule property, for the period "
    "stated and no longer.",
    "The authority conferred by this instrument ceases automatically upon the expiry date stated "
    "above, upon revocation by the Principal, or upon the death of the Principal, whichever "
    "occurs first.",
]

MORTGAGE_RECITALS = [
    "In consideration of the loan advanced, the Mortgagor hereby creates a charge over the "
    "schedule property in favour of the Mortgagee as security for repayment of the principal "
    "sum together with interest.",
    "The charge shall remain subsisting until the entire outstanding is repaid and a release is "
    "executed by the Mortgagee.",
]

NOC_RECITALS = [
    "We confirm that the loan account referenced above has been closed and that all dues "
    "outstanding to this institution in respect of the said facility have been fully repaid.",
    "We have no objection to the transfer of the schedule property and confirm that the charge "
    "created in our favour stands released. The original title documents held by us have been "
    "returned to the borrower.",
]

DECLARATION_RECITALS = [
    "I, the undersigned, declare that the particulars stated above in respect of the property "
    "listed by me are true to the best of my knowledge and belief. I understand that this "
    "declaration is a statement by me and is not, by itself, evidence of the matters stated.",
]

RECITALS = {
    DocumentType.SALE_DEED: DEED_RECITALS,
    DocumentType.ENCUMBRANCE_CERTIFICATE: EC_RECITALS,
    DocumentType.SURVEY_RECORD: SURVEY_RECITALS,
    DocumentType.TAX_RECEIPT: TAX_RECITALS,
    DocumentType.POWER_OF_ATTORNEY: POA_RECITALS,
    DocumentType.MORTGAGE_DOCUMENT: MORTGAGE_RECITALS,
    DocumentType.BANK_NOC: NOC_RECITALS,
    DocumentType.OWNER_DECLARATION: DECLARATION_RECITALS,
    DocumentType.IDENTITY_PROOF: [
        "This is a masked representation of an identity document. The platform never stores or "
        "displays a full identity number; only the last four characters are retained for "
        "reference."
    ],
}


def recitals_for(doc_type: DocumentType, page: int = 2, seed: int = 0) -> list[Para]:
    pool = RECITALS.get(doc_type, [])
    rng = random.Random(seed)
    chosen = pool if len(pool) <= 2 else rng.sample(pool, 2)
    return [Para(text, page) for text in chosen]
