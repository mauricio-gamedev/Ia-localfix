"""Normalized test summaries parsed from bounded tool output."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_REPORT_FILES = 50
MAX_REPORT_FILE_BYTES = 512_000


def _summary(report_format: str, total: int, passed: int, failed: int,
             skipped: int, todo: int = 0, suites: int = 0,
             duration_ms: int | None = None) -> dict:
    total = max(0, total)
    failed = min(total, max(0, failed))
    skipped = min(total - failed, max(0, skipped))
    passed = min(total - failed - skipped, max(0, passed))
    return {
        "format": report_format, "total": total, "passed": passed,
        "failed": failed, "skipped": skipped, "todo": max(0, todo),
        "suites": max(0, suites), "duration_ms": duration_ms,
    }


def _python_unittest(status: str, log: str) -> dict | None:
    match = re.search(r"^Ran\s+(\d+)\s+tests?\s+in\s+([0-9.]+)s\s*$", log, re.MULTILINE)
    if not match:
        return None
    total = int(match.group(1))
    duration_ms = round(float(match.group(2)) * 1000)
    tail = log[match.end():]
    failed_match = re.search(r"^FAILED\s*\(([^)]*)\)", tail, re.MULTILINE)
    ok_match = re.search(r"^OK(?:\s*\(([^)]*)\))?", tail, re.MULTILINE)
    counts_text = failed_match.group(1) if failed_match else (ok_match.group(1) if ok_match else "")
    counts = {
        key: int(value)
        for key, value in re.findall(r"(failures|errors|skipped)\s*=\s*(\d+)", counts_text)
    }
    failed = counts.get("failures", 0) + counts.get("errors", 0)
    if status == "failed" and failed == 0:
        failed = 1
    skipped = counts.get("skipped", 0)
    passed = max(0, total - failed - skipped)
    return _summary("python-unittest", total, passed, failed, skipped,
                    suites=1, duration_ms=duration_ms)


def _node_tap(status: str, log: str) -> dict | None:
    def count(name: str) -> int | None:
        match = re.search(rf"^# {name}\s+(\d+)\s*$", log, re.MULTILINE)
        return int(match.group(1)) if match else None

    total = count("tests")
    if total is None:
        return None
    passed = count("pass") or 0
    failed = (count("fail") or 0) + (count("cancelled") or 0)
    skipped = count("skipped") or 0
    todo = count("todo") or 0
    duration = re.search(r"^# duration_ms\s+([0-9.]+)\s*$", log, re.MULTILINE)
    duration_ms = round(float(duration.group(1))) if duration else None
    if status == "failed" and failed == 0:
        failed = 1
    return _summary("node-tap", total, passed, failed, skipped, todo=todo,
                    suites=1, duration_ms=duration_ms)


def _junit_xml(workspace: Path) -> dict | None:
    total = failed = skipped = suites = duration_ms = 0
    found_duration = False
    candidates_seen = 0
    root_dir = workspace.resolve()

    for candidate in workspace.glob("**/TEST-*.xml"):
        if candidates_seen >= MAX_REPORT_FILES:
            break
        candidates_seen += 1
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root_dir):
                continue
            size = resolved.stat().st_size
            if size <= 0 or size > MAX_REPORT_FILE_BYTES:
                continue
            root = ET.parse(resolved).getroot()
        except (OSError, ET.ParseError, ValueError):
            continue
        suite_nodes = list(root.iter("testsuite"))
        if root.tag == "testsuite" and not suite_nodes:
            suite_nodes = [root]
        for suite in suite_nodes:
            try:
                tests = int(suite.attrib.get("tests", "0"))
                failures = int(suite.attrib.get("failures", "0"))
                errors = int(suite.attrib.get("errors", "0"))
                skipped_count = int(suite.attrib.get("skipped", "0"))
            except ValueError:
                continue
            total += max(0, tests)
            failed += max(0, failures) + max(0, errors)
            skipped += max(0, skipped_count)
            suites += 1
            try:
                duration_ms += round(float(suite.attrib.get("time", "0")) * 1000)
                found_duration = True
            except ValueError:
                pass

    if not suites or not total:
        return None
    failed = min(total, failed)
    skipped = min(total - failed, skipped)
    passed = max(0, total - failed - skipped)
    return _summary("junit-xml", total, passed, failed, skipped,
                    suites=suites, duration_ms=duration_ms if found_duration else None)


def parse_test_report(profile_id: str, status: str, log: str,
                      workspace: Path | None = None) -> dict | None:
    """Parse unittest/TAP summaries or bounded Gradle JUnit XML files."""
    bounded_log = (log or "")[-40_000:]
    if profile_id == "python-unittest":
        return _python_unittest(status, bounded_log)
    if profile_id == "node-test":
        return _node_tap(status, bounded_log)
    if profile_id.startswith("android-") and workspace is not None:
        return _junit_xml(workspace)
    return None
