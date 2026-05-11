"""Unit tests for the API key auth and credit tracking module."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from ikusa.auth import (
    SCANS_PER_MONTH,
    ApiKey,
    QuotaExhaustedError,
    consume_credit,
    load_keys,
    require_api_key,
    save_keys,
)


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "keys.yaml"
    keys = {
        "k_free": ApiKey(key="k_free", user_id="u1", tier="free"),
        "k_team": ApiKey(key="k_team", user_id="u2", tier="team", credits=5),
        "k_ent": ApiKey(key="k_ent", user_id="u3", tier="enterprise"),
    }
    save_keys(keys, path)
    return path


def test_save_load_roundtrip(store):
    keys = load_keys(store)
    assert set(keys.keys()) == {"k_free", "k_team", "k_ent"}
    assert keys["k_team"].credits == 5


def test_load_missing_file_returns_empty(tmp_path):
    assert load_keys(tmp_path / "nonexistent.yaml") == {}


def test_consume_credit_increments_monthly_counter(store):
    keys = load_keys(store)
    updated = consume_credit(keys["k_team"], store)
    assert updated.scans_this_month == 1
    # Persisted to disk
    assert load_keys(store)["k_team"].scans_this_month == 1


def test_consume_credit_falls_back_to_pay_per_scan(store):
    # Exhaust free tier's monthly cap (3 scans), then verify credit decrement.
    # Free tier starts with credits=0; load and bump credits manually first.
    keys = load_keys(store)
    keys["k_free"].credits = 2
    save_keys(keys, store)

    # Consume 3 monthly scans
    for _ in range(SCANS_PER_MONTH["free"]):
        consume_credit(load_keys(store)["k_free"], store)
    # Now monthly is exhausted; credit consumption kicks in
    consume_credit(load_keys(store)["k_free"], store)
    after = load_keys(store)["k_free"]
    assert after.scans_this_month == SCANS_PER_MONTH["free"]
    assert after.credits == 1  # decremented from 2


def test_consume_credit_raises_when_fully_exhausted(store):
    # Free tier with 0 credits, after 3 scans, 4th raises 402
    for _ in range(SCANS_PER_MONTH["free"]):
        consume_credit(load_keys(store)["k_free"], store)
    with pytest.raises(QuotaExhaustedError):
        consume_credit(load_keys(store)["k_free"], store)


def test_consume_credit_resets_on_new_month(store):
    # Set the key's anchor to last month
    keys = load_keys(store)
    k = keys["k_team"]
    k.month_anchor = "2025-01"
    k.scans_this_month = 999
    keys[k.key] = k
    save_keys(keys, store)

    updated = consume_credit(load_keys(store)["k_team"], store)
    today_anchor = date.today().strftime("%Y-%m")
    assert updated.month_anchor == today_anchor
    assert updated.scans_this_month == 1  # reset then +1


def test_require_api_key_returns_anonymous_when_no_header():
    # When no Authorization header is sent, fallback to anonymous free tier.
    key = require_api_key(authorization=None)
    assert key.user_id == "anonymous"
    assert key.tier == "free"


def test_require_api_key_strips_bearer_prefix(store, monkeypatch):
    # Point settings at the test store
    monkeypatch.setenv("API_KEYS_PATH", str(store))

    key = require_api_key(authorization="Bearer k_team")
    assert key.user_id == "u2"


def test_require_api_key_rejects_unknown_key(store, monkeypatch):
    monkeypatch.setenv("API_KEYS_PATH", str(store))

    with pytest.raises(HTTPException) as exc:
        require_api_key(authorization="ikusa_sk_does_not_exist")
    assert exc.value.status_code == 401
