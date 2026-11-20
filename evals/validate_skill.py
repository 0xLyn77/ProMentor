#!/usr/bin/env python3
"""Deterministic validator for the ProMentor Skill repository itself."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "skills" / "promentor"
SKILL_MD = SKILL_DIR / "SKILL.md"
REFS_DIR = SKILL_DIR / "references"
HELPER_SCRIPT = SKILL_DIR / "scripts" / "promentor.py"
OPENAI_YAML = SKILL_DIR / "agents" / "openai.yaml"
README_MD = REPO_ROOT / "README.md"
GITIGNORE = REPO_ROOT / ".gitignore"

STALE_PATTERNS = [
    ("dashboard/", "legacy dashboard reference"),
    ("dsh-plugin", "legacy dsh-plugin reference"),
    ("serve.py", "removed local server script reference"),
    ("attempt_1.<ext>", "legacy single-file archive path"),
    ('sys.path.insert(0, ".promentor/', "broken relative sys.path insert"),
]


def parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            result[k.strip()] = v.strip()
    return result


def get_origin_repo_slug() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def validate_skill() -> list[str]:
    errors: list[str] = []

    if not SKILL_MD.is_file():
        return [f"Missing {SKILL_MD}"]

    skill_text = SKILL_MD.read_text(encoding="utf-8")
    skill_lines = skill_text.splitlines()
    if len(skill_lines) > 220:
        errors.append(f"SKILL.md is too long ({len(skill_lines)} lines > 220); violates progressive disclosure goal")
    if len(skill_lines) < 60:
        errors.append(f"SKILL.md is unexpectedly short ({len(skill_lines)} lines)")

    fm = parse_frontmatter(skill_text)
    if fm.get("name") != "promentor":
        errors.append(f"SKILL.md frontmatter name must be 'promentor', got {fm.get('name')!r}")
    if not fm.get("description"):
        errors.append("SKILL.md frontmatter missing description")

    # Verify bundled helper script exists, is indexed in SKILL.md, and runs --help cleanly.
    if not HELPER_SCRIPT.is_file():
        errors.append(f"Missing bundled helper script: {HELPER_SCRIPT.relative_to(REPO_ROOT)}")
    else:
        if "scripts/promentor.py" not in skill_text:
            errors.append("SKILL.md missing index entry for scripts/promentor.py")
        help_proc = subprocess.run(
            [sys.executable, str(HELPER_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        if help_proc.returncode != 0:
            errors.append(f"scripts/promentor.py --help failed (exit {help_proc.returncode}): {help_proc.stderr}")

    # Verify all referenced references/*.md files exist and none are orphaned.
    existing_refs = {p.name for p in REFS_DIR.glob("*.md")} if REFS_DIR.is_dir() else set()
    if not existing_refs:
        errors.append(f"No reference markdown files found in {REFS_DIR}")

    referenced_in_skill = set(re.findall(r"references/([a-zA-Z0-9._-]+\.md)", skill_text))
    missing_from_disk = referenced_in_skill - existing_refs
    if missing_from_disk:
        errors.append(f"SKILL.md references missing files: {sorted(missing_from_disk)}")

    unindexed_refs = existing_refs - referenced_in_skill
    if unindexed_refs:
        errors.append(f"Reference files not indexed in SKILL.md: {sorted(unindexed_refs)}")

    # Check internal references across all reference docs.
    all_skill_docs = [SKILL_MD, *sorted(REFS_DIR.glob("*.md"))]
    for doc in all_skill_docs:
        text = doc.read_text(encoding="utf-8")
        for ref_name in re.findall(r"references/([a-zA-Z0-9._-]+\.md)", text):
            if ref_name not in existing_refs:
                errors.append(f"{doc.relative_to(REPO_ROOT)} references missing references/{ref_name}")

    # Check agents/openai.yaml
    if not OPENAI_YAML.is_file():
        errors.append(f"Missing {OPENAI_YAML}")
    else:
        yaml_text = OPENAI_YAML.read_text(encoding="utf-8")
        for required_key in ("display_name:", "short_description:", "default_prompt:"):
            if required_key not in yaml_text:
                errors.append(f"agents/openai.yaml missing {required_key}")

    # Check stale legacy references in skill docs and README.
    check_files = [*all_skill_docs, README_MD]
    for path in check_files:
        if not path.is_file():
            errors.append(f"Missing file: {path.relative_to(REPO_ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, reason in STALE_PATTERNS:
            if pattern in text:
                errors.append(f"{path.relative_to(REPO_ROOT)} contains {reason}: {pattern!r}")

    # Ensure project_name is never used as a JSON key in examples.
    for path in all_skill_docs:
        text = path.read_text(encoding="utf-8")
        if '"project_name"' in text:
            errors.append(f"{path.relative_to(REPO_ROOT)} still uses deprecated JSON key \"project_name\"")

    # Check README repo URL matches git origin.
    slug = get_origin_repo_slug()
    if slug and README_MD.is_file():
        readme_text = README_MD.read_text(encoding="utf-8")
        if f"npx skills add {slug}" not in readme_text:
            errors.append(f"README.md missing matching install command: npx skills add {slug}")
        if f"https://github.com/{slug}.git" not in readme_text:
            errors.append(f"README.md missing matching clone URL: https://github.com/{slug}.git")

    # Check .gitignore rules and purity of skills/promentor/.
    if not GITIGNORE.is_file():
        errors.append("Missing .gitignore")
    else:
        gi_lines = {line.strip() for line in GITIGNORE.read_text(encoding="utf-8").splitlines()}
        for required in (".promentor/", "docs/"):
            if required not in gi_lines:
                errors.append(f".gitignore missing required entry: {required}")

    if (SKILL_DIR / "evals").exists() or (SKILL_DIR / ".promentor").exists():
        errors.append("skills/promentor/ must not contain evals/ or .promentor/")
    leaked_prom = [p for p in REPO_ROOT.rglob(".promentor") if ".git" not in p.parts]
    if leaked_prom:
        errors.append(f"Repository must not contain committed/stray .promentor directories: {leaked_prom}")

    return errors


def main() -> int:
    errors = validate_skill()
    if errors:
        print("SKILL VALIDATION FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1
    skill_lines = len(SKILL_MD.read_text(encoding="utf-8").splitlines())
    ref_count = len(list(REFS_DIR.glob("*.md")))
    print(f"SKILL VALIDATION PASSED (SKILL.md: {skill_lines} lines, {ref_count} reference docs, scripts/promentor.py OK)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
