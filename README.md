# ProMentor

> 把任意开源项目转成 MIT 风格的动手工程课程，在实践中掌握系统设计。

ProMentor 是一个 **AI Coding Agent Skill**。安装后，你的 AI 编程助手会化身为工程导师：扫描目标项目架构、规划阶梯式章节、生成讲义与源码导读、布置带行为测试的 Lab，并在你手写实现后判题、提供分层提示与对比源码的 AI Code Review。

## 工作流

```text
扫描架构 & 确认大纲      (/promentor init)
        ↓
讲义讲解 & 源码导读      (/promentor learn <ch>)
        ↓
手写实现 & 行为测试      (/promentor test · /promentor hint)
        ↓
正式提交 & 对比 Review   (/promentor submit → /promentor review)
```

## 安装

### 方式一：Skills CLI（推荐）

```bash
npx skills add 0xLyn77/ProMentor
```

### 方式二：手动安装

克隆仓库并将 `skills/promentor/` 复制到你的 Agent 技能目录：

```bash
git clone https://github.com/0xLyn77/ProMentor.git

# 全局安装（按你使用的 Agent 选择其一）
cp -r ProMentor/skills/promentor ~/.claude/skills/promentor    # Claude Code
cp -r ProMentor/skills/promentor ~/.codex/skills/promentor     # Codex
cp -r ProMentor/skills/promentor ~/.agents/skills/promentor    # 通用 Agent 目录
```

如需仅在单个项目中启用，可复制到该项目根目录的 `.claude/skills/promentor` 或 `.agents/skills/promentor`。

## 快速上手

在 AI 编程助手中打开任意想学习的项目目录：

1. **生成课程**：运行 `/promentor init`。AI 会扫描项目架构并输出章节大纲，你可以增删或调整顺序；确认后逐章生成讲义、源码导读、Lab 与行为测试。
2. **开始学习**：运行 `/promentor learn ch01`。AI 结合讲义和关键源码行讲解核心设计与权衡，随后给出本章 Lab 的接口签名与要求。
3. **实现与调试**：在章节目录手写实现，用 `/promentor test` 运行行为测试；遇到瓶颈时用 `/promentor hint` 获取基于当前代码与报错动态生成的分层提示。
4. **提交与复盘**：全部测试通过后运行 `/promentor submit` 归档并记录成绩，再运行 `/promentor review` 将你的实现与原始源码逐项对比。

## 命令速查

| 命令                       | 说明                                              |
| -------------------------- | ------------------------------------------------- |
| `/promentor init`          | 扫描项目架构，确认大纲并生成课程                  |
| `/promentor init --resume` | 从中断处继续生成剩余章节                          |
| `/promentor`               | 查看课程目录与学习进度面板                        |
| `/promentor learn <ch>`    | 进入指定章节学习（支持 `ch01`、`1` 或 slug 简写） |
| `/promentor test`          | 运行当前章节的行为测试并诊断失败原因              |
| `/promentor hint`          | 读取当前代码与报错，动态生成分层提示              |
| `/promentor submit`        | 运行全量测试，通过后归档提交并锁定成绩            |
| `/promentor review`        | 对比你的实现与原始源码，剖析设计权衡              |
| `/promentor progress`      | 查看各章节完成度与总体进度                        |

## 生成的课程目录

运行 `/promentor init` 后，课程内容统一存放在目标项目根目录的 `.promentor/` 中（并自动追加到 `.gitignore`）：

```text
.promentor/
├── course.json                # 课程大纲与章节元信息
├── progress.json              # 学习状态、得分与提示层级
├── chapters/
│   └── ch01-<slug>/
│       ├── lecture.md         # 概念讲解与设计决策讲义
│       ├── source.md          # 带行号标注的源码导读
│       ├── lab.json           # Lab 接口签名与测试命令
│       └── lab_test.<ext>     # 原生测试框架编写的行为测试
└── submissions/
    └── ch01-<slug>/
        └── attempt_1.<ext>    # 历次提交代码归档
```

## 特点

- **系统化路线**：按模块依赖拆解真实项目，从基础组件逐步组装完整系统。
- **动手实现**：围绕真实架构决策手写核心逻辑，通过黑盒行为测试验证。
- **源码对照 Review**：将你的实现与原项目源码逐维对比，讲清不同方案的 tradeoff。
- **语言无关**：适配任意语言的开源项目，使用目标语言原生测试框架判题。
