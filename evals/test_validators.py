#!/usr/bin/env python3
"""Unit tests verifying promentor.py / validate_course.py catch every specification and runtime violation."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from validate_course import validate_course


REPO_ROOT = Path(__file__).resolve().parent.parent
PROMENTOR_CLI = REPO_ROOT / "skills" / "promentor" / "scripts" / "promentor.py"
FIXTURE_GO = Path(__file__).resolve().parent / "fixtures" / "go-mini-router"
FIXTURE_PY = Path(__file__).resolve().parent / "fixtures" / "py-mini-kv"
FIXTURE_TS = Path(__file__).resolve().parent / "fixtures" / "ts-mini-eventbus"


def _run_git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


class TestValidateCourseNegativeCases(unittest.TestCase):
    def _setup_fixture(self, fixture: Path, tmp: Path) -> Path:
        work = tmp / fixture.name
        shutil.copytree(
            fixture,
            work,
            ignore=shutil.ignore_patterns("course_fixture", "solutions", "__pycache__"),
        )
        shutil.copytree(fixture / "course_fixture", work / ".promentor")
        return work

    def test_catches_out_of_bounds_line_reference(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            src_md = work / ".promentor" / "chapters" / "ch01-router" / "source.md"
            src_md.write_text(src_md.read_text() + "\n### Bad Ref：`router.go:1-999`\n", encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("out of bounds" in e for e in errors), errors)

    def test_catches_deprecated_project_name_and_score_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
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
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-router"
            (ch_dir / "source.md").write_text("# 源码导读\n\n## Part 1: 写前导读\n`router.go:1-20`\n", encoding="utf-8")
            (ch_dir / "lecture.md").write_text("# 讲义\n\n纯文字无图表。\n", encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("Part 2" in e for e in errors), errors)
            self.assertTrue(any("Mermaid" in e for e in errors), errors)

    def test_catches_syntax_build_failure_during_red_state_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            stub = work / ".promentor" / "chapters" / "ch01-router" / "router.go"
            stub.write_text("package router\n\nfunc BrokenSyntax( {\n", encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=False)
            self.assertTrue(any("infra/build error" in e for e in errors), errors)

    def test_catches_go_unrecovered_panic_aborting_remaining_tests(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-router"
            test_path = ch_dir / "lab_test.go"
            # Strip defer guardPanic(t) so the first panic aborts the entire Go test binary.
            ungarded = test_path.read_text(encoding="utf-8").replace("\tdefer guardPanic(t)\n", "")
            test_path.write_text(ungarded, encoding="utf-8")
            subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "checksum", "ch01-router"],
                check=True,
                capture_output=True,
            )
            errors = validate_course(work, mode="red", skip_tests=False)
            self.assertTrue(
                any("executed 1/4 tests" in e or "executed 0/4 tests" in e for e in errors),
                errors,
            )

    def test_catches_ts_test_filename_matching_host_vitest_jest_glob(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_TS, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-event-bus"
            shutil.move(ch_dir / "lab_test.ts", ch_dir / "lab.test.ts")
            lab_path = ch_dir / "lab.json"
            lab = json.loads(lab_path.read_text(encoding="utf-8"))
            lab["test_file"] = "lab.test.ts"
            lab_path.write_text(json.dumps(lab, indent=2), encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("Vitest/Jest default glob" in e for e in errors), errors)

    def test_catches_python_cd_with_relative_venv_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_PY, Path(td))
            lab_path = work / ".promentor" / "chapters" / "ch01-kv-ttl" / "lab.json"
            lab = json.loads(lab_path.read_text(encoding="utf-8"))
            lab["test_command"] = "cd {chapter_dir} && .venv/bin/python -m unittest -v test_lab.py"
            lab_path.write_text(json.dumps(lab, indent=2), encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("relative venv python path" in e for e in errors), errors)

    def test_exclude_uses_git_info_exclude_without_touching_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            shutil.rmtree(work / ".promentor")
            (work / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
            _run_git(work, "init", "-q")
            _run_git(work, "config", "user.email", "t@t.local")
            _run_git(work, "config", "user.name", "T")
            _run_git(work, "add", ".")
            _run_git(work, "commit", "-q", "-m", "init")

            shutil.copytree(FIXTURE_GO / "course_fixture", work / ".promentor")
            proc = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "exclude"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("info/exclude", proc.stdout)
            self.assertEqual((work / ".gitignore").read_text(encoding="utf-8"), "*.tmp\n")
            self.assertEqual(_run_git(work, "status", "--porcelain"), "")

    def test_line_refs_anchored_to_source_commit_survive_working_tree_drift(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            shutil.rmtree(work / ".promentor")
            _run_git(work, "init", "-q")
            _run_git(work, "config", "user.email", "t@t.local")
            _run_git(work, "config", "user.name", "T")
            _run_git(work, "add", ".")
            _run_git(work, "commit", "-q", "-m", "base")
            base_sha = _run_git(work, "rev-parse", "HEAD")

            shutil.copytree(FIXTURE_GO / "course_fixture", work / ".promentor")
            course_path = work / ".promentor" / "course.json"
            course = json.loads(course_path.read_text(encoding="utf-8"))
            course["source_commit"] = base_sha
            course_path.write_text(json.dumps(course, indent=2), encoding="utf-8")

            # Truncate router.go in a new commit; anchored verify must still pass!
            (work / "router.go").write_text("package minirouter\n", encoding="utf-8")
            _run_git(work, "add", "router.go")
            _run_git(work, "commit", "-q", "-m", "truncate")

            errors = validate_course(work, mode="red", skip_tests=True, strict_commit=False)
            self.assertEqual(errors, [])

            # But an out-of-bounds reference even against base_sha must still be rejected.
            src_md = work / ".promentor" / "chapters" / "ch01-router" / "source.md"
            src_md.write_text(src_md.read_text() + "\n### Bad：`router.go:1-500`\n", encoding="utf-8")
            bad_errors = validate_course(work, mode="red", skip_tests=True, strict_commit=False)
            self.assertTrue(any("out of bounds" in e for e in bad_errors), bad_errors)

    def test_catches_circular_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            course_path = work / ".promentor" / "course.json"
            course = json.loads(course_path.read_text(encoding="utf-8"))
            course["chapters"][0]["prerequisites"] = ["ch02-middleware"]
            course_path.write_text(json.dumps(course, indent=2), encoding="utf-8")
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("Circular prerequisite" in e for e in errors), errors)

    def test_catches_incomplete_chapter_for_resume(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            (work / ".promentor" / "chapters" / "ch01-router" / "router.go").unlink()
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertTrue(any("starter/implementation file missing" in e for e in errors), errors)

    def test_catches_non_directory_legacy_submission_archive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
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

    def test_archive_rejects_red_state_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_PY, Path(td))
            proc = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "archive", "ch01-kv-ttl"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("green gate failed", proc.stderr)
            self.assertFalse((work / ".promentor" / "submissions" / "ch01-kv-ttl" / "attempt_1").exists())
            prog = json.loads((work / ".promentor" / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["status"], "in_progress")
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["attempts"], 0)
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["score"], 0)

    def test_resume_scan_protects_in_progress_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-router"
            # Corrupt lecture.md while chapter is in_progress
            (ch_dir / "lecture.md").write_text("", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "resume-scan"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("PROTECTED ch01-router:", proc.stdout)
            self.assertNotIn("REGENERATE ch01-router:", proc.stdout)

            # When chapter has not_started & 0 attempts, corruption should emit REGENERATE
            prog_path = work / ".promentor" / "progress.json"
            prog = json.loads(prog_path.read_text(encoding="utf-8"))
            prog["chapters"]["ch01-router"]["status"] = "not_started"
            prog_path.write_text(json.dumps(prog, indent=2), encoding="utf-8")
            proc2 = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "resume-scan"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("REGENERATE ch01-router:", proc2.stdout)

    def test_gate_red_allows_syntax_error_in_test_assertion_when_all_tests_ran(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_TS, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-event-bus"
            test_path = ch_dir / "lab_test.ts"
            test_path.write_text(
                'import assert from "node:assert/strict";\n'
                'import test from "node:test";\n'
                'import { matchTopic } from "./event_bus.ts";\n'
                '// Part A\n'
                'test("Part A: empty input throws SyntaxError", () => {\n'
                '  assert.throws(() => matchTopic("", "a"), SyntaxError);\n'
                '});\n'
                '// Part B\n'
                'test("Part B: missing file reports No such file or directory", () => {\n'
                '  assert.equal(matchTopic("a.*", "a.b"), true);\n'
                '});\n',
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "checksum", "ch01-event-bus"],
                check=True,
                capture_output=True,
            )
            proc = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "gate", "red", "ch01-event-bus"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("2/2 tests executed", proc.stdout)

    def test_gate_rejects_zero_declared_tests(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_PY, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-kv-ttl"
            (ch_dir / "test_lab.py").write_text(
                "# Part A\n# Part B\nimport unittest\nif __name__ == '__main__':\n    unittest.main()\n",
                encoding="utf-8",
            )
            for mode in ("red", "green"):
                proc = subprocess.run(
                    [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "gate", mode, "ch01-kv-ttl"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(proc.returncode, 0, f"mode={mode}: {proc.stdout}")
                self.assertIn("no test cases declared", proc.stdout)

    def test_line_ref_dynamic_routes_dot_slash_and_ignores_ip_ports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_GO, Path(td))
            dyn_file = work / "app" / "users" / "[id]" / "route.ts"
            dyn_file.parent.mkdir(parents=True, exist_ok=True)
            dyn_file.write_text("line1\nline2\nline3\nline4\nline5\nline6\n", encoding="utf-8")

            src_md = work / ".promentor" / "chapters" / "ch01-router" / "source.md"
            src_md.write_text(
                "# 源码导读\n\n"
                "## Part 1: 写前导读\n"
                "动态路由：`app/users/[id]/route.ts:1-5`\n"
                "相对前缀：`./router.go:1-5`\n"
                "默认监听 `127.0.0.1:8000-8080` 端口范围，不应误判为源文件。\n\n"
                "## Part 2: 提交后深读\n"
                "核心：`router.go:10-20`\n",
                encoding="utf-8",
            )
            errors = validate_course(work, mode="red", skip_tests=True)
            self.assertEqual(errors, [])

    def test_cli_test_subcommand_partial_all_passed_and_completed_preservation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_PY, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-kv-ttl"

            # 1. Partial pass: implement only ttl.py (1/5 passes -> score 20, status stays in_progress)
            shutil.copy2(FIXTURE_PY / "solutions" / "attempt_1" / "ttl.py", ch_dir / "ttl.py")
            p_partial = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "test"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(p_partial.returncode, 0)
            self.assertIn("SUMMARY: ch01-kv-ttl passed=1/5 score=20 status=in_progress", p_partial.stdout)
            prog = json.loads((work / ".promentor" / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["score"], 20)
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["status"], "in_progress")

            # 2. Tamper warning check
            test_path = ch_dir / "test_lab.py"
            orig_bytes = test_path.read_bytes()
            try:
                test_path.write_bytes(orig_bytes + b"\n# tamper\n")
                p_tamper = subprocess.run(
                    [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "test", "ch01-kv-ttl"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertIn("WARNING: test_file checksum mismatch", p_tamper.stdout)
            finally:
                test_path.write_bytes(orig_bytes)

            # 3. Full pass before submit: exit 0, ALL_PASSED, does NOT auto-mark completed
            shutil.copy2(FIXTURE_PY / "solutions" / "attempt_1" / "store.py", ch_dir / "store.py")
            p_all = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "test"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p_all.returncode, 0, p_all.stdout + p_all.stderr)
            self.assertIn("ALL_PASSED", p_all.stdout)
            self.assertIn("SUMMARY: ch01-kv-ttl passed=5/5 score=99 status=in_progress", p_all.stdout)
            prog = json.loads((work / ".promentor" / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["status"], "in_progress")
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["score"], 99)

            # 4. After archive locks completed=100, failing tests during refactor must NOT downgrade progress
            subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "archive", "ch01-kv-ttl"],
                check=True,
                capture_output=True,
            )
            shutil.copy2(FIXTURE_PY / "course_fixture" / "chapters" / "ch01-kv-ttl" / "store.py", ch_dir / "store.py")
            p_refactor = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "test"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(p_refactor.returncode, 0)
            prog = json.loads((work / ".promentor" / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["status"], "completed")
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["score"], 100)

    def test_cli_test_subcommand_unparsed_language_uses_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            work = self._setup_fixture(FIXTURE_PY, Path(td))
            ch_dir = work / ".promentor" / "chapters" / "ch01-kv-ttl"
            lab_path = ch_dir / "lab.json"
            lab = json.loads(lab_path.read_text(encoding="utf-8"))
            lab["language"] = "rust"
            lab["test_command"] = f"{sys.executable} -c 'import sys; sys.exit(1)'"
            lab_path.write_text(json.dumps(lab, indent=2), encoding="utf-8")

            p_fail = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "test", "ch01-kv-ttl"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(p_fail.returncode, 0)
            self.assertIn("SUMMARY: ch01-kv-ttl passed=unknown score=0 status=in_progress", p_fail.stdout)
            self.assertNotIn("ALL_PASSED", p_fail.stdout)

            lab["test_command"] = f"{sys.executable} -c 'print(\"test result: ok.\")'"
            lab_path.write_text(json.dumps(lab, indent=2), encoding="utf-8")

            p_pass = subprocess.run(
                [sys.executable, str(PROMENTOR_CLI), "--root", str(work), "test", "ch01-kv-ttl"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(p_pass.returncode, 0, p_pass.stdout + p_pass.stderr)
            self.assertIn("ALL_PASSED", p_pass.stdout)
            self.assertIn("SUMMARY: ch01-kv-ttl passed=all score=99 status=in_progress", p_pass.stdout)
            prog = json.loads((work / ".promentor" / "progress.json").read_text(encoding="utf-8"))
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["score"], 99)
            self.assertEqual(prog["chapters"]["ch01-kv-ttl"]["status"], "in_progress")


if __name__ == "__main__":
    unittest.main()
