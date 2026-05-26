"""Tests for the PDF report generator.

WeasyPrint runs in-process; no Docker image or external service is needed.
The host (or container) must have libpango / libcairo / libgdk-pixbuf
installed, which is handled by the app image.
"""

from __future__ import annotations

from ikusa.models import (
    MasvsCategory,
    ScanResult,
    Severity,
    TriagedFinding,
)
from ikusa.report import generate_pdf


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
