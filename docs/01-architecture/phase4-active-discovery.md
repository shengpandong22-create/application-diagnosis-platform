# Phase 4 主动发现与诊断闭环

![Phase 4 主动发现与诊断闭环](./phase4-active-discovery.svg)

## 这张图回答什么

它回答“没有用户手工创建 Diagnosis 时，异常日志怎样安全地进入原有诊断闭环”。Phase 4 没有另建一套 Agent，而是在前面增加确定性的事件标准化、指纹、聚合和触发策略，然后复用 Phase 0～3 的 Diagnosis、Evidence、ToolLoopRunner、Report 与 Confirmation。

## 主链路

1. `FileLogEventSource`、`ReplayLogEventSource` 或 `RabbitMQLogEventConsumer` 产生 `DiscoveredLogEvent`；
2. `IncidentApplicationService.ingest()` 建立 `LogEvent`，计算版本化 `ErrorFingerprint`，再按服务、环境、指纹和固定时间窗聚合为 `Incident`；
3. `DiagnosisTriggerPolicy` 拦截重复 source event 和已经关联 Diagnosis 的 Incident；
4. 只有 `incident_without_diagnosis` 才创建 Diagnosis，并追加包含 `incident_id` 的初始 Evidence 与 Audit；
5. `EvidenceAwareDiagnosisApplicationService.run()` 复用既有受控 Agent Runtime；
6. Agent 失败不会删除已经写入的 Incident、Diagnosis、Evidence 或执行记录，后续可以 Replay 和复盘。

## 不应误读

- “主动发现”不是自动发现 Kubernetes 服务，也不是全网日志采集；
- `ErrorFingerprint` 是确定性规则，不由 LLM 生成；
- 相同 Incident 不会因为重复日志无限创建 AgentRun；
- 图中的反馈回流代表人工确认、摘要和评测沉淀，不表示模型自动修改 Incident 历史。

## 源码锚点

- `src/app_diagnosis/domain/incident/models.py`
- `src/app_diagnosis/domain/incident/trigger.py`
- `src/app_diagnosis/application/incidents.py`
- `src/app_diagnosis/application/discovery.py`
- `src/app_diagnosis/adapters/log_events/`
