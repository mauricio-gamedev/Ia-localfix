import re
import unicodedata
from pathlib import Path, PurePosixPath


MAX_GENERATED_FILES = 30
MAX_GENERATED_BYTES = 1_000_000


def make_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    if not slug:
        raise ValueError("Project name must contain letters or numbers.")
    return slug[:64].strip("-")


def create_workspace(root: Path, slug: str) -> Path:
    root = root.expanduser().resolve()
    target = (root / slug).resolve()
    if target == root or root not in target.parents:
        raise ValueError("Workspace path escapes the configured root.")
    target.mkdir(parents=True, exist_ok=False)
    return target


def _prepare_generated_files(
    root: Path, slug: str, files: list[dict]
) -> tuple[Path, list[tuple[str, Path, str, int]]]:
    if not isinstance(files, list) or not files or len(files) > MAX_GENERATED_FILES:
        raise ValueError(f"Generation must contain between 1 and {MAX_GENERATED_FILES} files.")

    workspace_root = root.expanduser().resolve()
    project_dir = (workspace_root / slug).resolve()
    if project_dir == workspace_root or workspace_root not in project_dir.parents:
        raise ValueError("Project workspace escapes the configured root.")
    if not project_dir.is_dir():
        raise FileNotFoundError("Project workspace does not exist.")

    prepared: list[tuple[str, Path, str, int]] = []
    seen: set[str] = set()
    total_bytes = 0

    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Each generated file must be an object.")
        relative = item.get("path")
        content = item.get("content")
        if not isinstance(relative, str) or not isinstance(content, str):
            raise ValueError("Each generated file requires string path and content fields.")
        if not relative or relative.startswith("/") or "\\\\" in relative or "\\x00" in relative:
            raise ValueError("Generated file paths must be safe relative POSIX paths.")

        raw_parts = relative.split("/")
        if any(part in ("", ".", "..") for part in raw_parts):
            raise ValueError("Generated file path contains an invalid segment.")
        pure_path = PurePosixPath(relative)
        normalized = pure_path.as_posix()
        if normalized in seen:
            raise ValueError("Generation contains duplicate file paths.")
        seen.add(normalized)

        target = project_dir.joinpath(*pure_path.parts)
        resolved = target.resolve(strict=False)
        if resolved == project_dir or project_dir not in resolved.parents:
            raise ValueError("Generated file path escapes the project workspace.")
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"File already exists: {normalized}")

        encoded_size = len(content.encode("utf-8"))
        total_bytes += encoded_size
        if total_bytes > MAX_GENERATED_BYTES:
            raise ValueError("Generated output exceeds the 1 MB project-file limit.")
        prepared.append((normalized, target, content, encoded_size))

    return project_dir, prepared


def validate_generated_files(root: Path, slug: str, files: list[dict]) -> list[dict]:
    """Validate a proposed file set without writing anything to disk."""
    _, prepared = _prepare_generated_files(root, slug, files)
    return [
        {"path": normalized, "size_bytes": encoded_size}
        for normalized, _, _, encoded_size in prepared
    ]


def write_generated_files(root: Path, slug: str, files: list[dict]) -> list[dict]:
    project_dir, prepared = _prepare_generated_files(root, slug, files)
    created: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for normalized, target, content, _ in prepared:
            missing = []
            parent = target.parent
            while parent != project_dir and not parent.exists():
                missing.append(parent)
                parent = parent.parent
            target.parent.mkdir(parents=True, exist_ok=True)
            for directory in reversed(missing):
                created_dirs.append(directory)

            resolved_parent = target.parent.resolve()
            if resolved_parent != project_dir and project_dir not in resolved_parent.parents:
                raise ValueError("Generated file parent escapes the project workspace.")
            with target.open("x", encoding="utf-8", newline="") as handle:
                handle.write(content)
            created.append(target)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    return [
        {"path": normalized, "size_bytes": encoded_size}
        for normalized, _, _, encoded_size in prepared
    ]
