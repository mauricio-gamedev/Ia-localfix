import hashlib
import os
import re
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath


MAX_GENERATED_FILES = 30
MAX_GENERATED_BYTES = 1_000_000
MAX_INSPECT_FILE_BYTES = 24_000
MAX_INSPECT_TOTAL_BYTES = 72_000
MAX_INSPECT_FILES = 160
PREVIEW_BYTES = 1_800

SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".gradle", "build", "dist",
    "target", ".idea", ".vscode", ".next", ".expo", ".dart_tool", "coverage",
}
SKIP_FILES = {
    ".env", ".env.local", ".env.production", "id_rsa", "id_ed25519",
}
ALLOWED_HIDDEN_DIRS = {".github", ".husky", ".circleci", ".devcontainer"}
ALLOWED_HIDDEN_FILES = {".gitignore", ".dockerignore", ".editorconfig", ".npmignore"}
TEXT_SUFFIXES = {
    ".py", ".pyi", ".kt", ".java", ".kts", ".gradle", ".toml", ".json",
    ".yaml", ".yml", ".xml", ".md", ".txt", ".properties", ".js", ".mjs",
    ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".sh", ".sql",
    ".go", ".rs", ".c", ".h", ".cpp", ".hpp", ".cs", ".swift", ".rb", ".php",
    ".ini", ".cfg", ".gradle.kts", ".bat", ".ps1",
}
TEXT_NAMES = {
    "Dockerfile", "Makefile", "Procfile", "Gemfile", "Podfile",
    "gradlew", "gradlew.bat", "settings.gradle", "settings.gradle.kts",
    "build.gradle", "build.gradle.kts",
}


def make_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    if not slug:
        raise ValueError("Project name must contain letters or numbers.")
    return slug[:64].strip("-")


def project_directory(root: Path, slug: str) -> Path:
    workspace_root = root.expanduser().resolve()
    project_dir = (workspace_root / slug).resolve()
    if project_dir == workspace_root or workspace_root not in project_dir.parents:
        raise ValueError("Project workspace escapes the configured root.")
    if not project_dir.is_dir():
        raise FileNotFoundError("Project workspace does not exist.")
    return workspace_root, project_dir


def create_workspace(root: Path, slug: str) -> Path:
    workspace_root = root.expanduser().resolve()
    target = (workspace_root / slug).resolve()
    if target == workspace_root or workspace_root not in target.parents:
        raise ValueError("Workspace path escapes the configured root.")
    target.mkdir(parents=True, exist_ok=False)
    return target


def _safe_relative_path(relative: str) -> PurePosixPath:
    if (
        not isinstance(relative, str)
        or not relative
        or relative.startswith("/")
        or "\\\\" in relative
        or "\\x00" in relative
    ):
        raise ValueError("File paths must be safe relative POSIX paths.")
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("File path contains an invalid segment.")
    path = PurePosixPath(relative)
    if any(
        part.startswith(".")
        and part not in ALLOWED_HIDDEN_DIRS
        and part not in ALLOWED_HIDDEN_FILES
        and part != ".well-known"
        for part in path.parts
    ):
        raise ValueError("Hidden paths are not available to the agent.")
    if any(part.lower() in SKIP_DIRS for part in path.parts):
        raise ValueError("Build, cache, or VCS paths are not available to the agent.")
    if path.name.lower() in SKIP_FILES or path.name.lower().endswith((".pem", ".key", ".p12", ".pfx")):
        raise ValueError("Secret and key files are not available to the agent.")
    return path


def _resolve_target(project_dir: Path, relative: str) -> tuple[str, Path]:
    pure_path = _safe_relative_path(relative)
    normalized = pure_path.as_posix()
    target = project_dir.joinpath(*pure_path.parts)
    resolved = target.resolve(strict=False)
    if resolved == project_dir or project_dir not in resolved.parents:
        raise ValueError("File path escapes the project workspace.")
    current = project_dir
    for part in pure_path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symbolic links are not available to the agent.")
    return normalized, target


def inspect_workspace(
    root: Path,
    slug: str,
    *,
    max_files: int = MAX_INSPECT_FILES,
    max_total_bytes: int = MAX_INSPECT_TOTAL_BYTES,
    max_file_bytes: int = MAX_INSPECT_FILE_BYTES,
) -> dict:
    """Read a bounded, text-only snapshot. Symlinks and secret/build folders are skipped."""
    _, project_dir = project_directory(root, slug)
    results: list[dict] = []
    total_bytes = 0
    omitted = 0
    markers: set[str] = set()

    for current_root, dirs, filenames in os.walk(project_dir, topdown=True, followlinks=False):
        current_path = Path(current_root)
        dirs[:] = sorted(
            name for name in dirs
            if name.lower() not in SKIP_DIRS
            and (not name.startswith(".") or name in ALLOWED_HIDDEN_DIRS)
            and not (current_path / name).is_symlink()
        )
        for filename in sorted(filenames):
            path = current_path / filename
            if path.is_symlink() or filename.lower() in SKIP_FILES:
                omitted += 1
                continue
            rel = path.relative_to(project_dir).as_posix()
            suffix = path.suffix.lower()
            if (
                filename not in TEXT_NAMES
                and filename not in ALLOWED_HIDDEN_FILES
                and suffix not in TEXT_SUFFIXES
            ):
                omitted += 1
                continue
            if filename in {"pyproject.toml", "requirements.txt", "package.json",
                            "settings.gradle", "settings.gradle.kts", "build.gradle",
                            "build.gradle.kts", "Cargo.toml", "go.mod", "pom.xml"}:
                markers.add(filename)
            if len(results) >= max_files:
                omitted += 1
                continue
            try:
                size = path.stat().st_size
                if size > max_file_bytes or total_bytes + size > max_total_bytes:
                    omitted += 1
                    continue
                raw = path.read_bytes()
                text = raw.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                omitted += 1
                continue
            total_bytes += len(raw)
            results.append(
                {
                    "path": rel,
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "preview": text[:PREVIEW_BYTES],
                    "content": text,
                    "truncated": len(text) > PREVIEW_BYTES,
                }
            )

    return {
        "files": results,
        "file_count": len(results),
        "omitted_count": omitted,
        "total_bytes": total_bytes,
        "project_markers": sorted(markers),
    }


def validate_generated_files(root: Path, slug: str, files: list[dict]) -> list[dict]:
    """Validate a new-file-only proposal without writing anything to disk."""
    _, project_dir = project_directory(root, slug)
    if not isinstance(files, list) or not files or len(files) > MAX_GENERATED_FILES:
        raise ValueError(f"Generation must contain between 1 and {MAX_GENERATED_FILES} files.")

    prepared = []
    seen: set[str] = set()
    total_bytes = 0
    for item in files:
        if not isinstance(item, dict) or item.get("operation", "create") != "create":
            raise ValueError("This operation only accepts create file entries.")
        relative = item.get("path")
        content = item.get("content")
        if not isinstance(content, str):
            raise ValueError("Each generated file requires string content.")
        normalized, target = _resolve_target(project_dir, relative)
        if normalized in seen:
            raise ValueError("Generation contains duplicate file paths.")
        seen.add(normalized)
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"File already exists: {normalized}")
        size = len(content.encode("utf-8"))
        total_bytes += size
        if total_bytes > MAX_GENERATED_BYTES:
            raise ValueError("Generated output exceeds the 1 MB project-file limit.")
        prepared.append({"path": normalized, "operation": "create", "size_bytes": size})
    return prepared


def validate_generated_changes(root: Path, slug: str, changes: list[dict]) -> list[dict]:
    """Validate create/update changes and optimistic hashes without modifying files."""
    _, project_dir = project_directory(root, slug)
    if not isinstance(changes, list) or not changes or len(changes) > MAX_GENERATED_FILES:
        raise ValueError(f"A proposal must contain between 1 and {MAX_GENERATED_FILES} file changes.")

    prepared = []
    seen: set[str] = set()
    total_bytes = 0
    for item in changes:
        if not isinstance(item, dict):
            raise ValueError("Each file change must be an object.")
        operation = item.get("operation", "create")
        if operation not in {"create", "update"}:
            raise ValueError("Only create and update file operations are supported.")
        content = item.get("content")
        if not isinstance(content, str):
            raise ValueError("Each file change requires string content.")
        normalized, target = _resolve_target(project_dir, item.get("path"))
        if normalized in seen:
            raise ValueError("Proposal contains duplicate file paths.")
        seen.add(normalized)

        current_hash = None
        if operation == "create":
            if target.exists() or target.is_symlink():
                raise FileExistsError(f"File already exists: {normalized}")
            if item.get("expected_sha256") is not None:
                raise ValueError("Create operations must not include an expected file hash.")
        else:
            if not target.is_file() or target.is_symlink():
                raise FileNotFoundError(f"File to update does not exist: {normalized}")
            raw = target.read_bytes()
            try:
                raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Binary files cannot be updated: {normalized}") from exc
            if len(raw) > MAX_INSPECT_FILE_BYTES:
                raise ValueError(f"File is too large to update safely: {normalized}")
            current_hash = hashlib.sha256(raw).hexdigest()
            expected = item.get("expected_sha256")
            if not isinstance(expected, str) or expected != current_hash:
                raise ValueError(f"File changed since inspection: {normalized}")
        size = len(content.encode("utf-8"))
        total_bytes += size
        if total_bytes > MAX_GENERATED_BYTES:
            raise ValueError("Proposed output exceeds the 1 MB limit.")
        prepared.append(
            {
                "path": normalized,
                "target": target,
                "operation": operation,
                "content": content,
                "size_bytes": size,
                "before_sha256": current_hash,
            }
        )
    return prepared


def _write_temp(target: Path, content: bytes) -> Path:
    fd, name = tempfile.mkstemp(prefix=".ia-localfix-", dir=target.parent)
    temp_path = Path(name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def apply_generated_changes(root: Path, slug: str, changes: list[dict]) -> list[dict]:
    """Apply approved create/update changes with hash checks and best-effort rollback."""
    _, project_dir = project_directory(root, slug)
    prepared = validate_generated_changes(root, slug, changes)
    created: list[Path] = []
    updated: list[tuple[Path, bytes]] = []
    created_dirs: list[Path] = []
    try:
        for item in prepared:
            target = item["target"]
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

            data = item["content"].encode("utf-8")
            if item["operation"] == "create":
                handle = target.open("xb")
                created.append(target)
                with handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            else:
                if target.is_symlink() or not target.is_file():
                    raise ValueError(f"File target is no longer a regular file: {item['path']}")
                original = target.read_bytes()
                actual_hash = hashlib.sha256(original).hexdigest()
                if actual_hash != item["before_sha256"]:
                    raise ValueError(f"File changed during approval: {item['path']}")
                updated.append((target, original))
                temp_path = _write_temp(target, data)
                try:
                    os.replace(temp_path, target)
                except Exception:
                    temp_path.unlink(missing_ok=True)
                    raise

    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        for path, original in reversed(updated):
            try:
                temp_path = _write_temp(path, original)
                os.replace(temp_path, path)
            except OSError:
                pass
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    results = []
    for item in prepared:
        data = item["content"].encode("utf-8")
        results.append(
            {
                "path": item["path"],
                "operation": item["operation"],
                "size_bytes": item["size_bytes"],
                "before_sha256": item["before_sha256"],
                "after_sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return results


def write_generated_files(root: Path, slug: str, files: list[dict]) -> list[dict]:
    """Compatibility wrapper for the explicit create-only generation endpoint."""
    if not isinstance(files, list):
        raise ValueError("Generated files must be a list.")
    create_changes = [
        {
            "path": item.get("path"),
            "content": item.get("content"),
            "operation": "create",
        }
        if isinstance(item, dict)
        else item
        for item in files
    ]
    validate_generated_files(root, slug, create_changes)
    return apply_generated_changes(root, slug, create_changes)
