"""Tests for the PDF report generator.

These tests run the real WeasyPrint Docker image -- they require that the
image has been built (`make weasyprint-build`). If Docker is not available
or the image is missing, the tests are skipped with a clear reason.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from ikusa.models import (
    MasvsCategory,
    ScanResult,
    Severity,
    TriagedFinding,
)
from ikusa.report import generate_pdf


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "ikusa-weasyprint:latest"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


pytestmark = pytest.mark.skipif(
    not _docker_available(),
    reason="ikusa-weasyprint:latest Docker image not available -- run `make weasyprint-build`",
)


def _triaged(idx: int, sev: Severity, priority: int = 1) -> TriagedFinding:
    return TriagedFinding(
        id=f"id-{idx}",
        title=f"Finding {idx}",
        severity=sev,
        masvs_category=MasvsCategory.STORAGE,
        description=f"description {idx}",
        priority=priority,
        explanation=f"explicacion {idx}",
        remediation=f"remediacion sugerida {idx}",
        cra_articles=["Annex I (1)(h)"],
    )


def test_generate_pdf_produces_real_pdf(tmp_path):
    result = ScanResult(
        scan_id="abc123",
        app_name="TestApp",
        package_name="com.test.app",
        apk_hash="deadbeefcafe",
        cra_score=72,
        findings=[
            _triaged(1, Severity.HIGH, priority=1),
            _triaged(2, Severity.MEDIUM, priority=2),
        ],
        categories_covered=[MasvsCategory.STORAGE],
        duration_seconds=423.5,
    )
    out = tmp_path / "report.pdf"
    generate_pdf(result, out)
    assert out.exists()
    # File must start with the PDF magic header.
    head = out.read_bytes()[:4]
    assert head == b"%PDF"
    # Real PDFs are at least several KB.
    assert out.stat().st_size > 4096


def test_generate_pdf_with_no_findings(tmp_path):
    result = ScanResult(
        scan_id="empty",
        app_name="CleanApp",
        package_name="com.clean.app",
        apk_hash="deadbeef",
        cra_score=88,
        findings=[],
        categories_covered=[MasvsCategory.STORAGE, MasvsCategory.CRYPTO],
        duration_seconds=120.0,
    )
    out = tmp_path / "clean.pdf"
    generate_pdf(result, out)
    assert out.exists()
    assert out.read_bytes()[:4] == b"%PDF"
