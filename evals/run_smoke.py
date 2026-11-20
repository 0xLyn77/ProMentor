#!/usr/bin/env python3
"""End-to-end smoke test suite exercising the bundled skills/promentor/scripts/promentor.py."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from validate_skill import validate_skill


EVALS_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALS_DIR.parent
FIXTURES_DIR = EVALS_DIR / "fixtures"
PROMPT_CASES_JSON = EVALS_DIR / "prompt_cases.json"
PROMENTOR_CLI = REPO_ROOT / "skills" / "promentor" / "scripts" / "promentor.py"

FIXTURE_SPECS = [
    ("go-mini-router", "ch01-router", "router.go", 4),
    ("py-mini-kv", "ch01-kv-ttl", "kv.py", 5),
    ("ts-mini-eventbus", "ch01-event-bus", "src/event_bus.ts", 4),
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


def run_promentor(work_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PROMENTOR_CLI), "--root", str(work_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def init_git_repo(repo_dir: Path) -> str:
    run_git(repo_dir, "init", "-q")
    run_git(repo_dir, "config", "user.email", "smoke@promentor.local")
    run_git(repo_dir, "config", "user.name", "ProMentor Smoke")
    # Track a normal host .gitignore that does NOT contain .promentor/.
    (repo_dir / ".gitignore").write_text("*.log\n", encoding="utf-8")
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


def run_fixture_lifecycle(
    fixture_name: str,
    chapter_id: str,
    source_file_for_drift: str,
    expected_tests: int,
) -> list[str]:
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
        original_gitignore = (work_dir / ".gitignore").read_text(encoding="utf-8")

        # Install course_fixture as .promentor/ and stamp real source_commit.
        prom_dir = work_dir / ".promentor"
        shutil.copytree(src_fixture / "course_fixture", prom_dir)
        course_path = prom_dir / "course.json"
        course = json.loads(course_path.read_text(encoding="utf-8"))
        course["source_commit"] = head_sha
        course_path.write_text(json.dumps(course, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # Stage 0: Run promentor.py exclude -> must write .git/info/exclude and keep tracked .gitignore + git status clean!
        ex_proc = run_promentor(work_dir, "exclude")
        if ex_proc.returncode != 0:
            errors.append(f"[{fixture_name}][exclude] failed: {ex_proc.stdout}{ex_proc.stderr}")
            return errors
        if (work_dir / ".gitignore").read_text(encoding="utf-8") != original_gitignore:
            errors.append(f"[{fixture_name}][exclude] modified tracked .gitignore!")
        status_out = run_git(work_dir, "status", "--porcelain")
        if status_out:
            errors.append(f"[{fixture_name}][exclude] git status not clean: {status_out!r}")

        # Stage 1: Verify schema/files/refs + Red State gate (checking full test count executed) + resume-scan.
        v_proc = run_promentor(work_dir, "verify", "--strict-commit")
        if v_proc.returncode != 0:
            errors.append(f"[{fixture_name}][verify] {v_proc.stdout}{v_proc.stderr}")
            return errors

        red_proc = run_promentor(work_dir, "gate", "red", chapter_id)
        if red_proc.returncode != 0:
            errors.append(f"[{fixture_name}][gate-red] {red_proc.stdout}{red_proc.stderr}")
            return errors
        expected_marker = f"{expected_tests}/{expected_tests} tests executed"
        if expected_marker not in red_proc.stdout:
            errors.append(f"[{fixture_name}][gate-red] expected {expected_marker!r} in output, got: {red_proc.stdout!r}")

        rs_proc = run_promentor(work_dir, "resume-scan")
        if rs_proc.returncode != 0 or "OK: all target chapters complete" not in rs_proc.stdout:
            errors.append(f"[{fixture_name}][resume-scan] unexpected output: {rs_proc.stdout}{rs_proc.stderr}")

        # Stage 2: Verify tamper detection blocks both verify and archive.
        ch_dir = prom_dir / "chapters" / chapter_id
        lab = json.loads((ch_dir / "lab.json").read_text(encoding="utf-8"))
        test_path = ch_dir / lab["test_file"]
        original_test_bytes = test_path.read_bytes()
        try:
            test_path.write_bytes(original_test_bytes + b"\n// tampered\n")
            t_verify = run_promentor(work_dir, "verify", chapter_id)
            if t_verify.returncode == 0 or "test_checksum mismatch" not in t_verify.stdout:
                errors.append(f"[{fixture_name}][tamper-verify] expected checksum rejection, got: {t_verify.stdout}")
            t_arch = run_promentor(work_dir, "archive", chapter_id)
            if t_arch.returncode == 0 or "test_checksum mismatch" not in t_arch.stderr:
                errors.append(f"[{fixture_name}][tamper-archive] expected archive rejection, got: {t_arch.stderr}")
        finally:
            test_path.write_bytes(original_test_bytes)

        # Stage 3: Attempt 1 -> gate green -> promentor.py archive -> review_1.md -> verify.
        copy_solution_files(src_fixture / "solutions" / "attempt_1", ch_dir)
        g1 = run_promentor(work_dir, "gate", "green", chapter_id)
        if g1.returncode != 0:
            errors.append(f"[{fixture_name}][attempt_1-gate] {g1.stdout}{g1.stderr}")
            return errors
        a1 = run_promentor(work_dir, "archive", chapter_id)
        if a1.returncode != 0:
            errors.append(f"[{fixture_name}][attempt_1-archive] {a1.stdout}{a1.stderr}")
            return errors
        (prom_dir / "submissions" / chapter_id / "review_1.md").write_text(
            f"# Code Review: {chapter_id} (Attempt #1)\n\nInitial review persisted.\n",
            encoding="utf-8",
        )
        v1 = run_promentor(work_dir, "verify", "--strict-commit")
        if v1.returncode != 0:
            errors.append(f"[{fixture_name}][attempt_1-verify] {v1.stdout}{v1.stderr}")
            return errors

        # Stage 4: Attempt 2 refactor -> gate green -> promentor.py archive -> review_2.md -> verify.
        copy_solution_files(src_fixture / "solutions" / "attempt_2", ch_dir)
        g2 = run_promentor(work_dir, "gate", "green", chapter_id)
        if g2.returncode != 0:
            errors.append(f"[{fixture_name}][attempt_2-gate] {g2.stdout}{g2.stderr}")
            return errors
        a2 = run_promentor(work_dir, "archive", chapter_id)
        if a2.returncode != 0:
            errors.append(f"[{fixture_name}][attempt_2-archive] {a2.stdout}{a2.stderr}")
            return errors
        (prom_dir / "submissions" / chapter_id / "review_2.md").write_text(
            f"# Code Review: {chapter_id} (Attempt #2)\n\nIncremental 3-way review persisted.\n",
            encoding="utf-8",
        )
        v2 = run_promentor(work_dir, "verify", "--strict-commit")
        if v2.returncode != 0:
            errors.append(f"[{fixture_name}][attempt_2-verify] {v2.stdout}{v2.stderr}")
            return errors

        for idx in (1, 2):
            review_file = prom_dir / "submissions" / chapter_id / f"review_{idx}.md"
            if not review_file.is_file():
                errors.append(f"[{fixture_name}] Missing {review_file.name}")

        # Stage 5: Upstream commit drift — truncate referenced source file in working tree & commit!
        # Anchored verify MUST STILL PASS because line refs resolve against source_commit via git show.
        drifted_file = work_dir / source_file_for_drift
        drifted_file.write_text("// upstream truncated file\n", encoding="utf-8")
        run_git(work_dir, "add", source_file_for_drift)
        run_git(work_dir, "commit", "-q", "-m", "upstream source rewrite")

        anchored_verify = run_promentor(work_dir, "verify")
        if anchored_verify.returncode != 0:
            errors.append(
                f"[{fixture_name}][commit-drift-anchored] expected verify to pass using source_commit, got: {anchored_verify.stdout}"
            )
        strict_verify = run_promentor(work_dir, "verify", "--strict-commit")
        if strict_verify.returncode == 0 or "source_commit drift detected" not in strict_verify.stdout:
            errors.append(f"[{fixture_name}][commit-drift-strict] expected drift notice, got: {strict_verify.stdout}")

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
        print("   PASS: skill package valid (including scripts/promentor.py)")

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

    print("4) Running Go / Python / TypeScript E2E lifecycle smoke tests via promentor.py...")
    for fixture_name, chapter_id, drift_file, expected_tests in FIXTURE_SPECS:
        fx_errors = run_fixture_lifecycle(fixture_name, chapter_id, drift_file, expected_tests)
        if fx_errors:
            all_errors.extend(fx_errors)
            print(f"   FAIL: {fixture_name}")
        else:
            print(
                f"   PASS: {fixture_name} (Exclude Clean -> Red {expected_tests}/{expected_tests} -> Tamper Reject -> Archive #1/#2 -> Anchored Commit Drift)"
            )

    if all_errors:
        print("\nSMOKE SUITE FAILED:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\nALL PROMENTOR SMOKE CHECKS PASSED!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
