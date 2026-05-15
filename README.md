# IKUSA Compliance Scanner -- Prototype

Automated MASVS / CRA compliance scanner for Android APKs.

## Requirements

- Python >= 3.11
- Docker (for MobSF + Ollama + WeasyPrint sandboxes)
- ~10 GB free disk (MobSF image + Qwen2.5-7B model)
- CPU-only is supported; GPU dramatically speeds up the LLM stage.

## First-time setup

```bash
cp .env.example .env
make install                 # uv sync
make mobsf-up                # MobSF on :8000
make ollama-up               # Ollama on :11434
docker exec ikusa-ollama ollama pull qwen2.5:7b   # ~5 GB download
make weasyprint-build        # builds ikusa-weasyprint:latest
make seed-keys               # 5 demo API keys in data/api_keys.yaml

# Capture the MobSF REST API key from container logs and pin it in .env:
docker logs ikusa-mobsf 2>&1 | grep -m1 "REST API Key" | awk '{print $NF}'
# Paste the value into MOBSF_API_KEY=... in .env
```

> **Important -- the MobSF key is not stable.** MobSF runs as uid 9901 and a
> Docker named volume would be root-owned and unwritable, so the prototype
> intentionally keeps MobSF state in the container layer (no volume). The
> consequence: the REST API key is **regenerated every time the MobSF
> container is recreated** (`docker compose down`, image pull, host reboot).
> After any restart you must re-run the `docker logs ... grep "REST API Key"`
> command above and update `MOBSF_API_KEY` in `.env`, or every scan fails with
> a silent MobSF 401. Ollama's model lives in the `ollama-data` named volume
> and is preserved across restarts.

## Run

```bash
make run
```

Open `http://localhost:9787`, drop an APK in the dropzone, wait, download the
PDF. CPU triage with Qwen2.5-7B takes ~3 minutes for 4-8 findings.

## LLM provider

Triage runs on a local Ollama model by default (`LLM_PROVIDER=ollama`), which
is the slow path (~3 min on CPU). To trade self-hosting for speed, switch to
OpenAI in `.env`:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini      # ~10 s instead of ~3 min
```

No code change or restart of the Docker stack is needed -- only `make run`
must be restarted to reload `.env`.

### Environment variables (`.env`)

| Variable | Purpose |
|----------|---------|
| `MOBSF_URL` | MobSF REST base URL (default `http://localhost:8000`) |
| `MOBSF_API_KEY` | MobSF REST key -- re-capture after every MobSF restart (see above) |
| `LLM_PROVIDER` | `ollama` (self-hosted, slow) or `openai` (fast, needs key) |
| `OLLAMA_URL` / `OLLAMA_MODEL` | Ollama endpoint and model tag |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Used only when `LLM_PROVIDER=openai` |
| `SCAN_STORAGE` | Per-scan state/result/PDF root (default `/tmp/ikusa-scans`) |

## Restart / teardown

```bash
docker compose stop            # stop services, keep containers + model
docker compose down            # remove containers; MobSF key + scan cache lost
docker compose down -v         # ALSO deletes ollama-data -> 5 GB model re-download
```

After `docker compose down` (without `-v`): the Ollama model survives, but the
MobSF REST key is regenerated (re-capture it -- see the setup note) and the
MobSF in-container scan cache is cleared, so the first scan of a given APK is
"cold" (~16 s) instead of "cached" (<5 s).

## CLI

```bash
uv run ikusa-cli login --api-key ikusa_sk_demo
uv run ikusa-cli scan path/to/app.apk -o report.pdf --fail-on alto
# Exit 0 = ok, 2 = findings above severity threshold
```

## MCP server

```bash
make mcp-stdio               # or: uv run ikusa-mcp
```

JSON-RPC over stdio for any MCP-compatible client (Cursor, etc.). 4 tools
exposed: `scan_apk`, `get_scan_status`, `get_scan_findings`, `list_scans`.

Environment overrides:

- `IKUSA_SERVER` -- backend base URL (default `http://localhost:9787`)
- `IKUSA_API_KEY` -- default `ikusa_sk_*` key if the caller passes none

## Test

```bash
make test                    # unit + integration suite (96 tests)
bash scripts/smoke_full.sh   # E2E across all 6 features, needs all services up
```

`tests/test_report.py` needs the Docker WeasyPrint image; CI deselects it
because the runner has no Docker. Locally (image built) the full 96 pass.
`smoke_full.sh` boots its own uvicorn on :9787 -- stop any running `make run`
first so the port is free.

## Troubleshooting

- **MobSF container shows `unhealthy` but the API works.** Cosmetic. The
  image's healthcheck probes `host.docker.internal`, which native Linux Docker
  does not resolve. Verify the API directly:
  `curl -H "Authorization: $MOBSF_API_KEY" http://localhost:8000/api/v1/scans`
  -- HTTP 200 means MobSF is fine.
- **Every scan fails with a MobSF 401 after a restart.** The MobSF key was
  regenerated. Re-capture it and update `.env` (see the setup note).
- **`make weasyprint-build` fails resolving `deb.debian.org`.** On restricted
  DNS the build needs host networking; the Makefile already passes
  `--network=host`. If you build manually, add that flag.
- **WeasyPrint missing Cairo/Pango/GdkPixbuf at render time.** Rendering runs
  inside the `ikusa-weasyprint` image precisely to avoid host system
  libraries -- rebuild the image rather than installing libs on the host.
- **`docker exec ikusa-ollama ollama pull qwen2.5:7b` times out.** Some
  networks cannot reach `registry.ollama.ai`. Pull the model from a network
  that can; once in the `ollama-data` volume it persists.

## Architecture

```
Browser -> FastAPI (uvicorn :9787)
                |
           BackgroundTask
          /         |         \              \
      MobSF      Parser    Ollama      WeasyPrint
     (:8000)   (in-proc)  (:11434)    (docker run)
          \         |         /              /
           state.json + result.json + report.pdf
              under /tmp/ikusa-scans/{scan_id}/
```

State is plain JSON/PDF files under `SCAN_STORAGE`; there is no database.

### Demo API keys

After `make seed-keys`:

| Key | Tier | Initial credits |
|-----|------|-----------------|
| `ikusa_sk_demo` | free | 10 |
| `ikusa_sk_free_demo` | free | 0 |
| `ikusa_sk_team_demo` | team | 0 |
| `ikusa_sk_biz_demo` | business | 0 |
| `ikusa_sk_ent_demo` | enterprise | 0 |

Anonymous requests (no `Authorization` header) work too -- they get the free
tier in-memory fallback.
