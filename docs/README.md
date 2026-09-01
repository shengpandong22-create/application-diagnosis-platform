# Application Diagnosis Platform 文档导航

这是项目文档的统一入口。架构演进、实现规格、开发记录、阶段验收和架构决策均从这里进入。

> 项目根目录：[README](../README.md)

## 阶段演进

| 阶段 | 核心目标 | 架构图 | 实现与设计 | 验收 | 状态 |
|---|---|---|---|---|---|
| Phase 0A | 独立骨架与最小 Agent Loop | [框架图与说明](./01-architecture/phase0a-framework.md) · [SVG](./01-architecture/phase0a-framework.svg) · [Graphviz 源文件](./01-architecture/phase0a-framework.dot) | [Phase 0 实现规格](./02-specifications/Phase%200%20实现规格说明.md) | [验收记录](./04-validation/phase0a-acceptance.md) | 已完成 |
| Phase 0B | Evidence、知识检索与人工确认 | [扩展图与说明](./01-architecture/phase0b-extension.md) · [SVG](./01-architecture/phase0b-extension.svg) · [Graphviz 源文件](./01-architecture/phase0b-extension.dot) | [平台设计文档](./02-specifications/独立应用诊断闭环平台设计文档.md) | [验收记录](./04-validation/phase0b-acceptance.md) | 已完成 |
| Phase 0C | 评测、报告和极简界面 | [扩展架构与学习总结](./01-architecture/phase0c-extension.md) · [SVG](./01-architecture/phase0c-extension.svg) · [Graphviz](./01-architecture/phase0c-extension.dot) | [实现规格](./02-specifications/Phase%200C%20实现规格说明.md) | [验收记录](./04-validation/phase0c-acceptance.md) | 已完成 |
| Phase 1 | 日志与授权源码联合诊断 | [扩展架构与学习总结](./01-architecture/phase1-extension.md) · [端到端链路图](./01-architecture/phase1-log-code-flow.md) | [实现规格](./02-specifications/Phase%201%20实现规格说明.md) · [能力总结](./03-progress/2026-07-17-Phase1当前能力总结.md) | [验收记录](./04-validation/phase1-acceptance.md) | 本地最小闭环完成 |
| Phase 2 | 可观测、多策略、现场感知 | [扩展架构与学习总结](./01-architecture/phase2-extension.md) · [SVG](./01-architecture/phase2-extension.svg) · [Graphviz](./01-architecture/phase2-extension.dot) | [实现规格](./02-specifications/Phase%202%20实现规格说明.md) · [开发总结](./03-progress/2026-07-18-Phase2开发总结.md) | [验收记录](./04-validation/phase2-acceptance.md) | 已完成 |
| Phase 3A/3B/3C | 可解释诊断、轻量计划与服务驱动工具上下文 | [Phase 3C 架构图](./01-architecture/phase3c-service-context.md) · [SVG](./01-architecture/phase3c-service-context.svg) | [实现规格](./02-specifications/Phase%203%20实现规格说明.md) | [3A/3B/3C-1](./04-validation/phase3a-3b-acceptance.md) · [3C-2](./04-validation/phase3c-service-context-acceptance.md) | 已完成 |
| Phase 4 | 日志主动发现、故障指纹与企业接入 | [主动发现](./01-architecture/phase4-active-discovery.md) · [企业 Adapter](./01-architecture/phase4-enterprise-adapters.md) | [融合设计与实现规格](./02-specifications/日志主动发现能力融合设计与Phase%204实施规格.md) · [4E 总结](./03-progress/2026-08-08-Phase4E企业Adapter.md) | [4E 验收](./04-validation/phase4e-acceptance.md) | 4A～4E 已完成 |
| Phase 5 | 服务拓扑与跨服务因果诊断 | 待实施 | [实施计划与验收标准](./02-specifications/服务拓扑与跨服务因果诊断Phase%205实施计划与验收标准.md) | 待实施 | 已设计、暂缓实施 |

## 按内容查找

### 0. 项目总览与展示

- [项目介绍](./00-overview/项目介绍.md)
- [Phase 0～4 项目核心掌握手册（图片 + 文字 + 代码）](./00-overview/Phase%200-4%20项目核心掌握手册.md)
- [Phase 0～2 项目掌握与面试准备指南](./00-overview/Phase%200-2%20项目掌握与面试准备指南.md)
- [Phase 0～2 源码学习路线图](./00-overview/Phase%200-2%20源码学习路线图.md)
- [Phase 0 离线演示指南](./00-overview/演示指南.md)
- [Phase 1 实现规格](./02-specifications/Phase%201%20实现规格说明.md)
- [Phase 2 实现规格与验收标准](./02-specifications/Phase%202%20实现规格说明.md)
- [Phase 3 实现规格与验收标准](./02-specifications/Phase%203%20实现规格说明.md)
- [日志主动发现能力融合设计与 Phase 4 实施规格](./02-specifications/日志主动发现能力融合设计与Phase%204实施规格.md)
- [服务拓扑与跨服务因果诊断：Phase 5 实施计划与验收标准](./02-specifications/服务拓扑与跨服务因果诊断Phase%205实施计划与验收标准.md)
- [Phase 4A 质量基线与故障靶场增强总结](./03-progress/2026-08-08-Phase4A质量基线与故障靶场增强.md)
- [Phase 4A 验收记录](./04-validation/phase4a-acceptance.md)
- [Phase 4B 主动发现领域核心总结](./03-progress/2026-08-08-Phase4B主动发现领域核心.md)
- [Phase 4B 验收记录](./04-validation/phase4b-acceptance.md)
- [Phase 4C 本地主动发现闭环总结](./03-progress/2026-08-08-Phase4C本地主动发现闭环.md)
- [Phase 4C 验收记录](./04-validation/phase4c-acceptance.md)
- [Phase 4D 运营复盘与反馈回流总结](./03-progress/2026-08-08-Phase4D运营复盘与反馈回流.md)
- [Phase 4D 验收记录](./04-validation/phase4d-acceptance.md)
- [Phase 4E 企业 Adapter 总结](./03-progress/2026-08-08-Phase4E企业Adapter.md)
- [Phase 4E 契约验收记录](./04-validation/phase4e-acceptance.md)
- [Phase 3 当前能力总结](./03-progress/2026-07-30-Phase3当前能力总结.md)
- [本地诊断 Agent 到企业平台演进设计](./02-specifications/本地诊断Agent到企业平台演进设计.md)
- [Phase 1 验收记录](./04-validation/phase1-acceptance.md)
- [Phase 1 真实日志与源码联合诊断验收](./04-validation/phase1-real-log-acceptance.md)
- [Phase 1 真实模型端到端诊断验收](./04-validation/phase1-real-model-acceptance.md)
- [Phase 1 Java Lab 多故障评测](./04-validation/phase1-java-lab-evaluation.md)
- [Phase 1 当前能力总结](./03-progress/2026-07-17-Phase1当前能力总结.md)
- [简历与面试项目描述](./00-overview/简历项目描述.md)

### 1. 架构与演进图

- [架构图可视化风格规范](./01-architecture/visual-style-guide.md)
- [Phase 0A 框架图：独立骨架与最小 Agent Loop](./01-architecture/phase0a-framework.md)
- [Phase 0A SVG 成品](./01-architecture/phase0a-framework.svg)
- [Phase 0A Graphviz 源文件](./01-architecture/phase0a-framework.dot)
- [Phase 0A Agent Loop SVG](./01-architecture/phase0a-agent-loop.svg)
- [Phase 0A Agent Loop Graphviz 源文件](./01-architecture/phase0a-agent-loop.dot)
- [Phase 0A Port / Adapter SVG](./01-architecture/phase0a-ports-adapters.svg)
- [Phase 0A Port / Adapter Graphviz 源文件](./01-architecture/phase0a-ports-adapters.dot)
- [Phase 0B 扩展图：证据驱动的人工诊断闭环](./01-architecture/phase0b-extension.md)
- [Phase 0B SVG 成品](./01-architecture/phase0b-extension.svg)
- [Phase 0B Graphviz 源文件](./01-architecture/phase0b-extension.dot)
- [Phase 0C 扩展图：评测、报告与极简界面](./01-architecture/phase0c-extension.md)
- [Phase 0C SVG 成品](./01-architecture/phase0c-extension.svg)
- [Phase 0C Graphviz 源文件](./01-architecture/phase0c-extension.dot)
- [Phase 1 扩展架构：真实日志与受限源码联合诊断](./01-architecture/phase1-extension.md)
- [Phase 1 扩展架构 SVG 成品](./01-architecture/phase1-extension.svg)
- [Phase 1 扩展架构 Graphviz 源文件](./01-architecture/phase1-extension.dot)
- [Phase 1 端到端链路图](./01-architecture/phase1-log-code-flow.md)
- [Phase 1 端到端链路 SVG](./01-architecture/phase1-log-code-flow.svg)
- [Phase 1 端到端链路 Graphviz 源文件](./01-architecture/phase1-log-code-flow.dot)
- [Phase 2 扩展架构：可观测、多策略、现场感知](./01-architecture/phase2-extension.md)
- [Phase 2 SVG 成品](./01-architecture/phase2-extension.svg)
- [Phase 2 Graphviz 源文件](./01-architecture/phase2-extension.dot)
- [Phase 3C 架构图：服务目录驱动的受限工具上下文](./01-architecture/phase3c-service-context.md)
- [Phase 3C SVG 成品](./01-architecture/phase3c-service-context.svg)
- [Phase 3C Graphviz 源文件](./01-architecture/phase3c-service-context.dot)
- [Phase 0～4 项目演进地图](./01-architecture/phase0-4-evolution-map.md)
- [Phase 0～4 演进地图 SVG](./01-architecture/phase0-4-evolution-map.svg)
- [Phase 0～4 演进地图 Graphviz 源文件](./01-architecture/phase0-4-evolution-map.dot)
- [Phase 4 主动发现架构与说明](./01-architecture/phase4-active-discovery.md)
- [Phase 4 主动发现 SVG](./01-architecture/phase4-active-discovery.svg)
- [Phase 4 主动发现 Graphviz 源文件](./01-architecture/phase4-active-discovery.dot)
- [Phase 4E 企业 Adapter 架构与说明](./01-architecture/phase4-enterprise-adapters.md)
- [Phase 4E 企业 Adapter SVG](./01-architecture/phase4-enterprise-adapters.svg)
- [Phase 4E 企业 Adapter Graphviz 源文件](./01-architecture/phase4-enterprise-adapters.dot)
- [企业目标架构 SVG](./01-architecture/enterprise-target-architecture.svg)
- [企业目标架构 Graphviz 源文件](./01-architecture/enterprise-target-architecture.dot)

### 2. 设计与实现规格

- [独立应用诊断闭环平台设计文档](./02-specifications/独立应用诊断闭环平台设计文档.md)
- [Phase 0 实现规格说明](./02-specifications/Phase%200%20实现规格说明.md)
- [ITOps 参考实现复用矩阵](./02-specifications/ITOps参考实现复用矩阵.md)
- [本地诊断 Agent 到企业平台演进设计](./02-specifications/本地诊断Agent到企业平台演进设计.md)
- [日志主动发现能力融合设计与 Phase 4 实施规格](./02-specifications/日志主动发现能力融合设计与Phase%204实施规格.md)
- [服务拓扑与跨服务因果诊断：Phase 5 实施计划与验收标准](./02-specifications/服务拓扑与跨服务因果诊断Phase%205实施计划与验收标准.md)

### 3. 开发过程记录

- [2026-07-16：Phase 0A 完成与 Phase 0B 计划](./03-progress/2026-07-16-Phase0A开发总结与Phase0B计划.md)
- [2026-07-16：Phase 0B 完成情况与 Phase 0C 计划](./03-progress/2026-07-16-Phase0B开发总结与Phase0C计划.md)
- [2026-07-17：Phase 0C 评测、报告与极简界面](./03-progress/2026-07-17-Phase0C开发总结.md)
- [2026-07-17：Phase 1 日志与源码联合诊断能力总结](./03-progress/2026-07-17-Phase1当前能力总结.md)
- [2026-07-18：Phase 2 可观测、多策略、现场感知](./03-progress/2026-07-18-Phase2开发总结.md)
- [2026-07-30：Phase 3 可解释诊断、轻量计划与服务目录](./03-progress/2026-07-30-Phase3当前能力总结.md)
- [2026-08-08：Phase 4A 质量基线与故障靶场增强](./03-progress/2026-08-08-Phase4A质量基线与故障靶场增强.md)

后续开发总结统一放入 `03-progress`，文件名使用 `YYYY-MM-DD-阶段-主题.md`。

### 4. 阶段验收

- [Phase 0A 验收记录](./04-validation/phase0a-acceptance.md)
- [Phase 0B 验收记录](./04-validation/phase0b-acceptance.md)
- [Phase 0C 验收记录](./04-validation/phase0c-acceptance.md)
- [Phase 2 验收记录](./04-validation/phase2-acceptance.md)
- [Phase 3A/3B/3C-1 验收记录](./04-validation/phase3a-3b-acceptance.md)
- [Phase 3C-2 服务目录驱动工具上下文验收记录](./04-validation/phase3c-service-context-acceptance.md)
- [面试收尾增强：服务历史、知识候选与企业演进设计验收](./04-validation/interview-readiness-enhancements-acceptance.md)
- [Phase 4A 质量基线与故障靶场增强验收](./04-validation/phase4a-acceptance.md)
- [真实模型 v1 基线评测](./04-validation/2026-09-01-真实模型v1基线评测.md)
- [真实模型 v2 单变量复验](./04-validation/2026-09-01-真实模型v2单变量复验.md)
- [真实模型迭代评测终版](./04-validation/2026-09-01-真实模型迭代评测终版.md)

### 5. 架构决策 ADR

- [ADR-0001：使用独立 Python 项目](./05-decisions/0001-independent-python-project.md)
- [ADR-0002：供应商无关的 LLM Runtime](./05-decisions/0002-provider-neutral-llm-runtime.md)
- [ADR-0003：有界诊断工具与显式 Registry](./05-decisions/0003-bounded-diagnostic-tools.md)
- [ADR-0004：可持久化的有界 Tool Loop](./05-decisions/0004-durable-bounded-tool-loop.md)
- [ADR-0005：将应用时间作为可注入依赖](./05-decisions/0005-injectable-application-clock.md)

### 6. 学习教案

- [八课学习路线与完成状态](./06-learning/README.md)
- [第1课：业务定位与系统全景](./06-learning/第1课：业务定位与系统全景.md)
- [第2课：诊断用例与状态机](./06-learning/第2课：诊断用例与状态机.md)
- [第3课：Agent Loop与工具闸门](./06-learning/第3课：Agent%20Loop与工具闸门.md)
- [第4课：Evidence可信闭环](./06-learning/第4课：Evidence可信闭环.md)
- [第5课：Java应用联合诊断](./06-learning/第5课：Java应用联合诊断.md)
- [第6课：主动发现与Incident](./06-learning/第6课：主动发现与Incident.md)
- [第7课：企业Adapter与可靠性](./06-learning/第7课：企业Adapter与可靠性.md)
- [第8课：项目走读与面试实战](./06-learning/第8课：项目走读与面试实战.md)
## 目录规则

| 目录 | 内容 |
|---|---|
| `00-overview` | 项目介绍、演示指南和简历/面试表达 |
| `01-architecture` | 阶段框架图、演进图及其可维护源文件 |
| `02-specifications` | 总体设计、实现规格和参考实现复用矩阵 |
| `03-progress` | 每日总结、阶段总结和下一阶段计划 |
| `04-validation` | 自动验收范围、执行方式和验收结果 |
| `05-decisions` | 重要架构选择及其原因、取舍和影响 |
| `06-learning` | 按课时组织的业务、代码与面试学习教案 |

新增文档时，应同时在本页对应章节增加链接。阶段图统一保留源文件、SVG 成品和 Markdown 说明。
