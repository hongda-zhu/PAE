"""Smoke test: end-to-end PDF generation using real fixture + real LLM triage.

Hits Ollama at :11434 for triage, then writes a real PDF to /tmp.
Not part of pytest; run manually to see a real artifact.
"""

import asyncio
import json
from pathlib import Path

from ikusa.llm import LLMTriageClient
from ikusa.models import ScanResult
from ikusa.parser import (
    TARGET_CATEGORIES,
    filter_to_target_categories,
    parse_mobsf_report,
)
from ikusa.report import generate_pdf
from ikusa.score import compute_cra_score


async def main() -> None:
    fixture = Path("tests/fixtures/insecurebank_mobsf.json")
    data = json.loads(fixture.read_text())

    findings = filter_to_target_categories(
        parse_mobsf_report(data), TARGET_CATEGORIES,
    )

    client = LLMTriageClient(
        provider="ollama",
        model="qwen2.5:7b",
    )
    triaged = await client.triage(
        findings=findings,
        app_name=data.get("app_name", "InsecureBankv2"),
        package_name=data.get("package_name", "com.android.insecurebankv2"),
    )

    score = compute_cra_score(triaged, categories_covered=3)

    result = ScanResult(
        scan_id="smoke",
        app_name=data.get("app_name", "InsecureBankv2"),
        package_name=data.get("package_name", "com.android.insecurebankv2"),
        apk_hash=data.get("md5", "unknown"),
        cra_score=score,
        findings=triaged,
        categories_covered=list(TARGET_CATEGORIES),
        duration_seconds=0.0,
    )

    out = Path("/tmp/ikusa_smoke_report.pdf")
    generate_pdf(result, out)
    print(f"PDF written: {out}  ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
