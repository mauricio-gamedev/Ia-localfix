# Architecture — phone-local Intelligent Access Point

## Product boundary

The Android device is the runtime host and primary system boundary. The Android app does not act as a thin client to a different API server. It owns the model engine, local project database, memory, workspace files and user interface. No PC, LAN router, VPS, external API, Ollama service or always-on cloud runtime is required.

The original Python/FastAPI control plane remains in the repository as an optional developer/compatibility backend. It is not in the Android app's request path and is not required for local app operation.

## Android components

- MainActivity.kt: Compose UI for chat, projects, model setup, proposal review and user approvals.
- IaLocalfixApplication.kt: process-scoped inference engine owner; unloads the model under severe memory pressure.
- LocalInference.kt: LiteRT-LM runtime adapter, CPU backend and serialized engine/conversation access on a dedicated thread.
- ModelInstaller.kt: HTTPS model download to a temporary private file, size checks, SHA-256 integrity verification and atomic finalization.
- LocalStore.kt: SQLite persistence for projects, messages, explicit memory notes and proposals.
- LocalProjectFiles.kt: private project workspaces, JSON proposal parsing, path validation, no-overwrite file application and ZIP export.

## On-device inference

The first model profile is Qwen3-0.6B in LiteRT-LM format. The model is intentionally not packaged in the APK: it is downloaded on first setup and stored under app-private files. The expected published SHA-256 is pinned in the model catalog. A failed/incomplete download is discarded. The first runtime uses CPU for predictable compatibility; GPU/accelerator backends are deferred until physical-device profiling.

Engine initialization and inference run on a dedicated single-thread dispatcher, never the main/UI thread. One engine instance is owned by the application process, calls are serialized, each conversation is closed after generation, and the engine is unloaded when requested or when Android reports critical memory pressure. If initialization fails, the engine instance is not retained.

## Hardware envelope

The target phone class has 4 GB physical RAM. The 0.6B model is a realistic first experiment, not a claim of desktop-class reasoning. Runtime memory includes model weights, native runtime, KV cache, prompt, output buffers and the rest of Android. Context and file generation are therefore bounded, generation may be slow, and the OS may reclaim the app. Physical Galaxy A06 tests are required before describing runtime performance or stability as verified. The app does not embed Android SDK/Gradle or compile arbitrary APKs on-device.

## Local data and memory

SQLite is stored in the app-private database directory. It holds project metadata, conversation messages, explicit remember-notes and pending proposals. Recent conversation and notes are included in the model context with bounded counts. No credentials or external API tokens are used by the Android runtime.

Project source files are stored separately in app-private per-project directories. ZIP export uses Android's Storage Access Framework. Project deletion removes its workspace and its database records. Memory in this milestone is explicit note storage and bounded recency retrieval; semantic embeddings, summarization/compaction, FTS and automatic memory extraction are future work.

## Agent/file workflow

Chat requests run through the on-device model. File generation requests require a JSON proposal with a summary and relative file paths/content. The parser enforces a maximum of 12 files, 64 KiB per file and 400 KiB total. Paths are rejected when absolute, traversal-based, symlink-escaping or likely to target credentials/keys/system metadata. Existing file paths are checked before proposal persistence.

The user sees file previews and must explicitly apply or reject the proposal. Applying creates new files only and rolls back files created by the current proposal if an error occurs. Existing files are never overwritten in this milestone. Generated code is not executed. No model-generated shell commands are accepted. The app does not claim a project was compiled or tested.

## Optional backend

The Python/FastAPI/Ollama/Docker code remains a distinct optional host-side subsystem. Its existing authentication, workspace isolation, approval workflow, build profiles and tests continue to apply only when someone deliberately operates that backend. It is not exposed as a dependency or setting in the Android client.

## CI and release boundary

GitHub Actions runs backend tests, the real Docker worker smoke test, Android JVM unit tests and an Android debug APK build. CI establishes source/build correctness for the runner's environment. It does not execute the model on a Galaxy A06, measure device RAM/thermals, or establish on-device APK compilation capability. The uploaded debug APK is not production-signed.
