#!/usr/bin/env python3
"""Deterministic helper CLI bundled with the ProMentor skill (Python >= 3.9, stdlib only)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


CHAPTER_ID_RE = re.compile(r"^(ch[0-9]{2}|final)-[a-z0-9]+(-[a-z0-9]+)*$")
CHECKSUM_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^$|^[0-9a-f]{40}$")
_PATH_SEG = r"(?:[A-Za-z0-9_@\[\]+.-]+|\([A-Za-z0-9_@\[\]+.-]+\))+"
LINE_REF_RE = re.compile(
    rf"(?<![A-Za-z0-9_./@\[\]+-])((?:{_PATH_SEG}/)*{_PATH_SEG}\.[A-Za-z][A-Za-z0-9_]*):(\d+)-(\d+)"
)
MERMAID_BLOCK_RE = re.compile(
    r"```mermaid\s*\n\s*(flowchart|graph|sequenceDiagram|classDiagram)\b",
    re.MULTILINE,
)
JS_TS_HOST_GLOB_RE = re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$", re.IGNORECASE)
PY_CD_REL_VENV_RE = re.compile(r"\bcd\s+[^&;]+&&\s*(?:\./)?\.?venv[/\\]")

HARD_BUILD_ERROR_SIGNATURES = [
    "[build failed]",
    "[setup failed]",
    "command not found",
    "cannot find package",
    "no Go files",
]

INFRA_ERROR_SIGNATURES = [
    *HARD_BUILD_ERROR_SIGNATURES,
    "ModuleNotFoundError",
    "ImportError",
    "SyntaxError",
    "Ran 0 tests",
    "ERR_MODULE_NOT_FOUND",
    "No such file or directory",
]

EXPECTED_RED_SIGNATURES = [
    "FAIL",
    "FAILED",
    "NotImplementedError",
    "not implemented",
    "AssertionError",
    "panic:",
    "not ok",
    "todo!",
    "UnsupportedOperationException",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return f"sha256:{h.hexdigest()}"


def load_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        errors.append(f"Missing required JSON file: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {path}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"Expected JSON object in {path}")
        return None
    return data


def is_git_repo(project_root: Path) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def normalize_rel_path(project_root: Path, rel_path: str) -> str | None:
    """Normalize a repo-relative POSIX path and reject absolute or escaping paths."""
    raw = rel_path.strip()
    if not raw or raw.startswith("/") or "\\" in raw:
        return None
    while raw.startswith("./"):
        raw = raw[2:]
    if not raw or raw.startswith("/"):
        return None
    parts = [p for p in raw.split("/") if p != "."]
    if not parts or any(p == ".." or p == "" for p in parts):
        return None
    normalized = "/".join(parts)
    try:
        resolved = (project_root / normalized).resolve()
        resolved.relative_to(project_root.resolve())
    except (OSError, ValueError):
        return None
    return normalized


def read_source_lines(project_root: Path, rel_path: str, source_commit: str) -> list[str] | None:
    """Read source file anchored to source_commit when available, else from working tree."""
    norm = normalize_rel_path(project_root, rel_path)
    if norm is None:
        return None
    if source_commit and is_git_repo(project_root):
        proc = subprocess.run(
            ["git", "show", f"{source_commit}:{norm}"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.splitlines()
    target = project_root / norm
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8").splitlines()


def detect_cycles(prereqs_map: dict[str, list[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    cycle_errors: list[str] = []

    def dfs(node: str) -> None:
        visiting.add(node)
        for nxt in prereqs_map.get(node, []):
            if nxt in visiting:
                cycle_errors.append(f"Circular prerequisite detected involving {node} -> {nxt}")
            elif nxt not in visited and nxt in prereqs_map:
                dfs(nxt)
        visiting.remove(node)
        visited.add(node)

    for ch_id in prereqs_map:
        if ch_id not in visited:
            dfs(ch_id)
    return cycle_errors


def check_line_ref(
    project_root: Path,
    rel_path: str,
    start: int,
    end: int,
    source_commit: str,
    origin: str,
    errors: list[str],
) -> None:
    norm = normalize_rel_path(project_root, rel_path)
    if norm is None:
        errors.append(f"{origin}: invalid or escaping source path: {rel_path}")
        return
    lines = read_source_lines(project_root, norm, source_commit)
    if lines is None:
        ref_scope = f"commit {source_commit[:7]}" if source_commit else "working tree"
        errors.append(f"{origin}: referenced source file does not exist in {ref_scope}: {norm}")
        return
    total_lines = len(lines)
    if start < 1 or end < start or end > total_lines:
        errors.append(
            f"{origin}: line range {norm}:{start}-{end} out of bounds (file has {total_lines} lines)"
        )


def extract_line_refs(text: str) -> list[tuple[str, str, str]]:
    """Extract (path, start, end) references while ignoring URLs."""
    refs: list[tuple[str, str, str]] = []
    for m in LINE_REF_RE.finditer(text):
        prefix = text[max(0, m.start() - 8) : m.start()]
        if "://" in prefix:
            continue
        refs.append((m.group(1), m.group(2), m.group(3)))
    return refs


def count_declared_tests(language: str, test_path: Path) -> int | None:
    text = test_path.read_text(encoding="utf-8")
    lang = language.lower()
    if lang == "go":
        return len(re.findall(r"^func\s+Test\w+\s*\(\s*\w+\s+\*testing\.T\s*\)", text, re.MULTILINE))
    if lang == "python":
        return len(re.findall(r"^\s*def\s+test_\w+\s*\(", text, re.MULTILINE))
    if lang in ("typescript", "javascript", "ts", "js"):
        return len(re.findall(r"^\s*(?:test|it)\s*\(\s*[\"'`]", text, re.MULTILINE))
    return None


def count_executed_tests(language: str, combined_output: str) -> int | None:
    lang = language.lower()
    if lang == "go":
        return len(re.findall(r"^--- (?:PASS|FAIL|SKIP): Test\w+ ", combined_output, re.MULTILINE))
    if lang == "python":
        m_unittest = re.search(r"^Ran (\d+) tests? in ", combined_output, re.MULTILINE)
        if m_unittest:
            return int(m_unittest.group(1))
        pytest_cases = re.findall(r"::test_\w+\s+(?:PASSED|FAILED|ERROR|SKIPPED|XFAIL)", combined_output)
        if pytest_cases:
            return len(pytest_cases)
        m_pytest_sum = re.findall(r"(\d+)\s+(?:passed|failed|error|errors|skipped|xfailed)", combined_output)
        if m_pytest_sum:
            return sum(int(x) for x in m_pytest_sum)
        return 0
    if lang in ("typescript", "javascript", "ts", "js"):
        m_node = re.search(r"(?:ℹ|#)\s+tests\s+(\d+)", combined_output)
        if m_node:
            return int(m_node.group(1))
        return 0
    return None


def count_passed_tests(language: str, combined_output: str) -> int | None:
    lang = language.lower()
    if lang == "go":
        return len(re.findall(r"^--- PASS: Test\w+ ", combined_output, re.MULTILINE))
    if lang == "python":
        m_unittest = re.search(r"^Ran (\d+) tests? in ", combined_output, re.MULTILINE)
        if m_unittest:
            ran = int(m_unittest.group(1))
            m_failed = re.search(r"^FAILED \(([^)]+)\)", combined_output, re.MULTILINE)
            if not m_failed:
                m_ok_skip = re.search(r"^OK \(skipped=(\d+)\)", combined_output, re.MULTILINE)
                skipped = int(m_ok_skip.group(1)) if m_ok_skip else 0
                return max(0, ran - skipped)
            non_pass = sum(
                int(v)
                for v in re.findall(r"(?:failures|errors|skipped)=(\d+)", m_failed.group(1))
            )
            return max(0, ran - non_pass)
        pytest_passed = re.findall(r"::test_\w+\s+PASSED", combined_output)
        if pytest_passed:
            return len(pytest_passed)
        m_pytest_sum = re.search(r"(\d+)\s+passed", combined_output)
        if m_pytest_sum:
            return int(m_pytest_sum.group(1))
        return 0
    if lang in ("typescript", "javascript", "ts", "js"):
        m_node = re.search(r"(?:ℹ|#)\s+pass\s+(\d+)", combined_output)
        if m_node:
            return int(m_node.group(1))
        return 0
    return None


def verify_chapter_files(
    project_root: Path,
    ch_id: str,
    source_commit: str,
    prog_entry: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    prom_dir = project_root / ".promentor"
    ch_dir = prom_dir / "chapters" / ch_id
    if not ch_dir.is_dir():
        return [f"Generated chapter directory missing: {ch_dir}"]

    # lecture.md
    lecture_path = ch_dir / "lecture.md"
    if not lecture_path.is_file():
        errors.append(f"{ch_id}: missing lecture.md")
    else:
        lecture_text = lecture_path.read_text(encoding="utf-8")
        lecture_lines = lecture_text.splitlines()
        if not lecture_text.strip():
            errors.append(f"{ch_id}: lecture.md is empty")
        if len(lecture_lines) > 300:
            errors.append(f"{ch_id}: lecture.md exceeds 300 lines ({len(lecture_lines)})")
        if not MERMAID_BLOCK_RE.search(lecture_text):
            errors.append(f"{ch_id}: lecture.md missing supported Mermaid diagram block")

    # source.md
    source_path = ch_dir / "source.md"
    if not source_path.is_file():
        errors.append(f"{ch_id}: missing source.md")
    else:
        source_text = source_path.read_text(encoding="utf-8")
        if "## Part 1:" not in source_text:
            errors.append(f"{ch_id}: source.md missing '## Part 1:' pre-lab section")
        if "## Part 2:" not in source_text:
            errors.append(f"{ch_id}: source.md missing '## Part 2:' post-submit section")
        refs = extract_line_refs(source_text)
        if not refs:
            errors.append(f"{ch_id}: source.md contains no file:start-end line references")
        for rel_path, s_str, e_str in refs:
            check_line_ref(
                project_root,
                rel_path,
                int(s_str),
                int(e_str),
                source_commit,
                f"{ch_id}/source.md",
                errors,
            )

    # lab.json
    lab = load_json(ch_dir / "lab.json", errors)
    if lab is None:
        return errors
    if lab.get("chapter_id") != ch_id:
        errors.append(f"{ch_id}/lab.json chapter_id mismatch: {lab.get('chapter_id')!r}")
    for req in (
        "title",
        "description",
        "language",
        "package",
        "files",
        "test_file",
        "test_checksum",
        "interface",
        "test_command",
    ):
        if req not in lab:
            errors.append(f"{ch_id}/lab.json missing required field: {req}")

    files = lab.get("files", [])
    if not isinstance(files, list) or not files:
        errors.append(f"{ch_id}/lab.json files must be a non-empty list")
        file_paths: list[str] = []
    else:
        file_paths = [f["path"] for f in files if isinstance(f, dict) and isinstance(f.get("path"), str)]
        for rel in file_paths:
            if not (ch_dir / rel).is_file():
                errors.append(f"{ch_id}: starter/implementation file missing: {rel}")

    starter_files = lab.get("starter_files", [])
    if starter_files:
        if not isinstance(starter_files, list):
            errors.append(f"{ch_id}/lab.json starter_files must be a list")
        else:
            for rel in starter_files:
                if not (ch_dir / rel).is_file():
                    errors.append(f"{ch_id}: starter_file missing: {rel}")

    if "notes" in lab and not isinstance(lab["notes"], (list, str)):
        errors.append(f"{ch_id}/lab.json notes must be a list of strings or a string")

    lang = str(lab.get("language", "")).lower()
    test_file = lab.get("test_file", "")
    test_cmd = lab.get("test_command", "")

    if lang in ("typescript", "javascript", "ts", "js") and isinstance(test_file, str):
        if JS_TS_HOST_GLOB_RE.search(test_file):
            errors.append(
                f"{ch_id}/lab.json: TS/JS test_file {test_file!r} matches host Vitest/Jest default glob (*.test.*/*.spec.*); use lab_test.ts or lab_test.mjs"
            )
    if lang == "python" and isinstance(test_cmd, str):
        if PY_CD_REL_VENV_RE.search(test_cmd):
            errors.append(
                f"{ch_id}/lab.json: Python test_command changes directory before invoking a relative venv python path; run from project root without 'cd'"
            )

    test_path = ch_dir / test_file if isinstance(test_file, str) and test_file else None
    if test_path is None or not test_path.is_file():
        errors.append(f"{ch_id}: missing test_file {test_file!r}")
    else:
        checksum = lab.get("test_checksum", "")
        if not isinstance(checksum, str) or not CHECKSUM_RE.match(checksum):
            errors.append(f"{ch_id}/lab.json invalid test_checksum format: {checksum!r}")
        else:
            actual = sha256_file(test_path)
            if actual != checksum:
                errors.append(
                    f"{ch_id}: test_checksum mismatch (tampered test file? expected {checksum}, got {actual})"
                )
        test_text = test_path.read_text(encoding="utf-8")
        if "Part A" not in test_text or "Part B" not in test_text:
            errors.append(f"{ch_id}/{test_file}: expected layered test markers ('Part A' and 'Part B')")

    if isinstance(prog_entry, dict):
        attempts = prog_entry.get("attempts", 0)
        if isinstance(attempts, int) and attempts >= 1:
            for attempt_idx in range(1, attempts + 1):
                attempt_dir = prom_dir / "submissions" / ch_id / f"attempt_{attempt_idx}"
                if not attempt_dir.is_dir():
                    errors.append(f"{ch_id}: missing submission directory {attempt_dir.relative_to(project_root)}")
                else:
                    for rel in file_paths:
                        if not (attempt_dir / rel).is_file():
                            errors.append(f"{ch_id}: submission attempt_{attempt_idx}/ missing archived file {rel}")

    return errors


def verify_course(
    project_root: Path,
    chapter_filter: str | None = None,
    strict_commit: bool = False,
) -> list[str]:
    errors: list[str] = []
    prom_dir = project_root / ".promentor"
    if not prom_dir.is_dir():
        return [f"Missing .promentor directory in {project_root}"]

    course = load_json(prom_dir / "course.json", errors)
    progress = load_json(prom_dir / "progress.json", errors)
    if course is None or progress is None:
        return errors

    for field in ("project", "language", "mode", "generation_mode", "source_commit", "generated_at", "chapters"):
        if field not in course:
            errors.append(f"course.json missing required field: {field}")

    if course.get("mode") not in ("challenge", "guided"):
        errors.append(f"course.json invalid mode: {course.get('mode')!r}")
    if course.get("generation_mode") not in ("lazy", "all"):
        errors.append(f"course.json invalid generation_mode: {course.get('generation_mode')!r}")
    if "focus" in course and course["focus"] is not None and not isinstance(course["focus"], str):
        errors.append("course.json field 'focus' must be string or null")

    source_commit = course.get("source_commit", "")
    if not isinstance(source_commit, str) or not COMMIT_RE.match(source_commit):
        errors.append(f"course.json invalid source_commit: {source_commit!r}")
        source_commit = ""
    elif source_commit and strict_commit and is_git_repo(project_root):
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if head.returncode == 0 and head.stdout.strip() != source_commit:
            errors.append(
                f"source_commit drift detected: course={source_commit[:7]} vs HEAD={head.stdout.strip()[:7]}"
            )

    chapters = course.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        errors.append("course.json chapters must be a non-empty list")
        return errors

    chapter_ids: list[str] = []
    prereqs_map: dict[str, list[str]] = {}
    for ch in chapters:
        if not isinstance(ch, dict):
            errors.append("course.json chapter entry must be an object")
            continue
        ch_id = ch.get("id", "")
        if not isinstance(ch_id, str) or not CHAPTER_ID_RE.match(ch_id):
            errors.append(f"course.json invalid chapter id: {ch_id!r}")
        if ch_id in chapter_ids:
            errors.append(f"course.json duplicate chapter id: {ch_id}")
        chapter_ids.append(ch_id)

        for req in (
            "title",
            "summary",
            "difficulty",
            "generation_status",
            "prerequisites",
            "learning_goals",
            "source_files",
            "lab_interface",
        ):
            if req not in ch:
                errors.append(f"course.json chapter {ch_id} missing required field: {req}")

        if ch.get("difficulty") not in ("easy", "mid", "hard"):
            errors.append(f"course.json chapter {ch_id} invalid difficulty: {ch.get('difficulty')!r}")
        if ch.get("generation_status") not in ("pending", "in_progress", "generated"):
            errors.append(
                f"course.json chapter {ch_id} invalid generation_status: {ch.get('generation_status')!r}"
            )
        prereqs = ch.get("prerequisites", [])
        if isinstance(prereqs, list):
            prereqs_map[ch_id] = prereqs
        for src_ref in ch.get("source_files", []):
            m = LINE_REF_RE.fullmatch(src_ref) if isinstance(src_ref, str) else None
            if m:
                check_line_ref(
                    project_root,
                    m.group(1),
                    int(m.group(2)),
                    int(m.group(3)),
                    source_commit,
                    f"course.json[{ch_id}]",
                    errors,
                )
            elif isinstance(src_ref, str):
                norm = normalize_rel_path(project_root, src_ref)
                if norm is None or read_source_lines(project_root, norm, source_commit) is None:
                    errors.append(f"course.json[{ch_id}]: source file does not exist: {src_ref}")

    for ch_id, prereqs in prereqs_map.items():
        for p in prereqs:
            if p not in chapter_ids:
                errors.append(f"course.json chapter {ch_id} prerequisite not found: {p}")
    errors.extend(detect_cycles(prereqs_map))

    if chapter_filter and chapter_filter not in chapter_ids:
        errors.append(f"Requested chapter not found in course.json: {chapter_filter}")

    # Validate progress.json
    if "project_name" in progress:
        errors.append("progress.json uses deprecated key 'project_name'; must use 'project'")
    if progress.get("project") != course.get("project"):
        errors.append(
            f"progress.json project ({progress.get('project')!r}) != course.json project ({course.get('project')!r})"
        )
    curr = progress.get("current_chapter")
    if curr is not None and curr not in chapter_ids:
        errors.append(f"progress.json current_chapter not in course chapters: {curr!r}")

    prog_chapters = progress.get("chapters")
    if not isinstance(prog_chapters, dict):
        errors.append("progress.json chapters must be an object")
        return errors

    for ch_id in chapter_ids:
        entry = prog_chapters.get(ch_id)
        if not isinstance(entry, dict):
            errors.append(f"progress.json missing chapter entry: {ch_id}")
            continue
        status = entry.get("status")
        score = entry.get("score")
        attempts = entry.get("attempts")
        hint_level = entry.get("hint_level_reached")

        if status not in ("not_started", "in_progress", "completed"):
            errors.append(f"progress.json[{ch_id}] invalid status: {status!r}")
        if not isinstance(score, (int, float)) or not (0 <= score <= 100):
            errors.append(f"progress.json[{ch_id}] invalid score: {score!r}")
        if not isinstance(attempts, int) or attempts < 0:
            errors.append(f"progress.json[{ch_id}] invalid attempts: {attempts!r}")
        if not isinstance(hint_level, int) or not (0 <= hint_level <= 3):
            errors.append(f"progress.json[{ch_id}] invalid hint_level_reached: {hint_level!r}")

        if status == "completed":
            if score != 100:
                errors.append(f"progress.json[{ch_id}] completed chapter must have score == 100, got {score}")
            if isinstance(attempts, int) and attempts < 1:
                errors.append(f"progress.json[{ch_id}] completed chapter must have attempts >= 1")
            if not entry.get("completed_at"):
                errors.append(f"progress.json[{ch_id}] completed chapter missing completed_at")
        elif status == "in_progress":
            if isinstance(score, (int, float)) and score >= 100:
                errors.append(f"progress.json[{ch_id}] in_progress chapter score must be < 100, got {score}")
        elif status == "not_started":
            if score != 0:
                errors.append(f"progress.json[{ch_id}] not_started chapter must have score == 0, got {score}")

    for ch in chapters:
        ch_id = ch.get("id", "")
        if chapter_filter and ch_id != chapter_filter:
            continue
        if ch.get("generation_status") != "generated" and chapter_filter is None:
            continue
        errors.extend(verify_chapter_files(project_root, ch_id, source_commit, prog_chapters.get(ch_id)))

    return errors


def run_gate(project_root: Path, chapter_id: str, mode: str) -> tuple[bool, str]:
    ch_dir = project_root / ".promentor" / "chapters" / chapter_id
    errors: list[str] = []
    lab = load_json(ch_dir / "lab.json", errors)
    if lab is None:
        return False, "; ".join(errors)

    test_cmd = lab.get("test_command")
    test_file = lab.get("test_file")
    language = str(lab.get("language", ""))
    if not isinstance(test_cmd, str) or not isinstance(test_file, str):
        return False, f"{chapter_id}: lab.json missing test_command or test_file"

    test_path = ch_dir / test_file
    if not test_path.is_file():
        return False, f"{chapter_id}: missing test_file {test_file}"

    declared = count_declared_tests(language, test_path)
    if declared is not None and declared == 0:
        return False, f"{chapter_id}: no test cases declared in {test_file}"

    rel_ch_dir = f".promentor/chapters/{chapter_id}"
    cmd = test_cmd.replace("{chapter_dir}", rel_ch_dir)
    proc = subprocess.run(
        cmd,
        cwd=project_root,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = f"{proc.stdout}\n{proc.stderr}"
    executed = count_executed_tests(language, combined)

    if mode == "red":
        if proc.returncode == 0:
            return False, f"{chapter_id}: expected Red State (non-zero exit), but test_command passed"
        for hard in HARD_BUILD_ERROR_SIGNATURES:
            if hard in combined:
                return False, f"{chapter_id}: test_command failed with infra/build error ({hard}):\n{combined}"

        if declared is not None and executed is not None:
            if executed != declared:
                for bad in INFRA_ERROR_SIGNATURES:
                    if bad in combined:
                        return False, f"{chapter_id}: test_command failed with infra/build error ({bad}):\n{combined}"
                return (
                    False,
                    f"{chapter_id}: executed {executed}/{declared} tests (aborted early by unrecovered panic/exit?):\n{combined}",
                )
        else:
            for bad in INFRA_ERROR_SIGNATURES:
                if bad in combined:
                    return False, f"{chapter_id}: test_command failed with infra/build error ({bad}):\n{combined}"

        if not any(sig in combined for sig in EXPECTED_RED_SIGNATURES):
            return False, f"{chapter_id}: test_command exited non-zero without clear test failure signal:\n{combined}"
        count_info = f"{executed}/{declared} tests executed" if declared is not None else "tests executed"
        return True, f"PASS: {chapter_id} red gate ({count_info})"

    if mode == "green":
        if proc.returncode != 0:
            return False, f"{chapter_id}: expected Green State (exit 0), got {proc.returncode}:\n{combined}"
        if declared is not None and executed is not None and executed != declared:
            return False, f"{chapter_id}: green gate ran {executed}/{declared} tests:\n{combined}"
        count_info = f"{executed}/{declared} tests passed" if declared is not None else "all tests passed"
        return True, f"PASS: {chapter_id} green gate ({count_info})"

    return False, f"Unsupported gate mode: {mode}"


def cmd_checksum(project_root: Path, chapter_id: str) -> int:
    ch_dir = project_root / ".promentor" / "chapters" / chapter_id
    lab_path = ch_dir / "lab.json"
    errors: list[str] = []
    lab = load_json(lab_path, errors)
    if lab is None:
        print("\n".join(errors), file=sys.stderr)
        return 1
    test_file = lab.get("test_file")
    if not isinstance(test_file, str) or not (ch_dir / test_file).is_file():
        print(f"ERROR: {chapter_id} missing test_file {test_file!r}", file=sys.stderr)
        return 1
    digest = sha256_file(ch_dir / test_file)
    lab["test_checksum"] = digest
    lab_path.write_text(json.dumps(lab, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OK: {chapter_id} test_checksum={digest}")
    return 0


def cmd_verify(project_root: Path, chapter_id: str | None, strict_commit: bool) -> int:
    errors = verify_course(project_root, chapter_filter=chapter_id, strict_commit=strict_commit)
    if errors:
        print("VERIFY FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    scope = chapter_id or "all generated chapters"
    print(f"VERIFY PASSED ({scope})")
    return 0


def cmd_gate(project_root: Path, mode: str, chapter_id: str) -> int:
    ok, message = run_gate(project_root, chapter_id, mode)
    print(message)
    return 0 if ok else 1


def cmd_test(project_root: Path, chapter_id: str | None) -> int:
    prom_dir = project_root / ".promentor"
    errors: list[str] = []
    progress_path = prom_dir / "progress.json"
    progress = load_json(progress_path, errors)
    if progress is None:
        print("\n".join(errors), file=sys.stderr)
        return 1

    target_ch = chapter_id or progress.get("current_chapter")
    if not isinstance(target_ch, str) or not target_ch:
        print("ERROR: no chapter specified and progress.json current_chapter is empty", file=sys.stderr)
        return 1

    ch_dir = prom_dir / "chapters" / target_ch
    lab = load_json(ch_dir / "lab.json", errors)
    if lab is None:
        print("\n".join(errors), file=sys.stderr)
        return 1

    test_file = lab.get("test_file", "")
    test_cmd = lab.get("test_command", "")
    language = str(lab.get("language", ""))
    expected_checksum = lab.get("test_checksum", "")
    test_path = ch_dir / test_file if isinstance(test_file, str) and test_file else None
    if test_path is None or not test_path.is_file() or not isinstance(test_cmd, str):
        print(f"ERROR: {target_ch} missing test_file or test_command", file=sys.stderr)
        return 1

    actual_checksum = sha256_file(test_path)
    if actual_checksum != expected_checksum:
        print(
            f"WARNING: test_file checksum mismatch for {target_ch} (expected {expected_checksum}, got {actual_checksum}); /promentor submit will be rejected until restored"
        )

    rel_ch_dir = f".promentor/chapters/{target_ch}"
    cmd = test_cmd.replace("{chapter_dir}", rel_ch_dir)
    proc = subprocess.run(
        cmd,
        cwd=project_root,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n", file=sys.stderr)

    combined = f"{proc.stdout}\n{proc.stderr}"
    declared = count_declared_tests(language, test_path)
    executed = count_executed_tests(language, combined)
    passed = count_passed_tests(language, combined)

    total = max(declared or 0, executed or 0)
    passed_val = passed if passed is not None else 0

    chapters_prog = progress.get("chapters")
    ch_prog = chapters_prog.get(target_ch) if isinstance(chapters_prog, dict) else None
    status = ch_prog.get("status", "unknown") if isinstance(ch_prog, dict) else "unknown"
    score = ch_prog.get("score", 0) if isinstance(ch_prog, dict) else 0

    all_passed = proc.returncode == 0 and total > 0 and passed_val == total
    if isinstance(ch_prog, dict) and status == "in_progress" and total > 0:
        if all_passed:
            # Keep status in_progress and score < 100 until formal /promentor submit.
            ch_prog["score"] = 99
            score = 99
        else:
            score = min((passed_val * 100) // total, 99)
            ch_prog["score"] = score
        progress_path.write_text(json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if all_passed and status == "in_progress":
        print(f"ALL_PASSED (100% ready to submit): run /promentor submit to archive {target_ch} and lock 100%")
    print(f"SUMMARY: {target_ch} passed={passed_val}/{total} score={score} status={status}")
    return 0 if proc.returncode == 0 else 1


def cmd_archive(project_root: Path, chapter_id: str) -> int:
    prom_dir = project_root / ".promentor"
    ch_dir = prom_dir / "chapters" / chapter_id
    errors: list[str] = []
    lab = load_json(ch_dir / "lab.json", errors)
    progress = load_json(prom_dir / "progress.json", errors)
    if lab is None or progress is None:
        print("\n".join(errors), file=sys.stderr)
        return 1

    test_file = lab.get("test_file", "")
    expected_checksum = lab.get("test_checksum", "")
    test_path = ch_dir / test_file if isinstance(test_file, str) and test_file else None
    if test_path is None or not test_path.is_file():
        print(f"ERROR: {chapter_id} missing test_file {test_file!r}", file=sys.stderr)
        return 1
    actual_checksum = sha256_file(test_path)
    if actual_checksum != expected_checksum:
        print(
            f"ERROR: {chapter_id} test_checksum mismatch (expected {expected_checksum}, got {actual_checksum}); aborting archive",
            file=sys.stderr,
        )
        return 1

    # Built-in green gate: archive MUST reject failing/incomplete implementations atomically.
    green_ok, green_msg = run_gate(project_root, chapter_id, "green")
    if not green_ok:
        print(f"ERROR: {chapter_id} green gate failed; aborting archive\n{green_msg}", file=sys.stderr)
        return 1

    chapters_prog = progress.get("chapters")
    if not isinstance(chapters_prog, dict) or chapter_id not in chapters_prog:
        print(f"ERROR: {chapter_id} not found in progress.json", file=sys.stderr)
        return 1

    ch_prog = chapters_prog[chapter_id]
    attempt_num = int(ch_prog.get("attempts", 0)) + 1
    attempt_dir = prom_dir / "submissions" / chapter_id / f"attempt_{attempt_num}"
    attempt_dir.mkdir(parents=True, exist_ok=True)

    archived_files: list[str] = []
    for spec in lab.get("files", []):
        rel = spec.get("path") if isinstance(spec, dict) else None
        if not isinstance(rel, str):
            continue
        src = ch_dir / rel
        if not src.is_file():
            print(f"ERROR: {chapter_id} missing implementation file to archive: {rel}", file=sys.stderr)
            return 1
        dst = attempt_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        archived_files.append(rel)

    now = utc_now_iso()
    ch_prog["status"] = "completed"
    ch_prog["score"] = 100
    ch_prog["attempts"] = attempt_num
    ch_prog.setdefault("completed_at", now)
    ch_prog["last_submitted_at"] = now
    (prom_dir / "progress.json").write_text(json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rel_attempt = attempt_dir.relative_to(project_root)
    print(f"OK: archived {chapter_id} -> {rel_attempt}/ ({', '.join(archived_files)})")
    return 0


def cmd_resume_scan(project_root: Path) -> int:
    prom_dir = project_root / ".promentor"
    course_path = prom_dir / "course.json"
    if not course_path.is_file():
        print("NEED_INIT: .promentor/course.json missing; restart from /promentor init")
        return 1
    errors: list[str] = []
    course = load_json(course_path, errors)
    if course is None:
        print("\n".join(errors), file=sys.stderr)
        return 1

    progress_errors: list[str] = []
    progress = load_json(prom_dir / "progress.json", progress_errors) if (prom_dir / "progress.json").is_file() else None
    prog_chapters = progress.get("chapters", {}) if isinstance(progress, dict) and isinstance(progress.get("chapters"), dict) else {}

    chapters = course.get("chapters", [])
    gen_mode = course.get("generation_mode", "lazy")
    source_commit = course.get("source_commit", "") if isinstance(course.get("source_commit"), str) else ""

    targets: list[dict[str, Any]] = []
    for idx, ch in enumerate(chapters):
        if not isinstance(ch, dict) or not isinstance(ch.get("id"), str):
            continue
        ch_id = ch["id"]
        ch_dir_exists = (prom_dir / "chapters" / ch_id).exists()
        if gen_mode == "all" or idx == 0 or ch.get("generation_status") in ("in_progress", "generated") or ch_dir_exists:
            targets.append(ch)

    incomplete: list[tuple[str, list[str], bool]] = []
    for ch in targets:
        ch_id = ch["id"]
        prog_entry = prog_chapters.get(ch_id, {}) if isinstance(prog_chapters.get(ch_id), dict) else {}
        ch_errors: list[str] = []
        if ch.get("generation_status") != "generated":
            ch_errors.append(f"generation_status is {ch.get('generation_status')!r}")
        ch_errors.extend(verify_chapter_files(project_root, ch_id, source_commit, prog_entry))
        if ch_errors:
            sub_dir = prom_dir / "submissions" / ch_id
            has_submissions = sub_dir.is_dir() and any(sub_dir.iterdir())
            is_protected = (
                prog_entry.get("status") in ("in_progress", "completed")
                or (isinstance(prog_entry.get("attempts"), int) and prog_entry.get("attempts", 0) >= 1)
                or has_submissions
            )
            incomplete.append((ch_id, ch_errors, is_protected))

    if not incomplete:
        print("OK: all target chapters complete")
        return 0

    for ch_id, reasons, is_protected in incomplete:
        if is_protected:
            print(
                f"PROTECTED {ch_id}: {reasons[0]} (student work in progress/completed; do not overwrite implementation files)"
            )
        else:
            print(f"REGENERATE {ch_id}: {reasons[0]}")
    return 0


def cmd_exclude(project_root: Path) -> int:
    entry = ".promentor/"
    if is_git_repo(project_root):
        proc = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        exclude_path = Path(proc.stdout.strip())
        if not exclude_path.is_absolute():
            exclude_path = project_root / exclude_path
    else:
        exclude_path = project_root / ".gitignore"

    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.is_file() else ""
    existing_lines = {line.strip() for line in existing.splitlines()}
    if entry in existing_lines or ".promentor" in existing_lines:
        print(f"OK: {entry} already excluded in {exclude_path}")
        return 0

    prefix = "" if (not existing or existing.endswith("\n")) else "\n"
    exclude_path.write_text(f"{existing}{prefix}{entry}\n", encoding="utf-8")
    print(f"OK: added {entry} to {exclude_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promentor.py",
        description="Deterministic verification, testing, gating, archival, and exclude helper for ProMentor.",
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="Target project root directory (default: .)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_checksum = sub.add_parser("checksum", help="Compute and write lab.json test_checksum for a chapter")
    p_checksum.add_argument("chapter", help="Chapter ID (e.g. ch01-router)")

    p_verify = sub.add_parser("verify", help="Validate schema, line refs, partitions, files, and checksums")
    p_verify.add_argument("chapter", nargs="?", default=None, help="Optional single chapter ID to verify")
    p_verify.add_argument("--strict-commit", action="store_true", help="Fail if git HEAD differs from source_commit")

    p_gate = sub.add_parser("gate", help="Run test_command and verify red/green state + executed test count")
    p_gate.add_argument("mode", choices=("red", "green"), help="Expected gate state")
    p_gate.add_argument("chapter", help="Chapter ID")

    p_test = sub.add_parser("test", help="Run chapter tests, check tamper warning, and update progress score")
    p_test.add_argument("chapter", nargs="?", default=None, help="Optional chapter ID (defaults to current_chapter)")

    p_archive = sub.add_parser("archive", help="Verify checksum + green gate, archive files to attempt_N/, update progress.json")
    p_archive.add_argument("chapter", help="Chapter ID")

    sub.add_parser("resume-scan", help="List missing or incomplete chapters needing regeneration")
    sub.add_parser("exclude", help="Ignore .promentor/ via .git/info/exclude (or .gitignore if non-Git)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()

    if args.command == "checksum":
        return cmd_checksum(root, args.chapter)
    if args.command == "verify":
        return cmd_verify(root, args.chapter, args.strict_commit)
    if args.command == "gate":
        return cmd_gate(root, args.mode, args.chapter)
    if args.command == "test":
        return cmd_test(root, args.chapter)
    if args.command == "archive":
        return cmd_archive(root, args.chapter)
    if args.command == "resume-scan":
        return cmd_resume_scan(root)
    if args.command == "exclude":
        return cmd_exclude(root)
    return 1


if __name__ == "__main__":
    sys.exit(main())
