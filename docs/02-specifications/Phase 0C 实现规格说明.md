# Phase 0C 实现规格说明：评测、报告与极简界面

> [返回文档导航](../README.md)

## 1. 目标

Phase 0C 在 Phase 0B 证据闭环上增加三项交付能力：可重复的离线评测、无需再次调用模型的诊断报告、可完成核心人工操作的极简界面。

## 2. 范围边界

- 默认评测不访问网络，不读取 API Key；
- 报告只聚合现有 Diagnosis、Evidence、AgentRun、ToolRun 和 Confirmation；
- 报告生成不得再次调用 LLM；
- UI 使用服务端静态 HTML、CSS 和原生 JavaScript，不建立独立前端工程；
- 不增加数据库表、向量数据库、Worker、队列、RBAC 或远程日志接入。

## 3. 评测契约

EvalCase 同时描述期望与一次可重复观察值。评测至少输出：结构化结论合法性、引用合法性、必要 Evidence 类型覆盖、工具成功率、终止原因匹配和根因关键词匹配。CLI 输出包含逐案例结果和聚合指标的 JSON。

## 4. 报告契约

DiagnosisReport 必须聚合诊断状态、结构化结论、Evidence、运行摘要和人工动作；构造时验证所有引用属于当前 Diagnosis。Markdown 明确区分事实、候选根因、建议、缺失信息与人工决定。

## 5. UI 契约

`GET /ui` 提供创建诊断、输入诊断 ID、查看详情/Evidence、启动 Run、补充信息、人工动作和查看报告的入口。浏览器只调用版本化 API，不复制领域规则。

## 6. 验收

- Ruff 与全量 pytest 通过；
- 固定评测可重复运行并生成机器可读 JSON；
- 报告引用归属校验通过，生成过程零模型调用；
- `/ui` 可加载且包含核心操作；
- 空库迁移、Alembic 漂移和 Phase 0C OpenAPI 路径检查通过。
