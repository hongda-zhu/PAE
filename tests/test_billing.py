"""Tests for the mock pay-per-scan billing module."""

import pytest
from fastapi.testclient import TestClient

from ikusa.api import app
from ikusa.auth import ApiKey, load_keys, save_keys
from ikusa.billing import load_sessions


@pytest.fixture
def billing_client(tmp_path, monkeypatch, mocker):
    """A TestClient with auth + sessions stores pointed at tmp_path."""
    keys_path = tmp_path / "keys.yaml"
    sess_path = tmp_path / "sessions.yaml"
    save_keys(
        {"k_user": ApiKey(key="k_user", user_id="alice", tier="free", credits=0)},
        keys_path,
    )
    monkeypatch.setenv("API_KEYS_PATH", str(keys_path))
    monkeypatch.setenv("PAYMENT_SESSIONS_PATH", str(sess_path))
    monkeypatch.setenv("SCAN_STORAGE", str(tmp_path / "scans"))

    # Stub pipeline so any /scan calls don't try real MobSF/Ollama.
    async def _noop(*args, **kwargs):
        from ikusa.state import ScanState, save_state

        save_state(
            ScanState(
                scan_id=kwargs.get("scan_id", "x"),
                status="done",
                stage="done",
                user_id=kwargs.get("user_id"),
            ),
            tmp_path / "scans",
        )

    mocker.patch("ikusa.api.run_scan_pipeline", side_effect=_noop)

    yield TestClient(app), keys_path, sess_path


def test_checkout_creates_session(billing_client):
    client, _, sess_path = billing_client
    resp = client.post(
        "/payment/checkout",
        headers={"Authorization": "k_user"},
        json={"product_id": "web-scan"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"].startswith("cs_test_")
    assert data["checkout_url"].startswith("/payment/mock?session=")
    assert data["credits"] == 1

    # Persisted.
    sessions = load_sessions(sess_path)
    assert data["session_id"] in sessions


def test_checkout_unknown_product_returns_400(billing_client):
    client, _, _ = billing_client
    resp = client.post(
        "/payment/checkout",
        headers={"Authorization": "k_user"},
        json={"product_id": "credits-9999"},
    )
    assert resp.status_code == 400


def test_checkout_anonymous_rejected(billing_client):
    client, _, _ = billing_client
    resp = client.post(
        "/payment/checkout",
        json={"product_id": "web-scan"},
    )
    assert resp.status_code == 401


def test_mock_page_renders_for_valid_session(billing_client):
    client, _, _ = billing_client
    checkout = client.post(
        "/payment/checkout",
        headers={"Authorization": "k_user"},
        json={"product_id": "web-scan"},
    )
    session_id = checkout.json()["session_id"]
    page = client.get(f"/payment/mock?session={session_id}")
    assert page.status_code == 200
    assert "MOCK CHECKOUT" in page.text
    assert "$5.00 USD" in page.text


def test_webhook_completes_session_and_grants_credits(billing_client):
    client, keys_path, _ = billing_client

    checkout = client.post(
        "/payment/checkout",
        headers={"Authorization": "k_user"},
        json={"product_id": "web-scan"},
    )
    session_id = checkout.json()["session_id"]

    # Fire the webhook.
    hook = client.post(
        "/payment/webhook",
        data={"event_type": "checkout.session.completed", "session_id": session_id},
    )
    assert hook.status_code == 200

    # Credit balance went from 0 -> 1 (web-scan grants 1 credit).
    after = load_keys(keys_path)["k_user"]
    assert after.credits == 1
