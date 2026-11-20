import ast
import json
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from app.workspaces import inspect_workspace


def validate_project(root: Path, slug: str) -> dict:
    """Perform non-executing syntax/format checks on supported text files."""
    snapshot = inspect_workspace(
        root,
        slug,
        max_files=300,
        max_total_bytes=1_000_000,
        max_file_bytes=256_000,
    )
    diagnostics: list[dict] = []
    checked_files = 0
    recognized = {".py", ".pyi", ".json", ".toml", ".xml"}

    for item in snapshot["files"]:
        path = item["path"]
        suffix = Path(path).suffix.lower()
        if suffix not in recognized:
            continue
        checked_files += 1
        content = item["content"]
        try:
            if suffix in {".py", ".pyi"}:
                ast.parse(content, filename=path)
            elif suffix == ".json":
                json.loads(content)
            elif suffix == ".toml":
                tomllib.loads(content)
            elif suffix == ".xml":
                ET.fromstring(content)
        except SyntaxError as exc:
            diagnostics.append(
                {
                    "path": path,
                    "severity": "error",
                    "message": exc.msg,
                    "line": exc.lineno,
                    "column": exc.offset,
                }
            )
        except json.JSONDecodeError as exc:
            diagnostics.append(
                {
                    "path": path,
                    "severity": "error",
                    "message": exc.msg,
                    "line": exc.lineno,
                    "column": exc.colno,
                }
            )
        except tomllib.TOMLDecodeError as exc:
            diagnostics.append(
                {
                    "path": path,
                    "severity": "error",
                    "message": str(exc),
                    "line": None,
                    "column": None,
                }
            )
        except ET.ParseError as exc:
            diagnostics.append(
                {
                    "path": path,
                    "severity": "error",
                    "message": str(exc),
                    "line": getattr(exc, "position", (None, None))[0],
                    "column": getattr(exc, "position", (None, None))[1],
                }
            )

    errors = sum(item["severity"] == "error" for item in diagnostics)
    return {
        "success": errors == 0,
        "checked_files": checked_files,
        "error_count": errors,
        "diagnostics": diagnostics[:100],
        "omitted_count": snapshot["omitted_count"],
        "project_markers": snapshot["project_markers"],
        "execution_performed": False,
    }
