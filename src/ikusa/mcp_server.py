"""MCP stdio server for the IKUSA Compliance Scanner.

This server exposes the HTTP backend (default http://localhost:9787) as MCP
tools so AI assistants (Claude Code, Cursor, Claude Desktop) can invoke scans
directly. It is a thin wrapper around the FastAPI surface in ``ikusa.api``;
all business logic stays in the HTTP backend.

API in use:
    from mcp.server.fastmcp import FastMCP        # high-level decorator API
    mcp = FastMCP("ikusa-compliance")
    @mcp.tool() async def ...                     # registers a tool
    mcp.run()                                     # blocking stdio server

Verified against mcp==1.27.1 (see ``uv run pip show mcp``).

Tools exposed:
    scan_apk(apk_path, api_key=None, tier="compliance")
        -> {"scan_id": str, "status_url": str} | {"error": str}
    get_scan_status(scan_id, api_key=None)
        -> ScanState dict | {"error": str}
    get_scan_findings(scan_id, api_key=None)
        -> ScanResult dict | {"error": str}
    list_scans(api_key=None)
        -> list[ScanState dict] | [{"error": str}]

Environment overrides:
    IKUSA_SERVER   -- backend base URL (default http://localhost:9787)
    IKUSA_API_KEY  -- default ikusa_sk_* key when caller does not pass api_key

Run:
    uv run ikusa-mcp           # stdio server, blocks until host closes stdin
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

_DEFAULT_SERVER = os.environ.get("IKUSA_SERVER", "http://localhost:9787")
_DEFAULT_API_KEY = os.environ.get("IKUSA_API_KEY")

mcp = FastMCP("ikusa-compliance")


def _headers(api_key: str | None) -> dict[str, str]:
    """Build the Authorization header from the explicit arg or env default."""
    key = api_key or _DEFAULT_API_KEY
    return {"Authorization": key} if key else {}


@mcp.tool()
async def scan_apk(
    apk_path: str,
    api_key: str | None = None,
    tier: str = "compliance",
) -> dict[str, Any]:
    """Upload an APK from disk and start a compliance scan.

    Returns the scan_id and a URL to poll status. The scan runs asynchronously
    on the server; use get_scan_status with the returned scan_id to track progress.

    Args:
        apk_path: Absolute path to the .apk file on the machine running the server.
        api_key: Optional ikusa_sk_* key. If omitted, falls back to anonymous (free tier).
        tier: Must be "compliance" (the only plan available).
    """
    path = Path(apk_path).expanduser().resolve()
    if not path.exists():
        return {"error": f"File not found: {path}"}
    async with httpx.AsyncClient(timeout=60.0) as client:
        with path.open("rb") as f:
            resp = await client.post(
                f"{_DEFAULT_SERVER}/scan",
                headers=_headers(api_key),
                files={"file": (path.name, f, "application/octet-stream")},
                data={"tier": tier},
            )
    if resp.status_code != 200:
        return {"error": f"Server returned {resp.status_code}: {resp.text}"}
    data = resp.json()
    return {
        "scan_id": data["scan_id"],
        "status_url": f"{_DEFAULT_SERVER}/scan/{data['scan_id']}",
    }


@mcp.tool()
async def get_scan_status(scan_id: str, api_key: str | None = None) -> dict[str, Any]:
    """Get the current state of a running scan.

    Returns a dict with: status (processing/done/failed), stage
    (uploaded/decompiling/analyzing/triaging/rendering/done), message,
    app_name (when known), cra_score (when done), findings_count.

    Call this in a loop while status == "processing" to track progress.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_DEFAULT_SERVER}/scan/{scan_id}",
            headers=_headers(api_key),
        )
    if resp.status_code != 200:
        return {"error": f"Server returned {resp.status_code}: {resp.text}"}
    return resp.json()


@mcp.tool()
async def get_scan_findings(scan_id: str, api_key: str | None = None) -> dict[str, Any]:
    """Get the full set of findings for a completed scan.

    Returns the full ScanResult including app_name, package_name, cra_score (0-100),
    and a list of triaged findings (id, title, severity, priority, masvs_category,
    explanation, remediation, cra_articles).

    Only callable when the scan status is "done". Returns an error otherwise.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_DEFAULT_SERVER}/scan/{scan_id}/result",
            headers=_headers(api_key),
        )
    if resp.status_code == 404:
        return {"error": "Result not yet available. Check status first."}
    if resp.status_code != 200:
        return {"error": f"Server returned {resp.status_code}: {resp.text}"}
    return resp.json()


@mcp.tool()
async def list_scans(api_key: str | None = None) -> list[dict[str, Any]]:
    """List the most recent scans the authenticated user has run."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{_DEFAULT_SERVER}/scans",
            headers=_headers(api_key),
        )
    if resp.status_code != 200:
        return [{"error": f"Server returned {resp.status_code}: {resp.text}"}]
    return resp.json()


def main() -> None:
    """Entry point for the ``ikusa-mcp`` console script. Runs the stdio server."""
    mcp.run()


if __name__ == "__main__":
    main()
