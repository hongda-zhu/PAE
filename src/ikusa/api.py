"""FastAPI surface: POST /scan, GET /scan/{id}, GET /scan/{id}/report.

The actual heavy lifting happens in pipeline.run_scan_pipeline, invoked as
a BackgroundTask so the upload response returns immediately. The frontend
polls GET /scan/{id} to follow progress.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ikusa.auth import (
    SCANS_PER_MONTH,
    ApiKey,
    consume_credit,
    load_keys,
    require_api_key,
    save_keys,
)
from ikusa.billing import (
    PRODUCTS,
    create_session,
    credits_for_product,
    fulfill_session,
    load_sessions,
)
from ikusa.config import get_settings
from ikusa.pipeline import run_scan_pipeline
from ikusa.state import ScanState, list_states_for_user, load_state, save_state


app = FastAPI(title="IKUSA Compliance Scanner -- Prototype")


@app.post("/scan")
async def scan(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tier: str = Form("compliance"),
    api_key: ApiKey = Depends(require_api_key),
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

    # Consume one scan from the key's quota BEFORE enqueueing the pipeline.
    # Anonymous keys are not in the YAML store; they use the in-memory fallback
    # which has no persisted counter. Anonymous scans are tagged user_id=None
    # in state.json so /scans returns them under the anonymous bucket.
    if api_key.user_id != "anonymous":
        consume_credit(api_key, settings.api_keys_path)

    user_id = None if api_key.user_id == "anonymous" else api_key.user_id

    save_state(
        ScanState(
            scan_id=scan_id,
            status="processing",
            stage="uploaded",
            message=f"Received {file.filename} ({len(content)} bytes, tier={tier})",
            user_id=user_id,
        ),
        settings.scan_storage,
    )

    background_tasks.add_task(
        run_scan_pipeline,
        scan_id=scan_id,
        apk_path=apk_path,
        apk_filename=file.filename,
        settings=settings,
        user_id=user_id,
    )

    return JSONResponse({"scan_id": scan_id, "status": "processing"})


@app.get("/scans")
async def list_scans(
    api_key: ApiKey = Depends(require_api_key),
):
    """List scans belonging to the authenticated user (anonymous if no key)."""
    settings = get_settings()
    user_id = None if api_key.user_id == "anonymous" else api_key.user_id
    states = list_states_for_user(settings.scan_storage, user_id)
    return JSONResponse([s.model_dump(mode="json") for s in states])


@app.get("/account")
async def account_info(api_key: ApiKey = Depends(require_api_key)):
    """Return tier, quota cap, used, and credits for the authenticated key.

    Anonymous keys get the in-memory fallback state (free tier, 0 used, 0 credits).
    """
    cap = SCANS_PER_MONTH[api_key.tier]
    return {
        "user_id": api_key.user_id,
        "tier": api_key.tier,
        "scans_this_month": api_key.scans_this_month,
        "scans_cap": cap,
        "credits": api_key.credits,
        "month_anchor": api_key.month_anchor,
    }


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
    return FileResponse(
        result_file,
        media_type="application/json",
        filename=f"ikusa_result_{scan_id}.json",
        content_disposition_type="attachment",
    )


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


# --- Mock pay-per-scan billing (Stripe-shaped stub) ---


class CheckoutRequest(BaseModel):
    product_id: str  # "credits-10" | "credits-50" | "credits-200"


@app.post("/payment/checkout")
async def payment_checkout(
    body: CheckoutRequest,
    api_key: ApiKey = Depends(require_api_key),
):
    """Create a new mock checkout session. Mirrors Stripe Checkout API shape."""
    if api_key.user_id == "anonymous":
        raise HTTPException(401, "Login required to buy credits")
    if body.product_id not in PRODUCTS:
        raise HTTPException(400, f"Unknown product: {body.product_id}")

    settings = get_settings()
    session = create_session(api_key.key, body.product_id, settings.payment_sessions_path)
    return {
        "session_id": session.session_id,
        "checkout_url": f"/payment/mock?session={session.session_id}",
        "amount_cents": PRODUCTS[body.product_id]["amount_cents"],
        "credits": PRODUCTS[body.product_id]["credits"],
    }


@app.get("/payment/mock", response_class=HTMLResponse)
async def payment_mock_page(session: str):
    """Serve a fake Stripe-styled checkout page for a session."""
    settings = get_settings()
    sessions = load_sessions(settings.payment_sessions_path)
    sess = sessions.get(session)
    if sess is None:
        raise HTTPException(404, "Session not found")
    product = PRODUCTS[sess.product_id]
    # Inline HTML so we don't need to add another template file.
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>IKUSA Checkout (mock)</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f6f9fc; margin: 0; padding: 40px; }}
  .container {{ max-width: 480px; margin: 40px auto; background: white;
                border-radius: 8px; box-shadow: 0 7px 14px rgba(50,50,93,.10),
                                                   0 3px 6px rgba(0,0,0,.08);
                padding: 32px; }}
  h1 {{ font-size: 18px; margin: 0 0 4px 0; color: #424770; }}
  .product {{ color: #6b7c93; margin-bottom: 24px; }}
  .amount {{ font-size: 32px; font-weight: 600; color: #32325d; margin-bottom: 24px; }}
  .row {{ margin-bottom: 12px; }}
  label {{ display: block; font-size: 11px; color: #6b7c93;
           text-transform: uppercase; letter-spacing: .025em; }}
  input {{ width: 100%; padding: 10px 12px; border: 1px solid #e0e6ed;
           border-radius: 4px; font-size: 14px; box-sizing: border-box; }}
  button {{ width: 100%; padding: 12px; background: #5469d4; color: white;
            border: 0; border-radius: 4px; font-size: 15px; font-weight: 600;
            cursor: pointer; margin-top: 12px; }}
  button:hover {{ background: #4757b8; }}
  .mock-banner {{ background: #fff3cd; color: #856404; padding: 8px 12px;
                  border-radius: 4px; font-size: 12px; margin-bottom: 16px;
                  text-align: center; }}
  .note {{ font-size: 11px; color: #94a3b8; text-align: center;
           margin-top: 16px; }}
</style>
</head>
<body>
  <div class="container">
    <div class="mock-banner">MOCK CHECKOUT -- sin cargo real</div>
    <h1>IKUSA Compliance Scanner</h1>
    <p class="product">{product['label']}</p>
    <p class="amount">${product['amount_cents'] / 100:.2f} USD</p>

    <div class="row">
      <label>Numero de tarjeta</label>
      <input value="4242 4242 4242 4242" readonly>
    </div>
    <div class="row" style="display:flex; gap: 12px;">
      <div style="flex:1"><label>Caduca</label>
        <input value="12 / 28" readonly></div>
      <div style="flex:1"><label>CVC</label>
        <input value="123" readonly></div>
    </div>

    <form method="post" action="/payment/webhook">
      <input type="hidden" name="event_type" value="checkout.session.completed">
      <input type="hidden" name="session_id" value="{sess.session_id}">
      <button type="submit">Pagar ${product['amount_cents'] / 100:.2f}</button>
    </form>

    <p class="note">Powered by Stripe (mock).</p>
  </div>
</body>
</html>"""


@app.post("/payment/webhook")
async def payment_webhook(
    event_type: str = Form(...),
    session_id: str = Form(...),
):
    """Fulfillment endpoint. In real Stripe this is HMAC-verified; mock just trusts the form."""
    if event_type != "checkout.session.completed":
        # Real Stripe sends many event types; mock only handles this one.
        return {"received": True, "handled": False}

    settings = get_settings()
    try:
        sess = fulfill_session(session_id, settings.payment_sessions_path)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except RuntimeError as e:
        raise HTTPException(410, str(e))

    # Grant credits to the api_key that started the session.
    keys = load_keys(settings.api_keys_path)
    api_key = keys.get(sess.api_key)
    if api_key is None:
        raise HTTPException(500, "Underlying API key disappeared during fulfillment")
    api_key.credits += credits_for_product(sess.product_id)
    keys[api_key.key] = api_key
    save_keys(keys, settings.api_keys_path)

    # After fulfillment, redirect back to the app's main page. Use HTML
    # response so the form submit lands in the browser nicely.
    return HTMLResponse(
        """<!doctype html><meta charset='utf-8'>
        <script>window.location='/';</script>
        Payment recorded. Returning to app...""",
        status_code=200,
    )


# Serve the SPA frontend last so it does not shadow API routes.
# StaticFiles mounted at "/" is a wildcard that swallows any route registered
# AFTER it -- this mount MUST be the final declaration in this module.
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")
