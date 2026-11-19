from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path = Path("./data/ia-localfix.sqlite3")
    workspace_root: Path = Path("./workspaces")
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:3b"
    max_plan_chars: int = 12_000
    artifact_root: Path = Path("./artifacts")
    docker_binary: str = "docker"
    python_builder_image: str = "python:3.12-slim"
    node_builder_image: str = "node:22-bookworm-slim"
    android_builder_image: str = ""
    build_timeout_seconds: int = 900
    build_memory_limit: str = "2g"
    build_cpus: float = 2.0
    build_pids_limit: int = 128

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=Path(os.getenv("IA_DATABASE_PATH", "./data/ia-localfix.sqlite3")),
            workspace_root=Path(os.getenv("IA_WORKSPACE_ROOT", "./workspaces")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b"),
            max_plan_chars=int(os.getenv("IA_MAX_PLAN_CHARS", "12000")),
            artifact_root=Path(os.getenv("IA_ARTIFACT_ROOT", "./artifacts")),
            docker_binary=os.getenv("IA_DOCKER_BINARY", "docker"),
            python_builder_image=os.getenv("IA_PYTHON_BUILDER_IMAGE", "python:3.12-slim"),
            node_builder_image=os.getenv("IA_NODE_BUILDER_IMAGE", "node:22-bookworm-slim"),
            android_builder_image=os.getenv("IA_ANDROID_BUILDER_IMAGE", "").strip(),
            build_timeout_seconds=int(os.getenv("IA_BUILD_TIMEOUT_SECONDS", "900")),
            build_memory_limit=os.getenv("IA_BUILD_MEMORY_LIMIT", "2g"),
            build_cpus=float(os.getenv("IA_BUILD_CPUS", "2.0")),
            build_pids_limit=int(os.getenv("IA_BUILD_PIDS_LIMIT", "128")),
        )
