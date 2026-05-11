"""Unit tests for the MCP stdio server tool functions.

The functions are plain async httpx wrappers, so we test them directly with
pytest-httpx. The MCP protocol itself (stdio framing, JSON-RPC handshake) is
covered by the upstream mcp SDK and not retested here.
"""

from __future__ import annotations

import pytest

from ikusa.mcp_server import (
    get_scan_findings,
    get_scan_status,
    scan_apk,
)


@pytest.mark.asyncio
async def test_get_scan_status_returns_state(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/abc",
        json={"scan_id": "abc", "status": "done", "stage": "done", "cra_score": 72},
    )
    result = await get_scan_status("abc")
    assert result["status"] == "done"
    assert result["cra_score"] == 72


@pytest.mark.asyncio
async def test_get_scan_findings_handles_404(httpx_mock):
    httpx_mock.add_response(
        method="GET",
        url="http://localhost:9787/scan/abc/result",
        status_code=404,
    )
    result = await get_scan_findings("abc")
    assert "error" in result
    assert "not yet available" in result["error"].lower()


@pytest.mark.asyncio
async def test_scan_apk_missing_file_returns_error(tmp_path):
    result = await scan_apk(str(tmp_path / "does_not_exist.apk"))
    assert "error" in result
    assert "not found" in result["error"].lower()
