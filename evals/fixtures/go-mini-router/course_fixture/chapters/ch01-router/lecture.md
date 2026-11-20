# Ch 1: HTTP 路由匹配与优先级设计

本章学习 HTTP 请求如何从 `(method, path)` 映射到对应的业务 `Handler`，并解决动态路径参数（如 `/users/:id/posts/:pid`）与静态路径共存时的匹配优先级问题。

## 1. 在系统中的位置

```mermaid
flowchart LR
    Req["HTTP Request (method, path)"] --> Router["Router (ch01-router)"]
    Router -->|"Handler + params"| MW["Middleware Chain (ch02-middleware)"]
    MW --> Resp["HTTP Response"]
```

## 2. 核心问题与设计权衡

当只有静态路由时，`map[string]Handler` 提供 $O(1)$ 查找，几乎没有设计难度。但一旦引入动态路径参数 `:id`，单层哈希表就无法表达“按段匹配”和“提取参数”。

常见两类方案的权衡：

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| 线性规则表遍历 | 实现直白、改动成本低 | 路由数增长后每次请求 $O(R \cdot S)$，静态优先级需要额外排序或二阶段扫描 |
| 按段前缀树（Trie） | 共享公共前缀、天然按段回溯、查询与路径深度 $O(S)$ 成正比 | 节点结构与回溯清理参数逻辑更精细 |

## 3. 本章 Lab 目标

打开本章目录中的骨架文件 `router.go`，实现 `NewRouter`、`AddRoute` 与 `FindRoute`：
- 按 HTTP Method 隔离路由表；
- 支持静态路径、单参数路径与多级嵌套参数；
- 保证静态段优先于参数段，且不存在匹配时返回 `(nil, nil)`。
