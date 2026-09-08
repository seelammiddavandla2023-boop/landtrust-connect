"""Shared types for the extraction subsystem."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ...domain import ExtractionMode


@dataclass
class WordBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float = 1.0


@dataclass
class PageText:
    page_number: int
    text: str
    width: float
    height: float
    words: list[WordBox] = field(default_factory=list)
    ocr_confidence: float = 1.0
    layout_blocks: list[dict] = field(default_factory=list)


@dataclass
class DocumentText:
    """Text acquired from a file, page by page, with geometry for provenance."""

    pages: list[PageText]
    engine: str
    mode: ExtractionMode
    duration_ms: int = 0

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)

    @property
    def mean_confidence(self) -> float:
        if not self.pages:
            return 0.0
        return sum(p.ocr_confidence for p in self.pages) / len(self.pages)


@dataclass
class ExtractedClaim:
    """
    Output of the extraction layer.

    Deliberately carries NO verification status — the extractor is not permitted to
    decide whether a claim is verified.  See services/verification/resolver.py.
    """

    claim_type: str
    value: str
    page: int
    confidence: float
    source_span: str = ""
    region: dict | None = None
    method: str = ExtractionMode.DEMO.value


class TextAcquisition(ABC):
    """Strategy for turning a file into per-page text with geometry."""

    name: str = "base"

    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def read(self, path: Path) -> DocumentText:
        ...
