# Ia-localfix

Local-first AI software engineering agent. The Android app is designed as a self-contained **Intelligent Access Point**: the phone itself owns inference, project storage, memory and the user interface.

## Android runtime (on-device)

- Native Kotlin + Jetpack Compose application under android/.
- Google LiteRT-LM 0.19.1 with a CPU inference backend.
- Qwen3-0.6B dynamic INT4 LiteRT-LM starter model (approximately 328 MiB), downloaded and integrity-checked on first setup; model files remain outside the APK in private app storage.
- SQLite project store for projects, chat history, saved project notes and pending proposals.
- Private project workspaces with validated relative paths, secret-path exclusions and explicit proposal approval.
- ZIP export through Android's document picker.
- No required PC, router, VPS, Ollama instance, remote API, API Base URL, bearer token or always-on server.

After the model is downloaded, normal inference is performed locally and can work offline. Internet access is needed for the initial model download and app updates.

## Hardware expectations

The dynamic-INT4 starter model reduces model file size; the engine is capped at a 2,048-token context and 512 output tokens for the low-memory Android target. It is not equivalent to a desktop coding model. On the Galaxy A06 class of device, generation may be slow, context and code-output sizes are limited, and other apps may be evicted under RAM pressure. Performance and thermal behavior still need physical-device validation. The app does not bundle Android SDK/Gradle and does not compile arbitrary APKs on-device.

## Current Android capabilities

- Create, select, export and delete projects stored on the phone.
- Persist recent conversation history and explicit remember-notes.
- Generate structured proposals for new source/configuration files.
- Review file previews, approve or reject a proposal.
- Apply new files into a private project directory with path/symlink/overwrite safeguards.
- Load/unload the local model to manage memory.

The current file-generation milestone is intentionally supervised. It creates new files only; it does not execute generated code or arbitrary shell commands. Build/test execution, safe updates to existing files, richer retrieval/compaction and additional model choices remain follow-on milestones.

## Backend foundation (optional)

The Python 3.12/FastAPI/Ollama/Docker backend under app/ is retained as an optional developer/compatibility service for capable hosts and existing API tests. **The Android app does not call it and does not require it to operate.** The backend is not the phone's runtime and no remote endpoint is configured in the Android client.

See android/README.md for the on-device model setup and device constraints, and docs/ARCHITECTURE.md for runtime boundaries.

## CI

GitHub Actions runs the Python API suite, real Docker worker smoke test, Android unit tests and Android debug APK build. The APK is uploaded as ia-localfix-debug-apk with a SHA-256 checksum. The debug APK is not a Play Store release.

The Android CI build does not simulate a physical phone or establish that the model runs acceptably on the Galaxy A06. Real-device testing is still required.
