"""Scan pipeline: MobSF -> parser -> LLM -> PDF.

Called from a FastAPI BackgroundTask. Persists state.json after each stage
so the frontend can poll progress.
"""

from __future__ import annotations

import time
from pathlib import Path

from ikusa.config import Settings
from ikusa.llm import LLMTriageClient
from ikusa.mobsf import MobSFClient
from ikusa.models import ScanResult
from ikusa.parser import (
    TARGET_CATEGORIES,
    filter_to_target_categories,
    parse_mobsf_report,
)
from ikusa.report import generate_pdf
from ikusa.score import compute_cra_score
from ikusa.state import ScanState, save_state


async def run_scan_pipeline(
    scan_id: str,
    apk_path: Path,
    apk_filename: str,
    settings: Settings,
) -> None:
    """End-to-end scan pipeline. Writes state.json + result.json + report.pdf
    under settings.scan_storage / scan_id. Any exception is captured into
    a 'failed' state instead of propagating."""

    started = time.monotonic()
    storage = settings.scan_storage
    scan_dir = storage / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)

    def _update(stage: str, message: str = "") -> None:
        save_state(
            ScanState(
                scan_id=scan_id,
                status="processing",
                stage=stage,  # type: ignore[arg-type]
                message=message,
            ),
            storage,
        )

    try:
        _update("decompiling", "Uploading APK to MobSF")
        mobsf = MobSFClient(
            base_url=settings.mobsf_url,
            api_key=settings.mobsf_api_key,
        )
        content = apk_path.read_bytes()
        file_hash = await mobsf.upload(content, apk_filename)

        _update("decompiling", f"MobSF scanning hash={file_hash[:12]}")
        await mobsf.scan(file_hash)
        raw = await mobsf.report_json(file_hash)

        _update("analyzing", "Classifying findings to MASVS categories")
        app_name = raw.get("app_name") or apk_filename
        package_name = raw.get("package_name", "unknown.package")
        all_findings = parse_mobsf_report(raw)
        findings = filter_to_target_categories(all_findings, TARGET_CATEGORIES)

        _update("triaging", f"LLM triaging {len(findings)} findings")
        llm = LLMTriageClient(
            provider=settings.llm_provider,  # type: ignore[arg-type]
            model=(
                settings.openai_model
                if settings.llm_provider == "openai"
                else settings.ollama_model
            ),
            api_key=settings.openai_api_key,
            ollama_url=settings.ollama_url,
        )
        triaged = await llm.triage(
            findings=findings,
            app_name=app_name,
            package_name=package_name,
        )

        score = compute_cra_score(triaged, categories_covered=len(TARGET_CATEGORIES))
        duration = time.monotonic() - started

        result = ScanResult(
            scan_id=scan_id,
            app_name=app_name,
            package_name=package_name,
            apk_hash=file_hash,
            cra_score=score,
            findings=triaged,
            categories_covered=list(TARGET_CATEGORIES),
            duration_seconds=duration,
        )

        (scan_dir / "result.json").write_text(
            result.model_dump_json(indent=2),
            encoding="utf-8",
        )

        _update("rendering", "Generating compliance PDF")
        generate_pdf(result, scan_dir / "report.pdf")

        save_state(
            ScanState(
                scan_id=scan_id,
                status="done",
                stage="done",
                message="Scan complete",
                app_name=app_name,
                package_name=package_name,
                cra_score=score,
                findings_count=len(triaged),
                duration_seconds=duration,
            ),
            storage,
        )

    except Exception as exc:  # noqa: BLE001 -- we want any failure captured
        save_state(
            ScanState(
                scan_id=scan_id,
                status="failed",
                stage="triaging",  # best-effort label
                error=f"{type(exc).__name__}: {exc}",
            ),
            storage,
        )
