# Ia-localfix

Local-first AI software engineering agent.

## Implemented foundation

- Python 3.12 + FastAPI control-plane API.
- Ollama local inference adapter with structured project-file generation.
- SQLite persistence with FTS5 project memory and a LIKE fallback.
- Bounded workspace inspection with text-only snapshots, secret/build-folder exclusions, and SHA-256 file fingerprints.
- Safe file creation and hash-checked updates: relative paths only, no traversal, no symlink escape, no unreviewed overwrite, and bounded output.
- Non-executing syntax validation for Python, JSON, TOML and XML.
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
- `GET /v1/projects/{project_id}/inspect` (bounded file inventory and previews)
- `POST /v1/projects/{project_id}/validate` (static syntax checks; no code execution)
- `POST /v1/projects`
- `POST /v1/memory`
- `GET /v1/memory?q=...`
- `POST /v1/agent/plan`
- `POST /v1/agent/generate` (direct, explicit generation)
- `POST /v1/agent/runs` (create a persisted proposal)
- `GET /v1/agent/runs?project_id=...` (list project runs)
- `GET /v1/agent/runs/{run_id}` (inspect plan and file previews)
- `GET /v1/agent/runs/{run_id}/events` (audit timeline)
- `POST /v1/agent/runs/{run_id}/approve` (apply approved files)
- `POST /v1/agent/runs/{run_id}/reject` (reject without writing)

Interactive API documentation is available at `/docs`.

## Hardware and deployment

The inference/build host should be a capable desktop or Linux machine. Android devices can use the API as clients. Running a coding model, Android SDK and builds concurrently on a low-memory phone is not assumed.

## Security boundaries

The agent-run workflow stores a plan and file proposal first. It does not write those files until the user explicitly approves the run. Application is single-claim and audited. The older direct generation endpoint remains an explicit immediate-write operation. It rejects absolute paths, traversal, symlink escapes, duplicate paths and overwrites. This foundation does not execute shell commands or generated code. Build execution will be introduced later through isolated, explicitly permissioned adapters.

The assistant is intended to be viewpoint-neutral and configurable, while retaining safeguards for destructive actions, secrets, untrusted code and unauthorized activity.

## Agent execution lifecycle

1. `POST /v1/agent/runs` asks the local model for a typed plan, ordered steps, and a proposed new-file set. The latest eight project memories are supplied as context.
2. The proposal is schema-validated and checked against workspace path, symlink, file-count, size, duplicate, and overwrite constraints. It is persisted as `awaiting_approval` without writing files.
3. The client can inspect the plan, previews, status, and audit events.
4. `POST /v1/agent/runs/{id}/approve` atomically claims an awaiting run and applies the new files once. `reject` records rejection without writing.
5. Runs and events remain in SQLite for later inspection.

This milestone adds project inspection, create/update proposals, optimistic concurrency checks, and non-executing syntax validation. It does not yet run project build scripts, execute generated tests, or automatically repair compiler failures. Those capabilities require a separately isolated worker.
