# IKUSA Compliance Scanner -- Prototype

Automated MASVS / CRA compliance scanner for Android APKs.

## Requirements

- Python >= 3.11
- Docker (for MobSF + Ollama + WeasyPrint sandboxes)
- ~10 GB free disk (MobSF image + Qwen2.5-7B model)

## Install

```bash
cp .env.example .env
# edit .env if needed
make install
```

## Run

```bash
make mobsf-up
make ollama-up
make run
```

Then open `http://localhost:9000` in a browser, upload an APK, wait, download the PDF.

## Test

```bash
make test
```
