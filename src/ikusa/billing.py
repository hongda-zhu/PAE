"""Mock pay-per-scan billing.

This is a Stripe-shaped STUB. It mirrors the API surface of Stripe Checkout +
Webhook so Phase 2 can replace it with the real SDK without touching the
frontend or the rest of the backend.

NO REAL STRIPE SDK. NO REAL MONEY.

Sessions are persisted to YAML so a server restart between checkout and
"payment" doesn't lose state. State machine:
    pending  -> checkout created, payment not yet confirmed
    completed -> webhook fired, credits granted
    expired  -> session older than _SESSION_TTL_SECONDS
"""

from __future__ import annotations

import os
import secrets
import tempfile
import time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

# Available "products" -- each maps a stripe-like price tier to scan credit grants or tier upgrades.
PRODUCTS: dict[str, dict] = {
    "web-scan": {"label": "Análisis web único", "amount_cents": 500, "credits": 1},
    "terminal-sub": {"label": "Suscripción Terminal (mensual)", "amount_cents": 4900, "credits": 0},
}

_SESSION_TTL_SECONDS = 3600  # 1 hour


SessionStatus = Literal["pending", "completed", "expired"]


class PaymentSession(BaseModel):
    session_id: str
    api_key: str
    product_id: str
    status: SessionStatus = "pending"
    created_at: float = Field(default_factory=time.time)
    completed_at: float | None = None


def _now() -> float:
    return time.time()


def load_sessions(path: Path) -> dict[str, PaymentSession]:
    """Load all sessions, keyed by session_id."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        return {}
    sessions: dict[str, PaymentSession] = {}
    for entry in raw:
        sess = PaymentSession(**entry)
        sessions[sess.session_id] = sess
    return sessions


def save_sessions(sessions: dict[str, PaymentSession], path: Path) -> None:
    """Atomically write all sessions to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [s.model_dump() for s in sessions.values()]
    yaml_text = yaml.safe_dump(payload, sort_keys=False)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as tmp:
        tmp.write(yaml_text)
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def create_session(api_key: str, product_id: str, store_path: Path) -> PaymentSession:
    """Create a new pending session for the given api_key + product."""
    if product_id not in PRODUCTS:
        raise ValueError(f"Unknown product: {product_id}")
    sessions = load_sessions(store_path)
    session_id = "cs_test_" + secrets.token_urlsafe(16)
    sess = PaymentSession(session_id=session_id, api_key=api_key, product_id=product_id)
    sessions[session_id] = sess
    save_sessions(sessions, store_path)
    return sess


def fulfill_session(session_id: str, store_path: Path) -> PaymentSession:
    """Mark a session completed. Idempotent: second call is a no-op (but returns the session)."""
    sessions = load_sessions(store_path)
    sess = sessions.get(session_id)
    if sess is None:
        raise KeyError(f"Session not found: {session_id}")

    if sess.status == "completed":
        return sess

    age = _now() - sess.created_at
    if age > _SESSION_TTL_SECONDS:
        sess.status = "expired"
        sessions[session_id] = sess
        save_sessions(sessions, store_path)
        raise RuntimeError(f"Session expired (age {age:.0f}s)")

    sess.status = "completed"
    sess.completed_at = _now()
    sessions[session_id] = sess
    save_sessions(sessions, store_path)
    return sess


def credits_for_product(product_id: str) -> int:
    return PRODUCTS[product_id]["credits"]
