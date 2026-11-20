# ProMentor Eval & Smoke Test Suite

> 仓库开发期回归测试与确定性校验工具。本目录位于仓库根目录，**不会打入 `skills/promentor/` 安装包**。

## 快速运行

一键执行全量规范校验与 Go / Python / TypeScript 三语言端到端生命周期测试（纯 Python 标准库，零外部依赖）：

```bash
python3 evals/run_smoke.py
```

## 工具说明

| 文件 | 用途 |
| --- | --- |
| `validate_skill.py` | 校验 `SKILL.md` 篇幅（渐进式披露 ≤ 220 行）、frontmatter、内部参考文档与 `scripts/promentor.py` 可用性、`agents/openai.yaml`、`README.md` 仓库地址、`.gitignore` 与无旧架构残留 |
| `validate_course.py` | 复用 `skills/promentor/scripts/promentor.py` 执行确定性检查：JSON Schema、统一评分、锚定 `source_commit` 的行号真实性、`source.md` 两阶段分区、Mermaid、SHA-256 防篡改、TS/Python 运行时卫生、目录制归档，以及 Red/Green 门禁与执行数核对 |
| `test_validators.py` | 校验器反向用例单测（Go panic 中断、TS 命名污染宿主测试、Python `cd` + 相对 venv、`.git/info/exclude` 保护 `.gitignore`、锚定 `source_commit` 抗行号漂移、越界行号、评分冲突等） |
| `run_smoke.py` | 直接调用 `skills/promentor/scripts/promentor.py` 对 3 个基准项目执行完整闭环：`exclude`（`.gitignore` 不变脏）→ `Red State`（全量测试数）→ `篡改拦截` → `Attempt 1/2 archive` → `Commit Drift 锚定校验` |
| `prompt_cases.json` | 防代写护栏、防剧透、Level 1–3 分层提示、测试防篡改、五维 Review 与二次重构增量 Review 的行为抽测用例集（可用于人工抽测或 LLM-as-judge 回归） |

## 校验任意真实项目课程

在真实项目上用 Agent 跑完 `/promentor init` 后，直接用确定性脚本核验生成产物：

```bash
# 验证初始 Red State、Schema、行号与校验和
python3 evals/validate_course.py /path/to/target-project --mode red --strict-commit

# 验证完成实现后的 Green State 与目录制归档
python3 evals/validate_course.py /path/to/target-project --mode green
```

## 基准项目（Fixtures）

- `fixtures/go-mini-router` — Go 分段前缀树 HTTP 路由器 + 中间件链（验证 Go 隐藏目录隔离、外部测试包与 `--focus` 课程）
- `fixtures/py-mini-kv` — Python 可注入时钟 KV 存储 + TTL + WAL（验证多文件 Lab 目录制归档与 `Path(__file__).resolve().parent` 路径安全导入）
- `fixtures/ts-mini-eventbus` — TypeScript 异步通配符事件总线 + 洋葱中间件（验证 Node 原生 TS `node --test` 与隐藏目录隔离）
