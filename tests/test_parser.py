"""Tests for the MobSF v4.5 report parser, exercised against the real InsecureBank fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ikusa.models import MasvsCategory, Severity
from ikusa.parser import (
    MOBSF_SEVERITY_MAP,
    TARGET_CATEGORIES,
    classify_finding,
    filter_to_target_categories,
    parse_mobsf_report,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "insecurebank_mobsf.json"


@pytest.fixture(scope="module")
def mobsf_report() -> dict:
    """Load the real captured MobSF v4.5 report for InsecureBankv2."""
    with FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def parsed_findings(mobsf_report: dict) -> list:
    return parse_mobsf_report(mobsf_report)


def test_parser_finds_at_least_10_findings_in_fixture(parsed_findings: list) -> None:
    """The fixture contains 30 substantive findings; we must classify at least 10."""
    assert len(parsed_findings) >= 10


def test_parser_classifies_at_least_one_storage(parsed_findings: list) -> None:
    """allowBackup / hardcoded secrets should map to MASVS-STORAGE."""
    storage = [f for f in parsed_findings if f.masvs_category == MasvsCategory.STORAGE]
    assert storage, "expected at least one MASVS-STORAGE finding (allowBackup)"


def test_parser_classifies_at_least_one_crypto(parsed_findings: list) -> None:
    """Janus / signature scheme findings should map to MASVS-CRYPTO."""
    crypto = [f for f in parsed_findings if f.masvs_category == MasvsCategory.CRYPTO]
    assert crypto, "expected at least one MASVS-CRYPTO finding (Janus/signature)"


def test_parser_classifies_certificate_section_to_crypto_or_network(parsed_findings: list) -> None:
    """The InsecureBank fixture has no cleartext/TLS finding; its only
    certificate-section entry is the Janus v1-signature weakness, which
    we classify as MASVS-CRYPTO (signing scheme weakness). Net-net the
    parser still produces either NETWORK or CRYPTO coverage for the
    'certificate' bucket.
    """
    relevant = [
        f for f in parsed_findings
        if f.masvs_category in {MasvsCategory.CRYPTO, MasvsCategory.NETWORK}
    ]
    assert relevant, "expected at least one CRYPTO or NETWORK finding"


def test_parser_skips_info_severity(parsed_findings: list) -> None:
    """The parser drops 'secure' / 'good' / 'info' entries."""
    assert all(f.severity > Severity.INFO for f in parsed_findings)
    assert not any(f.severity == Severity.INFO for f in parsed_findings)


def test_filter_to_target_keeps_only_subset(parsed_findings: list) -> None:
    """filter_to_target_categories returns only the chosen subset."""
    targets = {
        MasvsCategory.STORAGE,
        MasvsCategory.CRYPTO,
        MasvsCategory.NETWORK,
    }
    filtered = filter_to_target_categories(parsed_findings, targets)
    assert filtered
    assert {f.masvs_category for f in filtered} <= targets


def test_severity_mapping_correct() -> None:
    """Spot-check the MobSF severity table."""
    assert MOBSF_SEVERITY_MAP["high"] == Severity.HIGH
    assert MOBSF_SEVERITY_MAP["warning"] == Severity.MEDIUM
    assert MOBSF_SEVERITY_MAP["hotspot"] == Severity.LOW
    assert MOBSF_SEVERITY_MAP["info"] == Severity.INFO
    assert MOBSF_SEVERITY_MAP["secure"] == Severity.INFO


def test_parser_unique_ids(parsed_findings: list) -> None:
    """Every emitted finding has a unique id (needed for downstream dedupe)."""
    ids = [f.id for f in parsed_findings]
    assert len(ids) == len(set(ids)), f"duplicate ids in parser output: {ids}"


def test_parser_preserves_raw_mobsf_key(parsed_findings: list) -> None:
    """raw_mobsf_key is set for traceability on every emitted finding."""
    assert all(f.raw_mobsf_key for f in parsed_findings)


def test_filter_empty_target_set_returns_empty(parsed_findings: list) -> None:
    """An empty target set filters everything out."""
    assert filter_to_target_categories(parsed_findings, set()) == []


def test_target_categories_constant_is_storage_crypto_network() -> None:
    """TARGET_CATEGORIES is the prototype's in-scope MASVS trio."""
    assert TARGET_CATEGORIES == {
        MasvsCategory.STORAGE,
        MasvsCategory.CRYPTO,
        MasvsCategory.NETWORK,
    }


def test_parse_covers_at_least_two_target_categories(parsed_findings: list) -> None:
    """The InsecureBank fixture must surface >=2 of the target trio."""
    cats = {f.masvs_category for f in parsed_findings}
    overlap = cats & TARGET_CATEGORIES
    assert len(overlap) >= 2, f"expected >=2 of {TARGET_CATEGORIES}, got {overlap}"


def test_filter_with_target_constant_keeps_only_subset(parsed_findings: list) -> None:
    """filter_to_target_categories with TARGET_CATEGORIES yields valid subset."""
    kept = filter_to_target_categories(parsed_findings, TARGET_CATEGORIES)
    assert kept, "expected at least one in-scope finding for InsecureBank"
    assert all(f.masvs_category in TARGET_CATEGORIES for f in kept)


def test_classify_finding_storage() -> None:
    """Hardcoded-secret titles classify into MASVS-STORAGE."""
    cat = classify_finding(
        title="Files may contain hardcoded sensitive information like passwords",
        description="...",
        section="code",
    )
    assert cat == MasvsCategory.STORAGE


def test_classify_finding_crypto() -> None:
    """Weak hash titles classify into MASVS-CRYPTO."""
    cat = classify_finding(
        title="MD5 is a weak hash known to have collisions",
        description="...",
        section="code",
    )
    assert cat == MasvsCategory.CRYPTO


def test_classify_finding_network() -> None:
    """SSL trust-all titles classify into MASVS-NETWORK."""
    cat = classify_finding(
        title="Insecure implementation of SSL, accepting all certificates",
        description="...",
        section="network",
    )
    assert cat == MasvsCategory.NETWORK


def test_classify_finding_not_in_target_trio_for_platform_finding() -> None:
    """Permission-section findings must not be misclassified as the target trio."""
    cat = classify_finding(
        title="App can be installed on a vulnerable unpatched Android version",
        description="...",
        section="permissions",
    )
    assert cat not in {
        MasvsCategory.STORAGE,
        MasvsCategory.CRYPTO,
        MasvsCategory.NETWORK,
    }
