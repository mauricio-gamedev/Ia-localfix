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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=Path(os.getenv("IA_DATABASE_PATH", "./data/ia-localfix.sqlite3")),
            workspace_root=Path(os.getenv("IA_WORKSPACE_ROOT", "./workspaces")),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b"),
            max_plan_chars=int(os.getenv("IA_MAX_PLAN_CHARS", "12000")),
        )
