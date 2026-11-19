import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.workspaces import SKIP_DIRS, project_directory

MAX_BUILD_SOURCE_BYTES = 250_000_000
MAX_BUILD_SOURCE_FILES = 10_000
MAX_BUILD_LOG_CHARS = 40_000
MAX_ARTIFACTS = 20
MAX_ARTIFACT_BYTES = 200_000_000
IMAGE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/:@-]{0,255}$")
SECRET_NAMES = {
    ".npmrc", ".pypirc", ".netrc", "credentials", "credentials.json",
    "service-account.json", "google-services.json",
}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore", ".jks"}


@dataclass(frozen=True, slots=True)
class BuildProfile:
    id: str
    title: str
    description: str
    image: str
    command: tuple[str, ...]
    command_preview: str
    requires: str
    artifact_patterns: tuple[str, ...] = ()


def profile_registry(settings: Any) -> dict[str, BuildProfile]:
    return {
        "python-unittest": BuildProfile(
            "python-unittest", "Python unit tests",
            "Run the standard-library unittest discovery runner.",
            settings.python_builder_image,
            ("python", "-m", "unittest", "discover", "-v"),
            "python -m unittest discover -v",
            "At least one Python source or test file.",
        ),
        "node-test": BuildProfile(
            "node-test", "Node.js tests",
            "Run Node's built-in test runner without npm lifecycle scripts.",
            settings.node_builder_image, ("node", "--test"), "node --test",
            "A package.json file.",
        ),
        "android-debug": BuildProfile(
            "android-debug", "Android debug APK",
            "Run the Gradle wrapper offline and collect APK/AAB outputs.",
            settings.android_builder_image,
            ("./gradlew", "--no-daemon", "--offline", "assembleDebug"),
            "./gradlew --no-daemon --offline assembleDebug",
            "Gradle wrapper plus an Android SDK builder image with dependencies preloaded.",
            ("**/build/outputs/**/*.apk", "**/build/outputs/**/*.aab"),
        ),
        "android-unit-tests": BuildProfile(
            "android-unit-tests", "Android unit tests",
            "Run Gradle debug unit tests offline.",
            settings.android_builder_image,
            ("./gradlew", "--no-daemon", "--offline", "testDebugUnitTest"),
            "./gradlew --no-daemon --offline testDebugUnitTest",
            "Gradle wrapper plus an Android SDK builder image with dependencies preloaded.",
        ),
    }


def _is_secret(path: Path) -> bool:
    name = path.name.lower()
    return (
        name.startswith(".env") or name in SECRET_NAMES
        or path.suffix.lower() in SECRET_SUFFIXES
        or name.endswith((".pem", ".key", ".p12", ".pfx"))
    )


def get_build_profiles(root: Path, slug: str, settings: Any) -> list[dict]:
    _, project_dir = project_directory(root, slug)
    has_python = any(
        path.suffix.lower() in {".py", ".pyi"}
        for path in project_dir.rglob("*")
        if path.is_file() and not path.is_symlink()
        and not any(part.lower() in SKIP_DIRS for part in path.relative_to(project_dir).parts)
    )
    has_node = (project_dir / "package.json").is_file()
    has_wrapper = (project_dir / "gradlew").is_file()
    has_gradle = any(
        (project_dir / name).is_file()
        for name in ("build.gradle", "build.gradle.kts")
    ) or any(
        path.name in {"build.gradle", "build.gradle.kts"}
        and not any(part.lower() in SKIP_DIRS for part in path.relative_to(project_dir).parts)
        for path in project_dir.rglob("*") if path.is_file() and not path.is_symlink()
    )
    available = {
        "python-unittest": (has_python, "No Python source or test files were found."),
        "node-test": (has_node, "No package.json was found."),
        "android-debug": (
            has_wrapper and has_gradle and bool(settings.android_builder_image),
            "Requires gradlew, a Gradle build file, and IA_ANDROID_BUILDER_IMAGE.",
        ),
        "android-unit-tests": (
            has_wrapper and has_gradle and bool(settings.android_builder_image),
            "Requires gradlew, a Gradle build file, and IA_ANDROID_BUILDER_IMAGE.",
        ),
    }
    output = []
    for profile in profile_registry(settings).values():
        enabled, reason = available[profile.id]
        if profile.id.startswith("android-") and not settings.android_builder_image:
            reason = "Android SDK image is not configured (IA_ANDROID_BUILDER_IMAGE)."
        output.append({
            "id": profile.id, "title": profile.title, "description": profile.description,
            "command_preview": profile.command_preview, "requires": profile.requires,
            "available": enabled, "reason": None if enabled else reason,
        })
    return output


def _copy_workspace_for_build(source: Path, destination: Path) -> None:
    """Copy project input into scratch, excluding secrets, symlinks and caches."""
    total_bytes = 0
    file_count = 0
    destination.mkdir(parents=True, exist_ok=True)
    os.chmod(destination, 0o777)
    for current_root, dirs, filenames in os.walk(source, topdown=True, followlinks=False):
        current = Path(current_root)
        target_dir = destination / current.relative_to(source)
        target_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(target_dir, 0o777)
        dirs[:] = [
            name for name in dirs
            if name.lower() not in SKIP_DIRS
            and name.lower() not in {".ssh", ".aws", ".gnupg", "secrets"}
            and not name.lower().startswith(".env")
            and not (current / name).is_symlink()
        ]
        for filename in filenames:
            src = current / filename
            if src.is_symlink() or _is_secret(src) or not src.is_file():
                continue
            stat = src.stat()
            file_count += 1
            total_bytes += stat.st_size
            if file_count > MAX_BUILD_SOURCE_FILES:
                raise ValueError("Build source contains too many files (limit: 10,000).")
            if total_bytes > MAX_BUILD_SOURCE_BYTES:
                raise ValueError("Build source exceeds the 250 MB safety limit.")
            target = destination / src.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target, follow_symlinks=False)
            mode = (stat.st_mode & 0o777) | 0o666
            if stat.st_mode & 0o111:
                mode |= 0o111
            os.chmod(target, mode)


def _collect_artifacts(workspace: Path, artifact_root: Path, job_id: str, patterns: tuple[str, ...]) -> list[dict]:
    if not patterns:
        return []
    destination = artifact_root / job_id
    artifacts: list[dict] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for candidate in workspace.glob(pattern):
            if candidate in seen or not candidate.is_file() or candidate.is_symlink():
                continue
            seen.add(candidate)
            if len(artifacts) >= MAX_ARTIFACTS:
                break
            size = candidate.stat().st_size
            if size <= 0 or size > MAX_ARTIFACT_BYTES:
                continue
            destination.mkdir(parents=True, exist_ok=True)
            name = f"{len(artifacts) + 1}-{candidate.name}"
            target = destination / name
            shutil.copy2(candidate, target)
            artifacts.append({
                "name": name, "size_bytes": size,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            })
    return artifacts


def _container_args(docker_binary: str, profile: BuildProfile, workspace: Path, settings: Any) -> list[str]:
    if not IMAGE_REF.fullmatch(profile.image):
        raise ValueError("Configured builder image reference is invalid.")
    if not 1 <= settings.build_timeout_seconds <= 1800:
        raise ValueError("Build timeout must be between 30 and 1800 seconds.")
    if not re.fullmatch(r"[1-9][0-9]*[mMgG]", settings.build_memory_limit):
        raise ValueError("Build memory limit must use a positive M or G value.")
    if not 0.1 <= settings.build_cpus <= 8 or not 32 <= settings.build_pids_limit <= 512:
        raise ValueError("Build CPU or PID limit is outside the supported range.")
    return [
        docker_binary, "run", "--rm", "--pull=missing", "--network=none",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit", str(settings.build_pids_limit),
        "--memory", settings.build_memory_limit, "--memory-swap", settings.build_memory_limit,
        "--cpus", str(settings.build_cpus), "--user", "10001:10001",
        "--workdir", "/workspace", "--hostname", "ia-localfix-worker",
        "--env", "CI=true", "--env", "HOME=/home/runner",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=128m,uid=10001,gid=10001",
        "--tmpfs", "/home/runner:rw,nosuid,size=512m,uid=10001,gid=10001",
        "--mount", f"type=bind,source={workspace},target=/workspace",
        profile.image, *profile.command,
    ]


def execute_build(root: Path, slug: str, profile_id: str, settings: Any, job_id: str) -> dict:
    """Run a server-allowlisted profile in an offline, resource-limited Docker container."""
    profile = profile_registry(settings).get(profile_id)
    if profile is None:
        raise ValueError("Unknown build profile.")
    if not profile.image:
        return {
            "status": "failed", "exit_code": None, "duration_ms": 0,
            "log": "", "error": "The required builder image is not configured on the server.",
            "artifacts": [],
        }
    _, project_dir = project_directory(root, slug)
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="ia-localfix-build-") as temp:
            workspace = Path(temp) / "workspace"
            _copy_workspace_for_build(project_dir, workspace)
            args = _container_args(settings.docker_binary, profile, workspace, settings)
            try:
                completed = subprocess.run(
                    args, capture_output=True, text=True, errors="replace",
                    timeout=settings.build_timeout_seconds, check=False,
                )
                log = ((completed.stdout or "") + (completed.stderr or ""))[-MAX_BUILD_LOG_CHARS:]
                status = "succeeded" if completed.returncode == 0 else "failed"
                error = None if completed.returncode == 0 else (
                    f"Build container exited with status {completed.returncode}."
                )
                exit_code = completed.returncode
            except subprocess.TimeoutExpired as exc:
                out, err = exc.stdout or "", exc.stderr or ""
                if isinstance(out, bytes):
                    out = out.decode("utf-8", errors="replace")
                if isinstance(err, bytes):
                    err = err.decode("utf-8", errors="replace")
                log = (str(out) + str(err))[-MAX_BUILD_LOG_CHARS:]
                status, error, exit_code = (
                    "timed_out",
                    f"Build exceeded the {settings.build_timeout_seconds}-second timeout.",
                    None,
                )
            except FileNotFoundError:
                log, status, exit_code = "", "failed", None
                error = f"Docker executable '{settings.docker_binary}' was not found."
            artifacts = []
            if status == "succeeded":
                artifacts = _collect_artifacts(
                    workspace, settings.artifact_root, job_id, profile.artifact_patterns
                )
            return {
                "status": status, "exit_code": exit_code,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "log": log, "error": error, "artifacts": artifacts,
            }
    except (OSError, ValueError) as exc:
        return {
            "status": "failed", "exit_code": None,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "log": "", "error": str(exc)[:1000], "artifacts": [],
        }


def add_build_event(db, job_id: str, event_type: str, payload: dict) -> None:
    import json
    import uuid
    db.execute(
        """INSERT INTO build_events (id, build_id, event_type, payload_json)
           VALUES (?, ?, ?, ?)""",
        (str(uuid.uuid4()), job_id, event_type, json.dumps(payload, ensure_ascii=False)),
    )


def build_job_response(row) -> dict:
    import json
    return {
        "id": row["id"], "project_id": row["project_id"],
        "profile_id": row["profile_id"], "status": row["status"],
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "error": row["error"], "created_at": row["created_at"],
        "updated_at": row["updated_at"], "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


def build_event_responses(db, job_id: str) -> list[dict]:
    import json
    rows = db.execute(
        """SELECT id, event_type, payload_json, created_at
           FROM build_events WHERE build_id = ? ORDER BY created_at, rowid""",
        (job_id,),
    ).fetchall()
    return [
        {
            "id": row["id"], "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"]), "created_at": row["created_at"],
        }
        for row in rows
    ]
