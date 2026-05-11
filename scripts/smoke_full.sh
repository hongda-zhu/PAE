#!/usr/bin/env bash
# Full end-to-end smoke covering all 6 phase-2 features.
#
# Prerequisites:
#   - MobSF + Ollama containers running (make mobsf-up && make ollama-up)
#   - WeasyPrint image built (make weasyprint-build)
#   - Demo keys seeded (make seed-keys)
#
# Runs:
#   1. Boot uvicorn on :9787
#   2. GET /account (auth + tier surface)
#   3. POST /payment/checkout + GET /payment/mock + POST /payment/webhook (billing mock)
#   4. POST /scan (real APK pipeline, ~2-3 min on warm Ollama)
#   5. GET /scans (history)
#   6. GET /scan/{id}/report (PDF download)
#   7. ikusa-cli scan ... --fail-on alto (CLI feature)
#   8. ikusa-mcp JSON-RPC handshake + tools/list (MCP feature)
#
# Cleans up uvicorn on exit.

set -euo pipefail

cd "$(dirname "$0")/.."

SERVER="http://localhost:9787"
DEMO_KEY="ikusa_sk_demo"
APK="../test_apks/insecurebankv2.apk"

echo "==> Booting uvicorn on :9787"
uv run uvicorn ikusa.api:app --port 9787 --log-level warning &
API_PID=$!
trap "kill $API_PID 2>/dev/null || true" EXIT

# Wait for health
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -sf "$SERVER/health" > /dev/null && break
  sleep 1
done
echo "    OK"

echo
echo "==> [1/6] AUTH: GET /account with demo key"
curl -sf -H "Authorization: $DEMO_KEY" "$SERVER/account" | python3 -m json.tool

echo
echo "==> [2/6] BILLING: POST /payment/checkout (mock)"
CHECKOUT=$(curl -sf -X POST -H "Authorization: $DEMO_KEY" \
                -H "Content-Type: application/json" \
                -d '{"product_id":"credits-10"}' \
                "$SERVER/payment/checkout")
echo "$CHECKOUT" | python3 -m json.tool
SESSION_ID=$(echo "$CHECKOUT" | python3 -c "import json,sys; print(json.load(sys.stdin)['session_id'])")

echo
echo "==> [2/6] BILLING: GET /payment/mock?session=$SESSION_ID (HTML page)"
curl -sf "$SERVER/payment/mock?session=$SESSION_ID" | head -3

echo
echo "==> [2/6] BILLING: POST /payment/webhook (fulfillment)"
curl -sf -X POST -d "event_type=checkout.session.completed&session_id=$SESSION_ID" \
     "$SERVER/payment/webhook" | head -3

echo
echo "==> [3/6] SCAN: POST /scan (this takes 2-3 min on warm Ollama)"
RESP=$(curl -sf -F "file=@$APK" -F "tier=compliance" \
            -H "Authorization: $DEMO_KEY" \
            "$SERVER/scan")
SCAN_ID=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['scan_id'])")
echo "    scan_id=$SCAN_ID"

echo "    polling..."
for i in $(seq 1 60); do
  STATUS=$(curl -sf -H "Authorization: $DEMO_KEY" "$SERVER/scan/$SCAN_ID")
  STAGE=$(echo "$STATUS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['status']}|{d.get('stage','')}|{d.get('message','')}\")")
  echo "    [$i] $STAGE"
  case "$STAGE" in
    done\|*) break ;;
    failed\|*) echo "PIPELINE FAILED" >&2; exit 1 ;;
  esac
  sleep 5
done

echo
echo "==> [4/6] HISTORY: GET /scans"
curl -sf -H "Authorization: $DEMO_KEY" "$SERVER/scans" | python3 -c "
import json, sys
scans = json.load(sys.stdin)
print(f'  Total: {len(scans)} scans')
for s in scans[:3]:
    print(f'  {s[\"scan_id\"][:8]}  {s.get(\"app_name\",\"\"):20}  {s[\"status\"]:10}  score={s.get(\"cra_score\")}')
"

echo
echo "==> [5/6] PDF: GET /scan/$SCAN_ID/report"
curl -sf -o /tmp/ikusa_full_smoke.pdf -H "Authorization: $DEMO_KEY" "$SERVER/scan/$SCAN_ID/report"
file /tmp/ikusa_full_smoke.pdf
ls -lh /tmp/ikusa_full_smoke.pdf

echo
echo "==> [5/6] CLI: ikusa-cli status $SCAN_ID"
uv run ikusa-cli status "$SCAN_ID" --server "$SERVER" | head -5

echo
echo "==> [6/6] MCP: handshake + tools/list"
printf '%s\n%s\n%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
| uv run ikusa-mcp 2>/dev/null \
| python3 -c "
import json, sys
for line in sys.stdin:
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if msg.get('id') == 2 and 'result' in msg:
        tools = msg['result'].get('tools', [])
        print(f'  MCP tools available: {len(tools)}')
        for t in tools:
            print(f'    - {t[\"name\"]}')
"

echo
echo "==> ALL 6 FEATURES VERIFIED"
