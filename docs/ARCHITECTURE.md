# Architecture — initial foundation

## Runtime boundaries

The API is the control plane. Model inference is delegated to a replaceable provider adapter. Project files live in per-project workspaces beneath a configured root. Generated source files are written but never executed by this API foundation.

## Components

- `app/main.py`: FastAPI application factory and HTTP routes.
- `app/config.py`: environment-backed settings.
- `app/database.py`: SQLite connection and schema initialization.
- `app/inference.py`: Ollama chat and schema-constrained file generation.
- `app/workspaces.py`: normalized project slugs, bounded text inspection, path containment, SHA-256 snapshots and safe create/update writes.
- `app/validation.py`: non-executing AST/JSON/TOML/XML validation.
- `app/schemas.py`: request and response contracts.

## Memory strategy

SQLite is the durable source of truth. FTS5 is enabled when the SQLite build supports it; a LIKE-based fallback keeps search functional otherwise. Embeddings/vector retrieval are deferred until benchmarks demonstrate a need. This avoids adding a heavy vector database before the memory corpus justifies it.

## Project generation

The model returns a schema-constrained JSON object containing relative file paths and UTF-8 contents. The API validates file count, total output size, path segments, workspace containment, symlink resolution, duplicate names and overwrite conflicts before writing. A failed write removes files created during that request. Generated files are not executed.

## Agent run lifecycle

The agent creates a typed proposal containing a summary, implementation plan, ordered steps, and proposed files. Recent project memories (up to eight) are supplied as context. The proposal is validated without touching the workspace, then persisted in SQLite with status `awaiting_approval`. Only an explicit approve request can transition it to `applying`; successful file application moves it to `completed`. Rejection is terminal. Each state transition is written to the `agent_events` audit table. Conditional SQL updates prevent duplicate approval/rejection claims.

If the process restarts while a run is `applying`, the run is marked failed and requires workspace inspection rather than automatic replay.

## Workspace inspection and static validation

The inspection endpoint returns a bounded text-only inventory, SHA-256 fingerprints and previews. It skips symlinks, common build/cache/VCS directories, environment files and key material. The model receives a bounded source snapshot; the API response does not expose full file contents. Agent proposals may create new files or update inspected text files. Updates include the inspected SHA-256 and are rejected if a file changes before approval. Static validation parses Python AST, JSON, TOML and XML without importing or executing project code. Unsupported toolchains are reported through markers, not misrepresented as built or tested.

After approved changes are applied, a static validation result is recorded in the run event timeline. When diagnostics exist, the repair endpoint can use them plus the current file snapshot to create a separate repair proposal. It never edits files automatically; the repair proposal requires its own approval.

## Controlled build execution

Build jobs are persisted separately from agent file proposals. A user selects one available profile and a job enters awaiting_approval; approval is claimed with a conditional SQL update so a job cannot execute twice. Every transition is recorded in build_events.

The profile registry is server-owned. API payloads contain only a profile ID; the model cannot choose a container image, executable, arguments, shell fragment, environment variables or network mode. Each profile maps to a fixed argument vector. Docker is invoked with an argument array, image pulling is disabled, and subprocess shell mode is never used.

The build worker copies the project into a temporary scratch workspace, skipping symlinks, .env* and key/credential files, VCS/dependency/cache directories, and enforcing source file/count/size ceilings. Only that scratch copy is mounted into the container. The container runs with networking disabled, read-only root filesystem, all capabilities dropped, the default seccomp profile, no-new-privileges, non-root UID, PID/memory/CPU/file-descriptor limits, tmpfs scratch locations and a hard timeout. The original project workspace is not mounted into the container. Android artifacts are copied back into a per-job artifact directory with size and SHA-256 metadata.

The initial build profiles use Python unittest, Node's built-in node --test, and offline Android Gradle assemble/unit-test tasks. Android profiles require a server-configured builder image; that image must already contain its SDK/toolchains and dependency caches. There is no automatic network-enabled dependency resolution. This initial worker is a hardened baseline, not a substitute for a dedicated VM/microVM boundary against kernel/container-runtime vulnerabilities; Docker daemon access remains a privileged host capability and the API should remain loopback-bound until authentication is implemented.

## Planned agent execution

1. Add toolchain-specific result parsers and richer compiler/test diagnostics.
2. Extend repair proposals to approved build/test diagnostics and bounded repair iteration controls.
3. Improve memory with ranking, summarization/compaction, retention controls and user-editable decisions.
4. Add authentication before any non-loopback deployment.

## Security invariants

- Never accept arbitrary workspace paths from API callers.
- Never expose unrestricted shell execution to the model.
- Treat model output, repository files and dependencies as untrusted.
- Require explicit approval for destructive or external side effects.
- Keep model endpoints loopback-bound by default.
- Do not store credentials or secrets in long-term memory.
