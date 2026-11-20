# ProMentor 命令执行手册

> 执行具体命令或自然语言路由到对应动作时查阅本手册。读写课程文件前结合 `references/data-format.md`。

## 目录

- [1. `/promentor init`（含 `--focus` / `--all` / `--resume`）](#1-promentor-init含---focus----all----resume)
- [2. `/promentor`（课程面板）与 `/promentor progress`](#2-promentor课程面板与-promentor-progress)
- [3. `/promentor learn <chapter>`](#3-promentor-learn-chapter)
- [4. `/promentor test`](#4-promentor-test)
- [5. `/promentor hint`](#5-promentor-hint)
- [6. `/promentor submit`](#6-promentor-submit)
- [7. `/promentor review`](#7-promentor-review)
- [8. 通用前置检查（Commit 锚定与测试防篡改）](#8-通用前置检查commit-锚定与测试防篡改)

---

## 1. `/promentor init`（含 `--focus` / `--all` / `--resume`）

执行前加载 `references/generation.md`、`references/data-format.md`，并在识别语言后加载 `references/languages.md`。

### 1.1 标准流程（`/promentor init` / `--focus <主题>` / `--all`）

1. **Step 1：识别项目与工具链**
   - 探测语言、入口文件、文件数/代码行数、本地测试运行器（参考 `references/languages.md`）以及 `git rev-parse HEAD`（作为 `source_commit`，非 Git 仓库为 `""`）。
   - 向用户汇报项目摘要，确认是否继续。
2. **Step 2：四轮扫描**
   - 按 `references/generation.md` §4.1 执行四轮扫描；若带 `--focus <模块/主题>`（或自然语言聚焦某子系统），仅聚焦目标模块及上下游边界规划 3–5 章；若全项目超过 200 文件则执行 §4.2 裁剪。
3. **Step 3：展示大纲并等待用户确认**
   - 展示完整大纲（含章节 ID、标题、难度、一句话简介、依赖与总章数），同时说明默认设置：**按需逐章生成（先生成第 1 章）**、**防剧透挑战模式（`challenge`）**，允许用户增删改章节、切换 `guided` 模式或要求一次生成全部章节。

```text
ProMentor 课程大纲：《{项目名} 内部设计》

  ch01-http-server   HTTP Server 基础    [mid]   net/http Server 的生命周期
  ch02-router        Router 设计         [hard]  前缀树路由与路径参数匹配
  ch03-middleware    Middleware 管道     [mid]   责任链模式实践
  final-mini-gin     组装 Mini Gin       [hard]  把所有组件拼成可运行框架

默认设置：challenge 防剧透模式 · 按需逐章生成（确认后先生成第 1 章）
回复可调整：新增 / 删除 / 调整顺序 / 切换 guided 模式 / 全量生成
```

4. **Step 4：确认后立即落盘元数据**
   - 写入 `.promentor/course.json`（每章初始 `generation_status: "pending"`）与初始 `.promentor/progress.json`（每章初始 `status: "not_started"`、`score: 0`、`attempts: 0`、`hint_level_reached: 0`）。
   - 若目标项目根目录 `.gitignore` 未包含 `.promentor/`，自动追加 `.promentor/`。
5. **Step 5：生成章节 + Red-State 自检**
   - 默认模式（`generation_mode: "lazy"`）：仅生成第 1 章。
   - `--all` 模式（`generation_mode: "all"`）：按顺序逐章生成，每完成一章汇报进度（如 `Ch 1/4 已生成并通过 Red-State 自检`）。
   - 每章严格生成：`lecture.md`、`source.md`（Part 1 + Part 2）、`lab.json`、Starter Stub 骨架代码、分层 `lab_test`（以及 Final 章根目录入口），执行 `test_command` 验证进入干净的 **Red State**，计算并写入 `test_checksum`，最后将 `course.json` 该章更新为 `generation_status: "generated"`。
6. **Step 6：输出启动引导**

```text
🎓 课程已就绪：{项目名}（共 {N} 章 · 已生成 {G}/{N} 章）

开始学习：/promentor learn {first_chapter_id}
查看目录：/promentor progress
```

### 1.2 断点续传（`/promentor init --resume`）

当 `init` 在中途中断时，按以下规则可靠恢复：

1. 检查 `.promentor/course.json` 是否存在：
   - 若不存在（中断在大纲确认前），提示并从标准 `init` 流程重新开始。
2. 确保 `.promentor/progress.json` 存在并与 `course.json` 章节列表对齐（缺失章节补默认 `not_started` 条目）。
3. **逐章文件完整性校验**：对目标需要生成的章节（`generation_mode == "all"` 检查全部章节；`lazy` 模式至少检查首章及所有已标记 `generated` / `in_progress` 的章节）逐一校验：
   - `course.json` 中 `generation_status == "generated"`；
   - `lecture.md` 存在且非空；
   - `source.md` 存在、非空且包含 Part 1 与 Part 2；
   - `lab.json` 存在、JSON 合法且包含有效 `test_checksum`；
   - `lab.json` 中 `files` 与 `starter_files` 声明的全部骨架文件存在；
   - `lab.json` 中 `test_file` 存在且与 `test_checksum` 一致；
   - （若为 Final 章）课程根目录可运行入口存在。
4. 任意一项缺失或残缺时，**完整重新生成该章**并重新通过 Red-State 自检与 `test_checksum` 写入；已完整通过校验的章节直接跳过，不重复生成。

---

## 2. `/promentor`（课程面板）与 `/promentor progress`

读取 `.promentor/course.json` 与 `.promentor/progress.json`（若不存在则提示运行 `/promentor init`），严格按 `references/data-format.md` §1.4 的统一评分公式渲染：

```text
ProMentor: {project} ({language} · {mode})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ch01-http-server   HTTP Server 基础    [mid]   ✓   100%  (attempts: 1, hint: L1)
  ch02-router        Router 设计         [hard]  ▶    60%  (attempts: 0, hint: L2)
  ch03-middleware    Middleware 管道     [mid]   -      -  [待按需生成]
  final-mini-gin     组装 Mini Gin       [hard]  -      -  [待按需生成]

  Overall: 1/4 chapters · 25% complete

命令：learn <ch> | test | hint | submit | review | progress
```

状态符号：`✓` 已完成（`score == 100`）、`▶` 进行中（`score` 为 `0–99`）、`-` 未开始；若章节 `generation_status != "generated"`，标注 `[待按需生成]`。

---

## 3. `/promentor learn <chapter>`

1. **定位章节**：按 `references/data-format.md` §1.2 简写规则匹配 `course.json`（支持 `ch01`、`1`、`router`、`final` 等）。
2. **检查 Commit 锚定**：执行 §8.1 检查；如源码有变更，先告知用户并提供选项。
3. **检查前置依赖**：若 `prerequisites` 中存在未完成章节，礼貌提醒但允许继续。
4. **按需生成（Lazy Generation）**：
   - 检查该章 `generation_status` 及文件完整性（同 §1.2 校验清单）。
   - 若尚未生成或残缺：先加载 `references/generation.md` 与 `references/languages.md`，现场读取原始源码及前置章节学生实现，生成本章完整产物、跑通 Red-State 自检、写入 `test_checksum`，并将 `course.json` 标记为 `"generated"`。
5. **展开教学**（结合 `references/teaching.md` §3）：
   - **概念引入**：1–2 句话点明本章在系统中的定位与核心矛盾。
   - **讲义讲解**：基于 `lecture.md` 对话式讲解概念、设计权衡与 Mermaid 图表（`challenge` 模式下严禁剧透实现代码）。
   - **源码导读**：
     - `challenge` 模式：仅讲解 `source.md` **Part 1（写前导读）**，聚焦契约与边界。
     - `guided` 模式：可完整讲解 Part 1 与 Part 2。
   - **Lab 指引**：说明 `lab.json` 契约、已生成的骨架文件路径、测试分层重点与 `notes` 提示。
6. **更新进度**：若本章原为 `not_started`，更新为 `in_progress`；更新 `progress.json` 的 `current_chapter`。
7. **结尾引导**：

```text
骨架代码已准备好：.promentor/chapters/{chapter_id}/{starter_file}
写完直接告诉我“帮我测一下”或运行 /promentor test。
```

---

## 4. `/promentor test`

1. 读取 `progress.json` 的 `current_chapter`（为空时询问测试哪一章）。
2. 读取该章 `lab.json`：
   - 可顺带检查 `test_file` 的 SHA-256（§8.2）；若发现被篡改，立即给出警告并说明提交会被拒绝。
   - 在项目根目录执行 `test_command`（替换 `{chapter_dir}`），捕获完整输出。
3. **按分层解析并展示结果**（通过与失败用例均展示，每个失败用例说明“期望 vs 实际”）：

```text
3/5 通过（60%）

Part A · 基础行为
  ✅ TestPartA_StaticRoute       (0.01s)
  ✅ TestPartA_MethodMatch       (0.01s)

Part B · 边界与异常
  ✅ TestPartB_MethodMismatch    (0.01s)
  ❌ TestPartB_ParamRoute        (0.01s) —— params["id"] 期望 "42"，得到空 map

Part C · 优先级与扩展
  ❌ TestPartC_StaticPriority    (0.01s) —— 静态段未优先于参数段

基础路由和常规边界已通过，参数提取与优先级仍待完善。需要提示直接说“给点提示”或运行 /promentor hint。
```

4. **更新进度**：
   - 若章节为 `in_progress` 且 `passed < total`：更新 `score = floor(passed / total * 100)`（上限 99）。
   - 若 `passed == total`：提示全部通过，引导运行 `/promentor submit` 正式归档与锁定成绩（不直接改为 `completed`）。

---

## 5. `/promentor hint`

执行前加载 `references/teaching.md` §2 & §4，严格遵守**防代写护栏**：

1. 读取当前章节学生实现文件（`lab.json` 中 `files` 声明的全部文件）。
2. 读取最近一次测试输出（若无最新输出或代码已修改，主动执行一次 `test_command`）。
3. 读取 `progress.json` 中本章的 `hint_level_reached`（0/1/2/3），按递增策略确定本次提示层级（`min(hint_level_reached + 1, 3)`，若当前错误属于全新的测试失败点可回到 Level 1）。
4. 精准结合学生代码具体行号与报错生成提示，**绝不编辑学生文件、绝不贴完整代码**。
5. 若本次层级高于历史记录，更新 `progress.json` 中的 `hint_level_reached`。

---

## 6. `/promentor submit`

1. 确定当前章节，读取 `lab.json`。
2. **测试文件防篡改校验（强制）**：执行 §8.2 核验 `test_file` 的 SHA-256 与 `lab.json` 的 `test_checksum` 一致；不一致时**拒绝提交**，提示恢复测试文件。
3. **运行全量行为测试**：执行 `test_command`。若存在任何失败用例，**拒绝提交**并展示失败详情，建议继续修改或请求 `/promentor hint`。
4. **目录制归档**：
   - 计算本次提交编号 `N = progress.chapters[id].attempts + 1`。
   - 创建目录 `.promentor/submissions/{chapter_id}/attempt_{N}/`，将 `lab.json` 的 `files[].path` 声明的全部实现文件按相对路径完整复制进去。
5. **更新 `progress.json`**：
   - `status`: `"completed"`
   - `score`: `100`
   - `attempts`: `N`
   - `completed_at`: 若此前未设置，写入当前 ISO-8601 UTC 时间戳
   - `last_submitted_at`: 写入当前 ISO-8601 UTC 时间戳
6. **展示提交结果**：
   - 若为首次提交（`N == 1`）：祝贺通过，提示运行 `/promentor review` 解锁源码深读与五维对比，或直接 `/promentor learn <next_ch>`。
   - 若为二次重构提交（`N >= 2`）：祝贺完成重构版本 `attempt_{N}`，提示运行 `/promentor review` 获取与上一版及原始源码的三方增量对比！

---

## 7. `/promentor review`

执行前加载 `references/teaching.md` §5。

1. 确定目标章节（默认 `current_chapter`，也可指定章节）。
2. 检查是否存在提交归档 `.promentor/submissions/{chapter_id}/attempt_{N}/`（`N` 为最新提交编号）；若尚未提交，提示先完成并通过 `/promentor submit`。
3. **检查 Commit 锚定**：执行 §8.1，若源码已变更则提示用户。
4. **收集材料**：
   - 读取 `.promentor/submissions/{chapter_id}/attempt_{N}/` 下的学生代码；
   - 若 `N >= 2`，同时读取 `attempt_{N-1}/` 用于增量对比；
   - 读取 `course.json` 中本章 `source_files` 对应的原始源码；
   - 读取本章 `lecture.md` 与 `source.md`（此时**正式解锁 Part 2 提交后深读**）。
5. **输出并落盘 Review**：
   - 按 `references/teaching.md` §5 进行五维对比（`N >= 2` 时增加“与 `attempt_{N-1}` 的演进对比”）、剖析原项目关键源码行与设计权衡，并在结尾给出 1 个具体的**重构挑战（Challenge）**。
   - 将完整评审报告按 `references/data-format.md` §1.8 规范写入 `.promentor/submissions/{chapter_id}/review_{N}.md`。
6. 保持对话开放，欢迎学生追问设计细节或接受 Challenge 进行下一轮重构。

---

## 8. 通用前置检查（Commit 锚定与测试防篡改）

### 8.1 源码 Commit 锚定检查（`learn` / `review` 时）

- 若 `course.json` 的 `source_commit` 非空，执行 `git rev-parse HEAD` 对比：
  - 若当前 HEAD 与 `source_commit` 不一致（或本章 `source_files` 存在本地修改），主动提醒用户：
    > “检测到原项目源码已从 `{old_sha[:7]}` 变更到 `{new_sha[:7]}`，`source.md` 中的行号可能偏移。你可以选择：继续阅读 / 仅刷新本章行号标注 / 更新课程锚点。”

### 8.2 测试文件防篡改校验（`submit` 前强制、`test` 时建议）

- 计算 `{chapter_dir}/{test_file}` 的 SHA-256 摘要（如 `shasum -a 256` 或 `sha256sum` 或 `python3 -c 'import hashlib...'`），与 `lab.json` 的 `test_checksum`（去掉 `sha256:` 前缀）比对。
- 若不一致：
  - `submit` 立即中止并拒绝提交；
  - 提示学生检查对测试文件的改动并还原；若学生反馈测试本身存在 Bug，需先核实并经用户明确确认后再由导师修正测试并更新 `test_checksum`。
