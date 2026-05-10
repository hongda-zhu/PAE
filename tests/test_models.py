"""Tests for the IKUSA domain models."""

from __future__ import annotations

import pytest

from ikusa.models import Finding, MasvsCategory, ScanResult, Severity, TriagedFinding


def test_finding_minimum_fields() -> None:
    """A Finding can be instantiated with only the required fields and survives roundtrip."""
    f = Finding(
        id="F1",
        title="Hardcoded API key",
        severity=Severity.HIGH,
        masvs_category=MasvsCategory.STORAGE,
        description="Detected a hardcoded API key in source.",
    )
    assert f.id == "F1"
    assert f.file_path is None
    assert f.cwe is None
    assert f.raw_mobsf_key is None

    dumped = f.model_dump()
    revived = Finding.model_validate(dumped)
    assert revived == f


def test_severity_ordering() -> None:
    """Severity must compare HIGH > MEDIUM > LOW > INFO and equal itself."""
    assert Severity.HIGH > Severity.MEDIUM
    assert Severity.MEDIUM > Severity.LOW
    assert Severity.LOW > Severity.INFO
    assert Severity.HIGH > Severity.INFO
    assert not (Severity.INFO > Severity.INFO)
    assert Severity.INFO < Severity.HIGH


def test_triaged_inherits_from_finding() -> None:
    """TriagedFinding carries every Finding field plus triage-specific fields."""
    t = TriagedFinding(
        id="F2",
        title="Cleartext HTTP traffic",
        severity=Severity.MEDIUM,
        masvs_category=MasvsCategory.NETWORK,
        description="Endpoints contacted over plain HTTP.",
        priority=1,
        explanation="Plaintext network exposes data in transit.",
        remediation="Move to HTTPS with valid certificate pinning.",
        cra_articles=["Annex I.2.h"],
    )
    assert isinstance(t, Finding)
    assert t.priority == 1
    assert t.cra_articles == ["Annex I.2.h"]
    assert t.title == "Cleartext HTTP traffic"


def test_priority_bounds_enforced() -> None:
    """TriagedFinding rejects priorities outside [1, 3]."""
    with pytest.raises(ValueError):
        TriagedFinding(
            id="F3",
            title="x",
            severity=Severity.LOW,
            masvs_category=MasvsCategory.CODE,
            description="x",
            priority=4,
            explanation="x",
            remediation="x",
        )


def test_scan_result_holds_triaged_findings() -> None:
    """ScanResult aggregates triaged findings with a CRA score in [0, 100]."""
    finding = TriagedFinding(
        id="F4",
        title="MD5 hash usage",
        severity=Severity.MEDIUM,
        masvs_category=MasvsCategory.CRYPTO,
        description="MD5 is broken.",
        priority=2,
        explanation="MD5 collisions are practical.",
        remediation="Use SHA-256 or stronger.",
    )
    result = ScanResult(
        scan_id="scan-1",
        app_name="InsecureBankv2",
        package_name="com.android.insecurebankv2",
        apk_hash="deadbeef",
        cra_score=42,
        findings=[finding],
        categories_covered=[MasvsCategory.CRYPTO],
        duration_seconds=12.5,
    )
    assert result.cra_score == 42
    assert result.findings[0].priority == 2
