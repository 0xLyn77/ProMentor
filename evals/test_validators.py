#!/usr/bin/env python3
"""Unit tests verifying validate_course.py catches every specification violation."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from validate_course import validate_course


FIXTURE_GO = Path(__file__).resolve().parent / "fixtures" / "go-mini-router"


class TestValidateCourseNegativeCases(unittest.TestCase):
    def _setup_go_course(self, tmp: Path) -> Path:
        work = tmp / "go-mini-router"
        shutil.copytree(
            FIXTURE_GO,
            work,
            ignore=shutil.ignore_patterns("course_fixture", "solutions"),
        )
        shutil.copytree(FIXTURE_GO / "course_fixture", work / ".promentor")
        return work

    def test_catches_out_of_bounds_line_reference(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_go_course(Path(td))
            src_md = work / ".promentor" / "chapters" / "ch01-router" / "source.md"
            src_md.write_text(src_md.read_text() + "\n### Bad Ref：`router.go:1-999`\n", encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("out of bounds" in e for e in errors), errors)

    def test_catches_deprecated_project_name_and_score_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_go_course(Path(td))
            prog_path = work / ".promentor" / "progress.json"
            prog = json.loads(prog_path.read_text(encoding="utf-8"))
            prog["project_name"] = prog.pop("project")
            prog["chapters"]["ch01-router"] = {
                "status": "completed",
                "score": 95,
                "attempts": 1,
                "hint_level_reached": 1,
                "completed_at": "2026-11-20T10:00:00Z",
            }
            prog_path.write_text(json.dumps(prog, indent=2), encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("project_name" in e for e in errors), errors)
            self.assertTrue(any("must have score == 100" in e for e in errors), errors)

    def test_catches_missing_anti_spoiler_part2_and_mermaid(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_go_course(Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-router"
            (ch_dir / "source.md").write_text("# 源码导读\n\n## Part 1: 写前导读\n`router.go:1-20`\n", encoding="utf-8")
            (ch_dir / "lecture.md").write_text("# 讲义\n\n纯文字无图表。\n", encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("Part 2" in e for e in errors), errors)
            self.assertTrue(any("Mermaid" in e for e in errors), errors)

    def test_catches_syntax_build_failure_during_red_state_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_go_course(Path(td))
            stub = work / ".promentor" / "chapters" / "ch01-router" / "router.go"
            stub.write_text("package router\n\nfunc BrokenSyntax( {\n", encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=False)
            self.assertTrue(any("infra/build error" in e for e in errors), errors)

    def test_catches_circular_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_go_course(Path(td))
            course_path = work / ".promentor" / "course.json"
            course = json.loads(course_path.read_text(encoding="utf-8"))
            course["chapters"][0]["prerequisites"] = ["ch02-middleware"]
            course_path.write_text(json.dumps(course, indent=2), encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("Circular prerequisite" in e for e in errors), errors)

    def test_catches_incomplete_chapter_for_resume(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_go_course(Path(td))
            (work / ".promentor" / "chapters" / "ch01-router" / "router.go").unlink()
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("starter/implementation file missing" in e for e in errors), errors)

    def test_catches_non_directory_legacy_submission_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_go_course(Path(td))
            sub_dir = work / ".promentor" / "submissions" / "ch01-router"
            sub_dir.mkdir(parents=True, exist_ok=True)
            (sub_dir / "attempt_1.go").write_text("package router\n", encoding="utf-8")
            prog_path = work / ".promentor" / "progress.json"
            prog = json.loads(prog_path.read_text(encoding="utf-8"))
            prog["chapters"]["ch01-router"] = {
                "status": "completed",
                "score": 100,
                "attempts": 1,
                "hint_level_reached": 0,
                "completed_at": "2026-11-20T10:00:00Z",
            }
            prog_path.write_text(json.dumps(prog, indent=2), encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("missing submission directory" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
