#!/usr/bin/env python3
"""Deterministic validator for a generated .promentor/ course inside a target project."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


CHAPTER_ID_RE = re.compile(r"^(ch[0-9]{2}|final)-[a-z0-9]+(-[a-z0-9]+)*$")
CHECKSUM_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^$|^[0-9a-f]{40}$")
LINE_REF_RE = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+):(\d+)-(\d+)")
MERMAID_BLOCK_RE = re.compile(
    r"```mermaid\s*\n\s*(flowchart|graph|sequenceDiagram|classDiagram)\b",
    re.MULTILINE,
)

INFRA_ERROR_SIGNATURES = [
    "ModuleNotFoundError",
    "ImportError",
    "SyntaxError",
    "command not found",
    "cannot find package",
    "[build failed]",
    "[setup failed]",
    "no Go files",
    "Ran 0 tests",
    "ERR_MODULE_NOT_FOUND",
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


def check_line_ref(project_root: Path, rel_path: str, start: int, end: int, origin: str, errors: list[str]) -> None:
    target = project_root / rel_path
    if not target.is_file():
        errors.append(f"{origin}: referenced source file does not exist: {rel_path}")
        return
    total_lines = len(target.read_text(encoding="utf-8").splitlines())
    if start < 1 or end < start or end > total_lines:
        errors.append(
            f"{origin}: line range {rel_path}:{start}-{end} out of bounds (file has {total_lines} lines)"
        )


def validate_course(
    project_root: Path,
    mode: str = "red",
    skip_tests: bool = False,
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

    # 1. Validate course.json schema
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
    elif source_commit and strict_commit and (project_root / ".git").exists():
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

        for req in ("title", "summary", "difficulty", "generation_status", "prerequisites", "learning_goals", "source_files", "lab_interface"):
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
                check_line_ref(project_root, m.group(1), int(m.group(2)), int(m.group(3)), f"course.json[{ch_id}]", errors)
            elif isinstance(src_ref, str):
                if not (project_root / src_ref).is_file():
                    errors.append(f"course.json[{ch_id}]: source file does not exist: {src_ref}")

    for ch_id, prereqs in prereqs_map.items():
        for p in prereqs:
            if p not in chapter_ids:
                errors.append(f"course.json chapter {ch_id} prerequisite not found: {p}")
    errors.extend(detect_cycles(prereqs_map))

    # 2. Validate progress.json schema and unified scoring invariants
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

    # 3. Validate each generated chapter
    for ch in chapters:
        if ch.get("generation_status") != "generated":
            continue
        ch_id = ch["id"]
        ch_dir = prom_dir / "chapters" / ch_id
        if not ch_dir.is_dir():
            errors.append(f"Generated chapter directory missing: {ch_dir}")
            continue

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
            refs = LINE_REF_RE.findall(source_text)
            if not refs:
                errors.append(f"{ch_id}: source.md contains no file:start-end line references")
            for rel_path, s_str, e_str in refs:
                check_line_ref(project_root, rel_path, int(s_str), int(e_str), f"{ch_id}/source.md", errors)

        # lab.json
        lab = load_json(ch_dir / "lab.json", errors)
        if lab is None:
            continue
        if lab.get("chapter_id") != ch_id:
            errors.append(f"{ch_id}/lab.json chapter_id mismatch: {lab.get('chapter_id')!r}")
        for req in ("title", "description", "language", "package", "files", "test_file", "test_checksum", "interface", "test_command"):
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

        test_file = lab.get("test_file", "")
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

        # Check directory-based submission archives when attempts >= 1
        prog_entry = prog_chapters.get(ch_id, {})
        attempts = prog_entry.get("attempts", 0) if isinstance(prog_entry, dict) else 0
        if isinstance(attempts, int) and attempts >= 1:
            for attempt_idx in range(1, attempts + 1):
                attempt_dir = prom_dir / "submissions" / ch_id / f"attempt_{attempt_idx}"
                if not attempt_dir.is_dir():
                    errors.append(f"{ch_id}: missing submission directory {attempt_dir.relative_to(project_root)}")
                else:
                    for rel in file_paths:
                        if not (attempt_dir / rel).is_file():
                            errors.append(
                                f"{ch_id}: submission attempt_{attempt_idx}/ missing archived file {rel}"
                            )

        # Live test execution
        if not skip_tests and isinstance(lab.get("test_command"), str):
            rel_ch_dir = f".promentor/chapters/{ch_id}"
            cmd = lab["test_command"].replace("{chapter_dir}", rel_ch_dir)
            proc = subprocess.run(
                cmd,
                cwd=project_root,
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
            combined = f"{proc.stdout}\n{proc.stderr}"
            if mode == "red":
                if proc.returncode == 0:
                    errors.append(f"{ch_id}: expected Red State (non-zero exit), but test_command passed!")
                else:
                    for bad in INFRA_ERROR_SIGNATURES:
                        if bad in combined:
                            errors.append(f"{ch_id}: test_command failed with infra/build error ({bad}):\n{combined}")
                            break
                    else:
                        if not any(sig in combined for sig in EXPECTED_RED_SIGNATURES):
                            errors.append(
                                f"{ch_id}: test_command exited non-zero without clear test failure signal:\n{combined}"
                            )
            elif mode == "green":
                if proc.returncode != 0:
                    errors.append(f"{ch_id}: expected Green State (exit 0), got {proc.returncode}:\n{combined}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a ProMentor .promentor/ course directory.")
    parser.add_argument("project_dir", type=Path, help="Target project directory containing .promentor/")
    parser.add_argument("--mode", choices=("red", "green"), default="red", help="Expected test state (default: red)")
    parser.add_argument("--skip-tests", action="store_true", help="Skip executing lab test_command")
    parser.add_argument("--strict-commit", action="store_true", help="Fail if source_commit differs from git HEAD")
    args = parser.parse_args()

    errors = validate_course(
        args.project_dir.resolve(),
        mode=args.mode,
        skip_tests=args.skip_tests,
        strict_commit=args.strict_commit,
    )
    if errors:
        print(f"COURSE VALIDATION FAILED ({args.project_dir}):")
        for err in errors:
            print(f"  - {err}")
        return 1
    print(f"COURSE VALIDATION PASSED ({args.project_dir}, mode={args.mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
