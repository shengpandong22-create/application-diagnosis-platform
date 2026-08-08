# Phase 4C 验收记录

## 验收矩阵

| 验收项 | 结果 |
|---|---|
| 新 Incident 自动创建并运行一个 Diagnosis | 通过 |
| 同 source_event 重放不重复调用模型 | 通过 |
| 未注册服务在模型调用前拒绝 | 通过 |
| ServiceProfile 限定工具资源范围 | 通过，复用 Phase 3C 能力 |
| FileSource 路径穿越被拒绝 | 通过 |
| 日志在持久化和入模前脱敏 | 通过 |
| 自动诊断仍经过 Runner 与 CitationPolicy | 通过 |
| 模型不能直接产生 confirmed | 通过 |
| 模型失败保留 Incident/Diagnosis/Evidence/Run/ToolRun/Audit | 通过 |
| Report 与 Trace 展示 Incident 来源 | 通过 |
| 默认演示不调用外部模型 | 通过 |
| Ruff 与全量 pytest | 通过 |

## 一键验收

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-phase4c.ps1
```

脚本依次执行 Ruff、全量测试、Phase 4C 专项测试和 Fake LLM 演示。最终数字以本次脚本输出为准。

本次执行结果：

```text
Ruff: passed
Full pytest: 226 passed
Phase 4C focused tests: 15 passed
Fake LLM calls: first discovery 1, replay 0
Redaction verified: true
Phase 4C acceptance: PASSED
```
