"""CRA Readiness Score calculator.

The score is a 0-100 integer that summarises how compliance-ready an APK is.
The intent is to give end users a single comparable headline number that
moves down with each unfixed vulnerability and up when issues are addressed.

Formula (deliberately simple, easy to explain at the demo):

    base = 100 - 12 * count(HIGH) - 5 * count(MEDIUM) - 2 * count(LOW)
    base = clamp(base, 0, 100)

    coverage_ratio = clamp(categories_covered / 8, 0, 1)
    final = base * (0.5 + 0.5 * coverage_ratio)
    return round(final) clamped to [0, 100]

The coverage factor reflects that a report covering only 1 of 8 MASVS
categories cannot, in good faith, attest full compliance even with zero
findings -- so the maximum achievable score scales with coverage.
"""

from __future__ import annotations

from ikusa.models import Finding, Severity

_MAX_MASVS_CATEGORIES = 8

_PENALTY: dict[Severity, int] = {
    Severity.HIGH: 12,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
    Severity.INFO: 0,
}


def compute_cra_score(findings: list[Finding], categories_covered: int) -> int:
    base = 100
    for finding in findings:
        base -= _PENALTY.get(finding.severity, 0)
    base = max(base, 0)

    coverage = max(0, min(categories_covered, _MAX_MASVS_CATEGORIES))
    coverage_ratio = coverage / _MAX_MASVS_CATEGORIES
    adjusted = base * (0.5 + 0.5 * coverage_ratio)
    return max(0, min(100, int(round(adjusted))))
