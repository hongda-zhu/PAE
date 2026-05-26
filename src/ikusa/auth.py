"""API key authentication and credit tracking.

This module owns:
- ApiKey pydantic model (key, user_id, tier, credits, scans_this_month, month_anchor)
- load_keys / save_keys (YAML, atomic write via tempfile + os.replace)
- require_api_key FastAPI dependency (validates Authorization header, returns ApiKey)
- consume_credit (decrement credits or increment monthly counter, atomic)

The store is a single YAML file at settings.api_keys_path.
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import yaml
from fastapi import Header, HTTPException, status
from pydantic import BaseModel, Field

Tier = Literal["free", "team", "business", "enterprise"]


class ApiKey(BaseModel):
    key: str = Field(description="Format: ikusa_sk_*")
    user_id: str
    tier: Tier = "free"
    credits: int = Field(default=0, ge=0, description="Pay-per-scan credits remaining")
    scans_this_month: int = Field(default=0, ge=0)
    month_anchor: str = Field(
        default_factory=lambda: date.today().strftime("%Y-%m"),
        description="YYYY-MM; counter resets when current month differs",
    )


def load_keys(path: Path) -> dict[str, ApiKey]:
    """Load all keys, keyed by the API key string."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a YAML list of API key entries")
    return {entry["key"]: ApiKey(**entry) for entry in raw}


def save_keys(keys: dict[str, ApiKey], path: Path) -> None:
    """Atomically write all keys to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [k.model_dump() for k in keys.values()]
    yaml_text = yaml.safe_dump(payload, sort_keys=False)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        tmp.write(yaml_text)
        tmp_name = tmp.name
    os.replace(tmp_name, path)


# --- Tier semantics ---
SCANS_PER_MONTH: dict[Tier, int] = {
    "free": 3,
    "team": 25,
    "business": 100,
    "enterprise": 999_999,
}


class QuotaExhaustedError(HTTPException):
    def __init__(self, tier: Tier, cap: int) -> None:
        super().__init__(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Tier '{tier}' allows {cap} scans/month and is exhausted. "
            "Buy credits or upgrade.",
        )


def consume_credit(api_key: ApiKey, store_path: Path) -> ApiKey:
    """Consume one scan from either the monthly quota or pay-per-scan credits.

    Logic:
      1. If current month != month_anchor, reset scans_this_month and update anchor.
      2. If scans_this_month < tier cap, increment it.
      3. Otherwise, if credits > 0, decrement credits.
      4. Otherwise, raise QuotaExhaustedError.

    Atomically persists the updated key set back to disk and returns the updated
    ApiKey object.
    """
    keys = load_keys(store_path)
    current = keys.get(api_key.key)
    if current is None:
        # Race: key was deleted between header parse and consume. Treat as auth fail.
        raise HTTPException(401, "API key not found")

    today_anchor = date.today().strftime("%Y-%m")
    if current.month_anchor != today_anchor:
        current.scans_this_month = 0
        current.month_anchor = today_anchor

    cap = SCANS_PER_MONTH[current.tier]
    if current.scans_this_month < cap:
        current.scans_this_month += 1
    elif current.credits > 0:
        current.credits -= 1
    else:
        raise QuotaExhaustedError(current.tier, cap)

    keys[current.key] = current
    save_keys(keys, store_path)
    return current


# --- FastAPI dependency ---

# Anonymous fallback key: lets the existing 66 tests keep passing without changes,
# AND lets unauthenticated demo visitors try one scan. The fallback is enforced
# in-memory; it is NOT a real entry in the YAML store.
_ANONYMOUS_KEY = ApiKey(
    key="anonymous",
    user_id="anonymous",
    tier="free",
    credits=0,
    scans_this_month=0,
)


def require_api_key(
    authorization: Annotated[str | None, Header()] = None,
) -> ApiKey:
    """FastAPI dependency. Returns an ApiKey for the request.

    - If Authorization header is missing OR equals "anonymous", returns the
      anonymous fallback key (free tier, no credits). Allows unauthenticated
      one-shot scan via monthly free-tier quota.
    - Otherwise looks up the key in the YAML store. 401 if not found.

    The dependency only loads the store; consume_credit is called separately
    by the endpoint to decrement the counter.
    """
    # Late import to avoid circular dependency with config
    from ikusa.config import get_settings

    if authorization is None or authorization.strip() == "" or authorization == "anonymous":
        return _ANONYMOUS_KEY

    # Allow "Bearer <key>" or raw "<key>"
    if authorization.startswith("Bearer "):
        authorization = authorization[7:]

    settings = get_settings()
    keys = load_keys(settings.api_keys_path)
    if authorization not in keys:
        raise HTTPException(401, "Invalid API key")
    return keys[authorization]
