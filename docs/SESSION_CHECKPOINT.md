# Session checkpoint — Ia-localfix

Updated: 2026-11-19

## Repository state

- Repository: mauricio-gamedev/Ia-localfix
- Active branch: feat/local-ai-api-foundation
- Pull request: #1, draft and open; do not merge without explicit user approval.
- Legacy backend: Python 3.12 / FastAPI / SQLite / Ollama / Docker (retained, optional).
- Android app target: phone-local Intelligent Access Point; no external API dependency.
- Android runtime: Kotlin + Jetpack Compose + LiteRT-LM CPU backend.
- Starter model: Qwen3-0.6B LiteRT-LM, approximately 614 MB.

## Android on-device work implemented in source

- Replaced remote API client UI direction with local chat, projects and device/model setup.
- Added application-scoped LiteRT-LM engine adapter on a dedicated single-thread dispatcher.
- Added first-run HTTPS model downloader, temporary-file staging, size bounds and pinned SHA-256 verification.
- Added private SQLite tables for projects, chat messages, explicit memory notes and pending proposals.
- Added private per-project file workspace, bounded JSON file proposals, safe relative path validation, path/symlink/secret-path checks, no-overwrite behavior, rollback on partial file application and ZIP export.
- Added explicit user approval/rejection for generated files.
- Added memory command: remember: ...
- Removed the need for API Base URL, bearer token, PC, router, VPS, Ollama server or remote service in Android runtime.
- Added model unload control and critical-memory trimming.
- Added JVM tests for proposal path policy.
- Upgraded Android build toolchain to AGP 8.13.2 / Kotlin 2.3.21 / Gradle 8.13 and added LiteRT-LM Android 0.19.1 dependency.
- CI now runs Android JVM unit tests and builds the debug APK.

## Current Android limitations

- The selected 0.6B model is intentionally small. It is not a desktop-grade coding model; code quality, speed and stability on a Galaxy A06 remain subject to real-device testing.
- Model download requires internet once (approximately 614 MB); subsequent model inference is on-device/offline.
- The app does not bundle Android SDK/Gradle and does not build arbitrary APKs on the phone.
- File proposal workflow currently creates new files only; editing existing files, deleting project files, running tests/builds, tool orchestration, semantic vector retrieval and memory summarization are not implemented yet.
- The model output schema can fail; malformed or unsafe proposals are rejected and not written.
- CI compilation/unit tests cannot prove physical-device inference speed, RAM/thermal behavior or app lifecycle stability.

## Legacy backend status

The existing FastAPI/Ollama/Docker API, guarded workspaces, persistent server SQLite memory, approval state machine, fixed build profiles and build diagnostics remain in the repository as a separate optional subsystem. It is not called by the Android app. The backend's previous host deployment instructions are not applicable to phone-local app usage.

## Validation policy

- Never claim device inference was tested on the Galaxy A06 unless it was run on that physical device.
- Never claim generated project files were compiled or tested unless an actual approved build/test ran.
- Keep development on feature branches and update the PR; do not merge it.
