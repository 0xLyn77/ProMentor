# ProMentor

> 把任意开源项目转成 MIT 风格的动手工程课程，在实践中掌握系统设计。

ProMentor 是一个 **AI Coding Agent Skill**。安装后，你的 AI 编程助手会化身为工程导师：扫描目标项目架构、规划阶梯式章节、按需生成讲义与防剧透源码导读、自动创建可编译的骨架代码与分层行为测试，并在你手写实现后判题、提供防代写分层提示、解锁源码深读与二次重构增量 Review。

## 工作流

```text
扫描架构 & 确认大纲            (/promentor init [--focus <模块>] [--all])
        ↓
概念讲解 & 写前契约导读        (/promentor learn <ch> · 按需生成章节)
        ↓
手写实现 & 分层行为测试        (/promentor test · /promentor hint 防代写护栏)
        ↓
防篡改校验 & 正式归档提交      (/promentor submit → attempt_N/)
        ↓
解锁源码深读 & 对比 Review     (/promentor review → review_N.md · 支持二次重构增量对比)
```

## 安装

### 方式一：Skills CLI（推荐）

```bash
npx skills add Lyn-77/ProMentor
```

### 方式二：手动安装

克隆仓库并将 `skills/promentor/` 复制到你的 Agent 技能目录：

```bash
git clone https://github.com/Lyn-77/ProMentor.git

# 全局安装（按你使用的 Agent 选择其一）
cp -r ProMentor/skills/promentor ~/.claude/skills/promentor    # Claude Code
cp -r ProMentor/skills/promentor ~/.codex/skills/promentor     # Codex
cp -r ProMentor/skills/promentor ~/.agents/skills/promentor    # 通用 Agent 目录
```

如需仅在单个项目中启用，可复制到该项目根目录的 `.claude/skills/promentor` 或 `.agents/skills/promentor`。

## 快速上手

在 AI 编程助手中打开任意想学习的项目目录：

1. **生成课程**：运行 `/promentor init`（或 `/promentor init --focus 路由层` 聚焦单一子系统）。AI 扫描项目架构并输出大纲，确认后立即落盘课程元数据，默认先生成第 1 章骨架与行为测试并通过 Red-State 自检；如需一次性生成全量章节可用 `/promentor init --all`。
2. **开始学习**：运行 `/promentor learn ch01`（或直接说“开始学第 1 章”）。若目标章节尚未生成，AI 会结合前置实现按需生成；在默认 `challenge` 防剧透模式下，先讲解概念、Mermaid 架构图与写前契约，再给出骨架代码位置。
3. **实现与调试**：在章节目录的骨架文件中手写实现，说“帮我测一下”或运行 `/promentor test` 查看 Part A/B/C 分层结果；卡住时说“给点提示”或运行 `/promentor hint`，防代写护栏确保只给思路不替你改代码。
4. **提交、深读与重构**：全部测试通过后运行 `/promentor submit` 校验测试未被篡改并目录制归档；再运行 `/promentor review` 解锁原项目核心源码行级深读、落盘 Review 报告并获取重构挑战——重构后可再次 `submit` + `review` 获取三方增量对比。

## 命令速查

支持显式斜杠命令，也支持自然语言直接交互（如“帮我测一下”“卡住了”“交作业”“对比下源码”）：

| 命令                              | 说明                                                        |
| --------------------------------- | ----------------------------------------------------------- |
| `/promentor init`                 | 扫描项目架构，确认大纲后默认按需生成第 1 章并通过自检       |
| `/promentor init --focus <模块>`  | 聚焦特定子系统（如路由层、存储引擎），规划 3–5 章精简课程   |
| `/promentor init --all`           | 确认大纲后一次性逐章生成全部章节                            |
| `/promentor init --resume`        | 逐章校验文件与校验和完整性，从中断或残缺处继续生成          |
| `/promentor`                      | 查看课程目录、生成状态与总体进度面板                        |
| `/promentor learn <ch>`           | 进入指定章节（支持 `ch01`、`1`、`router`、`final` 等简写）  |
| `/promentor test`                 | 运行当前章节的分层行为测试（Part A/B/C）并诊断失败原因      |
| `/promentor hint`                 | 读取当前代码与报错，触发防代写护栏并给出 Level 1–3 分层提示 |
| `/promentor submit`               | 校验测试完整性并全量跑通，目录制归档提交并锁定 100% 成绩    |
| `/promentor review`               | 解锁提交后源码深读、落盘 Review 报告，二次提交自动增量对比  |
| `/promentor progress`             | 查看各章节完成度、提交次数、提示层级与总体进度              |

## 生成的课程目录

运行 `/promentor init` 后，课程内容统一存放在目标项目根目录的 `.promentor/` 中（并自动追加到 `.gitignore`）：

```text
.promentor/
├── course.json                    # 课程大纲、mode、focus、source_commit 与章节生成状态
├── progress.json                  # 学习状态、得分、提交次数与提示层级
├── main.<ext>                     # （仅 Final 章）课程根目录可运行入口
├── chapters/
│   └── ch01-<slug>/
│       ├── lecture.md             # 概念讲解、设计权衡与 Mermaid 图表
│       ├── source.md              # 两阶段源码导读（Part 1 写前契约 + Part 2 提交后深读）
│       ├── lab.json               # Lab 契约、测试命令与 SHA-256 测试校验和
│       ├── <starter>.<ext>        # 自动生成的骨架代码（学生直接在此实现）
│       └── <test_file>            # 分层黑盒行为测试（只读，提交前防篡改校验）
└── submissions/
    └── ch01-<slug>/
        ├── attempt_1/             # 目录制归档：完整保留多文件 Lab 的历次提交
        ├── review_1.md            # 落盘的源码对比 Review 报告
        ├── attempt_2/             # （可选）二次重构提交归档
        └── review_2.md            # （可选）三方增量对比 Review 报告
```

## 特点

- **按需生成与子系统聚焦**：支持 Lazy Generation 边学边生成与 `--focus` 单子系统裁剪，降低大项目初始化耗时与行号偏移。
- **开箱即用的骨架与自检**：自动生成可编译 Starter Stub，并在生成期实跑测试确保进入干净的 Red State，内置 Go / Python / TypeScript / Rust / Java / C++ 多语言隔离规范。
- **防剧透 + 防代写双护栏**：默认 `challenge` 模式拆分写前导读与提交后深读；调试阶段强制锁定防代写护栏，确保真正动手训练。
- **对比与重构闭环**：每次提交支持目录制归档与 Review 落盘，支持完成 Challenge 重构后对 `attempt_1` vs `attempt_2` vs 原项目源码做三方增量对比。
- **零构建可视化**：以纯文本 Markdown + Mermaid（`flowchart` / `sequenceDiagram` / `classDiagram`）交付架构与调用链图解。

## 仓库开发自检（Maintainers）

仓库根目录的 `evals/` 提供纯标准库 Smoke Test 与规范校验套件（不打入 `skills/promentor/` 安装包）：

```bash
python3 evals/run_smoke.py
```
