"""Async HTTP client for the MobSF REST API.

MobSF endpoints used by IKUSA:

* ``POST /api/v1/upload``      -> ``{hash, scan_type, file_name}``
* ``POST /api/v1/scan``        -> ``{status}``; blocks until the scan
                                  completes (can take several minutes
                                  on large APKs - that is why the
                                  default timeout is 15 minutes).
* ``POST /api/v1/report_json`` -> full MobSF v4.5 JSON report.

All requests require an ``Authorization: <api_key>`` header (no
``Bearer `` prefix - this is MobSF's REST API convention, not OAuth2).
The key is generated once per MobSF deployment and surfaced through the
``REST API`` page in the MobSF web UI.
"""

from __future__ import annotations

from typing import Any

import httpx


class MobSFError(RuntimeError):
    """Raised when MobSF returns an unexpected or malformed response."""


class MobSFClient:
    """Thin async wrapper around the three MobSF REST endpoints we use.

    Each call constructs its own ``httpx.AsyncClient`` so the wrapper is
    safe to share across asyncio tasks without serializing them. The
    long default timeout (900s) accommodates the synchronous ``/scan``
    endpoint, which holds the connection open for the duration of the
    scan.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 900.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": api_key}
        self._timeout = timeout

    async def upload(self, content: bytes, filename: str) -> str:
        """Upload an APK and return MobSF's content-addressed hash."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            files = {
                "file": (filename, content, "application/octet-stream"),
            }
            response = await client.post(
                f"{self._base}/api/v1/upload",
                files=files,
                headers=self._headers,
            )
            response.raise_for_status()
            data = response.json()
            file_hash = data.get("hash")
            if not file_hash:
                raise MobSFError(f"Upload response missing hash: {data}")
            return file_hash

    async def scan(self, file_hash: str, scan_type: str = "apk") -> None:
        """Trigger a static scan on a previously uploaded APK.

        Blocks until MobSF finishes the scan. Use the timeout argument
        on the constructor to bound the wait.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base}/api/v1/scan",
                data={"scan_type": scan_type, "hash": file_hash},
                headers=self._headers,
            )
            response.raise_for_status()

    async def report_json(self, file_hash: str) -> dict[str, Any]:
        """Fetch the full v4.5 JSON report for a completed scan."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base}/api/v1/report_json",
                data={"hash": file_hash},
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()
