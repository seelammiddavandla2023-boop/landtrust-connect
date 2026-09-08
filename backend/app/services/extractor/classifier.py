"""
Document classification.

A transparent weighted-keyword classifier over the acquired text.  It is
deliberately explainable: every classification stores the signals that fired, so a
reviewer can see *why* a file was called an Encumbrance Certificate.  A learned
classifier can be swapped in behind `classify()` without touching callers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ...domain import DocumentType

# (regex, weight) per document type.  Weights are small integers; the final
# confidence is a softmax-free normalised share, which keeps it interpretable.
SIGNATURES: dict[DocumentType, list[tuple[str, float]]] = {
    DocumentType.SALE_DEED: [
        (r"\bsale\s+deed\b", 6), (r"\bdeed\s+of\s+sale\b", 6), (r"\bvendor\b", 3),
        (r"\bpurchaser\b", 3), (r"\bsale\s+consideration\b", 3),
        (r"\bsub[- ]registrar\b", 2), (r"\bconveyance\b", 3),
        (r"\bhereby\s+convey", 3),
    ],
    DocumentType.ENCUMBRANCE_CERTIFICATE: [
        (r"\bencumbrance\s+certificate\b", 7), (r"\bform\s+no\.?\s*1[56]\b", 3),
        (r"\bsearch\s+period\b", 3), (r"\bencumbrances?\s+found\b", 3),
        (r"\bnil\s+encumbrance\b", 2), (r"\bregistering\s+officer\b", 2),
    ],
    DocumentType.SURVEY_RECORD: [
        (r"\bsurvey\s+record\b", 6), (r"\bfield\s+measurement\s+book\b", 5),
        (r"\bFMB\b", 3), (r"\bpatta\b", 3), (r"\bchitta\b", 3), (r"\badangal\b", 3),
        (r"\bsurveyor\b", 2), (r"\bsub[- ]division\b", 2), (r"\bresurvey\b", 2),
    ],
    DocumentType.TAX_RECEIPT: [
        (r"\bproperty\s+tax\b", 6), (r"\btax\s+receipt\b", 6), (r"\bassessee\b", 3),
        (r"\bmunicipal(?:ity)?\b", 2), (r"\bcorporation\s+of\b", 2),
        (r"\bhalf[- ]year\b", 2), (r"\breceipt\s+no\b", 2),
    ],
    DocumentType.IDENTITY_PROOF: [
        (r"\baadhaar\b", 6), (r"\bunique\s+identification\b", 4), (r"\bpan\s+card\b", 5),
        (r"\bpassport\b", 4), (r"\bdate\s+of\s+birth\b", 2), (r"\bidentity\s+proof\b", 5),
    ],
    DocumentType.POWER_OF_ATTORNEY: [
        (r"\bpower\s+of\s+attorney\b", 7), (r"\battorney\s+holder\b", 4),
        (r"\bprincipal\b", 2), (r"\bhereby\s+appoint\b", 3), (r"\bGPA\b", 3),
        (r"\bspecial\s+power\b", 3),
    ],
    DocumentType.MORTGAGE_DOCUMENT: [
        (r"\bmortgage\s+deed\b", 7), (r"\bmortgagee\b", 4), (r"\bmortgagor\b", 4),
        (r"\bhypothecation\b", 3), (r"\bloan\s+account\b", 3),
        (r"\bequitable\s+mortgage\b", 4),
    ],
    DocumentType.BANK_NOC: [
        (r"\bno\s+objection\s+certificate\b", 7), (r"\bNOC\b", 4),
        (r"\bloan\s+closure\b", 4), (r"\bcharge\s+released\b", 4),
        (r"\brelease\s+of\s+mortgage\b", 5), (r"\bfully\s+repaid\b", 3),
    ],
    DocumentType.OWNER_DECLARATION: [
        (r"\bowner\s+self[- ]declaration\b", 9), (r"\bself[- ]declaration\b", 6),
        (r"\bdeclared\s+by\s+owner\b", 5), (r"\bowner\s+declaration\b", 6),
        (r"\bself[- ]declared\b", 4),
    ],
    DocumentType.AFFIDAVIT: [
        (r"\baffidavit\b", 8), (r"\bsolemnly\s+affirm\b", 6),
        (r"\bdeponent\b", 5), (r"\bnotary\s+public\b", 5),
        (r"\bsworn\s+before\b", 5), (r"\bone\s+and\s+the\s+same\s+person\b", 6),
    ],
}


@dataclass
class Classification:
    doc_type: DocumentType
    confidence: float
    signals: dict[str, float]
    runner_up: DocumentType | None = None


def classify(text: str, filename: str = "") -> Classification:
    haystack = f"{filename}\n{text}".lower()
    scores: dict[DocumentType, float] = {}
    signals: dict[str, float] = {}

    for doc_type, rules in SIGNATURES.items():
        total = 0.0
        for pattern, weight in rules:
            hits = len(re.findall(pattern, haystack, re.IGNORECASE))
            if hits:
                # Diminishing returns: repeated boilerplate should not dominate.
                contribution = weight * (1 + min(hits - 1, 3) * 0.25)
                total += contribution
                signals[f"{doc_type.value}:{pattern}"] = round(contribution, 2)
        if total:
            scores[doc_type] = total

    if not scores:
        return Classification(DocumentType.UNKNOWN, 0.0, {})

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    total_score = sum(scores.values())
    # Confidence blends share-of-evidence with absolute evidence strength, so a
    # document with one weak keyword does not report 100 % confidence.
    share = best_score / total_score
    strength = min(1.0, best_score / 12.0)
    confidence = round(min(0.99, 0.45 * share + 0.55 * strength + 0.15 * (share > 0.6)), 4)
    return Classification(
        doc_type=best,
        confidence=confidence,
        signals=dict(sorted(signals.items(), key=lambda kv: kv[1], reverse=True)[:12]),
        runner_up=ranked[1][0] if len(ranked) > 1 else None,
    )
