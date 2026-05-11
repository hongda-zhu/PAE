"""Command-line interface for the IKUSA Compliance Scanner.

Subcommands:
    ikusa-cli login --api-key <key>            -- persist key to ~/.ikusa/credentials
    ikusa-cli scan <apk_path> [options]        -- upload, poll, download PDF
    ikusa-cli status <scan_id> [options]       -- one-shot status check
    ikusa-cli report <scan_id> -o <out> [opts] -- download PDF only

Environment variables:
    IKUSA_SERVER       Default server URL (overrides built-in default)
    IKUSA_API_KEY      Default API key (overrides ~/.ikusa/credentials)

Exit codes:
    0   success (no findings exceed --fail-on threshold)
    1   scan failed or other error
    2   --fail-on triggered (findings exceed threshold)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import click
import httpx

_DEFAULT_SERVER = "http://localhost:9787"
_CREDENTIALS_PATH = Path.home() / ".ikusa" / "credentials"

_SEVERITY_ORDER = {"info": 0, "low": 1, "medio": 2, "medium": 2, "alto": 3, "high": 3}


def _load_api_key() -> str | None:
    """Resolution order: env var > credentials file > None."""
    env_key = os.environ.get("IKUSA_API_KEY")
    if env_key:
        return env_key
    if _CREDENTIALS_PATH.exists():
        return _CREDENTIALS_PATH.read_text(encoding="utf-8").strip() or None
    return None


def _headers(api_key: str | None) -> dict[str, str]:
    if api_key:
        return {"Authorization": api_key}
    return {}


def _server_url(server_arg: str | None) -> str:
    return server_arg or os.environ.get("IKUSA_SERVER") or _DEFAULT_SERVER


@click.group()
@click.version_option(package_name="ikusa-prototype")
def main() -> None:
    """IKUSA Compliance Scanner CLI."""


@main.command()
@click.option("--api-key", required=True, help="ikusa_sk_* API key")
def login(api_key: str) -> None:
    """Persist API key to ~/.ikusa/credentials (mode 0600)."""
    _CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CREDENTIALS_PATH.write_text(api_key.strip() + "\n", encoding="utf-8")
    _CREDENTIALS_PATH.chmod(0o600)
    click.echo(f"Saved API key to {_CREDENTIALS_PATH}")


@main.command()
@click.argument("apk_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--tier",
    default="compliance",
    type=click.Choice(["basico", "completo", "compliance"]),
    help="Scan tier (default: compliance)",
)
@click.option("--api-key", help="API key (overrides env IKUSA_API_KEY and credentials file)")
@click.option("--server", help="Server URL (default: http://localhost:9787)")
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="PDF output path (default: <apk_name>-report.pdf)",
)
@click.option(
    "--fail-on",
    type=click.Choice(["alto", "medio", "bajo", "none"]),
    default="none",
    help="Exit non-zero if any finding has severity >= threshold",
)
@click.option(
    "--poll-interval",
    default=3.0,
    type=float,
    help="Seconds between status polls (default 3.0)",
)
@click.option(
    "--timeout",
    default=900,
    type=int,
    help="Max seconds to wait for scan (default 900)",
)
def scan(
    apk_path: Path,
    tier: str,
    api_key: str | None,
    server: str | None,
    output: Path | None,
    fail_on: str,
    poll_interval: float,
    timeout: int,
) -> None:
    """Scan an APK end-to-end: upload, poll until done, download PDF."""
    api_key = api_key or _load_api_key()
    base = _server_url(server)
    headers = _headers(api_key)

    click.echo(f"Server: {base}")
    click.echo(f"APK:    {apk_path.name} ({apk_path.stat().st_size:,} bytes)")
    click.echo(f"Tier:   {tier}")

    # Upload
    with apk_path.open("rb") as f:
        try:
            resp = httpx.post(
                f"{base}/scan",
                headers=headers,
                files={"file": (apk_path.name, f, "application/octet-stream")},
                data={"tier": tier},
                timeout=60.0,
            )
        except httpx.HTTPError as exc:
            click.echo(f"Upload failed: {exc}", err=True)
            sys.exit(1)

    if resp.status_code == 402:
        click.echo(f"Quota exhausted: {resp.json().get('detail', resp.text)}", err=True)
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(f"Upload failed [{resp.status_code}]: {resp.text}", err=True)
        sys.exit(1)

    scan_id = resp.json()["scan_id"]
    click.echo(f"Scan:   {scan_id}")
    click.echo()

    # Poll
    deadline = time.monotonic() + timeout
    last_message = ""
    while time.monotonic() < deadline:
        try:
            poll = httpx.get(f"{base}/scan/{scan_id}", headers=headers, timeout=15.0)
            poll.raise_for_status()
        except httpx.HTTPError as exc:
            click.echo(f"Poll failed: {exc}", err=True)
            sys.exit(1)
        state = poll.json()
        status = state["status"]
        stage = state.get("stage", "")
        message = state.get("message", "")

        if message and message != last_message:
            click.echo(f"  [{stage}] {message}")
            last_message = message

        if status == "done":
            break
        if status == "failed":
            click.echo(f"Scan failed: {state.get('error', 'unknown')}", err=True)
            sys.exit(1)

        time.sleep(poll_interval)
    else:
        click.echo(f"Timeout after {timeout}s waiting for scan to complete", err=True)
        sys.exit(1)

    # Fetch result for fail-on logic
    try:
        result_resp = httpx.get(
            f"{base}/scan/{scan_id}/result", headers=headers, timeout=15.0
        )
        result_resp.raise_for_status()
    except httpx.HTTPError as exc:
        click.echo(f"Could not fetch result: {exc}", err=True)
        sys.exit(1)
    result = result_resp.json()

    click.echo()
    click.echo(f"CRA Score: {result['cra_score']}/100")
    click.echo(f"Findings:  {len(result['findings'])}")

    # Download PDF
    if output is None:
        output = Path(f"{apk_path.stem}-report.pdf")
    try:
        pdf_resp = httpx.get(
            f"{base}/scan/{scan_id}/report", headers=headers, timeout=30.0
        )
        pdf_resp.raise_for_status()
    except httpx.HTTPError as exc:
        click.echo(f"Could not fetch PDF: {exc}", err=True)
        sys.exit(1)
    output.write_bytes(pdf_resp.content)
    click.echo(f"PDF saved: {output} ({len(pdf_resp.content):,} bytes)")

    # --fail-on check
    if fail_on != "none":
        threshold = _SEVERITY_ORDER.get(fail_on, 0)
        violating = [
            f
            for f in result["findings"]
            if _SEVERITY_ORDER.get(f["severity"], 0) >= threshold
        ]
        if violating:
            click.echo(
                f"\nFAIL: {len(violating)} finding(s) at severity >= {fail_on}",
                err=True,
            )
            sys.exit(2)


@main.command()
@click.argument("scan_id")
@click.option("--api-key", help="API key")
@click.option("--server", help="Server URL")
def status(scan_id: str, api_key: str | None, server: str | None) -> None:
    """Print scan status as JSON."""
    api_key = api_key or _load_api_key()
    base = _server_url(server)
    try:
        resp = httpx.get(
            f"{base}/scan/{scan_id}", headers=_headers(api_key), timeout=15.0
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        click.echo(f"Status fetch failed: {exc}", err=True)
        sys.exit(1)
    click.echo(json.dumps(resp.json(), indent=2))


@main.command()
@click.argument("scan_id")
@click.option(
    "--output", "-o", required=True, type=click.Path(path_type=Path), help="PDF output path"
)
@click.option("--api-key", help="API key")
@click.option("--server", help="Server URL")
def report(scan_id: str, output: Path, api_key: str | None, server: str | None) -> None:
    """Download a completed scan's PDF report."""
    api_key = api_key or _load_api_key()
    base = _server_url(server)
    try:
        resp = httpx.get(
            f"{base}/scan/{scan_id}/report", headers=_headers(api_key), timeout=30.0
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        click.echo(f"Report fetch failed: {exc}", err=True)
        sys.exit(1)
    output.write_bytes(resp.content)
    click.echo(f"Wrote {output} ({len(resp.content):,} bytes)")


if __name__ == "__main__":
    main()
