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

## Test

```bash
make test                    # unit + integration suite
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

See `FINAL_STATUS.md` for performance baseline and known gaps.
