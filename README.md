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
# Paste into MOBSF_API_KEY=... in .env
```

## Run

```bash
make run
```

Open `http://localhost:9787`, drop an APK in the dropzone, wait, download the
PDF. CPU triage with Qwen2.5-7B takes ~3 minutes for 4-8 findings.

## CLI

```bash
uv run ikusa-cli login --api-key ikusa_sk_demo
uv run ikusa-cli scan path/to/app.apk -o report.pdf --fail-on alto
# Exit 0 = ok, 2 = findings above severity threshold
```

## MCP server (Claude Code / Cursor / Claude Desktop)

```bash
make mcp-stdio               # or: uv run ikusa-mcp
```

4 tools exposed: `scan_apk`, `get_scan_status`, `get_scan_findings`,
`list_scans`. JSON-RPC over stdio.

## Test

```bash
make test                    # unit + integration suite (96 tests)
bash scripts/smoke_full.sh   # E2E across all 6 features, needs all services up
```

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
