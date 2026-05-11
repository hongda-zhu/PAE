from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ikusa.config import Settings
from ikusa.pipeline import run_scan_pipeline
from ikusa.state import load_state


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        mobsf_url="http://mobsf:8000",
        mobsf_api_key="test-key",
        llm_provider="ollama",
        ollama_url="http://ollama:11434",
        ollama_model="qwen2.5:7b",
        scan_storage=tmp_path,
    )


@pytest.mark.asyncio
async def test_pipeline_writes_done_state(tmp_path, mocker):
    apk = tmp_path / "in.apk"
    apk.write_bytes(b"FAKEAPK")

    mocker.patch(
        "ikusa.pipeline.MobSFClient.upload",
        new=AsyncMock(return_value="abc123"),
    )
    mocker.patch(
        "ikusa.pipeline.MobSFClient.scan",
        new=AsyncMock(return_value=None),
    )
    mocker.patch(
        "ikusa.pipeline.MobSFClient.report_json",
        new=AsyncMock(
            return_value={
                "app_name": "FakeApp",
                "package_name": "com.fake.app",
                "appsec": {"high": [], "warning": [], "info": [], "secure": [], "hotspot": []},
                "manifest_analysis": {"manifest_findings": []},
                "code_analysis": {"findings": {}},
            }
        ),
    )
    mocker.patch(
        "ikusa.pipeline.LLMTriageClient.triage",
        new=AsyncMock(return_value=[]),
    )
    mocker.patch("ikusa.pipeline.generate_pdf", return_value=tmp_path / "out.pdf")

    await run_scan_pipeline(
        scan_id="abc",
        apk_path=apk,
        apk_filename="in.apk",
        settings=_settings(tmp_path),
    )

    state = load_state("abc", tmp_path)
    assert state is not None
    assert state.status == "done"
    assert state.app_name == "FakeApp"


@pytest.mark.asyncio
async def test_pipeline_writes_failed_state_on_mobsf_error(tmp_path, mocker):
    apk = tmp_path / "in.apk"
    apk.write_bytes(b"FAKEAPK")

    mocker.patch(
        "ikusa.pipeline.MobSFClient.upload",
        new=AsyncMock(side_effect=RuntimeError("connection refused")),
    )

    await run_scan_pipeline(
        scan_id="abc",
        apk_path=apk,
        apk_filename="in.apk",
        settings=_settings(tmp_path),
    )

    state = load_state("abc", tmp_path)
    assert state is not None
    assert state.status == "failed"
    assert "connection refused" in state.error
