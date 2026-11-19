# Session checkpoint — Ia-localfix

Updated: 2026-11-19

## Repository state
- Repository: `mauricio-gamedev/Ia-localfix`
- Active development branch: `feat/local-ai-api-foundation`
- Pull request: #1 (draft), targeting `main`
- Package/API version: 0.7.0
- Base stack: Python 3.12, FastAPI, Pydantic, HTTPX, SQLite/FTS5, Ollama
- CI workflow: `.github/workflows/ci.yml`

## Implemented
- Project creation and bounded workspace management.
- Ollama planning and schema-constrained source generation.
- Persistent SQLite memory with FTS5 and LIKE fallback.
- Agent runs persisted with approval/rejection states and an audit event timeline.
- Bounded text-only workspace inspection with SHA-256 fingerprints and exclusions for symlinks, common build/cache/VCS directories, environment files and key material.
- Agent proposals can create files or update inspected text files; updates are rejected if their expected SHA-256 no longer matches.
- Approved file changes are followed by non-executing syntax/format checks for Python, JSON, TOML and XML.
- A repair endpoint can generate a new proposal based on static diagnostics; the repair still requires explicit approval.
- v0.5 CI passed on branch head `f245e8a` with 31 tests. v0.6 adds a live Docker smoke job to GitHub Actions in addition to its unit/API suite.

- Added a persisted build-job state machine, fixed server-side profile registry, build event timeline, Docker execution adapter, and APK/AAB artifact manifest/download endpoint.
- Build jobs require explicit approval and use a scratch copy; only that copy is mounted into the container. The container is network-disabled, image pulls are disabled, non-root, read-only except scratch mounts, capability-dropped, seccomp-filtered, no-new-privileges, resource-limited and time-limited.
- Android Gradle profiles require IA_ANDROID_BUILDER_IMAGE configured server-side; it must include the Android SDK and preloaded offline dependencies.
- The API does not execute generated code after file approval; project builds run only as separately approved build jobs.
- Build outputs are parsed into structured Python, Node TAP, Gradle compiler/task, generic failure and timeout diagnostics.
- Added `POST /v1/builds/{build_id}/repair`: it creates one normal agent-run patch proposal from the failed build and current workspace snapshot; no files change until that run is approved.
- Build jobs track `cycle_id`, `iteration` and `parent_build_id`. A retry requires the linked repair proposal to be applied, the same build profile, a failed parent, and no existing child. `IA_MAX_REPAIR_ITERATIONS` defaults to 2 and is limited to 1–5.
- Each repair and subsequent build requires a separate explicit approval; rejected or failed steps do not continue automatically.
- GitHub Actions live Docker smoke test now launches a real container with a controlled unittest fixture and verifies successful test execution and scratch cleanup.

## Current API additions
- `GET /v1/projects/{project_id}/inspect`
- `POST /v1/projects/{project_id}/validate`
- `POST /v1/agent/runs/{run_id}/repair`
- `GET /v1/projects/{project_id}/build-profiles`
- `POST /v1/projects/{project_id}/builds`
- `GET /v1/projects/{project_id}/builds`
- `GET /v1/builds/{build_id}` and `/events`
- `POST /v1/builds/{build_id}/repair`
- `POST /v1/builds/{build_id}/approve` and `/reject`
- `GET /v1/builds/{build_id}/artifacts/{artifact_name}`

Existing agent run endpoints remain documented in the README.

## v0.7 additions
- Optional bearer-token authentication protects every API endpoint except /health when IA_API_TOKEN is configured. The docs and OpenAPI schema remain readable, with protected operations marked for Bearer authorization in Swagger UI. Tokens require at least 32 ASCII non-whitespace characters and are checked with constant-time comparison.
- IA_ALLOW_REMOTE=true requires a valid token at startup as an explicit deployment guard. It does not detect the actual Uvicorn bind address or provide TLS; remote ingress still needs separate network/TLS hardening.
- Build result summaries are normalized for Python unittest, Node TAP and Gradle JUnit XML. Parsing is bounded to at most 50 report candidates of at most 512 KB each. Missing/unparseable reports remain null and are not treated as success.

## Not implemented yet
- No end-to-end Docker build has been run in this development environment; CI tests the Docker adapter through a mocked subprocess. A live Docker daemon/container remains unverified.
- Publication of the Android SDK builder image and dependency-cache provisioning.
- Additional parsers for toolchains beyond Python/Node/Gradle and richer test-report extraction.
- Unattended multi-tool autonomy; repair cycles are intentionally supervised with per-change and per-build approvals.
- Advanced memory ranking, summarization/compaction and retention controls.
- Fine-grained project authorization, rate limiting and a durable multi-worker build queue.
- Stronger VM/microVM execution isolation and TLS/reverse-proxy deployment automation.

## Important constraints
- Do not execute model-generated shell commands.
- Do not claim source projects were built or tests executed unless an approved build job and Docker worker actually completed. Static parsing remains separate from build execution.
- Keep changes on a feature branch; do not merge the draft PR without reviewing the complete diff and confirming CI.
