import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ikusa.llm import LLMTriageClient
from ikusa.models import Finding, MasvsCategory, Severity

_FIXTURE = Path(__file__).parent / "fixtures" / "diva_llm_response.json"


def _finding(fid: str, cat: MasvsCategory = MasvsCategory.STORAGE) -> Finding:
    return Finding(
        id=fid,
        title=f"Title {fid}",
        severity=Severity.HIGH,
        masvs_category=cat,
        description=f"Description for {fid}",
    )


@pytest.mark.asyncio
async def test_empty_findings_returns_empty():
    client = LLMTriageClient(provider="ollama", model="qwen2.5:7b")
    result = await client.triage(
        findings=[], app_name="X", package_name="com.x",
    )
    assert result == []


@pytest.mark.asyncio
async def test_triage_merges_llm_output_into_findings(mocker):
    raw = json.loads(_FIXTURE.read_text())
    client = LLMTriageClient(provider="ollama", model="qwen2.5:7b")
    mocker.patch.object(client, "_chat_json", AsyncMock(return_value=raw))

    inputs = [
        _finding("APPSEC-0"),
        _finding("MANIFEST-app_allowbackup", MasvsCategory.STORAGE),
    ]
    result = await client.triage(
        findings=inputs, app_name="DIVA", package_name="jakhar.aseem.diva",
    )
    assert len(result) == 2
    by_id = {t.id: t for t in result}
    assert by_id["APPSEC-0"].priority == 1
    assert "credenciales" in by_id["APPSEC-0"].explanation
    assert "Annex I (1)(h)" in by_id["APPSEC-0"].cra_articles


@pytest.mark.asyncio
async def test_findings_omitted_by_llm_get_placeholder_triage(mocker):
    raw = {"triaged": []}  # LLM returned nothing
    client = LLMTriageClient(provider="ollama", model="qwen2.5:7b")
    mocker.patch.object(client, "_chat_json", AsyncMock(return_value=raw))

    inputs = [_finding("APPSEC-0")]
    result = await client.triage(
        findings=inputs, app_name="X", package_name="com.x",
    )
    assert len(result) == 1
    assert result[0].priority == 3
    assert "[sin triaje LLM]" in result[0].explanation


@pytest.mark.asyncio
async def test_hallucinated_ids_are_dropped(mocker):
    raw = {
        "triaged": [
            {
                "id": "FAKE-999",
                "priority": 1,
                "explanation": "made up",
                "remediation": "made up",
                "cra_articles": [],
            },
        ],
    }
    client = LLMTriageClient(provider="ollama", model="qwen2.5:7b")
    mocker.patch.object(client, "_chat_json", AsyncMock(return_value=raw))

    inputs = [_finding("APPSEC-0")]
    result = await client.triage(
        findings=inputs, app_name="X", package_name="com.x",
    )
    # FAKE-999 must NOT appear; only APPSEC-0 with placeholder.
    assert len(result) == 1
    assert result[0].id == "APPSEC-0"
    assert result[0].priority == 3


@pytest.mark.asyncio
async def test_results_sorted_by_priority_then_severity_desc(mocker):
    raw = {
        "triaged": [
            {
                "id": "low-priority",
                "priority": 3,
                "explanation": "x",
                "remediation": "x",
                "cra_articles": [],
            },
            {
                "id": "high-priority",
                "priority": 1,
                "explanation": "x",
                "remediation": "x",
                "cra_articles": [],
            },
        ],
    }
    client = LLMTriageClient(provider="ollama", model="qwen2.5:7b")
    mocker.patch.object(client, "_chat_json", AsyncMock(return_value=raw))

    inputs = [_finding("low-priority"), _finding("high-priority")]
    result = await client.triage(
        findings=inputs, app_name="X", package_name="com.x",
    )
    assert [r.id for r in result] == ["high-priority", "low-priority"]


@pytest.mark.asyncio
async def test_malformed_json_string_response_still_parses(mocker):
    # Some Ollama 7B model outputs come back as JSON-string-encoded twice.
    raw = '{"triaged": []}'  # str not dict
    client = LLMTriageClient(provider="ollama", model="qwen2.5:7b")
    mocker.patch.object(
        client, "_chat_json", AsyncMock(return_value=raw),
    )
    result = await client.triage(
        findings=[_finding("x")], app_name="X", package_name="com.x",
    )
    # Should not crash; should emit placeholder for the input.
    assert len(result) == 1
    assert result[0].id == "x"
    assert result[0].priority == 3
