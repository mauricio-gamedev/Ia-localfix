# Ia Localfix — on-device Android app

The Android app is the actual runtime host. It runs a compact LiteRT-LM language model directly on the device, stores projects and memory in private SQLite, and writes project files into app-private storage. It does not require a PC, router, VPS, Ollama host, remote API, account, API Base URL or bearer token.

## Device runtime

- Kotlin + Jetpack Compose; min SDK 26, compile/target SDK 35, JDK 17.
- LiteRT-LM Android runtime 0.19.1, CPU backend.
- Starter model: Qwen3-0.6B dynamic INT4 LiteRT-LM, approximately 328 MiB (344,686,592 bytes).
- Engine context/KV budget is capped at 2,048 tokens and generated output at 512 tokens; recent chat and memory are truncated before prompt construction.
- The APK does not bundle the model. The app downloads it directly over HTTPS on first setup, streams to a temporary file, checks the expected size and SHA-256 digest, then moves the verified model into private app storage.
- Once the model is downloaded, chat and generation run offline on the phone. Internet is only required for the initial model download and later app updates.

## Local capabilities in this milestone

- Create, select, export and delete phone-local projects.
- Persist chat history and explicit remember-notes in SQLite.
- Build model context from the selected project, recent chat, saved notes and project file inventory.
- Generate JSON-based proposals containing up to 12 new source/configuration files.
- Preview, approve or reject proposals. Applying a proposal creates new files only; it refuses overwrites, path traversal, symlinks and common secret/key paths.
- Export each project workspace as a ZIP through Android's system document picker.
- Load or unload the model to manage memory pressure.

The app does not execute generated code, run arbitrary shell commands, compile arbitrary APKs on the phone, or claim projects were tested. Android SDK/Gradle toolchains are not bundled into the app. Build execution is a separate future capability.

## Model and device limits

Qwen3-0.6B dynamic INT4 is a deliberately small starting model for a 4 GB phone. The publisher marks this 328 MiB variant as recommended; its runtime memory use is much higher than file size and varies by device. This is a memory-conscious starting profile, not a guarantee of fit. Expect slower responses, limited reasoning depth and occasional malformed/incomplete code compared with a desktop coding model. Longer prompts and large project trees must be kept bounded. Close other memory-heavy apps before loading the model. The device must have at least 500 MB free internal storage for the model download; more free space and RAM are preferable.

Model card: https://huggingface.co/litert-community/Qwen3-0.6B

## Build and validation

GitHub Actions uses JDK 17, Gradle 8.13, AGP 8.13.2 and Kotlin 2.3.21. The Android job runs testDebugUnitTest and assembleDebug, then uploads app-debug.apk plus its SHA-256 checksum as the ia-localfix-debug-apk artifact.

The debug APK is a test build, not a production-signed Play Store release. CI verifies compilation and JVM unit tests; it does not prove inference speed, thermal behavior, memory stability or compatibility on a physical Galaxy A06. Those require a real-device test.
