"""MASVS top-level category -> CRA (Reg 2024/2847) article mapping.

The mapping is loaded from ``data/masvs_to_cra.yaml`` at package import time.
The file is informational only; the PDF report carries a disclaimer making
clear this is not a legal certification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ikusa.models import MasvsCategory

_DEFAULT_DATA_PATH: Path = Path(__file__).resolve().parents[2] / "data" / "masvs_to_cra.yaml"


@dataclass(frozen=True)
class CraArticle:
    """One CRA Annex I requirement referenced by a MASVS category."""

    id: str
    title: str
    rationale: str | None = None


class CraMapper:
    """Lookup table for MASVS -> CRA articles, loaded from YAML."""

    _FALLBACK_LABEL = "Art. 13 - General"

    def __init__(self, mapping: dict[str, dict[str, Any]]) -> None:
        self._mapping = mapping

    @classmethod
    def load_default(cls) -> "CraMapper":
        return cls.load_from(_DEFAULT_DATA_PATH)

    @classmethod
    def load_from(cls, path: Path) -> "CraMapper":
        data = yaml.safe_load(path.read_text())
        return cls(mapping=data or {})

    def articles_for(self, category: MasvsCategory) -> list[CraArticle]:
        entry = self._mapping.get(category.value, {})
        return [
            CraArticle(
                id=item["id"],
                title=item["title"],
                rationale=item.get("rationale"),
            )
            for item in entry.get("cra_articles", [])
        ]

    def short_label_for(self, category: MasvsCategory) -> str:
        entry = self._mapping.get(category.value, {})
        return entry.get("article_short", self._FALLBACK_LABEL)
