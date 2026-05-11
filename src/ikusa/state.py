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

    user_id: str | None = Field(
        default=None,
        description="The authenticated user this scan belongs to. None = anonymous.",
    )

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


def list_states_for_user(storage: Path, user_id: str | None) -> list[ScanState]:
    """Return all ScanState records belonging to a user.

    Iterates state.json files under storage/. Pass user_id=None to list
    anonymous scans (matches the anonymous fallback from auth.py).

    Order: newest first by updated_at.
    """
    if not storage.exists():
        return []
    states: list[ScanState] = []
    for scan_dir in storage.iterdir():
        if not scan_dir.is_dir():
            continue
        state_file = scan_dir / "state.json"
        if not state_file.exists():
            continue
        try:
            state = ScanState.model_validate_json(state_file.read_text(encoding="utf-8"))
        except Exception:
            # Skip corrupt state.json files instead of crashing the whole list.
            continue
        if state.user_id == user_id:
            states.append(state)
    states.sort(key=lambda s: s.updated_at, reverse=True)
    return states
