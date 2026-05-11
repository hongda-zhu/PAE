"""Tests for the ikusa-cli command-line interface."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from ikusa.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_login_writes_credentials(runner, tmp_path, monkeypatch):
    creds_path = tmp_path / ".ikusa" / "credentials"
    monkeypatch.setattr("ikusa.cli._CREDENTIALS_PATH", creds_path)

    result = runner.invoke(main, ["login", "--api-key", "ikusa_sk_test"])
    assert result.exit_code == 0
    assert creds_path.exists()
    assert creds_path.read_text().strip() == "ikusa_sk_test"


def test_status_fetches_scan_state(runner, httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/abc",
        json={"scan_id": "abc", "status": "done", "stage": "done", "cra_score": 72},
    )
    result = runner.invoke(main, ["status", "abc"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["scan_id"] == "abc"
    assert payload["status"] == "done"


def test_scan_end_to_end_against_mocked_server(runner, httpx_mock, tmp_path):
    # Create a fake APK file
    apk = tmp_path / "fake.apk"
    apk.write_bytes(b"FAKEAPK")

    # Mock the API calls: POST /scan, GET /scan/{id}, GET /scan/{id}/result, GET /scan/{id}/report
    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9787/scan",
        json={"scan_id": "sid", "status": "processing"},
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/sid",
        json={"scan_id": "sid", "status": "done", "stage": "done", "message": "ok"},
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/sid/result",
        json={"cra_score": 88, "findings": []},
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/sid/report",
        content=b"%PDF-fake-pdf-bytes",
    )

    out = tmp_path / "out.pdf"
    result = runner.invoke(
        main,
        ["scan", str(apk), "-o", str(out), "--poll-interval", "0.01"],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.read_bytes() == b"%PDF-fake-pdf-bytes"
    assert "CRA Score: 88/100" in result.output


def test_scan_fail_on_alto_triggers_exit_2(runner, httpx_mock, tmp_path):
    apk = tmp_path / "fake.apk"
    apk.write_bytes(b"FAKEAPK")

    httpx_mock.add_response(
        method="POST",
        url="http://localhost:9787/scan",
        json={"scan_id": "sid2", "status": "processing"},
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/sid2",
        json={"scan_id": "sid2", "status": "done", "stage": "done"},
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/sid2/result",
        json={
            "cra_score": 30,
            "findings": [
                {"severity": "high", "title": "bad"},
                {"severity": "low", "title": "meh"},
            ],
        },
    )
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/sid2/report",
        content=b"%PDF-x",
    )

    out = tmp_path / "out.pdf"
    result = runner.invoke(
        main,
        ["scan", str(apk), "-o", str(out), "--fail-on", "alto", "--poll-interval", "0.01"],
    )
    assert result.exit_code == 2, result.output
    assert "FAIL" in result.output
