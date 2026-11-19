# Architecture — initial foundation

## Runtime boundaries

The API is the control plane. Model inference is delegated to a replaceable provider adapter. Project files live in per-project workspaces beneath a configured root. Generated source files are written but never executed by this API foundation.

## Components

- `app/main.py`: FastAPI application factory and HTTP routes.
- `app/config.py`: environment-backed settings.
- `app/database.py`: SQLite connection and schema initialization.
- `app/inference.py`: Ollama chat and schema-constrained file generation.
- `app/workspaces.py`: normalized project slugs, path containment and bounded file writes.
- `app/schemas.py`: request and response contracts.

## Memory strategy

SQLite is the durable source of truth. FTS5 is enabled when the SQLite build supports it; a LIKE-based fallback keeps search functional otherwise. Embeddings/vector retrieval are deferred until benchmarks demonstrate a need. This avoids adding a heavy vector database before the memory corpus justifies it.

## Project generation

The model returns a schema-constrained JSON object containing relative file paths and UTF-8 contents. The API validates file count, total output size, path segments, workspace containment, symlink resolution, duplicate names and overwrite conflicts before writing. A failed write removes files created during that request. Generated files are not executed.

## Agent run lifecycle

The agent creates a typed proposal containing a summary, implementation plan, ordered steps, and proposed files. Recent project memories (up to eight) are supplied as context. The proposal is validated without touching the workspace, then persisted in SQLite with status `awaiting_approval`. Only an explicit approve request can transition it to `applying`; successful file application moves it to `completed`. Rejection is terminal. Each state transition is written to the `agent_events` audit table. Conditional SQL updates prevent duplicate approval/rejection claims.

If the process restarts while a run is `applying`, the run is marked failed and requires workspace inspection rather than automatic replay.

## Planned agent execution

1. Inspect existing project files and map the build environment.
2. Add a bounded tool-call loop for inspect, propose, validate and revise operations.
3. Integrate allowlisted build/test adapters in an isolated worker.
4. Capture logs, artifacts, test results and compiler diagnostics as project events.
5. Add controlled repair iterations that create a new proposal for review.
6. Improve memory with ranking, summarization/compaction, retention controls and user-editable decisions.

## Security invariants

- Never accept arbitrary workspace paths from API callers.
- Never expose unrestricted shell execution to the model.
- Treat model output, repository files and dependencies as untrusted.
- Require explicit approval for destructive or external side effects.
- Keep model endpoints loopback-bound by default.
- Do not store credentials or secrets in long-term memory.
