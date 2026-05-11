#!/usr/bin/env bash
# End-to-end smoke: start uvicorn, upload the InsecureBank APK, poll until done,
# download the PDF. Requires MobSF + Ollama already up.
set -euo pipefail

cd "$(dirname "$0")/.."

# Start the API in the background; capture PID so we can shut it down cleanly.
uv run uvicorn ikusa.api:app --port 9787 --log-level warning &
API_PID=$!
trap "kill $API_PID 2>/dev/null || true" EXIT

# Wait for uvicorn to start.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  curl -sf http://localhost:9787/health > /dev/null && break
  sleep 1
done

# Upload.
RESP=$(curl -sf -F "file=@../test_apks/insecurebankv2.apk" \
            -F "tier=compliance" \
            http://localhost:9787/scan)
SCAN_ID=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['scan_id'])")
echo "scan_id=$SCAN_ID"

# Poll.
for i in $(seq 1 60); do
  STATUS=$(curl -sf http://localhost:9787/scan/$SCAN_ID | python3 -c "import json,sys; d=json.load(sys.stdin); print(f\"{d['status']}|{d.get('stage','')}|{d.get('message','')}\")")
  echo "[$i] $STATUS"
  case "$STATUS" in
    done\|*) break ;;
    failed\|*) echo "PIPELINE FAILED"; exit 1 ;;
  esac
  sleep 5
done

# Download PDF.
curl -sf -o /tmp/ikusa_api_report.pdf http://localhost:9787/scan/$SCAN_ID/report
ls -lh /tmp/ikusa_api_report.pdf
file /tmp/ikusa_api_report.pdf
