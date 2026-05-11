
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch, tmp_path, mocker):
    # Override the SCAN_STORAGE so each test has an isolated dir.
    monkeypatch.setenv("SCAN_STORAGE", str(tmp_path))
    # Clear settings cache before import.

    # Force re-read of settings each call (no caching to override).
    from ikusa.api import app  # noqa: E402

    # Patch the pipeline so we don't actually hit MobSF / Ollama / WeasyPrint.
    async def _fake_pipeline(scan_id, apk_path, apk_filename, settings, user_id=None):
        from ikusa.state import ScanState, save_state

        save_state(
            ScanState(
                scan_id=scan_id,
                status="done",
                stage="done",
                app_name="MockApp",
                package_name="com.mock.app",
                cra_score=72,
                findings_count=4,
                duration_seconds=1.2,
                user_id=user_id,
            ),
            settings.scan_storage,
        )

    mocker.patch("ikusa.api.run_scan_pipeline", side_effect=_fake_pipeline)

    return TestClient(app)


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_scan_endpoint_returns_scan_id(client):
    resp = client.post(
        "/scan",
        files={"file": ("test.apk", b"FAKEAPK", "application/octet-stream")},
        data={"tier": "compliance"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "scan_id" in data
    assert data["status"] == "processing"
    assert len(data["scan_id"]) == 12


def test_scan_status_after_completion(client):
    resp = client.post(
        "/scan",
        files={"file": ("test.apk", b"FAKEAPK", "application/octet-stream")},
    )
    scan_id = resp.json()["scan_id"]
    # BackgroundTasks in TestClient run synchronously AFTER the response.
    status = client.get(f"/scan/{scan_id}").json()
    assert status["status"] == "done"
    assert status["cra_score"] == 72
    assert status["app_name"] == "MockApp"


def test_scan_status_404_for_unknown(client):
    resp = client.get("/scan/does_not_exist")
    assert resp.status_code == 404


def test_scan_missing_file_returns_422(client):
    resp = client.post("/scan", data={"tier": "compliance"})
    assert resp.status_code == 422


def test_root_returns_static_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "IKUSA" in body
    # The page must reference our scan endpoint, not a mock.
    assert "/scan" in body


def test_scan_report_404_when_not_ready(client):
    resp = client.post(
        "/scan",
        files={"file": ("test.apk", b"FAKEAPK", "application/octet-stream")},
    )
    scan_id = resp.json()["scan_id"]
    # Mock pipeline never wrote a PDF -- report endpoint must 404 cleanly.
    pdf_resp = client.get(f"/scan/{scan_id}/report")
    assert pdf_resp.status_code == 404


def test_list_scans_returns_empty_for_new_user(client):
    resp = client.get("/scans")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_scans_after_scan(client):
    post = client.post(
        "/scan",
        files={"file": ("dummy.apk", b"FAKE", "application/octet-stream")},
    )
    scan_id = post.json()["scan_id"]

    resp = client.get("/scans")
    assert resp.status_code == 200
    listed = resp.json()
    assert any(s["scan_id"] == scan_id for s in listed)


def test_list_scans_scopes_by_authenticated_key(client, tmp_path):
    # Drive the filter by writing ScanState directly into the per-test scan
    # storage (tmp_path is also the SCAN_STORAGE per the fixture). One scan
    # is tagged with user_id=demo, another stays anonymous (user_id=None).
    from ikusa.state import ScanState, save_state

    save_state(
        ScanState(scan_id="alice1", status="done", stage="done", user_id="demo"),
        tmp_path,
    )
    save_state(
        ScanState(scan_id="anon1", status="done", stage="done", user_id=None),
        tmp_path,
    )

    # The api_keys.yaml shipped under data/ has ikusa_sk_demo with user_id=demo;
    # use it so the GET /scans request is scoped to that user_id.
    auth_resp = client.get(
        "/scans",
        headers={"Authorization": "ikusa_sk_demo"},
    )
    assert auth_resp.status_code == 200
    auth_ids = {s["scan_id"] for s in auth_resp.json()}
    assert "alice1" in auth_ids
    assert "anon1" not in auth_ids

    # Anonymous request must only see the anon-tagged scan.
    anon_resp = client.get("/scans")
    assert anon_resp.status_code == 200
    anon_ids = {s["scan_id"] for s in anon_resp.json()}
    assert "anon1" in anon_ids
    assert "alice1" not in anon_ids


def test_list_scans_rejects_invalid_api_key(client):
    resp = client.get("/scans", headers={"Authorization": "ikusa_sk_NEVER_EXISTS"})
    assert resp.status_code == 401
