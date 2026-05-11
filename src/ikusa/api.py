"""FastAPI surface: POST /scan, GET /scan/{id}, GET /scan/{id}/report.

The actual heavy lifting happens in pipeline.run_scan_pipeline, invoked as
a BackgroundTask so the upload response returns immediately. The frontend
polls GET /scan/{id} to follow progress.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ikusa.config import get_settings
from ikusa.pipeline import run_scan_pipeline
from ikusa.state import ScanState, load_state, save_state


app = FastAPI(title="IKUSA Compliance Scanner -- Prototype")


@app.post("/scan")
async def scan(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tier: str = Form("compliance"),
):
    """Accept an APK upload, kick off the pipeline, return scan_id immediately."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")

    settings = get_settings()
    scan_id = uuid.uuid4().hex[:12]
    scan_dir = settings.scan_storage / scan_id
    scan_dir.mkdir(parents=True, exist_ok=True)

    apk_path = scan_dir / "input.apk"
    content = await file.read()
    apk_path.write_bytes(content)

    save_state(
        ScanState(
            scan_id=scan_id,
            status="processing",
            stage="uploaded",
            message=f"Received {file.filename} ({len(content)} bytes, tier={tier})",
        ),
        settings.scan_storage,
    )

    background_tasks.add_task(
        run_scan_pipeline,
        scan_id=scan_id,
        apk_path=apk_path,
        apk_filename=file.filename,
        settings=settings,
    )

    return JSONResponse({"scan_id": scan_id, "status": "processing"})


@app.get("/scan/{scan_id}")
async def get_scan(scan_id: str):
    settings = get_settings()
    state = load_state(scan_id, settings.scan_storage)
    if state is None:
        raise HTTPException(status_code=404, detail="scan not found")
    return JSONResponse(state.model_dump(mode="json"))


@app.get("/scan/{scan_id}/result")
async def get_scan_result(scan_id: str):
    """Full ScanResult JSON (findings, CRA articles, etc.). Available once status == done."""
    settings = get_settings()
    result_file = settings.scan_storage / scan_id / "result.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="scan result not available yet")
    return FileResponse(result_file, media_type="application/json")


@app.get("/scan/{scan_id}/report")
async def get_scan_report(scan_id: str):
    settings = get_settings()
    pdf_path = settings.scan_storage / scan_id / "report.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="report not available yet")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"ikusa_compliance_{scan_id}.pdf",
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve the SPA frontend last so it does not shadow API routes.
# StaticFiles mounted at "/" is a wildcard that swallows any route registered
# AFTER it -- this mount MUST be the final declaration in this module.
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
