from dataclasses import dataclass
import os
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value.")


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
    max_repair_iterations: int = 2
    api_token: str = ""
    allow_remote: bool = False

    def __post_init__(self) -> None:
        if self.api_token and (
            len(self.api_token) < 32
            or not self.api_token.isascii()
            or any(character.isspace() for character in self.api_token)
        ):
            raise ValueError("IA_API_TOKEN must contain at least 32 ASCII non-whitespace characters.")
        if self.allow_remote and not self.api_token:
            raise ValueError("IA_API_TOKEN is required when IA_ALLOW_REMOTE=true.")

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
            max_repair_iterations=int(os.getenv("IA_MAX_REPAIR_ITERATIONS", "2")),
            api_token=os.getenv("IA_API_TOKEN", "").strip(),
            allow_remote=_env_bool("IA_ALLOW_REMOTE"),
        )
