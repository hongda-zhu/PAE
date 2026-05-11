"""Tests for the async MobSF REST client.

We exercise the client against ``pytest-httpx`` mocks rather than a real
MobSF instance to keep the suite hermetic. The fixture-capture script
(``scripts/fixture_capture.py``) is what verifies the schema against the
real service.
"""

from __future__ import annotations

import pytest

from ikusa.mobsf import MobSFClient, MobSFError


@pytest.mark.asyncio
async def test_upload_extracts_hash(httpx_mock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://mobsf:8000/api/v1/upload",
        json={
            "hash": "abc123def456",
            "scan_type": "apk",
            "file_name": "app.apk",
        },
    )
    client = MobSFClient(base_url="http://mobsf:8000", api_key="secret")
    result = await client.upload(b"FAKEAPK", filename="app.apk")
    assert result == "abc123def456"


@pytest.mark.asyncio
async def test_upload_missing_hash_raises(httpx_mock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://mobsf:8000/api/v1/upload",
        json={"error": "bad apk"},
    )
    client = MobSFClient(base_url="http://mobsf:8000", api_key="secret")
    with pytest.raises(MobSFError):
        await client.upload(b"FAKEAPK", filename="app.apk")


@pytest.mark.asyncio
async def test_upload_sends_authorization_header(httpx_mock) -> None:
    """Authorization header is the raw API key, no Bearer prefix."""
    httpx_mock.add_response(
        method="POST",
        url="http://mobsf:8000/api/v1/upload",
        json={"hash": "h"},
        match_headers={"Authorization": "secret"},
    )
    client = MobSFClient(base_url="http://mobsf:8000", api_key="secret")
    await client.upload(b"x", filename="x.apk")


@pytest.mark.asyncio
async def test_scan_posts_correct_form(httpx_mock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://mobsf:8000/api/v1/scan",
        json={"status": "Analysis Complete"},
    )
    client = MobSFClient(base_url="http://mobsf:8000", api_key="secret")
    await client.scan("abc123")
    # If we got here without raising, the request was accepted.


@pytest.mark.asyncio
async def test_report_json_returns_dict(httpx_mock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="http://mobsf:8000/api/v1/report_json",
        json={"app_name": "TestApp", "appsec": {"high": []}},
    )
    client = MobSFClient(base_url="http://mobsf:8000", api_key="secret")
    report = await client.report_json("abc123")
    assert report["app_name"] == "TestApp"


@pytest.mark.asyncio
async def test_trailing_slash_in_base_url_is_normalized(httpx_mock) -> None:
    """Constructing with a trailing slash must not produce double slashes."""
    httpx_mock.add_response(
        method="POST",
        url="http://mobsf:8000/api/v1/upload",
        json={"hash": "h"},
    )
    client = MobSFClient(base_url="http://mobsf:8000/", api_key="secret")
    await client.upload(b"x", filename="x.apk")


@pytest.mark.asyncio
async def test_upload_propagates_http_error(httpx_mock) -> None:
    """Non-2xx HTTP responses are surfaced as httpx errors."""
    import httpx

    httpx_mock.add_response(
        method="POST",
        url="http://mobsf:8000/api/v1/upload",
        status_code=500,
        json={"error": "internal"},
    )
    client = MobSFClient(base_url="http://mobsf:8000", api_key="secret")
    with pytest.raises(httpx.HTTPStatusError):
        await client.upload(b"x", filename="x.apk")
