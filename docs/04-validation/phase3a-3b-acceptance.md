# Phase 3A / 3B 验收记录

## 验收目标

本次验收覆盖：

- Phase 3A：源码接手型注释、主链路学习文档、可视化风格规范；
- Phase 3B：规则版 DiagnosisPlan、Plan API、Report / Trace 集成。

## 功能验收清单

| 项目 | 状态 |
| --- | --- |
| 关键源码已增加接手型中文注释 | 已完成 |
| 架构图可视化风格规范已纳入 docs 导航 | 已完成 |
| ToolLoopRunner 创建 AgentRun 后生成 DiagnosisPlan | 已完成 |
| DiagnosisPlan 关联 Diagnosis 和 AgentRun | 已完成 |
| `GET /api/v1/diagnoses/{id}/plan` 可查询最新 Plan | 已完成 |
| 诊断存在但尚未运行时返回 `diagnosis_plan_not_found` | 已完成 |
| Report JSON 包含 `plans` | 已完成 |
| Markdown 报告包含“诊断计划”章节 | 已完成 |
| Trace 的 AgentRun 包含关联 Plan | 已完成 |
| Plan 不改变 Agent Loop 执行逻辑 | 已通过全量回归确认 |

## 自动化验收

已执行：

```powershell
uv run ruff check .
uv run pytest
```

结果：

```text
uv run ruff check .
All checks passed!

uv run pytest
190 passed, 1 warning
```

补充离线验收：

```powershell
uv run python scripts/demo-phase1-log-code.py --keyword NullPointerException
```

结果：

```text
termination_reason=completed
code_evidence_count=1
log_evidence_count=1
external_model_called=false
```

## 真实模型验收

本阶段允许少量真实模型端到端验收，但不作为自动化测试的一部分。

建议场景：

- Java Lab NPE 真实日志 + 源码联合诊断；
- 验证报告中同时出现 DiagnosisPlan、Evidence、Trace 和最终结论。

限制：

- 单场景最多 3 次真实模型调用；
- 每次失败需要记录原因；
- 不做无改动盲重试。

当前状态：

```text
已尝试执行 1 次 Java Lab NPE 真实模型验收；
执行前被安全审查拦截，因为该脚本会将本地 Java 日志和源码诊断上下文发送给外部模型。
后续如需执行，需要用户明确确认允许将该固定案例的日志/源码上下文发送给已配置的外部模型服务。
```
