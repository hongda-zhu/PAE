# IKUSA Prototype -- Status (2026-05-11)

## What works end-to-end

- Upload APK via web UI (`http://localhost:9000`) or `curl POST /scan`
- MobSF static analysis (Docker, port 8000)
- MASVS classification (STORAGE / CRYPTO / NETWORK / ...)
- LLM triage via local Ollama qwen2.5:7b (port 11434)
- CRA Annex I article mapping
- PDF compliance report (Docker WeasyPrint, ~20 KB output)

## Verified by

- `uv run pytest -v` -- 66 tests pass (52 unit + 14 integration, 0 fail)
- `uv run python scripts/smoke_pdf.py` -- generates `/tmp/ikusa_smoke_report.pdf`
- `bash scripts/smoke_api.sh` -- end-to-end via running uvicorn, produces `/tmp/ikusa_api_report.pdf` (20 KB, real PDF v1.7)

## Architecture (overview)

```
Browser ---HTTP---> FastAPI (uvicorn :9000)
                       |
                  BackgroundTask
                  /        \         \                \
              MobSF      Parser     LLM (Ollama)    WeasyPrint
            (:8000)    (in-proc)    (:11434)       (docker run)
                  \        /         /                /
                   state.json + result.json + report.pdf
                   under /tmp/ikusa-scans/{scan_id}/
```

## Run the stack

```bash
make install            # uv sync --extra dev
make mobsf-up           # docker compose up -d mobsf
make ollama-up          # docker compose up -d ollama
make weasyprint-build   # docker build ikusa-weasyprint:latest
make run                # uv run uvicorn ikusa.api:app --port 9000
```

Browser: http://localhost:9000

## Known gaps (deferred)

- No auth, no rate limit, no multi-tenant.
- No persistent DB; state lives under /tmp.
- LLM falls back to placeholder text if Ollama is unreachable (no auto-retry).
- Only MASVS STORAGE/CRYPTO/NETWORK rendered; other 5 categories shown as "no cubierto" / N/A.
- The InsecureBank fixture has no NETWORK findings; demo will show STORAGE+CRYPTO only.
- No tests against multi-APK or concurrency.
- LLM triage on CPU-only Ollama runs ~3 minutes for 4 findings; smoke_api.sh polls every 5 s for up to 60 iterations (5 min) and that headroom is consumed in practice.

## Repo state

- Branch: master
- Commits: 11 after Phase 7 commit
- Tests: 66 passing
- Remote: none configured (local-only)
