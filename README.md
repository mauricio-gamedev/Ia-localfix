# Ia-localfix

Local-first AI software engineering agent. The repository is being bootstrapped from an empty state.

## Initial architecture
- Python 3.12 + FastAPI for the control-plane API.
- Provider abstraction for local inference backends (Ollama first; llama.cpp-compatible providers planned).
- SQLite with FTS5 for durable, searchable project memory.
- Explicit project workspaces with path validation and no unrestricted shell execution.
- Build/test adapters added as separately permissioned capabilities.

## Device and deployment reality
The API and project build workers target a desktop/Linux host or a capable local machine. Android phones can act as clients; running a capable coding model and Android SDK builds entirely on a low-memory phone is not assumed.

## Safety model
The assistant is designed to be viewpoint-neutral and configurable, while retaining safeguards for destructive actions, secrets, untrusted code, and unauthorized activity.

## Status
Bootstrap only. See the implementation branch for the first API foundation.
