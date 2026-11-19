"""Structured diagnostics extracted from bounded build-worker output."""
from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import unquote

MAX_DIAGNOSTICS = 100
MAX_MESSAGE_CHARS = 2_000
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PYTHON_FRAME_RE = re.compile(r'File ["\'](?P<path>/workspace/[^"\']+)["\'], line (?P<line>\d+)')
NODE_LOCATION_RE = re.compile(
    r"""location:\s*['"]?file://(?P<path>/workspace/[^:'"\s]+):(?P<line>\d+):(?P<column>\d+)"""
)
GRADLE_KOTLIN_RE = re.compile(r"(?P<path>file:///workspace/[^:\s]+):\s*\((?P<line>\d+),\s*(?P<column>\d+)\):\s*(?P<message>.+)")
GRADLE_COMPILER_RE = re.compile(r"(?P<path>file:///workspace/[^:\s]+):(?P<line>\d+):(?P<column>\d+):\s*error:\s*(?P<message>.+)")
GRADLE_TASK_RE = re.compile(r"> Task (?P<task>:[A-Za-z0-9_:-]+) FAILED")
ERROR_LINE_RE = re.compile(r"^(?:ERROR|FAIL|FAILED|not ok\b|error:|AssertionError:|ImportError:|ModuleNotFoundError:)(.*)$", re.I)


def _workspace_path(value: str | None) -> str | None:
    if not value:
        return None
    decoded = unquote(value)
    marker = "/workspace/"
    if marker not in decoded:
        return None
    relative = decoded.split(marker, 1)[1].replace("\\", "/")
    path = PurePosixPath(relative)
    if not relative or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path.as_posix()


def _diagnostic(category: str, message: str, *, path: str | None = None,
                line: int | None = None, column: int | None = None) -> dict:
    return {
        "severity": "error", "category": category, "path": _workspace_path(path),
        "line": line, "column": column,
        "message": (message.strip() or "Build failed.")[:MAX_MESSAGE_CHARS],
    }


def parse_build_diagnostics(profile_id: str, status: str, log: str, exit_code: int | None) -> list[dict]:
    """Parse common compiler/test failure formats without executing project code."""
    clean = ANSI_RE.sub("", (log or "")[-40_000:])
    lines = clean.splitlines()
    found: list[dict] = []
    seen: set[tuple] = set()

    def add(item: dict) -> None:
        key = (item["category"], item["path"], item["line"], item["column"], item["message"])
        if key not in seen and len(found) < MAX_DIAGNOSTICS:
            seen.add(key)
            found.append(item)

    if status == "timed_out":
        return [_diagnostic("timeout", "Build exceeded its configured execution timeout.")]
    if status == "succeeded":
        return []

    for index, line in enumerate(lines):
        py = PYTHON_FRAME_RE.search(line)
        if py:
            message = "Python traceback"
            for tail in lines[index + 1:index + 10]:
                if tail.strip():
                    message = tail.strip()
            add(_diagnostic("python_test_or_runtime", message, path=py.group("path"), line=int(py.group("line"))))
            continue
        node = NODE_LOCATION_RE.search(line)
        if node:
            message = "Node.js test failure"
            for tail in lines[index + 1:index + 8]:
                stripped = tail.strip()
                if stripped.startswith(("error:", "message:", "name:")):
                    message = stripped.split(":", 1)[-1].strip().strip("'\"")
                    break
            add(_diagnostic("node_test", message, path=node.group("path"),
                            line=int(node.group("line")), column=int(node.group("column"))))
            continue
        gradle = GRADLE_KOTLIN_RE.search(line)
        if gradle:
            add(_diagnostic("gradle_compiler", gradle.group("message"), path=gradle.group("path"),
                            line=int(gradle.group("line")), column=int(gradle.group("column"))))
            continue
        compiler = GRADLE_COMPILER_RE.search(line)
        if compiler:
            add(_diagnostic("gradle_compiler", compiler.group("message"), path=compiler.group("path"),
                            line=int(compiler.group("line")), column=int(compiler.group("column"))))
            continue
        task = GRADLE_TASK_RE.search(line)
        if task:
            add(_diagnostic("gradle_task", f"Gradle task {task.group('task')} failed."))
            continue
        if ERROR_LINE_RE.match(line.strip()) and line.strip():
            add(_diagnostic("test_or_build", line.strip()))

    if not found and status == "failed":
        reason = f"Build command exited with status {exit_code}." if exit_code is not None else (
            "Build worker failed before returning an exit status."
        )
        add(_diagnostic("build_failure", reason))
    return found
