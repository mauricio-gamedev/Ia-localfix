# Ia Localfix Android MVP

Native Android client for the Ia-localfix API. Kotlin + Jetpack Compose; min SDK 26, compile/target SDK 35, JDK 17, AGP 8.7.3, Gradle 8.9.

## MVP scope

- Create/list projects.
- Submit prompts as supervised agent runs.
- Review plan, steps and file previews.
- Explicitly approve or reject proposed file changes.
- Configure an API base URL and optional bearer token.
- Store the token encrypted with Android Keystore (AES-GCM).

## API connection

Set the API base URL to a host reachable from the phone, such as `http://192.168.1.10:8000`. If the server is protected with `IA_API_TOKEN`, enter that same token in the app's Settings. A working Ollama runtime is required to generate proposals.

The debug variant allows cleartext HTTP for trusted-LAN testing. Do not use that configuration across untrusted networks; use HTTPS for remote access. The main manifest does not enable cleartext.

## Build

Open this directory in Android Studio, or run `gradle assembleDebug` with JDK 17, Gradle 8.9 and Android SDK Platform 35. GitHub Actions runs the same build and publishes `app-debug.apk` with a SHA-256 checksum as the `ia-localfix-debug-apk` workflow artifact.
