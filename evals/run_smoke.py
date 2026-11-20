#!/usr/bin/env python3
"""End-to-end smoke test suite for ProMentor across Go, Python, and TypeScript fixtures."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from validate_course import validate_course
from validate_skill import validate_skill


EVALS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = EVALS_DIR / "fixtures"
PROMPT_CASES_JSON = EVALS_DIR / "prompt_cases.json"

FIXTURE_SPECS = [
    ("go-mini-router", "ch01-router"),
    ("py-mini-kv", "ch01-kv-ttl"),
    ("ts-mini-eventbus", "ch01-event-bus"),
]


def run_git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def init_git_repo(repo_dir: Path) -> str:
    run_git(repo_dir, "init", "-q")
    run_git(repo_dir, "config", "user.email", "smoke@promentor.local")
    run_git(repo_dir, "config", "user.name", "ProMentor Smoke")
    (repo_dir / ".gitignore").write_text(".promentor/\n", encoding="utf-8")
    run_git(repo_dir, "add", ".")
    run_git(repo_dir, "commit", "-q", "-m", "initial fixture commit")
    return run_git(repo_dir, "rev-parse", "HEAD")


def copy_solution_files(src_dir: Path, dst_dir: Path) -> list[str]:
    copied: list[str] = []
    for path in sorted(src_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(src_dir)
            target = dst_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            copied.append(str(rel))
    return copied


def archive_submission(project_dir: Path, chapter_id: str, attempt_num: int, review_body: str) -> None:
    prom_dir = project_dir / ".promentor"
    ch_dir = prom_dir / "chapters" / chapter_id
    lab = json.loads((ch_dir / "lab.json").read_text(encoding="utf-8"))

    attempt_dir = prom_dir / "submissions" / chapter_id / f"attempt_{attempt_num}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    for file_spec in lab["files"]:
        rel = Path(file_spec["path"])
        target = attempt_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ch_dir / rel, target)

    review_path = prom_dir / "submissions" / chapter_id / f"review_{attempt_num}.md"
    review_path.write_text(review_body, encoding="utf-8")

    progress_path = prom_dir / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    ch_prog = progress["chapters"][chapter_id]
    ch_prog["status"] = "completed"
    ch_prog["score"] = 100
    ch_prog["attempts"] = attempt_num
    ch_prog.setdefault("completed_at", "2026-11-20T10:00:00Z")
    ch_prog["last_submitted_at"] = f"2026-11-20T10:0{attempt_num}:00Z"
    progress_path.write_text(json.dumps(progress, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_fixture_lifecycle(fixture_name: str, chapter_id: str) -> list[str]:
    errors: list[str] = []
    src_fixture = FIXTURES_DIR / fixture_name
    if not src_fixture.is_dir():
        return [f"Missing fixture directory: {src_fixture}"]

    with tempfile.TemporaryDirectory(prefix=f"promentor-smoke-{fixture_name}-") as tmp:
        work_dir = Path(tmp) / fixture_name
        shutil.copytree(
            src_fixture,
            work_dir,
            ignore=shutil.ignore_patterns("course_fixture", "solutions", "__pycache__"),
        )
        head_sha = init_git_repo(work_dir)

        # Install course_fixture as .promentor/ and stamp real source_commit.
        prom_dir = work_dir / ".promentor"
        shutil.copytree(src_fixture / "course_fixture", prom_dir)
        course_path = prom_dir / "course.json"
        course = json.loads(course_path.read_text(encoding="utf-8"))
        course["source_commit"] = head_sha
        course_path.write_text(json.dumps(course, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Stage 1: Validate initial Red State + schema + line refs + checksums + strict commit match.
        red_errors = validate_course(work_dir, mode="red", skip_tests=False, strict_commit=True)
        if red_errors:
            errors.extend([f"[{fixture_name}][red] {e}" for e in red_errors])
            return errors

        # Stage 2: Verify tamper detection triggers if test file is modified.
        ch_dir = prom_dir / "chapters" / chapter_id
        lab = json.loads((ch_dir / "lab.json").read_text(encoding="utf-8"))
        test_path = ch_dir / lab["test_file"]
        original_test_bytes = test_path.read_bytes()
        try:
            test_path.write_bytes(original_test_bytes + b"\n// tampered\n")
            tamper_errors = validate_course(work_dir, mode="red", skip_tests=True)
            if not any("test_checksum mismatch" in e for e in tamper_errors):
                errors.append(f"[{fixture_name}][tamper] Expected test_checksum mismatch error, got: {tamper_errors}")
        finally:
            test_path.write_bytes(original_test_bytes)

        # Stage 3: Apply Attempt 1 solution -> Green State -> Directory archive + review_1.md.
        sol1_dir = src_fixture / "solutions" / "attempt_1"
        copy_solution_files(sol1_dir, ch_dir)
        archive_submission(
            work_dir,
            chapter_id,
            attempt_num=1,
            review_body=f"# Code Review: {chapter_id} (Attempt #1)\n\nInitial review persisted.\n",
        )
        green1_errors = validate_course(work_dir, mode="green", skip_tests=False, strict_commit=True)
        if green1_errors:
            errors.extend([f"[{fixture_name}][attempt_1] {e}" for e in green1_errors])
            return errors

        # Stage 4: Apply Attempt 2 refactor -> Green State -> Directory archive + incremental review_2.md.
        sol2_dir = src_fixture / "solutions" / "attempt_2"
        copy_solution_files(sol2_dir, ch_dir)
        archive_submission(
            work_dir,
            chapter_id,
            attempt_num=2,
            review_body=f"# Code Review: {chapter_id} (Attempt #2)\n\nIncremental 3-way review persisted.\n",
        )
        green2_errors = validate_course(work_dir, mode="green", skip_tests=False, strict_commit=True)
        if green2_errors:
            errors.extend([f"[{fixture_name}][attempt_2] {e}" for e in green2_errors])
            return errors

        # Verify both review_1.md and review_2.md exist without overwriting.
        for idx in (1, 2):
            review_file = prom_dir / "submissions" / chapter_id / f"review_{idx}.md"
            if not review_file.is_file():
                errors.append(f"[{fixture_name}] Missing {review_file.name}")

        # Stage 5: Verify commit drift detection works when upstream repo advances.
        (work_dir / "CHANGELOG.md").write_text("upstream change\n", encoding="utf-8")
        run_git(work_dir, "add", "CHANGELOG.md")
        run_git(work_dir, "commit", "-q", "-m", "upstream source update")
        drift_errors = validate_course(work_dir, mode="green", skip_tests=True, strict_commit=True)
        if not any("source_commit drift detected" in e for e in drift_errors):
            errors.append(f"[{fixture_name}][commit-drift] Expected drift warning, got: {drift_errors}")

    return errors


def validate_prompt_cases() -> list[str]:
    errors: list[str] = []
    if not PROMPT_CASES_JSON.is_file():
        return [f"Missing {PROMPT_CASES_JSON}"]
    data = json.loads(PROMPT_CASES_JSON.read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not isinstance(cases, list) or len(cases) < 5:
        return ["prompt_cases.json must define at least 5 regression prompt cases"]
    categories = set()
    for case in cases:
        cid = case.get("id", "<missing>")
        for key in ("id", "category", "scenario", "user_prompt", "expected_route", "must_do", "must_not_do"):
            if not case.get(key):
                errors.append(f"prompt_cases.json case {cid} missing {key}")
        categories.add(case.get("category"))
    for required_cat in ("anti_ghostwriting", "anti_spoiler", "layered_hint", "integrity", "review", "incremental_review"):
        if required_cat not in categories:
            errors.append(f"prompt_cases.json missing required category: {required_cat}")
    return errors


def main() -> int:
    all_errors: list[str] = []

    print("1) Validating skill package & repository invariants...")
    skill_errors = validate_skill()
    if skill_errors:
        all_errors.extend([f"[skill] {e}" for e in skill_errors])
    else:
        print("   PASS: skill package valid")

    print("2) Validating prompt regression suite...")
    prompt_errors = validate_prompt_cases()
    if prompt_errors:
        all_errors.extend([f"[prompts] {e}" for e in prompt_errors])
    else:
        print("   PASS: prompt regression suite valid")

    print("3) Running validator unit tests (negative & edge cases)...")
    unit_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", str(EVALS_DIR / "test_validators.py")],
        cwd=EVALS_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if unit_proc.returncode != 0:
        all_errors.append(f"[unit-tests]\n{unit_proc.stdout}\n{unit_proc.stderr}")
        print("   FAIL: validator unit tests")
    else:
        print("   PASS: validator unit tests")

    print("4) Running Go / Python / TypeScript E2E lifecycle smoke tests...")
    for fixture_name, chapter_id in FIXTURE_SPECS:
        fx_errors = run_fixture_lifecycle(fixture_name, chapter_id)
        if fx_errors:
            all_errors.extend(fx_errors)
            print(f"   FAIL: {fixture_name}")
        else:
            print(f"   PASS: {fixture_name} (Red -> Tamper Reject -> Attempt 1 -> Attempt 2 -> Commit Drift)")

    if all_errors:
        print("\nSMOKE SUITE FAILED:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\nALL PROMENTOR SMOKE CHECKS PASSED!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
