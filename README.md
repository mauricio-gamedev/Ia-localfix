# Ia-localfix

Local-first AI software engineering agent.

## Initial implementation

- Python 3.12 + FastAPI control-plane API.
- Ollama local inference adapter; the model runtime is replaceable.
- SQLite persistence with searchable project memory.
- Project workspaces constrained to a configured root directory.
- Pytest suite and GitHub Actions CI.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` to use a local Ollama instance. The API starts without a model runtime; planning requests return a clear 503 until the runtime is available.

## API

- `GET /health`
- `GET /v1/projects`
- `POST /v1/projects`
- `POST /v1/memory`
- `GET /v1/memory?q=...`
- `POST /v1/agent/plan`

Interactive API documentation is available at `/docs`.

## Hardware and deployment

The inference/build host should be a capable desktop or Linux machine. Android devices can use the API as clients. Running a coding model, Android SDK and builds concurrently on a low-memory phone is not assumed.

## Security boundaries

Project names are converted to safe slugs and workspace paths are checked against the configured root. This foundation does not execute shell commands or arbitrary generated code. Build execution will be introduced later through isolated, explicitly permissioned adapters.

The assistant is intended to be viewpoint-neutral and configurable, while retaining safeguards for destructive actions, secrets, untrusted code and unauthorized activity.
