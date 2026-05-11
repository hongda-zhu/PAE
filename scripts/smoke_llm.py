"""Integration smoke test: hit real Ollama with real fixture data.

Not part of the pytest suite -- this is a manual sanity check that the
prompt + Ollama qwen2.5:7b combination produces usable triage. Run it
directly after `make ollama-up` to see real LLM output.
"""

import asyncio
import json
from pathlib import Path

from ikusa.llm import LLMTriageClient
from ikusa.parser import filter_to_target_categories, parse_mobsf_report, TARGET_CATEGORIES


async def main() -> None:
    fixture = Path("tests/fixtures/insecurebank_mobsf.json")
    data = json.loads(fixture.read_text())

    findings = filter_to_target_categories(
        parse_mobsf_report(data),
        TARGET_CATEGORIES,
    )
    print(f"Input findings: {len(findings)}")
    for f in findings:
        print(f"  {f.id}: {f.title[:60]}")
    print()

    client = LLMTriageClient(
        provider="ollama",
        model="qwen2.5:7b",
        ollama_url="http://localhost:11434",
    )

    triaged = await client.triage(
        findings=findings,
        app_name=data.get("app_name", "InsecureBankv2"),
        package_name=data.get("package_name", "com.android.insecurebankv2"),
    )

    print(f"Triaged: {len(triaged)}")
    for t in triaged:
        print(f"  [P{t.priority}] {t.id}: {t.title[:50]}")
        print(f"    -> {t.explanation}")
        print(f"    fix: {t.remediation}")
        print(f"    cra: {t.cra_articles}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
