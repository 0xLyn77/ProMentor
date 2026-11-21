# ProMentor

English | [简体中文](README_CN.md)

> Turn any open-source repository into an MIT-style hands-on engineering course and master system design by building it yourself.

ProMentor is an **AI Coding Agent Skill**. Once installed, your AI coding assistant becomes an engineering mentor: it scans the target project's architecture, plans a progressive syllabus, generates lectures and anti-spoiler source walkthroughs on demand, scaffolds compilable starter stubs with layered behavioral tests, grades your implementation, provides anti-ghostwriting layered hints, and unlocks deep source comparison reviews with iterative refactoring feedback.

## Workflow

```text
Scan Architecture & Confirm Syllabus       (/promentor init [--focus <module>] [--all])
        ↓
Lectures & Pre-Lab Contract Walkthrough    (/promentor learn <ch> · lazy generation)
        ↓
Hands-On Coding & Layered Behavioral Tests (/promentor test · /promentor hint guardrails)
        ↓
Tamper Check & Atomic Submission Archive   (/promentor submit → attempt_N/)
        ↓
Unlock Deep Source Read & Code Review      (/promentor review → review_N.md · 3-way refactor diff)
```

## Installation

### Option 1: Skills CLI (Recommended)

```bash
npx skills add 0xLyn77/ProMentor
```

### Option 2: Manual Installation

Clone this repository and copy `skills/promentor/` into your agent's skills directory:

```bash
git clone https://github.com/0xLyn77/ProMentor.git

# Global installation (pick the directory for your agent)
cp -r ProMentor/skills/promentor ~/.claude/skills/promentor    # Claude Code
cp -r ProMentor/skills/promentor ~/.codex/skills/promentor     # Codex
cp -r ProMentor/skills/promentor ~/.agents/skills/promentor    # Generic Agent directory
```

To enable ProMentor for a single project only, copy it to `.claude/skills/promentor` or `.agents/skills/promentor` inside that project's root directory.

## Quick Start

Open any codebase you want to learn in your AI coding assistant:

1. **Generate a Course**: Run `/promentor init` (or `/promentor init --focus router` to target a single subsystem). The AI scans the architecture and proposes a syllabus; once confirmed, it immediately writes course metadata and generates Chapter 1 with starter stubs and behavioral tests verified in a clean Red State. Use `/promentor init --all` to generate all chapters upfront.
2. **Start Learning**: Run `/promentor learn ch01` (or simply say "start chapter 1"). If a chapter has not been generated yet, ProMentor generates it on demand using the anchored source commit and your prior implementations. In the default `challenge` anti-spoiler mode, it walks through concepts, Mermaid architecture diagrams, and pre-lab interface contracts before pointing you to the starter stub.
3. **Implement & Debug**: Write your implementation in the chapter's starter files, then say "run the tests" or run `/promentor test` to see Part A/B/C layered diagnostics. When stuck, ask for a hint or run `/promentor hint` — anti-ghostwriting guardrails ensure the agent gives structured guidance without editing your solution or spoiling the code.
4. **Submit, Deep-Read & Refactor**: Once all tests pass, run `/promentor submit` to verify test integrity and atomically archive your submission. Then run `/promentor review` to unlock line-by-line deep source analysis, persist a structured review report, and get a concrete refactoring challenge — after refactoring, submit and review again for a 3-way incremental comparison.

## Commands

Both explicit slash commands and natural language prompts (e.g., "run the tests", "I'm stuck", "submit my solution", "compare with the original source") are supported:

| Command                           | Description                                                                        |
| --------------------------------- | ---------------------------------------------------------------------------------- |
| `/promentor init`                 | Scan project architecture, confirm syllabus, and lazily generate Chapter 1         |
| `/promentor init --focus <scope>` | Focus on a specific subsystem (e.g., router, storage engine) with 3–5 chapters     |
| `/promentor init --all`           | Generate all chapters sequentially right after confirming the syllabus             |
| `/promentor init --resume`        | Check chapter integrity and resume interrupted generation without overwriting code |
| `/promentor`                      | Show the course syllabus, chapter generation status, and progress dashboard        |
| `/promentor learn <ch>`           | Enter a chapter (supports shorthands like `ch01`, `1`, `router`, `final`)          |
| `/promentor test`                 | Run layered behavioral tests (Part A/B/C) and diagnose failures                    |
| `/promentor hint`                 | Inspect your code & errors and provide Level 1–3 hints under anti-ghostwriting rules |
| `/promentor submit`               | Verify test checksum & full green pass, archive to `attempt_N/`, and lock 100%     |
| `/promentor review`               | Unlock post-submit source deep read, save `review_N.md`, and diff refactors        |
| `/promentor progress`             | View per-chapter completion, attempts, hint level reached, and overall progress    |

## Generated Course Layout

Running `/promentor init` stores all course artifacts in `.promentor/` at the target repository root (automatically ignored via `.git/info/exclude` in Git repos so the target project's tracked `.gitignore` stays untouched):

```text
.promentor/
├── course.json                    # Syllabus, mode, focus, source_commit, and generation status
├── progress.json                  # Status, score, attempts, and highest hint level per chapter
├── main.<ext>                     # (Final chapter only) runnable entry point at course root
├── chapters/
│   └── ch01-<slug>/
│       ├── lecture.md             # Concepts, design tradeoffs, and Mermaid diagrams
│       ├── source.md              # Two-stage walkthrough (Part 1 Pre-Lab + Part 2 Post-Submit)
│       ├── lab.json               # Lab contract, test command, and SHA-256 test checksum
│       ├── <starter>.<ext>        # Auto-generated starter stub where you write your solution
│       └── <test_file>            # Layered black-box behavioral tests (read-only, checksummed)
└── submissions/
    └── ch01-<slug>/
        ├── attempt_1/             # Directory-based archive preserving all multi-file lab sources
        ├── review_1.md            # Persisted source comparison review report
        ├── attempt_2/             # (Optional) refactored resubmission archive
        └── review_2.md            # (Optional) 3-way incremental comparison review report
```

## Key Features

- **Lazy Generation & Subsystem Focus**: Generate chapters on demand or narrow large codebases to a single subsystem via `--focus`, keeping initialization fast and line references anchored to `source_commit`.
- **Ready-to-Run Starter Stubs & Red-State Gates**: Automatically scaffolds compilable starter code and executes every chapter's tests during generation to verify a clean Red State, with built-in isolation conventions for Go, Python, TypeScript/JavaScript, Rust, Java, and C/C++.
- **Anti-Spoiler & Anti-Ghostwriting Guardrails**: Default `challenge` mode separates pre-lab contracts from post-submit deep dives, while strict guardrails prevent the coding agent from editing student lab files or pasting full solutions.
- **Compare & Refactor Loop**: Directory-based submission archives and persisted review reports enable iterative refactoring with 3-way reviews comparing `attempt_1`, `attempt_2`, and the original upstream source.
- **Zero-Build Visualization**: Plain Markdown plus native Mermaid diagrams (`flowchart`, `sequenceDiagram`, `classDiagram`) render cleanly across Markdown viewers with no dashboard build step.

## License

[MIT](LICENSE)
