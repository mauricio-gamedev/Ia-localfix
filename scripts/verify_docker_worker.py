"""Live Docker smoke test for the isolated build worker (CI only)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from app.builds import execute_build
from app.config import Settings


def main() -> int:
    image = os.getenv("IA_PYTHON_BUILDER_IMAGE", "python:3.12-slim")
    with tempfile.TemporaryDirectory(prefix="ia-localfix-docker-ci-") as temp:
        root = Path(temp) / "workspaces"
        project = root / "docker-smoke"
        project.mkdir(parents=True)
        (project / "test_smoke.py").write_text(
            "import unittest\n"
            "class WorkerSmokeTest(unittest.TestCase):\n"
            "    def test_container_executes_project_test(self):\n"
            "        self.assertEqual(2 + 2, 4)\n",
            encoding="utf-8",
        )
        settings = Settings(
            workspace_root=root,
            artifact_root=Path(temp) / "artifacts",
            python_builder_image=image,
            build_timeout_seconds=90,
            build_memory_limit="1g",
            build_cpus=1.0,
            build_pids_limit=64,
        )
        result = execute_build(root, "docker-smoke", "python-unittest", settings, "ci-smoke")
        if result["status"] != "succeeded":
            print("Docker worker integration failed:", result.get("error"), file=sys.stderr)
            print(result.get("log", ""), file=sys.stderr)
            return 1
        if "Ran 1 test" not in result.get("log", ""):
            print("Container exited without reporting the expected test execution.", file=sys.stderr)
            print(result.get("log", ""), file=sys.stderr)
            return 1
        if result.get("diagnostics"):
            print("Unexpected diagnostics:", result["diagnostics"], file=sys.stderr)
            return 1
        print("Live Docker worker integration passed: 1 unittest executed in the isolated container.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
