# 多语言隔离与测试规范

> 在 `/promentor init` 识别项目语言后，以及按需生成章节时按对应语言查阅本规范。
> 核心原则：**不污染宿主项目构建与测试、每章骨架可独立编译/导入、测试命令从项目根目录可直接运行。**

## 目录

- [通用原则](#通用原则)
- [Go](#go)
- [Python](#python)
- [TypeScript / JavaScript](#typescript--javascript)
- [Rust](#rust)
- [Java](#java)
- [C / C++](#c--c)

---

## 通用原则

1. **优先零外部依赖**：Lab 测试尽量只依赖目标语言标准库与宿主已安装的测试框架，避免需要联网下载新依赖。
2. **禁止依赖宿主私有/内部包**：如 Go 的 `internal/`、Rust 私有模块或未导出符号；所需基础类型在章节 Lab 或前置章节中明确定义并导出。
3. **路径与工作目录无关**：测试脚本内绝不硬编码 `.promentor/chapters/...` 相对路径，统一基于测试文件自身位置或语言原生包导入解析。
4. **干净的 Red State**：骨架文件必须通过编译/语法检查与导入，调用未实现函数时触发明确的未实现异常/Panic 或断言失败，从而让 `test_command` 产出可区分的“测试已运行但未通过”状态。

---

## Go

### 隔离机制与避坑

- **隐藏目录隔离**：Go 工具链执行 `go test ./...` 时默认跳过 `.` 开头的目录，因此 `.promentor/` 不会干扰宿主项目的常规构建与测试。
- **目录名与 `package` 解耦**：章节目录名含连字符（如 `ch02-router`），但源码中的 `package` 必须是合法标识符（如 `package router`），测试文件使用外部测试包 `package router_test`。
- **Module 路径判定**：
  - 若宿主根目录存在 `go.mod`（假设 `module example.com/app`），且 Lab 不依赖宿主 `internal/`：可直接复用宿主 `go.mod`，测试文件通过 `example.com/app/.promentor/chapters/ch02-router` 导入学生包，或同包导入（若希望黑盒测试强制走导出接口，优先 `package <pkg>_test` + 完整 module path 导入）。
  - 若宿主无 `go.mod`、为多 module 仓库、或希望彻底解耦：在 `.promentor/` 下创建独立的 `.promentor/go.mod`（如 `module promentor/course`），此时测试导入路径为 `promentor/course/chapters/ch02-router`，且跨章依赖（如 Ch 3 引入 Ch 2）同样通过该 module 路径自然解决。

### 命名与命令模板

- **测试文件**：`lab_test.go`（必须以 `_test.go` 结尾）
- **`test_command`**：`cd {chapter_dir} && go test -v .`
- **骨架代码模板**：

```go
package router

import "net/http"

// Handler handles a single HTTP request.
type Handler func(w http.ResponseWriter, req *http.Request)

// Router stores routes and matches incoming requests.
type Router struct {
	// TODO: 选择合适的数据结构存储路由表
}

// NewRouter creates a new Router instance.
func NewRouter() *Router {
	panic("not implemented: NewRouter")
}

// AddRoute registers a handler for the given HTTP method and path pattern.
func (r *Router) AddRoute(method, path string, handler Handler) {
	panic("not implemented: AddRoute")
}

// FindRoute finds the matching handler and extracts path parameters.
func (r *Router) FindRoute(method, path string) (Handler, map[string]string) {
	panic("not implemented: FindRoute")
}
```

- **黑盒测试导入与 Panic 隔离模板**：
  - 骨架代码使用 `panic("not implemented")` 时，单个未捕获 panic 会直接中止整个 `go test` 进程，导致其余测试用例无法执行、分层报告与得分失真。
  - **规定**：在 `lab_test.go` 中定义统一的 `guardPanic(t *testing.T)`，每个 `Test*` 函数首行调用 `defer guardPanic(t)`（必须直接 `defer` 含 `recover()` 的函数，才能捕获当前测试协程的 panic）：

```go
package router_test

import (
	"testing"

	student "<module_path>/.promentor/chapters/ch02-router"
	// 若使用独立 .promentor/go.mod，则为：
	// student "promentor/course/chapters/ch02-router"
)

func guardPanic(t *testing.T) {
	t.Helper()
	if r := recover(); r != nil {
		t.Fatalf("unimplemented or panic: %v", r)
	}
}

func TestPartA_StaticRoute(t *testing.T) {
	defer guardPanic(t)
	r := student.NewRouter()
	_ = r
}
```

---

## Python

### 隔离机制与避坑

- **解释器探测顺序**（在 `init` 第一步检测并记录到 `test_command`）：
  1. `.venv/bin/python` 或 `venv/bin/python`
  2. `uv run python`（若存在 `uv.lock` 且 `uv` 可用）
  3. `poetry run python`（若存在 `poetry.lock` 且 `poetry` 可用）
  4. 系统 `python3`
- **测试框架探测**：
  - 统一从**项目根目录**执行，**不要先 `cd {chapter_dir}`**（否则相对路径 `.venv/bin/python` 在 `cd` 后会失效）；测试文件已通过 `Path(__file__).resolve().parent` 解析同目录导入，与工作目录无关。
  - 若探测到的解释器已安装 `pytest`：使用 `<python> -m pytest -v -p no:cacheprovider -o addopts="" {chapter_dir}/test_lab.py`（`-p no:cacheprovider` 避免在目录留缓存，`-o addopts=""` 屏蔽宿主覆写参数）。
  - 若未安装 `pytest`：回退到标准库 `<python> {chapter_dir}/test_lab.py -v`（测试文件末尾包含 `unittest.main()`），零依赖开箱即用。
- **模块导入路径**：
  - **严禁**把相对路径（如 `.promentor/chapters/...`）直接插入 `sys.path`（切换工作目录后立即失效）。
  - **必须**基于测试文件绝对路径解析：`sys.path.insert(0, str(Path(__file__).resolve().parent))`。
  - 跨章导入前章模块时，使用 `Path(__file__).resolve().parent.parent / "ch01-xxx"`。

### 命名与命令模板

- **测试文件**：`test_lab.py`（同时兼容 `pytest` 和 `unittest`）
- **`test_command`**（从项目根目录直接执行，不 `cd`）：
  - `pytest`：`<python> -m pytest -v -p no:cacheprovider -o addopts="" {chapter_dir}/test_lab.py`
  - `unittest`（零依赖回退）：`<python> {chapter_dir}/test_lab.py -v`
- **骨架代码模板**：

```python
from typing import Any, Callable, Optional


class Router:
    """支持路径参数与 HTTP 方法匹配的路由器。"""

    def __init__(self) -> None:
        raise NotImplementedError("TODO: 初始化路由表数据结构")

    def add_route(self, method: str, path: str, handler: Callable[..., Any]) -> None:
        """注册一条路由规则，path 可包含 :param 参数段。"""
        raise NotImplementedError("TODO: 实现 add_route")

    def find_route(self, method: str, path: str) -> tuple[Optional[Callable[..., Any]], dict[str, str]]:
        """查找匹配路由，返回 (handler, params)；无匹配时 handler 为 None。"""
        raise NotImplementedError("TODO: 实现 find_route")
```

- **路径安全导入模板**：

```python
from pathlib import Path
import sys
import unittest

CHAPTER_DIR = Path(__file__).resolve().parent
if str(CHAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(CHAPTER_DIR))

from router import Router
```

---

## TypeScript / JavaScript

### 隔离机制与避坑

- **避免被宿主 `npm test` 收集**：Vitest（`configDefaults.exclude` 仅排除 `.git`/`.idea`/`.cache` 等）和 Jest **默认都会扫描 `.promentor/` 目录**。若测试命名为 `*.test.ts` 或 `*.spec.ts`，初始红态的 Lab 测试会让宿主项目的 `npm test` 直接变红！
  - **规避规则**：Lab 测试文件一律命名为 **`lab_test.ts`**（TS）或 **`lab_test.mjs`**（JS）——不匹配 Vitest 默认 `**/*.{test,spec}.*` 与 Jest 默认 `?(*.)+(spec|test).*` 规则，彻底隔离宿主测试。
- **首选运行器（Node 原生 `node --test`）**：
  - Node 内置类型擦除在 **Node >= 22.18** 及 **Node >= 23.6** 默认开启；在 **Node 22.6–22.17** 需附加 `--experimental-strip-types`。
  - `init` 第一步检测 `node -v`，按版本生成对应 `test_command`：
    - Node >= 22.18 / >= 23.6：`node --test {chapter_dir}/lab_test.ts`
    - Node 22.6–22.17：`node --experimental-strip-types --test {chapter_dir}/lab_test.ts`
  - 原生 TS 模式下使用可擦除语法（避免 `enum`、parameter properties 等需转译语法），导入同目录 TS 文件写明 `.ts` 扩展名（如 `import { EventBus } from "./event_bus.ts";`）。
- **可选方案（Vitest / Jest）**：仅当目标项目强依赖非擦除 TS 特性或 Vite/Jest 插件时采用，仍保持 `lab_test.ts` 命名，并通过显式传入文件路径与独立配置运行，不修改宿主配置。
- **ESM / CJS 隔离**：若宿主 `package.json` 的 `"type"` 与课程脚本风格冲突，可在 `.promentor/package.json` 中放置最小配置 `{ "type": "module" }`，隔离模块解析模式，同时 Node 向上查找仍可复用宿主 `node_modules`。

### 命名与命令模板

- **测试文件**：`lab_test.ts`（TS）或 `lab_test.mjs`（JS）（**禁止**使用 `*.test.*` / `*.spec.*`）
- **`test_command`**：`node --test {chapter_dir}/lab_test.ts`（Node 22.6–22.17 加 `--experimental-strip-types`）
- **骨架代码模板**：

```ts
export type Handler<T = unknown> = (payload: T) => void | Promise<void>;

export class EventBus {
  constructor() {
    // 允许构造后再在方法内抛错，或在构造时初始化空状态
  }

  on<T = unknown>(topic: string, handler: Handler<T>): () => void {
    throw new Error("not implemented: on");
  }

  async emit<T = unknown>(topic: string, payload: T): Promise<void> {
    throw new Error("not implemented: emit");
  }
}
```

---

## Rust

### 隔离机制与避坑

- **Workspace 冲突**：Cargo 会从当前目录逐层向上查找 `Cargo.toml`，若宿主是 Cargo workspace，直接把 crate 放进 `.promentor/chapters/` 会报错 `current package believes it's in a workspace`。
- **标准隔离方案**：
  - 在每章 `{chapter_dir}/Cargo.toml`（或在 `.promentor/Cargo.toml`）中显式声明独立的 `[workspace]` 表，阻断向上查找宿主 workspace！
  - 目录结构遵循标准 crate：`Cargo.toml`、`src/lib.rs`（骨架文件）、`tests/lab_test.rs`（黑盒集成测试）。
  - 跨章依赖直接在 `Cargo.toml` 的 `[dependencies]` 中用 `path = "../ch01-xxx"` 引用前置章节 crate。

### 命名与命令模板

- **骨架文件**：`src/lib.rs`（`starter_files` 同时列出 `Cargo.toml` 与 `src/lib.rs`）
- **测试文件**：`tests/lab_test.rs`
- **`test_command`**：`cargo test --manifest-path {chapter_dir}/Cargo.toml -- --nocapture`
- **隔离 `Cargo.toml` 模板**：

```toml
[workspace]

[package]
name = "ch02_router"
version = "0.1.0"
edition = "2021"
```

- **骨架代码模板**：

```rust
pub struct Router;

impl Router {
    pub fn new() -> Self {
        todo!("not implemented: Router::new")
    }
}
```

---

## Java

### 隔离机制与避坑

- **避免侵入宿主 Maven / Gradle**：不修改宿主 `pom.xml` 或 `build.gradle`。
- **最小独立编译测试模板**：
  - 若仅依赖 JDK 标准库，用 `javac` 将骨架文件与 `LabTest.java` 编译到临时输出目录（如 `/tmp/promentor-{chapter_id}`），再用 `java -ea` 运行测试主类。
  - **逐用例异常隔离**：自制 `LabTest` 运行器必须对每条用例用 `try { test.run(); } catch (Throwable t) { ... }` 捕获异常（含 `UnsupportedOperationException` / `AssertionError`），逐项打印 `PASS` / `FAIL` 及汇总 `passed/total` 后，若有失败再调用 `System.exit(1)`，避免首条未实现异常中断剩余用例。
  - 若需复用 JUnit 5，可探测本地已有 `junit-platform-console-standalone.jar` 或宿主依赖 classpath；否则优先零依赖 `java -ea` 自包含测试运行器。

### 命名与命令模板

- **测试文件**：`LabTest.java`
- **`test_command`**：`cd {chapter_dir} && mkdir -p /tmp/promentor-ch02 && javac -d /tmp/promentor-ch02 *.java && java -ea -cp /tmp/promentor-ch02 LabTest`
- **骨架代码模板**：

```java
public class Router {
    public void addRoute(String method, String path, Runnable handler) {
        throw new UnsupportedOperationException("not implemented: addRoute");
    }
}
```

---

## C / C++

### 隔离机制与避坑

- **避免侵入宿主 CMake / Makefile**：章节 Lab 通过单条 `cc` / `c++` 命令直接编译，测试二进制输出到 `/tmp/`，避免在章节目录遗留二进制垃圾文件。
- **头文件与实现分离**：将公开签名放在 `<module>.h` / `<module>.hpp`（作为只读契约或同步列入 `starter_files`），学生实现文件为 `<module>.c` / `<module>.cpp`。
- **编译警告即错误检查**：编译命令带上 `-Wall -Wextra`，保证签名一致与基础内存安全。
- **逐用例异常/失败隔离**：
  - **C++**：自制测试运行器必须对每条用例用 `try { fn(); } catch (const std::exception& e) { ... }` 捕获异常，打印每项 `PASS` / `FAIL` 与汇总后再返回非零退出码，禁止未捕获异常直接 `std::terminate`。
  - **C**：骨架代码避免直接调用 `abort()`，改为返回明确错误码 / `NULL`；自制运行器使用返回状态检查替代直接终止进程的 `assert()`，确保全部用例均执行并输出每项 `PASS` / `FAIL` 与汇总后再返回非零码。

### 命名与命令模板

- **测试文件**：`lab_test.c`（C）或 `lab_test.cpp`（C++）
- **`test_command`**：
  - C：`cd {chapter_dir} && cc -std=c11 -Wall -Wextra router.c lab_test.c -o /tmp/promentor_lab_test && /tmp/promentor_lab_test`
  - C++：`cd {chapter_dir} && c++ -std=c++17 -Wall -Wextra router.cpp lab_test.cpp -o /tmp/promentor_lab_test && /tmp/promentor_lab_test`
- **骨架代码模板（C++）**：

```cpp
#include <stdexcept>
#include "router.hpp"

void Router::add_route(const std::string& method, const std::string& path, Handler handler) {
    throw std::logic_error("not implemented: add_route");
}
```
