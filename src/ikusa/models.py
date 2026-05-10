"""Domain models for the IKUSA compliance scanner.

These models represent the data flowing through the scan pipeline:
raw MobSF findings -> normalized Finding -> TriagedFinding (LLM enriched)
-> ScanResult (final aggregate).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity scale, ordered so HIGH > MEDIUM > LOW > INFO.

    Inheriting from ``str`` means default comparisons would be lexicographic
    on the string value, which gives the wrong order ("high" < "low"). We
    therefore override the rich comparison operators explicitly against an
    integer rank derived from ``_ORDER``.
    """

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def _order(self) -> int:
        return _SEVERITY_ORDER[self.value]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order < other._order

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order <= other._order

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order > other._order

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self._order >= other._order


_SEVERITY_ORDER: dict[str, int] = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
}


class MasvsCategory(str, Enum):
    """OWASP MASVS top-level categories used to bucket findings."""

    STORAGE = "MASVS-STORAGE"
    CRYPTO = "MASVS-CRYPTO"
    NETWORK = "MASVS-NETWORK"
    AUTH = "MASVS-AUTH"
    PLATFORM = "MASVS-PLATFORM"
    CODE = "MASVS-CODE"
    RESILIENCE = "MASVS-RESILIENCE"
    PRIVACY = "MASVS-PRIVACY"


class Finding(BaseModel):
    """A single normalized finding extracted from a MobSF report."""

    id: str
    title: str
    severity: Severity
    masvs_category: MasvsCategory
    description: str
    file_path: str | None = None
    cwe: str | None = None
    raw_mobsf_key: str | None = Field(
        default=None,
        description="Original MobSF rule or title for traceability",
    )


class TriagedFinding(Finding):
    """Finding after LLM triage, enriched with prioritization and remediation."""

    priority: int = Field(ge=1, le=3, description="1=critical, 3=informational")
    explanation: str
    remediation: str
    cra_articles: list[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    """Final aggregated output of a scan run."""

    scan_id: str
    app_name: str
    package_name: str
    apk_hash: str
    cra_score: int = Field(ge=0, le=100)
    findings: list[TriagedFinding]
    categories_covered: list[MasvsCategory]
    duration_seconds: float
