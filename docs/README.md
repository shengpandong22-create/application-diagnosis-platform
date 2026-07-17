# Application Diagnosis Platform 文档导航

这是项目文档的统一入口。架构演进、实现规格、开发记录、阶段验收和架构决策均从这里进入。

> 项目根目录：[README](../README.md)

## 阶段演进

| 阶段 | 核心目标 | 架构图 | 实现与设计 | 验收 | 状态 |
|---|---|---|---|---|---|
| Phase 0A | 独立骨架与最小 Agent Loop | [框架图与说明](./01-architecture/phase0a-framework.md) · [SVG](./01-architecture/phase0a-framework.svg) · [Graphviz 源文件](./01-architecture/phase0a-framework.dot) | [Phase 0 实现规格](./02-specifications/Phase%200%20实现规格说明.md) | [验收记录](./04-validation/phase0a-acceptance.md) | 已完成 |
| Phase 0B | Evidence、知识检索与人工确认 | [扩展图与说明](./01-architecture/phase0b-extension.md) · [SVG](./01-architecture/phase0b-extension.svg) · [Graphviz 源文件](./01-architecture/phase0b-extension.dot) | [平台设计文档](./02-specifications/独立应用诊断闭环平台设计文档.md) | [验收记录](./04-validation/phase0b-acceptance.md) | 已完成 |
| Phase 0C | 评测、报告和极简界面 | [扩展图](./01-architecture/phase0c-extension.md) · [SVG](./01-architecture/phase0c-extension.svg) · [Graphviz](./01-architecture/phase0c-extension.dot) | [实现规格](./02-specifications/Phase%200C%20实现规格说明.md) | [验收记录](./04-validation/phase0c-acceptance.md) | 已完成 |
| Phase 1 | 日志与授权源码联合诊断 | 待补充正式演进图 | [实现规格](./02-specifications/Phase%201%20实现规格说明.md) | [验收记录](./04-validation/phase1-acceptance.md) | 本地最小闭环完成 |

## 按内容查找

### 0. 项目总览与展示

- [项目介绍](./00-overview/项目介绍.md)
- [Phase 0 离线演示指南](./00-overview/演示指南.md)
- [Phase 1 实现规格](./02-specifications/Phase%201%20实现规格说明.md)
- [Phase 1 验收记录](./04-validation/phase1-acceptance.md)
- [Phase 1 真实日志与源码联合诊断验收](./04-validation/phase1-real-log-acceptance.md)
- [Phase 1 真实模型端到端诊断验收](./04-validation/phase1-real-model-acceptance.md)
- [简历与面试项目描述](./00-overview/简历项目描述.md)

### 1. 架构与演进图

- [Phase 0A 框架图：独立骨架与最小 Agent Loop](./01-architecture/phase0a-framework.md)
- [Phase 0A SVG 成品](./01-architecture/phase0a-framework.svg)
- [Phase 0A Graphviz 源文件](./01-architecture/phase0a-framework.dot)
- [Phase 0B 扩展图：证据驱动的人工诊断闭环](./01-architecture/phase0b-extension.md)
- [Phase 0B SVG 成品](./01-architecture/phase0b-extension.svg)
- [Phase 0B Graphviz 源文件](./01-architecture/phase0b-extension.dot)
- [Phase 0C 扩展图：评测、报告与极简界面](./01-architecture/phase0c-extension.md)
- [Phase 0C SVG 成品](./01-architecture/phase0c-extension.svg)
- [Phase 0C Graphviz 源文件](./01-architecture/phase0c-extension.dot)

### 2. 设计与实现规格

- [独立应用诊断闭环平台设计文档](./02-specifications/独立应用诊断闭环平台设计文档.md)
- [Phase 0 实现规格说明](./02-specifications/Phase%200%20实现规格说明.md)
- [ITOps 参考实现复用矩阵](./02-specifications/ITOps参考实现复用矩阵.md)

### 3. 开发过程记录

- [2026-07-16：Phase 0A 完成与 Phase 0B 计划](./03-progress/2026-07-16-Phase0A开发总结与Phase0B计划.md)
- [2026-07-16：Phase 0B 完成情况与 Phase 0C 计划](./03-progress/2026-07-16-Phase0B开发总结与Phase0C计划.md)
- [2026-07-17：Phase 0C 评测、报告与极简界面](./03-progress/2026-07-17-Phase0C开发总结.md)

后续开发总结统一放入 `03-progress`，文件名使用 `YYYY-MM-DD-阶段-主题.md`。

### 4. 阶段验收

- [Phase 0A 验收记录](./04-validation/phase0a-acceptance.md)
- [Phase 0B 验收记录](./04-validation/phase0b-acceptance.md)
- [Phase 0C 验收记录](./04-validation/phase0c-acceptance.md)

### 5. 架构决策 ADR

- [ADR-0001：使用独立 Python 项目](./05-decisions/0001-independent-python-project.md)
- [ADR-0002：供应商无关的 LLM Runtime](./05-decisions/0002-provider-neutral-llm-runtime.md)
- [ADR-0003：有界诊断工具与显式 Registry](./05-decisions/0003-bounded-diagnostic-tools.md)
- [ADR-0004：可持久化的有界 Tool Loop](./05-decisions/0004-durable-bounded-tool-loop.md)

## 目录规则

| 目录 | 内容 |
|---|---|
| `00-overview` | 项目介绍、演示指南和简历/面试表达 |
| `01-architecture` | 阶段框架图、演进图及其可维护源文件 |
| `02-specifications` | 总体设计、实现规格和参考实现复用矩阵 |
| `03-progress` | 每日总结、阶段总结和下一阶段计划 |
| `04-validation` | 自动验收范围、执行方式和验收结果 |
| `05-decisions` | 重要架构选择及其原因、取舍和影响 |

新增文档时，应同时在本页对应章节增加链接。阶段图统一保留源文件、SVG 成品和 Markdown 说明。
