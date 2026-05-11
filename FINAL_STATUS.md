# IKUSA Prototype -- Status (2026-05-11)

## What works end-to-end

- Upload APK via web UI (`http://localhost:9787`) or `curl POST /scan`
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
Browser ---HTTP---> FastAPI (uvicorn :9787)
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
make run                # uv run uvicorn ikusa.api:app --port 9787
```

Browser: http://localhost:9787

## Known gaps (deferred)

- No auth, no rate limit, no multi-tenant.
- No persistent DB; state lives under /tmp.
- LLM falls back to placeholder text if Ollama is unreachable (no auto-retry).
- Only MASVS STORAGE/CRYPTO/NETWORK rendered; other 5 categories shown as "no cubierto" / N/A.
- The InsecureBank fixture has no NETWORK findings; demo will show STORAGE+CRYPTO only.
- No tests against multi-APK or concurrency.
- LLM triage on CPU-only Ollama runs ~3 minutes for 4 findings; smoke_api.sh polls every 5 s for up to 60 iterations (5 min) and that headroom is consumed in practice.

## Repo state

- Branch: master (tracking `origin/master`)
- Commits: 17 (Phase 0-7 + CI workflow + docs sync + port change + post-push sync)
- Tests: 66 passing, `ruff check` clean
- Remote: `git@github.com:hongda-zhu/PAE.git` (pushed 2026-05-11)
- Author identity: `Hongda Zhu <hongdazhubcn@gmail.com>` for all commits
- CI: GitHub Actions workflow at `.github/workflows/test.yml` runs on every push
- CI: `.github/workflows/test.yml` runs `ruff check` + `pytest --deselect tests/test_report.py`
  (deselect because report tests need Docker; CI uses a clean Ubuntu runner)

## Demo prep state (overnight autonomous run)

- Ollama qwen2.5:7b model is **pre-warmed and kept resident** (`keep_alive=60m`).
  First scan after warm-up should still take ~3 min for triage but the model
  weights don't have to be reloaded from disk.
- MobSF has the InsecureBankv2 hash `5ee4829065640f9c936ac861d1650ffc` cached
  from prior smoke runs; the "decompiling" stage on a repeat scan of the same
  APK is near-instant.
- Demo backup PDF saved at `apkplan/demo_assets/insecurebank_qwen7b_20260511.pdf`
  (the same artifact `scripts/smoke_api.sh` produced, kept outside the repo).
- Attempted to pull qwen2.5:3b to halve LLM latency; the Ollama registry
  (`registry.ollama.ai`) timed out from this network. Stuck with 7b.

## Quick demo run (10 seconds to start)

```bash
cd apkplan/ikusa-prototype
make run                           # starts uvicorn on :9787
# Browser: http://localhost:9787
# Drop in: ../test_apks/insecurebankv2.apk
# Pick tier "Compliance PDF"
# Wait ~3 min on the "Triage IA" stage (live message updates every 2s)
# Score: 50/100 + 4 findings + PDF download
```
