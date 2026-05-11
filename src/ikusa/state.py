"""Scan state persistence: one JSON file per scan, atomic writes."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ScanStatus = Literal["processing", "done", "failed"]
ScanStage = Literal[
    "uploaded",
    "decompiling",
    "analyzing",
    "triaging",
    "rendering",
    "done",
]


class ScanState(BaseModel):
    """In-flight or completed scan state, persisted to ${storage}/{scan_id}/state.json."""

    scan_id: str
    status: ScanStatus
    stage: ScanStage
    message: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Populated when status == "done".
    app_name: str | None = None
    package_name: str | None = None
    cra_score: int | None = None
    findings_count: int | None = None
    duration_seconds: float | None = None

    # Populated when status == "failed".
    error: str | None = None


def _scan_dir(storage: Path, scan_id: str) -> Path:
    return storage / scan_id


def save_state(state: ScanState, storage: Path) -> None:
    """Atomically write state.json for the given scan."""
    target_dir = _scan_dir(storage, state.scan_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "state.json"

    payload = state.model_dump_json(indent=2)
    # Atomic write: temp file in same dir, then rename.
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_dir,
        delete=False,
        suffix=".tmp",
    ) as tmp:
        tmp.write(payload)
        tmp_name = tmp.name
    os.replace(tmp_name, target)


def load_state(scan_id: str, storage: Path) -> ScanState | None:
    target = _scan_dir(storage, scan_id) / "state.json"
    if not target.exists():
        return None
    return ScanState.model_validate_json(target.read_text(encoding="utf-8"))
