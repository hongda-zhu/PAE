
from ikusa.state import ScanState, load_state, save_state


def test_save_and_load_roundtrip(tmp_path):
    state = ScanState(
        scan_id="abc",
        status="processing",
        stage="decompiling",
        message="upload received",
    )
    save_state(state, tmp_path)
    loaded = load_state("abc", tmp_path)
    assert loaded is not None
    assert loaded.scan_id == "abc"
    assert loaded.status == "processing"
    assert loaded.stage == "decompiling"


def test_load_missing_returns_none(tmp_path):
    assert load_state("never", tmp_path) is None


def test_state_writes_per_scan_dir(tmp_path):
    state = ScanState(scan_id="abc", status="processing", stage="uploaded")
    save_state(state, tmp_path)
    state_file = tmp_path / "abc" / "state.json"
    assert state_file.exists()


def test_state_records_done_with_score(tmp_path):
    state = ScanState(
        scan_id="abc",
        status="done",
        stage="done",
        cra_score=72,
        findings_count=6,
        app_name="TestApp",
    )
    save_state(state, tmp_path)
    loaded = load_state("abc", tmp_path)
    assert loaded.status == "done"
    assert loaded.cra_score == 72
    assert loaded.findings_count == 6


def test_state_failed_carries_error(tmp_path):
    state = ScanState(
        scan_id="abc",
        status="failed",
        stage="triaging",
        error="ollama unreachable",
    )
    save_state(state, tmp_path)
    loaded = load_state("abc", tmp_path)
    assert loaded.status == "failed"
    assert loaded.error == "ollama unreachable"
