"""Parser for MobSF v4.5 JSON reports.

MobSF 4.5 splits static-analysis findings across two top-level sections:

* ``appsec.{high,warning,info,secure,hotspot}`` - each is a list of
  ``{title, description, section}`` dicts. ``section`` is a free-form
  category like ``certificate``, ``manifest``, ``code``, ``network``,
  ``permissions``, ``secrets``, ``trackers``.
* ``manifest_analysis.manifest_findings`` - list of
  ``{rule, title, severity, description, name?, component?}`` dicts.

This module normalizes those two sources into ``ikusa.models.Finding``
objects, classified into ``MasvsCategory`` buckets. Findings that cannot
be classified by section, manifest rule, or keyword heuristic are
silently dropped: we never assign a "default" MASVS category.

Public API:

* ``classify_finding(title, description, section) -> MasvsCategory | None``
* ``parse_mobsf_report(data) -> list[Finding]``
* ``filter_to_target_categories(findings, targets) -> list[Finding]``
* ``TARGET_CATEGORIES`` - the prototype's in-scope MASVS subset
* ``MOBSF_SEVERITY_MAP`` - exposed for tests / downstream callers
"""

from __future__ import annotations

from typing import Any

from .models import Finding, MasvsCategory, Severity


# Prototype scope: only these three MASVS categories are fully triaged
# downstream. Surfaced as a module constant so Phase 6 (triage agent)
# can import the same source of truth instead of re-declaring the set.
TARGET_CATEGORIES: set[MasvsCategory] = {
    MasvsCategory.STORAGE,
    MasvsCategory.CRYPTO,
    MasvsCategory.NETWORK,
}


# Map free-form ``appsec.*[].section`` values to a primary MASVS bucket.
# Used as the first attempt at classification for appsec entries.
SECTION_TO_CATEGORY: dict[str, MasvsCategory] = {
    "certificate": MasvsCategory.NETWORK,
    "network": MasvsCategory.NETWORK,
    "manifest": MasvsCategory.PLATFORM,
    "permissions": MasvsCategory.PRIVACY,
    "code": MasvsCategory.CODE,
    "secrets": MasvsCategory.STORAGE,
    "trackers": MasvsCategory.PRIVACY,
}


# Keyword fallback applied to ``(title + description + section).lower()``.
# Order matters - first match wins, so put higher-precision tokens first.
# This table targets the three primary buckets (STORAGE/CRYPTO/NETWORK)
# heavily; secondary buckets (PLATFORM/AUTH/CODE/PRIVACY/RESILIENCE) are
# present so we can still distinguish them when section is unhelpful.
KEYWORD_TO_CATEGORY: list[tuple[str, MasvsCategory]] = [
    # --- MASVS-STORAGE ---
    ("hardcoded", MasvsCategory.STORAGE),
    ("hard-coded", MasvsCategory.STORAGE),
    ("hardcode", MasvsCategory.STORAGE),
    ("api key", MasvsCategory.STORAGE),
    ("sharedpref", MasvsCategory.STORAGE),
    ("shared preference", MasvsCategory.STORAGE),
    ("shared_pref", MasvsCategory.STORAGE),
    ("sqlite", MasvsCategory.STORAGE),
    ("allowbackup", MasvsCategory.STORAGE),
    ("allow_backup", MasvsCategory.STORAGE),
    ("can be backed up", MasvsCategory.STORAGE),
    ("external storage", MasvsCategory.STORAGE),
    ("world readable", MasvsCategory.STORAGE),
    ("world writable", MasvsCategory.STORAGE),
    # --- MASVS-CRYPTO ---
    ("md5", MasvsCategory.CRYPTO),
    ("sha1", MasvsCategory.CRYPTO),
    ("sha-1", MasvsCategory.CRYPTO),
    ("ecb mode", MasvsCategory.CRYPTO),
    ("ecb", MasvsCategory.CRYPTO),
    ("rc4", MasvsCategory.CRYPTO),
    (" des ", MasvsCategory.CRYPTO),
    ("weak hash", MasvsCategory.CRYPTO),
    ("weak cipher", MasvsCategory.CRYPTO),
    ("weak cryptograph", MasvsCategory.CRYPTO),
    ("predictable random", MasvsCategory.CRYPTO),
    ("insecure random", MasvsCategory.CRYPTO),
    ("cryptograph", MasvsCategory.CRYPTO),
    # Janus / v1 signature scheme weakness is a crypto/signing issue,
    # not a network transport issue. Anchor it explicitly so it does
    # not get swallowed by the "certificate" section default.
    ("janus", MasvsCategory.CRYPTO),
    ("v1 signature", MasvsCategory.CRYPTO),
    ("signature scheme", MasvsCategory.CRYPTO),
    # --- MASVS-NETWORK ---
    # NB: "ssl" is intentionally listed before generic "certificate" so
    # that "Insecure implementation of SSL" classifies as NETWORK rather
    # than via the certificate section default.
    ("ssl", MasvsCategory.NETWORK),
    ("tls", MasvsCategory.NETWORK),
    ("hostname verifier", MasvsCategory.NETWORK),
    ("trustmanager", MasvsCategory.NETWORK),
    ("trust manager", MasvsCategory.NETWORK),
    ("cleartext", MasvsCategory.NETWORK),
    ("http traffic", MasvsCategory.NETWORK),
    ("unencrypted traffic", MasvsCategory.NETWORK),
    ("certificate pinning", MasvsCategory.NETWORK),
    ("no certificate validation", MasvsCategory.NETWORK),
    ("accepting all certificates", MasvsCategory.NETWORK),
    # --- MASVS-PLATFORM ---
    ("exported", MasvsCategory.PLATFORM),
    ("strandhogg", MasvsCategory.PLATFORM),
    ("task hijacking", MasvsCategory.PLATFORM),
    ("intent", MasvsCategory.PLATFORM),
    ("webview", MasvsCategory.PLATFORM),
    ("content provider", MasvsCategory.PLATFORM),
    ("broadcast receiver", MasvsCategory.PLATFORM),
    # --- MASVS-CODE ---
    ("debuggable", MasvsCategory.CODE),
    ("debug mode", MasvsCategory.CODE),
    ("minify", MasvsCategory.CODE),
    ("obfuscat", MasvsCategory.CODE),
    ("vulnerable os", MasvsCategory.CODE),
    ("min sdk", MasvsCategory.CODE),
    ("unpatched android", MasvsCategory.CODE),
    # --- MASVS-RESILIENCE ---
    ("root detection", MasvsCategory.RESILIENCE),
    ("anti-debug", MasvsCategory.RESILIENCE),
    ("tamper", MasvsCategory.RESILIENCE),
    # --- MASVS-AUTH ---
    ("authentication", MasvsCategory.AUTH),
    ("biometric", MasvsCategory.AUTH),
    ("credential", MasvsCategory.AUTH),
    ("session", MasvsCategory.AUTH),
    # --- MASVS-PRIVACY ---
    ("personal data", MasvsCategory.PRIVACY),
    ("tracker", MasvsCategory.PRIVACY),
    ("critical permission", MasvsCategory.PRIVACY),
]


# Explicit manifest rule -> category. Anything not present here falls
# back to keyword heuristics on the manifest finding's title/description.
MANIFEST_RULE_TO_CATEGORY: dict[str, MasvsCategory] = {
    "app_allowbackup": MasvsCategory.STORAGE,
    "app_debuggable": MasvsCategory.CODE,
    "app_is_debuggable": MasvsCategory.CODE,
    "vulnerable_os_version": MasvsCategory.CODE,
    "cleartext_traffic": MasvsCategory.NETWORK,
    "exported_activity": MasvsCategory.PLATFORM,
    "exported_service": MasvsCategory.PLATFORM,
    "exported_provider": MasvsCategory.PLATFORM,
    "exported_receiver": MasvsCategory.PLATFORM,
    "explicitly_exported": MasvsCategory.PLATFORM,
    "intent_filter": MasvsCategory.PLATFORM,
    "task_affinity": MasvsCategory.PLATFORM,
    "task_hijacking": MasvsCategory.PLATFORM,
    "task_hijacking2": MasvsCategory.PLATFORM,
}


MOBSF_SEVERITY_MAP: dict[str, Severity] = {
    "high": Severity.HIGH,
    "warning": Severity.MEDIUM,
    "medium": Severity.MEDIUM,
    "hotspot": Severity.LOW,
    "info": Severity.INFO,
    "secure": Severity.INFO,
    "good": Severity.INFO,
    "low": Severity.LOW,
}


# Sections whose default mapping in ``SECTION_TO_CATEGORY`` should be
# overridden by keyword analysis when a keyword hit is available. These
# sections are catch-all buckets in MobSF that mix several MASVS
# categories:
#   - manifest:    allowBackup -> STORAGE, debuggable -> CODE,
#                  vulnerable_os -> CODE, exported/StrandHogg -> PLATFORM.
#   - certificate: TLS cert chain hygiene -> NETWORK, but Janus / v1
#                  signature weakness is a crypto/signing issue -> CRYPTO.
#   - code:        per-finding keyword decides STORAGE/CRYPTO/NETWORK/...
_REFINABLE_SECTIONS = {"manifest", "certificate", "code"}


def _keyword_lookup(haystack: str) -> MasvsCategory | None:
    for keyword, category in KEYWORD_TO_CATEGORY:
        if keyword in haystack:
            return category
    return None


def classify_finding(
    title: str,
    description: str,
    section: str | None = None,
) -> MasvsCategory | None:
    """Best-effort MASVS classification for a single MobSF finding.

    Order of resolution:

    1. If ``section`` maps directly to a category in
       ``SECTION_TO_CATEGORY`` and it is NOT a refinable section,
       return that mapping immediately.
    2. Otherwise (or for refinable sections), look up keywords in
       ``title + description + section``.
    3. As a last resort, return the section default if any.
    4. Return ``None`` if nothing classifies - callers must drop the
       finding rather than assign a default category.
    """
    section_norm = (section or "").lower().strip()
    section_default = SECTION_TO_CATEGORY.get(section_norm)

    if section_default is not None and section_norm not in _REFINABLE_SECTIONS:
        return section_default

    haystack = f"{title} {description} {section_norm}".lower()
    via_keyword = _keyword_lookup(haystack)
    if via_keyword is not None:
        return via_keyword

    return section_default


def _classify_manifest_entry(entry: dict[str, Any]) -> MasvsCategory | None:
    """Classify a manifest_findings entry, preferring explicit rule map."""
    rule = (entry.get("rule") or "").lower()
    if rule in MANIFEST_RULE_TO_CATEGORY:
        return MANIFEST_RULE_TO_CATEGORY[rule]
    return classify_finding(
        title=entry.get("title", ""),
        description=entry.get("description", ""),
        section="manifest",
    )


def _map_severity(raw: str | None) -> Severity:
    if raw is None:
        return Severity.INFO
    return MOBSF_SEVERITY_MAP.get(raw.lower(), Severity.INFO)


def _from_appsec(data: dict[str, Any]) -> list[Finding]:
    appsec = data.get("appsec") or {}
    out: list[Finding] = []
    # Iterate every bucket but emit each entry's severity from the bucket
    # name itself. info/secure end up as Severity.INFO and are filtered
    # out by parse_mobsf_report below.
    for bucket_name in ("high", "warning", "hotspot", "info", "secure"):
        bucket = appsec.get(bucket_name) or []
        if not isinstance(bucket, list):
            continue
        for idx, entry in enumerate(bucket):
            if not isinstance(entry, dict):
                continue
            category = classify_finding(
                title=entry.get("title", ""),
                description=entry.get("description", ""),
                section=entry.get("section"),
            )
            if category is None:
                continue
            title = entry.get("title") or "Untitled finding"
            description = entry.get("description") or ""
            severity = _map_severity(bucket_name)
            section = entry.get("section") or "unknown"
            finding_id = f"appsec-{bucket_name}-{idx:03d}"
            out.append(
                Finding(
                    id=finding_id,
                    title=title,
                    severity=severity,
                    masvs_category=category,
                    description=description,
                    raw_mobsf_key=f"appsec.{bucket_name}[{idx}]:{section}",
                )
            )
    return out


def _from_manifest(data: dict[str, Any]) -> list[Finding]:
    manifest = data.get("manifest_analysis") or {}
    entries = manifest.get("manifest_findings") or []
    if not isinstance(entries, list):
        return []

    out: list[Finding] = []
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        category = _classify_manifest_entry(entry)
        if category is None:
            continue
        rule = entry.get("rule") or f"manifest-{idx}"
        title = entry.get("title") or rule
        description = entry.get("description") or ""
        severity = _map_severity(entry.get("severity"))
        finding_id = f"manifest-{rule}-{idx:03d}"
        out.append(
            Finding(
                id=finding_id,
                title=title,
                severity=severity,
                masvs_category=category,
                description=description,
                raw_mobsf_key=f"manifest_analysis.manifest_findings[{idx}]:{rule}",
            )
        )
    return out


def parse_mobsf_report(data: dict[str, Any]) -> list[Finding]:
    """Parse appsec + manifest_analysis sections into Finding objects.

    Returns only findings classifiable into a MASVS category, with
    severity strictly greater than INFO (drops ``secure``/``good``/``info``).
    """
    findings: list[Finding] = []
    findings.extend(_from_appsec(data))
    findings.extend(_from_manifest(data))
    return [f for f in findings if f.severity > Severity.INFO]


def filter_to_target_categories(
    findings: list[Finding],
    targets: set[MasvsCategory],
) -> list[Finding]:
    """Keep only findings whose ``masvs_category`` is in ``targets``."""
    return [f for f in findings if f.masvs_category in targets]
