# Fixture capture notes (Phase 1)

Captured a REAL MobSF v4.5.0 static-analysis report for InsecureBankv2.apk.

- APK MD5: `5ee4829065640f9c936ac861d1650ffc`
- Scan wall time: ~16 s on the dev box
- Report size: ~800 KB JSON

## MobSF v4.5 schema gotcha for Phase 2

The Phase 1 brief assumed findings live under `code_analysis.findings.*`.
In MobSF v4.5 that key is present but EMPTY for this APK (`{}`).

Real findings are split across two places in the report:

1. `appsec` -- aggregated unified findings buckets:
   - `appsec.high` (list of `{title, description, section}`)
   - `appsec.warning` (same shape)
   - `appsec.info`, `appsec.secure`, `appsec.hotspot` (same shape)
   - `appsec.security_score` (overall 0-100, e.g. 28 for InsecureBank)

2. `manifest_analysis.manifest_findings` -- list of
   `{rule, title, severity, description, name, ...}` per AndroidManifest issue.

Counts for the captured InsecureBankv2 fixture:
- appsec.high: 7
- appsec.warning: 9
- appsec.hotspot: 1
- manifest_findings: 13
- Total substantive findings: 30

Phase 2 parser must therefore key off `appsec.*` and
`manifest_analysis.manifest_findings`, NOT `code_analysis.findings`.

## How to re-capture (idempotent)

```bash
cd ikusa-prototype
docker compose up -d mobsf
# wait for HTTP 302 on :8000 (~40s on first boot, instant on restart)
source .env
APIKEY="$MOBSF_API_KEY"
cp ../test_apks/insecurebankv2.apk /tmp/insecurebank.apk
RESP=$(curl -fsS -F "file=@/tmp/insecurebank.apk" -H "Authorization: $APIKEY" \
            http://localhost:8000/api/v1/upload)
HASH=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['hash'])")
curl -fsS --max-time 900 -X POST -d "scan_type=apk&hash=$HASH&file_name=insecurebank.apk" \
     -H "Authorization: $APIKEY" http://localhost:8000/api/v1/scan > /dev/null
curl -fsS -X POST -d "hash=$HASH" -H "Authorization: $APIKEY" \
     http://localhost:8000/api/v1/report_json \
     -o tests/fixtures/insecurebank_mobsf.json
```

## Compose-volume gotcha (already worked around)

MobSF runs as uid 9901; mounting an empty Docker named volume on
`/home/mobsf/.MobSF` creates a root-owned directory the container
cannot write, so it crash-loops with
`PermissionError: '/home/mobsf/.MobSF/config.py'`.

Workaround applied in `docker-compose.yml`: drop the named volume for
`mobsf`. MobSF state (incl. REST API key) is regenerated on every
`docker compose down`. Capture the key once and pin it in `.env`.
