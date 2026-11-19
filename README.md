# Ia-localfix

Local-first AI software engineering agent.

**Current milestone: v0.6.0 — build diagnostics and supervised repair cycles.**

## Implemented foundation

- Python 3.12 + FastAPI control-plane API.
- Ollama local inference adapter with structured project-file generation.
- SQLite persistence with FTS5 project memory and a LIKE fallback.
- Bounded workspace inspection with text-only snapshots, secret/build-folder exclusions, and SHA-256 file fingerprints.
- Safe file creation and hash-checked updates: relative paths only, no traversal, no symlink escape, no unreviewed overwrite, and bounded output.
- Non-executing syntax validation for Python, JSON, TOML and XML.
- Pytest suite and GitHub Actions CI.
- Persisted build jobs with explicit approval, event history, fixed server-side profiles, and downloadable build artifacts.
- Docker execution with network disabled, image pulls disabled, read-only container root, dropped capabilities, no-new-privileges, non-root API-service UID, CPU/memory/PID/time limits, and secret/cache exclusions from the scratch build copy.
- Structured Python, Node TAP, Gradle compiler/task, generic build-failure, and timeout diagnostics extracted from bounded build logs.
- Supervised build-repair cycles: AI-generated patch proposals, explicit file approval, parent/child build lineage, and a configurable iteration ceiling.
- Live Docker worker integration smoke test in GitHub Actions, in addition to the mocked API/unit tests.

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
- `GET /v1/projects/{project_id}/build-profiles`
- `POST /v1/projects/{project_id}/builds` (create a build proposal; optional `parent_build_id` for an approved repair retry; does not execute)
- `GET /v1/projects/{project_id}/builds`
- `GET /v1/builds/{build_id}` and `/events`
- `POST /v1/builds/{build_id}/approve` and `/reject`
- `POST /v1/builds/{build_id}/repair` (propose a focused patch from build diagnostics; does not write files)
- `GET /v1/builds/{build_id}/artifacts/{artifact_name}`
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
- `POST /v1/agent/runs/{run_id}/repair` (create a repair proposal from static diagnostics)

Interactive API documentation is available at `/docs`.

## Hardware and deployment

The inference/build host should be a capable desktop or Linux machine with Docker installed and permission to launch isolated containers. Android devices can use the API as clients. Running a coding model, Android SDK and builds concurrently on a low-memory phone is not assumed.

## Security boundaries

The agent-run workflow stores a plan and file proposal first. It does not write those files until the user explicitly approves the run. Application is single-claim and audited. The older direct generation endpoint remains an explicit immediate-write operation. It rejects absolute paths, traversal, symlink escapes, duplicate paths and overwrites. Build jobs are separate from agent file proposals. A client first selects an available fixed profile, then explicitly approves the persisted job. The model cannot supply an image, executable, shell string, flags, or command arguments. The worker copies the workspace into a temporary scratch tree and executes the profile in Docker with network disabled, a read-only container root, dropped Linux capabilities, no-new-privileges, a non-root UID, resource limits, and a hard timeout. The original workspace is not mounted into the container. Secret files, symlinks, VCS directories and common dependency/build caches are excluded from the scratch copy.

The initial profiles are Python unittest, Node's built-in node --test, Android assembleDebug, and Android testDebugUnitTest. Android profiles are only offered when IA_ANDROID_BUILDER_IMAGE is configured. The image must already be present in the local Docker daemon and contain the Android SDK plus required Gradle/plugin/dependency caches because execution is offline. Docker does not pull missing images automatically. Python/Node profiles likewise assume runtime dependencies are available in the selected image or use built-in test tooling. Network access is disabled inside every build container; dependencies are never downloaded as a side effect of approving a job. If the builder image or Docker daemon is unavailable, the job records a failure rather than falling back to host execution.

The assistant is intended to be viewpoint-neutral and configurable, while retaining safeguards for destructive actions, secrets, untrusted code and unauthorized activity.

## Agent execution lifecycle

1. `POST /v1/agent/runs` asks the local model for a typed plan, ordered steps, and a proposed new-file set. The latest eight project memories are supplied as context.
2. The proposal is schema-validated and checked against workspace path, symlink, file-count, size, duplicate, and overwrite constraints. It is persisted as `awaiting_approval` without writing files.
3. The client can inspect the plan, previews, status, and audit events.
4. `POST /v1/agent/runs/{id}/approve` atomically claims an awaiting run and applies the new files once. `reject` records rejection without writing.
5. Runs and events remain in SQLite for later inspection.

This milestone adds project inspection, create/update proposals, optimistic concurrency checks, non-executing syntax validation after approval, and a diagnostics-driven repair proposal endpoint. A repair is always a new proposal and still requires approval. The API can run only the fixed build profiles described above. Failed build logs are parsed into structured diagnostics. `POST /v1/builds/{id}/repair` uses those diagnostics plus the current workspace snapshot to create an ordinary agent-run proposal. The patch still requires explicit approval through `/v1/agent/runs/{run_id}/approve`; only then can the client create a child build with `parent_build_id`. Each failed build can produce one repair proposal, each retry must descend from the same build cycle and use the same profile, and the server enforces `IA_MAX_REPAIR_ITERATIONS` (default 2, supported range 1–5). This is supervised automation, not an unattended code-writing loop.


## Build execution configuration

The Docker daemon runs on the API host. Configure resource limits and builder images through server environment variables, never through model output or client payloads:

- IA_DOCKER_BINARY (default docker)
- IA_PYTHON_BUILDER_IMAGE (default python:3.12-slim)
- IA_NODE_BUILDER_IMAGE (default node:22-bookworm-slim)
- IA_ANDROID_BUILDER_IMAGE (unset by default; required to enable Android profiles)
- IA_BUILD_TIMEOUT_SECONDS (default 900)
- IA_BUILD_MEMORY_LIMIT (default 2g)
- IA_BUILD_CPUS (default 2.0)
- IA_BUILD_PIDS_LIMIT (default 128)
- IA_ARTIFACT_ROOT (default ./artifacts)
- IA_MAX_REPAIR_ITERATIONS (default 2; configurable from 1 to 5)

All builder images must be pre-pulled into the local Docker daemon. Android builder images must be pre-provisioned with a compatible JDK, Android SDK/build-tools, and a complete Gradle dependency/wrapper cache stored at `/opt/ia-gradle-cache`. At runtime the worker copies that image cache into the disposable workspace, then runs Gradle offline against the copy. Python and Node profiles are shown only when their supported test files are discoverable; an empty test suite is not reported as a passing test run. A successful command is evidence of that specific profile only; it is not a blanket guarantee that every supported device or release variant is ready.


## Supervised repair cycle

1. A failed or timed-out build returns `result.diagnostics` with normalized workspace-relative paths where the toolchain exposes them.
2. Call `POST /v1/builds/{build_id}/repair` to create a patch proposal using those diagnostics, the bounded log tail and the current inspected source snapshot.
3. Review the generated files and approve the associated agent run. The repair endpoint never writes project files by itself.
4. Create the next build with the same `profile_id` and `parent_build_id` set to the failed build ID, then approve that build job separately.
5. Build jobs share a cycle ID and increment an iteration counter. The server rejects a retry unless the preceding repair was approved and applied, rejects duplicate children, and stops after the configured iteration limit.

A repair proposal can itself be rejected. The workflow does not continue automatically after a failure, timeout, or rejection; the user controls each file-application and build-execution approval.
