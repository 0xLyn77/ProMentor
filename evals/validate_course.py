#!/usr/bin/env python3
"""Deterministic course validator reusing the bundled skills/promentor/scripts/promentor.py."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "skills" / "promentor" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from promentor import load_json, run_gate, verify_course  # noqa: E402


def validate_course(
    project_root: Path,
    mode: str = "red",
    skip_tests: bool = False,
    strict_commit: bool = False,
) -> list[str]:
    errors = verify_course(project_root, chapter_filter=None, strict_commit=strict_commit)
    if skip_tests:
        return errors

    course_errors: list[str] = []
    course = load_json(project_root / ".promentor" / "course.json", course_errors)
    if course is None:
        return errors

    for ch in course.get("chapters", []):
        if isinstance(ch, dict) and ch.get("generation_status") == "generated" and isinstance(ch.get("id"), str):
            ok, msg = run_gate(project_root, ch["id"], mode)
            if not ok:
                errors.append(msg)

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
