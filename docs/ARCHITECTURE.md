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

## Planned agent execution

1. Convert a user request into a typed project plan.
2. Generate an initial project file set inside the selected workspace.
3. Ask for approval before overwrites, filesystem deletion or builds.
4. Run allowlisted build/test adapters in an isolated worker.
5. Capture logs, artifacts and test results as project events.
6. Store concise, user-controllable memories and project decisions.

## Security invariants

- Never accept arbitrary workspace paths from API callers.
- Never expose unrestricted shell execution to the model.
- Treat model output, repository files and dependencies as untrusted.
- Require explicit approval for destructive or external side effects.
- Keep model endpoints loopback-bound by default.
- Do not store credentials or secrets in long-term memory.
