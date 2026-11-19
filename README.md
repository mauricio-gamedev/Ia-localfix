# Ia-localfix

Local-first AI software engineering agent.

## Implemented foundation

- Python 3.12 + FastAPI control-plane API.
- Ollama local inference adapter with structured project-file generation.
- SQLite persistence with FTS5 project memory and a LIKE fallback.
- Project workspaces constrained to a configured root directory.
- Safe file creation: relative paths only, no traversal, no symlink escape, no overwrite, and bounded output.
- Pytest suite and GitHub Actions CI.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` to use a local Ollama instance. The API starts without a model runtime; planning and generation requests return a clear 503 until the runtime is available.

## API

- `GET /health`
- `GET /v1/projects`
- `POST /v1/projects`
- `POST /v1/memory`
- `GET /v1/memory?q=...`
- `POST /v1/agent/plan`
- `POST /v1/agent/generate`

Interactive API documentation is available at `/docs`.

## Hardware and deployment

The inference/build host should be a capable desktop or Linux machine. Android devices can use the API as clients. Running a coding model, Android SDK and builds concurrently on a low-memory phone is not assumed.

## Security boundaries

The initial generation API only creates new files inside a selected project workspace. It rejects absolute paths, traversal, symlink escapes, duplicate paths and overwrites. This foundation does not execute shell commands or generated code. Build execution will be introduced later through isolated, explicitly permissioned adapters.

The assistant is intended to be viewpoint-neutral and configurable, while retaining safeguards for destructive actions, secrets, untrusted code and unauthorized activity.

## Current milestone

Initial planning and safe file-generation endpoints are implemented on the feature branch. Build workers, agent tool orchestration, and advanced memory retrieval remain future milestones.
