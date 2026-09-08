"""
LLM integration seam for the evidence assistant (Review-3).

The point of this file is to record *how* an LLM may be introduced without losing
the grounding guarantee, because "we added an LLM and it started answering things
the documents do not say" is precisely the failure the research proposal identifies
in existing chatbots.

Contract for any implementation
-------------------------------
1. Retrieval happens first and is not delegated to the model.  The model receives
   only the records `retriever.retrieve()` returned.
2. If retrieval is empty, the model is never called.  The refusal is returned
   directly, so a missing-evidence case cannot become a fluent hallucination.
3. The citation set is computed *before* generation from the retrieved records, and
   is attached to the response unchanged.  The model cannot add or remove citations.
4. The model's only permitted job is to phrase, in the user's language, an answer
   whose factual content is already present in the supplied records.  Anything it
   adds is a defect.
5. `verify()` runs after generation: every numeric value and proper noun in the
   generated text must appear in the retrieved records, otherwise the deterministic
   answer is returned instead.  Post-hoc verification is cheap and catches the
   failure mode that matters.
"""
from __future__ import annotations

from dataclasses import dataclass

from ...config import settings
from .answerer import Answer


@dataclass
class GroundingViolation:
    token: str
    reason: str


class LLMAnswerAdapter:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def rephrase(self, deterministic: Answer, records: list[dict]) -> Answer:  # pragma: no cover
        if not self.configured:
            return deterministic
        raise NotImplementedError(
            "Review-3 scope. Implement against a provider SDK, then run verify() on the output "
            "and fall back to `deterministic` on any grounding violation."
        )

    @staticmethod
    def verify(text: str, records: list[dict]) -> list[GroundingViolation]:
        """
        Check that every number and capitalised token in `text` occurs in the retrieved
        records.  Used as a hard gate on generated output.
        """
        import re

        corpus = " ".join(str(v) for r in records for v in r.values()).lower()
        violations: list[GroundingViolation] = []
        for token in re.findall(r"\b\d[\d,./-]*\b", text):
            if token.lower().strip(".,") not in corpus:
                violations.append(GroundingViolation(token, "numeric value not present in evidence"))
        for token in re.findall(r"\b[A-Z][a-z]{2,}\b", text):
            if token.lower() not in corpus and token.lower() not in _ALLOWED_WORDS:
                violations.append(GroundingViolation(token, "proper noun not present in evidence"))
        return violations


_ALLOWED_WORDS = {
    "the", "this", "that", "landtrust", "connect", "verified", "conflicting", "pending",
    "expired", "owner", "buyer", "risk", "hold", "proceed", "warn", "escalate", "reject",
    "document", "documents", "page", "evidence", "confidence", "property", "survey", "area",
    "mortgage", "encumbrance", "registration", "tax", "status", "partially", "unverified",
    "insufficient", "available", "answer", "question", "platform", "registry", "prototype",
}
