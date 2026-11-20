# 代码扫描与课程生成规范

> 执行 `/promentor init`（含 `--all` / `--focus` / `--resume`）及 `/promentor learn` 按需生成章节时的详细规范。
> 识别项目语言后，同步阅读 `references/languages.md` 获取对应语言的隔离与测试模板。

## 目录

- [4.1 四轮扫描法](#41-四轮扫描法)
- [4.2 大项目裁剪与子系统聚焦（--focus）](#42-大项目裁剪与子系统聚焦--focus)
- [4.3 难度评级](#43-难度评级)
- [4.4 按需逐章生成（Lazy Generation）与落盘顺序](#44-按需逐章生成lazy-generation与落盘顺序)
- [4.5 Chapter 生成规范](#45-chapter-生成规范)
- [4.6 分层测试与 Red-State 自检规范](#46-分层测试与-red-state-自检规范)
- [4.7 跨章 Lab 依赖解耦](#47-跨章-lab-依赖解耦)

---

## 4.1 四轮扫描法

先在项目根目录记录 `source_commit`（执行 `git rev-parse HEAD`，非 Git 仓库置空 `""`），再按四轮扫描理解架构：

### 第一轮：结构探测
- **目标**：弄清项目语言、规模、工具链、运行环境与模块边界。
- **操作**：
  - 获取文件树（跳过 `.git`、`.promentor`、`vendor`、`node_modules`、`dist`、`build`、`test` 等目录）。
  - 搜索入口文件（`main.go`、`main.py`、`src/main.rs`、`index.ts`、`app.ts` 等）与包/模块清单（`go.mod`、`pyproject.toml`、`package.json`、`Cargo.toml`）。
  - 检测本地可用的解释器/编译器与测试框架（参考 `references/languages.md`）。
  - 统计源码文件数与代码行数，向用户汇报识别结果并确认继续。

### 第二轮：核心类型识别
- **目标**：定位核心数据结构、契约接口与组合关系。
- **操作**：
  - 搜索 `type` / `struct` / `class` / `interface` / `trait` 声明，读取关键类型源码。
  - 区分对外公开契约与内部实现细节，梳理依赖关系（供绘制 `classDiagram`）。

### 第三轮：调用链追踪
- **目标**：理解核心请求、事件或数据的完整生命周期。
- **操作**：
  - 从入口点出发追踪核心调用链、关键分支与扩展点（回调、中间件、插件、接口实现）。
  - 记录核心流程节点与交互顺序（供绘制 `sequenceDiagram`）。

### 第四轮：架构归纳
- **目标**：提炼设计模式与关键权衡，拟定阶梯式 Chapter 大纲。
- **操作**：
  - 按依赖拓扑顺序划分 Chapter（推荐 4–8 章；`--focus` 模式推荐 3–5 章）。
  - 为每章确定：合法 `id`（见 `references/data-format.md` §1.2）、`title`、`summary`、`difficulty`、`prerequisites`、`learning_goals`、`source_files`（带真实行号范围）与 `lab_interface`。

---

## 4.2 大项目裁剪与子系统聚焦（`--focus`）

### 场景 A：子系统聚焦（`/promentor init --focus <模块/主题>` 或自然语言指定模块）

当用户只关心大型仓库中的特定子系统（如“只学路由层”、“聚焦存储引擎和 WAL”、“focus scheduler”）时：
1. 定位目标子系统的核心目录/文件，仅向下追踪其直接契约边界（1–2 层调用上游与下游接口）。
2. 将外部依赖抽象为最小接口/Mock 契约，不把无关子系统拖入课程。
3. 规划 **3–5 章**精简路线（基础数据结构 → 核心流程 → 边界/并发处理 → 小型集成），在 `course.json` 中记录 `"focus": "<模块/主题>"`。

### 场景 B：全项目大仓库裁剪（>200 文件）

- **拓扑扩散**：从入口点 BFS，前 3 层完整读源码，4–6 层读签名与注释，7 层以上跳过。
- **功能去重**：同类 Controller / Middleware / Driver 只选 1 个代表深入剖析，其余仅记录名称。
- **优先级标记**：P0（入口、核心类型、主干方法）> P1（核心算法、关键调用链）> P2（配置、工具）；排除 `test`、`mock`、`vendor`、`generated`。

---

## 4.3 难度评级

| 难度 | 判定特征 |
| --- | --- |
| `easy` | 概念直白，实现短小（<100 行），标准惯用写法 |
| `mid` | 涉及 1–2 个设计决策，代码量中等，需理解 1 个前置概念 |
| `hard` | 包含核心架构或非平凡数据结构选型，需 2+ 前置概念，边界出错会导致隐蔽故障 |

---

## 4.4 按需逐章生成（Lazy Generation）与落盘顺序

为降低长上下文退化、避免行号幻觉并让用户快速开练，严格遵循以下落盘顺序：

1. **大纲确认后立即落盘元数据**：
   - 用户确认大纲（及 `mode`: 默认 `challenge` 或 `guided`）后，**立刻写入** `.promentor/course.json`（所有章初始 `generation_status: "pending"`）与 `.promentor/progress.json`（所有章初始 `status: "not_started"`）。
   - 执行 `python3 <skill_dir>/scripts/promentor.py exclude` 将 `.promentor/` 写入 `.git/info/exclude`（不修改目标仓库已跟踪的 `.gitignore`；仅非 Git 目录回退写入 `.gitignore`）。
   - 这样即使在生成任一章节中途断线，`/promentor init --resume` 也能可靠恢复，且保持目标仓库 `git status` 干净！
2. **默认仅生成首章（`generation_mode: "lazy"`）**：
   - 默认 `/promentor init` 只生成大纲中的**第 1 章**（通过 Red-State 自检后将 `course.json` 该章更新为 `generation_status: "generated"`），随后提示用户直接 `/promentor learn <ch1>` 开学。
   - 若用户明确指定 `/promentor init --all`，则设置 `generation_mode: "all"`，按顺序逐章生成并每章完成自检后即时更新 `course.json`。
3. **后续章节按需动态生成**：
   - 当用户执行 `/promentor learn <ch>` 进入一个 `generation_status != "generated"`（或文件残缺）的章节时，现场读取原始源码（依据 `course.json`）及前置章节学生的实际实现，动态生成本章全部产物并通过 Red-State 自检，更新 `course.json` 为 `"generated"` 后无缝进入教学。

---

## 4.5 Chapter 生成规范

每生成一章前，先将该章在 `course.json` 中的 `generation_status` 置为 `"in_progress"`；全部产物落盘并通过 Red-State 自检后再更新为 `"generated"`。

### 1. `lecture.md`（概念与设计决策讲义）
- 篇幅 **≤ 300 行**。
- 结构：开篇定位 → 核心概念与问题拆解 → 设计决策与替代方案权衡 → Mermaid 图表 → 衔接 Lab。
- **防剧透原则**：在 `challenge` 模式下，可讨论思路、抽象契约与复杂度权衡，**严禁贴出待实现核心算法的完整原始实现代码**。
- **Mermaid 可视化规范**（零构建依赖，确保所有 Markdown 渲染器直接可读）：
  - 架构总览 / 模块依赖 → `flowchart TD` 或 `flowchart LR`
  - 请求 / 数据生命周期 → `sequenceDiagram`
  - 核心类型 / 接口关系 → `classDiagram`
  - 节点标签含括号/特殊字符时用双引号包裹（如 `A["Router (Radix Tree)"]`），不使用 HTML 标签。

### 2. `source.md`（两阶段源码导读）
- **源码锚定读取**：若 `course.json` 的 `source_commit` 非空，生成 `lecture.md` 与 `source.md` 时一律通过 `git show {source_commit}:{path}` 读取原始源码（`source_commit` 为空时读工作区文件），确保行号永久锚定到初始化版本。
- 严格拆分为两个顶级分区（完整模板见 `references/data-format.md` §1.7）：
  - `## Part 1: 写前导读（Pre-Lab · 契约与边界）`：模块定位、Mermaid 交互图、外部接口签名与调用入口；隐藏内部核心算法细节。
  - `## Part 2: 提交后深读（Post-Submit · 核心实现剖析）`：在 `/promentor review` 解锁，逐段标注核心数据结构、关键算法与边界处理的精确行号及“为什么”。
- **行号核对**：写入后优先运行 `python3 <skill_dir>/scripts/promentor.py verify {chapter_id}` 校验每处 `path/to/file:start-end` 真实存在且未越界。

### 3. `lab.json`（Lab 契约定义）
- 严格遵守 `references/data-format.md` §1.5：声明精确的 `files`、`starter_files`、`test_file`、`interface.types`、`interface.functions`、`test_command` 与可选 `notes`。
- `test_checksum` 在 Red-State 自检通过后立即计算并写回。

### 4. Starter Stub（骨架代码）
- 按 `lab.json` 中 `files` 与 `interface` 在 `.promentor/chapters/{chapter_id}/` 直接创建全部骨架文件，消除学生手抄签名、拼错包路径的编译卡顿。
- **必须包含**：合法包/模块声明、所需标准库 import、导出类型定义、严格匹配的导出函数/方法签名、清晰文档注释（含契约与边界要求）。
- **空实现体**：使用语言惯用的未实现占位（如 Go `panic("not implemented")`、Python `raise NotImplementedError(...)`、TS/JS `throw new Error("not implemented")`、Rust `todo!()`、Java `throw new UnsupportedOperationException(...)`）。
- **严禁在骨架中剧透核心算法或写好关键实现**。

### 5. `lab_test.<ext>`（分层黑盒行为测试）
- 按 §4.6 与 `references/languages.md` 编写，命名贴合目标语言测试框架（`lab_test.go`、`test_lab.py`、`lab_test.ts` 等；TS/JS 禁止使用会被宿主收集的 `*.test.*` / `*.spec.*`）。

### 6. Final / 组装章可运行入口
- 仅在 Final / 组装章额外于课程根目录生成可运行入口（如 `.promentor/main.go`、`.promentor/main.py`、`.promentor/index.ts`），与章节目录分离避免包冲突。
- 入口仅做三件事：初始化数据层 → 组装顶层组件 → 启动运行时（CLI / HTTP / TUI）。
- 在 Final 章 `lab.json` 的 `notes` 中写明运行命令（如 `go run ./.promentor`、`python3 .promentor/main.py`、`node .promentor/index.ts`），并在生成后执行语法/构建检查（如 `go build ./.promentor`、`python3 -m py_compile`、`node --check`）。

---

## 4.6 分层测试与 Red-State 自检规范

### 黑盒原则与三层测试组织

所有行为测试只验证公开接口的输入/输出与可观测行为，不耦合内部私有字段，并在测试文件中明确划分为三层：

| 层级 | 名称 | 覆盖内容 |
| --- | --- | --- |
| **Part A** | 基础行为（Core Behavior） | 主干成功路径、典型输入输出、核心契约 |
| **Part B** | 边界与异常（Edge Cases & Errors） | 空输入、不存在的键、非法参数、重复注册、错误码/异常返回 |
| **Part C** | 并发 / 性能 / 扩展场景（Concurrency / Scale / Stretch） | 按项目真实特性选用：并发安全、较大量级复杂度、嵌套组合或协议进阶特性 |

### 路径安全示例

**Go 示例**（外部测试包 + `guardPanic` 隔离单个 panic + 清晰分层；若宿主有 `go.mod` 使用 `<host_module>/.promentor/chapters/ch02-router`，若使用独立 `.promentor/go.mod` 使用 `promentor/course/chapters/ch02-router`）：

```go
package router_test

import (
	"net/http"
	"testing"

	student "promentor/course/chapters/ch02-router"
)

func guardPanic(t *testing.T) {
	t.Helper()
	if r := recover(); r != nil {
		t.Fatalf("unimplemented or panic: %v", r)
	}
}

// Part A: 基础行为
func TestPartA_StaticRoute(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	r.AddRoute("GET", "/users", func(w http.ResponseWriter, req *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	h, _ := r.FindRoute("GET", "/users")
	if h == nil {
		t.Fatal("GET /users: expected handler, got nil")
	}
}

// Part B: 边界与异常
func TestPartB_MethodMismatch(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	r.AddRoute("GET", "/users", func(w http.ResponseWriter, req *http.Request) {})
	h, _ := r.FindRoute("POST", "/users")
	if h != nil {
		t.Fatal("POST /users: expected nil handler on method mismatch")
	}
}

// Part C: 嵌套参数与优先级
func TestPartC_StaticPriorityOverParam(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	var hit string
	r.AddRoute("GET", "/users/:id", func(w http.ResponseWriter, req *http.Request) { hit = "param" })
	r.AddRoute("GET", "/users/me", func(w http.ResponseWriter, req *http.Request) { hit = "static" })
	h, _ := r.FindRoute("GET", "/users/me")
	if h == nil {
		t.Fatal("GET /users/me: expected handler")
	}
	h(nil, nil)
	if hit != "static" {
		t.Fatalf("expected static route priority, got %q", hit)
	}
}
```

**Python 示例**（使用 `Path(__file__).resolve().parent` 解析路径，绝不硬编码 `.promentor/chapters/...`）：

```python
from pathlib import Path
import sys
import unittest

CHAPTER_DIR = Path(__file__).resolve().parent
if str(CHAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(CHAPTER_DIR))

from router import Router


class TestPartACoreBehavior(unittest.TestCase):
    def test_static_route(self) -> None:
        r = Router()
        r.add_route("GET", "/users", lambda req: {"status": 200})
        handler, params = r.find_route("GET", "/users")
        self.assertIsNotNone(handler, "GET /users: 未找到路由处理函数")
        self.assertEqual(params, {})


class TestPartBEdgeCases(unittest.TestCase):
    def test_method_mismatch_returns_none(self) -> None:
        r = Router()
        r.add_route("GET", "/users", lambda req: {"status": 200})
        handler, _ = r.find_route("POST", "/users")
        self.assertIsNone(handler)


if __name__ == "__main__":
    unittest.main()
```

### 生成期 Red-State 自检（强制门禁）

每章产物写完后，**优先运行内置脚本**完成门禁与校验和写入（无 Python 3 环境时按下方 4 点手工核验）：

```bash
python3 <skill_dir>/scripts/promentor.py gate red {chapter_id}
python3 <skill_dir>/scripts/promentor.py checksum {chapter_id}
python3 <skill_dir>/scripts/promentor.py verify {chapter_id}
```

核验要点：
1. **成功编译/加载**：无语法错误、无类型签名不匹配、无 `ImportError` / `ModuleNotFoundError` / 找不到包 / 命令不存在等环境问题。
2. **测试按预期失败（Red State）**：进程返回非零退出码，失败原因是骨架代码的 `not implemented` / `NotImplementedError` / `panic` 或行为断言失败，而非 0 tests collected。
3. **实际执行的测试数 = 测试文件声明的测试数**：确保所有用例均完整执行并报告结果，不会因单条未捕获的 `panic` / `abort` 中断整个测试进程。
4. **写入 `test_checksum` 与完成校验**：自检通过后计算 `test_file` 的 SHA-256（`sha256:<64位小写十六进制>`）写入 `lab.json`，再将 `course.json` 该章的 `generation_status` 置为 `"generated"`。

若自检遇到编译、导入、路径或用例中断错误，**当场修复并重新验证**，禁止带着坏掉的测试进入教学或下一章。

---

## 4.7 跨章 Lab 依赖解耦

按依赖顺序学习时，后置章节尚未编写。生成 Lab 时遵守：

1. **单向依赖**：`prerequisites` 只指向已定义的前置章节；学生代码只允许引用前置章节产物，禁止循环依赖。
2. **暂缺依赖占位**：后置章节能力未实现时，在 `lab.json` 的 `notes` 中写明占位行为（如“先返回自身 / 忽略中间件”），测试不覆盖暂缺能力。
3. **共享契约独立导出**：跨章节传递的消息、请求结构或接口定义在课程章节自身模块中导出，避免直接耦合宿主私有包。
4. **断言与原项目对齐**：黑盒断言严格贴合原始项目行为，避免因为测试过度假定实现细节而误杀正确解法。
