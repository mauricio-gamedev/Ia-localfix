# Session checkpoint — Ia-localfix

Updated: 2026-11-19

## Repository state
- Repository: `mauricio-gamedev/Ia-localfix`
- Active development branch: `feat/local-ai-api-foundation`
- Pull request: #1 (draft), targeting `main`
- Package/API version: 0.5.0
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
- v0.5 CI passed on commit 8a7279b with 26 passing tests and one Starlette/httpx deprecation warning; additional Android wrapper, interrupted-job and artifact-download tests are in this branch.

- Added a persisted build-job state machine, fixed server-side profile registry, build event timeline, Docker execution adapter, and APK/AAB artifact manifest/download endpoint.
- Build jobs require explicit approval and use a scratch copy; only that copy is mounted into the container. The container is network-disabled, image pulls are disabled, non-root, read-only except scratch mounts, capability-dropped, seccomp-filtered, no-new-privileges, resource-limited and time-limited.
- Android Gradle profiles require IA_ANDROID_BUILDER_IMAGE configured server-side; it must include the Android SDK and preloaded offline dependencies.
- The API does not automatically execute generated code after file approval; execution happens only through a separately approved build job.

## Current API additions
- `GET /v1/projects/{project_id}/inspect`
- `POST /v1/projects/{project_id}/validate`
- `POST /v1/agent/runs/{run_id}/repair`
- `GET /v1/projects/{project_id}/build-profiles`
- `POST /v1/projects/{project_id}/builds`
- `GET /v1/projects/{project_id}/builds`
- `GET /v1/builds/{build_id}` and `/events`
- `POST /v1/builds/{build_id}/approve` and `/reject`
- `GET /v1/builds/{build_id}/artifacts/{artifact_name}`

Existing agent run endpoints remain documented in the README.

## Not implemented yet
- An end-to-end Docker build has not yet been run in this development environment; the Docker adapter is covered by mocked subprocess tests and CI.
- Publication of the Android SDK builder image and dependency-cache provisioning.
- Repair from compiler/build/test diagnostics.
- Bounded autonomous multi-tool iteration.
- Advanced memory ranking, summarization/compaction and retention controls.
- Authentication and hardening for network-exposed deployments.

## Important constraints
- Do not execute model-generated shell commands.
- Do not claim source projects were built or tests executed unless an approved build job and Docker worker actually completed. Static parsing remains separate from build execution.
- Keep changes on a feature branch; do not merge the draft PR without reviewing the complete diff and confirming CI.
