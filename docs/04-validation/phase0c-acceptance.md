# Phase 0C 验收记录

> [返回文档导航](../README.md)

## 已验收能力

1. 固定评测案例可重复执行并输出机器可读 JSON；
2. 评测覆盖结构化输出、引用合法性、必要 Evidence、工具成功率、终止原因和根因关键词；
3. DiagnosisReport 聚合 Diagnosis、Conclusion、Evidence、AgentRun 和 Confirmation；
4. 报告构造时拒绝跨 Diagnosis Evidence ID；
5. JSON 与 Markdown 报告生成不调用 LLM；
6. `/ui` 提供创建、查看、运行、补充、人工动作和报告入口；
7. 默认验收离线执行，不读取模型 API Key。

## 一键验收

```powershell
.\scripts\verify-phase0c.ps1 -SkipSync
```

验收包含 Ruff、全量 pytest、固定评测、空库迁移、Alembic 漂移、OpenAPI 契约和临时文件清理。
