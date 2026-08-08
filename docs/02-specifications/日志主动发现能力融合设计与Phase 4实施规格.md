# 日志主动发现能力融合设计与 Phase 4 实施规格

> 文档状态：Phase 4A、4B、4C 已完成，Phase 4D 待实施
> 适用项目：Application Diagnosis Platform
> 目标版本：Phase 4
> 编写日期：2026-08-08

## 1. 文档目的

当前项目已经完成从人工创建诊断到人工确认和知识候选沉淀的可信闭环：

```text
ServiceProfile
→ DiagnosisCase
→ Strategy / DiagnosisPlan
→ 有界 ToolLoopRunner
→ 日志、源码、配置、健康和知识工具
→ Evidence 持久化与 CitationPolicy
→ Trace / Report
→ 人工确认、驳回或继续调查
→ Knowledge candidate
```

现有能力可以可信地回答“如何调查一次已知问题”，但尚未系统解决：

1. 如何持续发现值得调查的新 ERROR；
2. 如何把大量重复日志聚合为少量故障事件；
3. 如何识别首次出现的故障模式；
4. 如何把日志事件安全地转换成现有 DiagnosisCase；
5. 如何用固定评测集证明模型、Prompt 和工具策略变更没有降低质量。

`docs/design` 下的外部方案补充了日志事件接入、故障指纹、滑动窗口去重、新指纹发现、快慢路径、日报和评测运营等思路，但它以绿地项目为前提，重复设计了 Agent Runtime、Web API、报告和存储，并弱化了当前项目已经实现的 Evidence、Citation、Confirmation、Audit 和 Knowledge 生命周期。

本规格的目标是完成一次“能力融合”，而不是重写：

```text
外部方案负责提供可借鉴的主动发现思路
                    ↓
Phase 4 将其改造成现有六边形架构中的增量能力
                    ↓
现有可信诊断核心保持唯一且稳定
```

## 2. 核心结论

### 2.1 产品定位变化

Phase 3 之前的系统定位：

> 面向单次问题、由用户触发的证据驱动应用诊断 Agent。

Phase 4 完成后的系统定位：

> 能够从受控日志源主动发现、聚合并触发调查，同时保留证据引用、人工确认和知识审核的应用诊断 Agent。

### 2.2 唯一主调用链

Phase 4 不引入第二套诊断核心。融合后的唯一主链为：

```text
LogEventSource
→ LogEvent 解析、Schema 校验、截断和脱敏
→ ErrorFingerprint
→ Incident 聚合与 Novelty 判定
→ DiagnosisTriggerPolicy
→ 创建或关联 DiagnosisCase
→ 复用现有 StrategyRouter / DiagnosisPlan / ToolLoopRunner
→ EvidenceStore / CitationPolicy
→ Conclusion / Trace / Report
→ Confirmation / Knowledge candidate
→ Evaluation / Daily Summary
```

### 2.3 关键架构决策

1. **不创建新的 `log-bug-detect` 工程**，Phase 4 在当前仓库增量实现；
2. **不引入第二套 LangGraph ReAct Runtime**，慢路径继续复用 `ToolLoopRunner`；
3. **日志发现层不直接生成 confirmed 结论**，只能触发 Diagnosis；
4. **模型 confidence 不能单独决定结论可信度或快路径**，必须同时满足 Evidence 与 Citation 规则；
5. **先实现 File/Replay Adapter，再实现 RabbitMQ/Redis Adapter**，避免中间件掩盖领域问题；
6. **源码必须逐步绑定 deployed commit**，不能长期使用会移动的分支解释历史日志；
7. **语义召回延后**，只有确认知识达到一定规模且评测证明关键词检索不足时才实施。

## 3. 范围与非目标

### 3.1 Phase 4 目标

- 定义标准化 LogEvent 和错误指纹；
- 将重复 ERROR 聚合为 Incident；
- 识别首次出现的新指纹；
- 通过策略决定忽略、仅聚合、等待人工或触发 Diagnosis；
- 将 Incident 原始事实脱敏后转为 Evidence；
- 复用现有诊断引擎完成自动触发诊断；
- 建立版本化评测数据集、质量指标和回归机制；
- 扩充 Java Lab 故障类型；
- 提供服务维度的主动发现摘要。

### 3.2 Phase 4 非目标

- 不替代 ELK、Loki、OpenSearch 等日志平台；
- 不采集全量 INFO/WARN 日志；
- 不做生产自动修复或自动提交 PR；
- 不让模型执行任意 Shell、Git、SQL 或日志查询语句；
- 不在本阶段实现多 Agent 编排；
- 不为了展示强制引入 RabbitMQ、Redis、MySQL、FAISS 和 bge-m3 全家桶；
- 不把模型自报置信度当作生产告警阈值；
- 不把未确认报告直接写成 confirmed 知识；
- 不把原始敏感日志、完整 Prompt 或模型原始输出无条件写入 Trace。

## 4. 外部方案取舍矩阵

| 外部方案内容 | 决策 | 融合方式 | 原因 |
|---|---|---|---|
| `LogSource` 可插拔设计 | 吸收 | 定义 `LogEventSource` Port，提供 File/Replay/RabbitMQ Adapter | 与现有 Ports & Adapters 一致 |
| 结构化日志 Schema | 吸收并加强 | 增加大小限制、可信标记、脱敏状态和接收时间 | 原方案安全元数据不足 |
| 异常类型与前 N 帧指纹 | 吸收并加强 | 建模为 `ErrorFingerprint` 值对象并版本化算法 | 支持迁移和算法演进 |
| Redis 滑动窗口去重 | 条件吸收 | 先实现内存/SQLite语义，再实现原子Redis Adapter | 原伪代码存在并发竞态和清理问题 |
| 新指纹检测 | 吸收 | Incident 标记 `is_novel`，进入摘要和触发策略 | 补齐主动发现核心价值 |
| RabbitMQ + DLQ | 延后吸收 | Phase 4D 作为外部 Adapter | 本地领域闭环不应依赖中间件 |
| Java AmqpAppender | 仅作为实验方案 | Java Lab 可验证；企业接入需另做 ADR | 会增加业务服务与MQ耦合并可能丢日志 |
| service→repo 映射 | 吸收并替换 | 复用 `ServiceProfile`，后续扩展 Environment/Deployment/commit | 分支不是不可变代码版本 |
| 快慢双路径 | 吸收概念 | 快路径使用确定性门控；慢路径复用现有 Runner | 避免第二套 Runtime |
| 模型 confidence ≥ 0.8 直出 | 废弃原规则 | confidence 只作为信号之一，Evidence/Citation 为硬门槛 | LLM 自报置信度未校准 |
| LangGraph ReAct | 本阶段废弃 | 保留现有 `ToolLoopRunner` | 已有预算、持久化、Evidence和失败语义 |
| 5个只读工具 | 部分已实现 | code/config/knowledge 已有；新增 related logs | 继续使用统一 Tool Contract |
| 报告保存工具名 | 废弃原结构 | 报告必须保存正式 Evidence ID 和 ToolRun ID | 调过工具不等于结论有证据 |
| Trace记录Prompt/Token/路径 | 吸收并加强 | 保存安全摘要、版本、Token和耗时；敏感正文外置或脱敏 | 防止Trace成为泄漏源 |
| `correct/wrong`反馈 | 不直接采用 | 复用 Confirmation，并新增结构化错误标签 | 二元反馈无法表达部分正确和证据错误 |
| 日报/周报 | 吸收 | 先生成Markdown/JSON摘要，通知Adapter延后 | 展示主动发现价值，避免通知耦合 |
| 11类Java故障靶场 | 吸收 | 分批扩展现有 diagnosis-java-lab | 强化工具选择和跨服务评测 |
| Prompt版本化 | 吸收并扩大 | 同时绑定模型、Strategy、Tool Schema和Citation版本 | 结果不只由Prompt决定 |
| 误判回流评测集 | 吸收并加强 | reject/错误标签生成 `EvaluationCandidate`，人工标注后才进入正式集 | 防止错误标签自动污染评测 |
| bge-m3 + FAISS | 延后 | 达到数据量和评测门槛后单独立项 | 当前confirmed知识量不足 |
| 单独FastAPI/MySQL报告库 | 废弃 | 复用现有API、SQLAlchemy Repository和Report | 避免双数据源与双API |
| 新建独立项目骨架 | 废弃 | 仅保留原文档作为外部设计输入 | 当前项目已有成熟骨架 |

## 5. 与当前代码的映射

### 5.1 保持不变并直接复用

| 当前能力 | 代码位置 | Phase 4 用法 |
|---|---|---|
| Diagnosis 状态机 | `domain/diagnosis/case.py` | Incident触发后创建或关联Diagnosis |
| Agent执行记录 | `domain/execution/models.py` | 保存自动触发运行的AgentRun/ToolRun |
| Tool Loop | `agent/runtime/tool_loop.py` | 继续作为唯一慢路径调查Runtime |
| Strategy Router | `agent/strategies/router.py` | 根据Incident和服务上下文选择策略 |
| DiagnosisPlan | `domain/diagnosis_plan/models.py` | 解释自动诊断准备调查的步骤 |
| Tool Registry | `tools/registry.py` | 执行related logs等新增只读工具 |
| Evidence | `domain/evidence/models.py` | 保存日志、源码、配置、知识和关联日志证据 |
| Evidence Store | `ports/evidence_store.py` | 将发现层和工具结果统一落为正式Evidence |
| Redaction | `ports/redaction.py`、`adapters/redaction/local_rules.py` | 日志持久化和入模前脱敏 |
| Citation Policy | `agent/policies/evidence_citations.py` | 自动诊断仍必须引用当前Diagnosis的真实Evidence |
| Confirmation | `domain/confirmation/models.py` | 人工确认、驳回或继续调查 |
| Knowledge | `domain/knowledge/models.py` | confirmed Diagnosis生成candidate知识 |
| ServiceProfile | `domain/service_profile/models.py` | 确定日志、代码、配置和健康资源范围 |
| Trace/Report | `application/traces.py`、`application/reports.py` | 展示触发来源、Incident和诊断证据链 |
| Evaluation | `evaluation/models.py`、`evaluation/runner.py` | 扩展为版本化质量评测 |

### 5.2 需要扩展

| 当前模块 | 扩展内容 |
|---|---|
| `ServiceProfile` | 增加可选日志源引用；企业阶段拆分Environment和Deployment |
| `DiagnosisCase` | 增加可选 `incident_id` 或通过关联表保存来源，不破坏人工创建接口 |
| `EvidenceType` | 确认支持结构化日志事件与跨服务关联日志；必要时新增类型 |
| `ToolResourceContext` | 增加受限日志源、时间范围和trace_id查询范围 |
| `Trace` | 增加trigger source、fingerprint version、Prompt/模型/策略/工具版本和Token统计 |
| `Report` | 增加Incident摘要、occurrence、first_seen、last_seen、novelty和评测标签 |
| `Evaluation` | 增加数据集版本、预期Evidence、禁止结论、根因标签和成本指标 |
| `Audit` | 增加Incident创建、聚合、自动触发、评测候选和摘要生成事件 |

### 5.3 新增模块建议

```text
src/app_diagnosis/
├─ domain/
│  └─ incident/
│     ├─ models.py
│     ├─ fingerprint.py
│     └─ errors.py
├─ ports/
│  ├─ log_event_source.py
│  ├─ incident_repository.py
│  └─ deduplication_store.py
├─ adapters/
│  ├─ log_events/
│  │  ├─ file_source.py
│  │  ├─ replay_source.py
│  │  └─ rabbitmq_source.py       # Phase 4D
│  └─ deduplication/
│     ├─ memory.py
│     └─ redis.py                 # Phase 4D
├─ application/
│  ├─ incidents.py
│  ├─ discovery_pipeline.py
│  └─ discovery_summaries.py
└─ tools/
   └─ related_logs.py
```

实际实施前允许按现有命名习惯调整，但不得把这些模块塞入 `ToolLoopRunner` 或API路由中形成新的上帝对象。

## 6. 目标领域模型

### 6.1 LogEvent

```text
LogEvent
├─ id
├─ occurred_at
├─ received_at
├─ service_id / service_name
├─ environment
├─ deployment_ref（可选）
├─ instance_id（可选）
├─ trace_id / span_id（可选）
├─ level
├─ logger
├─ message
├─ stack_trace
├─ host
├─ source_ref
├─ trust_level = untrusted
├─ redaction_status
└─ content_hash
```

约束：

- Phase 4只接受ERROR，其他级别默认拒绝或忽略；
- message和stack trace均有独立大小上限；
- 所有外部日志视为不可信数据；
- 原始敏感内容不得先入库再脱敏；
- `occurred_at`和`received_at`必须分离；
- 无法映射服务的事件进入隔离状态，不允许扩大代码搜索范围。

### 6.2 ErrorFingerprint

第一版规范：

```text
normalized_frames =
  取前N个有效业务栈帧
  → 去除行号
  → 统一空白
  → 保留类名和方法名

fingerprint_material =
  service_id
  + environment
  + exception_type
  + normalized_frames

fingerprint = sha256(fingerprint_material)
```

字段：

- `value`；
- `algorithm_version`，第一版为 `stack-v1`；
- `exception_type`；
- `normalized_frames`；
- `service_id`；
- `environment`。

不使用MD5作为完整性或安全Hash；行号不参与指纹，以避免同一根因因代码小幅移动而完全失配。后续若引入部署版本，应评估指纹跨版本聚合规则。

### 6.3 Incident

```text
Incident
├─ id
├─ service_id
├─ environment
├─ fingerprint
├─ fingerprint_version
├─ status: observed | diagnosis_pending | diagnosing | waiting_review | closed
├─ occurrence_count
├─ first_seen_at
├─ last_seen_at
├─ is_novel
├─ latest_log_event_id
├─ diagnosis_id（可选）
├─ trigger_reason（可选）
├─ created_at
└─ updated_at
```

不把Incident等同于Diagnosis：

- Incident表示系统观察到的故障现象及其重复发生情况；
- Diagnosis表示对该现象的一次可审计调查；
- 一个Incident可以因为补充证据、部署变化或人工要求产生多次AgentRun；
- 是否允许一个Incident关联多个Diagnosis，在Phase 4A领域测试中固定规则，第一版建议一个活跃Incident最多关联一个未结束Diagnosis。

### 6.4 EvaluationCase / EvaluationCandidate

`EvaluationCandidate`来源于：

- 人工reject；
- 人工标记结论部分错误；
- CitationPolicy拦截；
- 新故障靶场；
- 真实日志脱敏样本。

Candidate必须经过人工标注，才能进入版本化EvaluationCase。正式Case至少保存：

- 输入事件和服务上下文；
- 可用工具；
- 预期分类；
- 可接受根因描述或根因标签；
- 预期Evidence类型/来源；
- 禁止结论；
- 是否应该信息不足；
- 最大预算；
- 数据集版本和来源；
- 敏感数据检查状态。

## 7. 发现与触发流程

### 7.1 标准处理顺序

```text
接收LogEvent
→ Schema校验
→ 服务与环境解析
→ 内容截断
→ 脱敏
→ 计算content hash
→ 解析exception type和业务栈帧
→ 计算ErrorFingerprint
→ 原子聚合Incident
→ 判断novelty和触发条件
→ 必要时创建Diagnosis及初始Evidence
→ 启动现有诊断流程
```

顺序不能随意调整。尤其禁止：

- 原文先入数据库再脱敏；
- 未完成服务映射就允许源码搜索；
- 先调用模型再去重；
- 模型直接决定是否拥有工具权限；
- 自动诊断绕过CitationPolicy或Confirmation。

### 7.2 DiagnosisTriggerPolicy

第一版采用确定性规则，不调用额外模型：

```text
触发诊断，当且仅当：
1. 事件属于已注册ServiceProfile；
2. 指纹是新指纹，或已有Incident明确要求重新调查；
3. 当前没有该Incident的活跃Diagnosis；
4. 服务/环境启用了自动发现；
5. 未超过服务级速率、并发和每日预算；
6. 日志内容通过脱敏和大小校验。
```

重复事件默认只更新occurrence和last_seen，不重复调用模型。可以通过人工操作或部署版本变化触发重新调查。

### 7.3 快慢路径

Phase 4定义的“快路径”不是绕过可信闭环：

```text
快路径候选：
  命中同服务、同环境、同指纹的confirmed知识
  + 关键事实Evidence齐全
  + 知识未过期
  + CitationPolicy通过
  → 生成possible/probable候选结论，仍等待人工确认

慢路径：
  无可靠历史知识、证据不足或出现冲突
  → 进入现有ToolLoopRunner调查
```

第一批实现可以只记录 `path_candidate`，不立即改变Runtime行为。只有评测证明快路径安全且节省成本后，才允许短路部分工具调用。

## 8. Evidence 与安全规则

### 8.1 初始Evidence

Incident触发Diagnosis时，至少创建：

- `log_excerpt`：脱敏后的异常日志；
- `user_statement`或系统触发说明：说明由哪个Incident、何种规则自动触发；
- 可选服务/部署事实Evidence。

Evidence元数据应包含：

- `incident_id`；
- `log_event_id/source_ref`；
- `fingerprint`和算法版本；
- `occurred_at`；
- `service/environment/deployment`；
- `trust_level=untrusted`；
- `redaction_status`。

### 8.2 跨服务相关日志

新增 `related_logs__query` 工具时：

- 模型只能提交当前Diagnosis已有的trace_id或受限时间窗；
- Adapter根据ServiceProfile和依赖范围生成查询；
- 不接受模型提供任意日志DSL；
- 返回数量和总字符数必须受限；
- 每条命中转为独立或分组Evidence；
- UI和报告必须区分真实trace_id与启发式时间关联；
- 关联失败只能降低结论，不得伪造Evidence。

### 8.3 Trace安全

Trace默认保存：

- Prompt模板版本和Hash；
- 模型标识；
- Strategy/Tool Schema/Citation版本；
- Evidence ID列表；
- 工具名称、状态、耗时和安全参数摘要；
- Token与延迟；
- 结构化结论和校验结果。

Trace不得默认保存未脱敏完整日志、密钥、任意源码全文和外部模型原始响应。调试正文需要独立开关、访问控制和保留期限。

## 9. 评测与质量门禁

### 9.1 版本绑定

每次评测必须记录：

```text
dataset_version
model_id
prompt_version
strategy_version
tool_schema_version
citation_policy_version
fingerprint_algorithm_version
code_revision
```

### 9.2 指标

最低指标集：

- 分类准确率与混淆矩阵；
- 根因Top-1/Top-3命中率；
- Evidence引用准确率与召回率；
- unsupported claim比例；
- 信息不足识别率；
- 错误高置信率；
- 工具选择正确率；
- 平均轮次和工具数；
- P50/P95延迟；
- 单次诊断Token和费用；
- 去重压缩比；
- 新指纹数量；
- 人工确认、驳回和继续调查比例；
- 敏感信息泄漏率；
- 跨服务/跨目录越权率。

### 9.3 Prompt迭代SOP

```text
发现失败Case
→ 判断失败属于数据、工具、Prompt、模型、Citation还是领域规则
→ 明确单一修改假设
→ 创建新版本
→ 跑固定离线评测
→ 对比质量、成本和延迟
→ 关键指标无回退后再启用
```

禁止为了提高靶场分数，把具体答案或文件名硬编码进Prompt。

### 9.4 真实模型调用策略

- 自动化测试默认使用Fake LLM；
- 每个代表性场景允许1～4次真实模型调用；
- 失败后必须先分析Trace、Evidence和Prompt，再决定是否重试；
- 不在实现没有变化时高频连续重试；
- 真实模型评测结果必须绑定模型和Prompt版本；
- 真实模型调用不替代领域、Repository和安全测试。

## 10. Phase 4 分阶段实施

### Phase 4A：质量基线与故障靶场增强

目标：先建立评价尺子，再改变运行链。

实施内容：

1. 扩展EvaluationCase模型和版本信息；
2. 增加分类混淆矩阵、根因、Evidence、成本和延迟指标；
3. 建立Prompt/模型/Strategy/Tool Schema版本记录；
4. 将Java Lab从3类逐步扩展到至少8类故障；
5. 为每个故障定义ground truth和理想上下文深度；
6. 建立一键离线回归脚本；
7. 建立少量真实模型基线，不连续盲重试。

暂不实施：MQ、Redis、FAISS、日报通知。

验收标准：

- 固定评测集可重复运行；
- 同一版本重复运行输出可比较结果；
- 至少覆盖code/config/dependency/external四类；
- 至少包含一个需要跨文件、一个需要配置、一个需要相关日志的案例；
- 报告区分工程测试通过与诊断质量达标；
- 敏感信息泄漏率为零；
- `ruff`和全量`pytest`通过。

### Phase 4B：LogEvent、Fingerprint 与 Incident Domain

目标：完成主动发现的确定性领域核心。

实施内容：

1. 定义LogEvent、ErrorFingerprint、Incident及状态；
2. 实现异常类型和业务栈帧规范化；
3. 实现版本化指纹算法；
4. 建立IncidentRepository Port和SQLAlchemy Adapter；
5. 建立DeduplicationStore Port及内存/SQLite实现；
6. 实现原子聚合语义、novelty和窗口规则；
7. 增加Alembic迁移；
8. 完成领域、Repository、迁移和并发语义测试。

验收标准：

- 行号变化不改变同版本指纹；
- 不同服务或环境默认产生不同指纹；
- 相同窗口重复事件只增加occurrence；
- 超过窗口后的行为符合明确规则；
- 并发重复输入不产生重复活跃Incident；
- 指纹算法版本可追踪；
- Repository不泄漏SQLAlchemy类型到Domain；
- 全量测试通过。

### Phase 4C：File/Replay主动发现闭环

目标：不依赖中间件完成“日志出现→自动诊断”的本地闭环。

实施内容：

1. 定义LogEventSource Port；
2. 实现FileSource和ReplaySource；
3. 实现Schema校验、截断、脱敏和服务映射；
4. 实现DiagnosisTriggerPolicy；
5. 自动创建或关联DiagnosisCase；
6. 创建初始log Evidence和触发说明Evidence；
7. 复用现有Runner执行诊断；
8. Report/Trace展示Incident和触发来源；
9. 增加一键主动发现演示脚本。

验收标准：

- 新指纹自动创建一个Diagnosis；
- 重复日志不会重复调用模型；
- 未注册服务不会获得源码/配置访问范围；
- 日志在持久化和入模前已脱敏；
- 自动触发诊断仍经过CitationPolicy；
- 模型不能直接产生confirmed状态；
- 失败保留Incident、AgentRun、ToolRun、Evidence和Audit；
- 演示默认Fake LLM，允许少量真实模型验收；
- 全量测试通过。

### Phase 4D：相关日志、摘要与人工回流

目标：让主动发现结果可运营、可复盘。

实施内容：

1. 新增受限 `related_logs__query` 工具；
2. 支持trace_id相关日志取证；
3. 增加服务每日摘要JSON/Markdown；
4. 展示新指纹、高频故障、待确认和驳回案例；
5. 将人工reject或结构化错误标签生成EvaluationCandidate；
6. Candidate经人工标注后进入正式评测集；
7. 增加质量趋势和Prompt版本对比。

验收标准：

- 相关日志只能在授权服务、时间和数量范围内查询；
- 每条相关日志可追溯到来源并形成Evidence；
- 日报统计与Incident/Diagnosis事实一致；
- 错误反馈不会直接污染正式评测集或confirmed知识；
- 日报不包含密钥和完整敏感日志；
- 全量测试通过。

### Phase 4E：RabbitMQ、Redis 与远程代码Adapter（可选）

进入条件：Phase 4A～4D本地闭环稳定，并且确实需要展示企业接入形态。

实施内容：

1. RabbitMQSource与DLQ；
2. Redis原子滑窗去重Adapter；
3. 消费幂等、重试、取消和恢复；
4. GitLabSource；
5. deployed commit代码快照；
6. 可选钉钉/企微通知Adapter。

验收标准：

- 重复投递不产生重复诊断；
- Consumer异常退出后消息可恢复；
- poison message进入DLQ且可安全重放；
- Redis操作原子且具备清理策略；
- GitLab查询受项目和commit白名单限制；
- 远程依赖失败时保留日志事实并安全降级；
- RabbitMQ不可用不阻塞Java业务请求；
- 未配置外部Adapter时本地模式继续可运行。

### Phase 4F：语义召回（条件阶段）

进入条件必须同时满足：

1. 至少50～100条人工确认的高质量知识；
2. 关键词检索在固定评测集上出现明确召回瓶颈；
3. 语义召回能在离线评测中显著改善指标；
4. 只索引confirmed知识；
5. 索引可以从数据库事实重建。

未满足条件时不得为了技术栈丰富度提前开发。

## 11. 数据库与迁移原则

- 延续SQLAlchemy Repository和Alembic迁移；
- SQLite继续作为本地实现，生产演进目标仍为PostgreSQL；
- 不因为外部方案使用MySQL而增加第二套主数据库；
- Incident与Diagnosis的关联必须有外键或明确的一致性约束；
- fingerprint、service、environment和活跃状态需要组合索引；
- 重复事件聚合必须有幂等键或唯一约束兜底；
- 大日志正文未来通过ObjectStorage Port外置，关系库保存元数据、Hash和安全摘要；
- 所有迁移必须覆盖upgrade和downgrade测试。

## 12. API草案

Phase 4B/4C建议增加：

```text
GET  /api/v1/incidents
GET  /api/v1/incidents/{id}
POST /api/v1/incidents/{id}/diagnoses
GET  /api/v1/services/{id}/incidents
POST /api/v1/log-events/replay        # 仅本地/开发模式
```

Phase 4D建议增加：

```text
GET  /api/v1/services/{id}/discovery-summary
GET  /api/v1/evaluations/runs
GET  /api/v1/evaluations/versions
POST /api/v1/evaluation-candidates/{id}/label
```

边界：

- 生产环境不开放任意日志正文上传或Replay接口；
- API只负责命令和查询，不在HTTP长事务中消费无限日志流；
- 自动消费进入企业化阶段后应使用Job/Worker，不长期占用请求；
- 所有分页、时间范围和最大条数必须受限。

## 13. 测试策略

### 13.1 测试金字塔

```text
领域测试
  Fingerprint / Incident / TriggerPolicy / 状态与窗口

Port与Adapter契约测试
  File / Replay / RabbitMQ / Redis / GitLab

Repository与迁移测试
  唯一约束、幂等、upgrade/downgrade

Runtime集成测试
  Incident → Diagnosis → Evidence → Citation → Report

安全测试
  脱敏、Prompt Injection、路径越权、跨服务Evidence引用

评测回归
  Fake确定性回归 + 少量真实模型质量评测

端到端演示
  Java Lab日志 → 主动发现 → 自动诊断 → 人工确认
```

### 13.2 必测失败场景

- 非法Schema；
- 超大日志；
- 敏感信息；
- 无堆栈日志；
- 相同行号变化；
- 并发重复事件；
- 未注册服务；
- 日志与源码版本不一致；
- 工具超时和预算耗尽；
- 相关日志查询越权；
- 模型伪造Evidence ID；
- 自动输出confirmed；
- Consumer重复投递；
- Redis/RabbitMQ/GitLab不可用；
- Prompt版本升级后质量回退。

## 14. 可观测性与审计

至少记录以下事件：

- LogEvent接收、拒绝和脱敏；
- Incident创建和重复聚合；
- 新指纹发现；
- 自动诊断触发、抑制及原因；
- Diagnosis与Incident关联；
- 相关日志查询；
- 评测运行和版本切换；
- EvaluationCandidate创建和标注；
- 摘要生成和通知尝试；
- 外部Adapter失败和降级。

指标至少包括：

- 每服务事件量；
- 指纹数和去重压缩比；
- 新指纹数；
- 自动触发数和抑制数；
- 诊断成功率、等待输入率、驳回率；
- 模型/工具耗时与Token；
- Adapter错误和DLQ数量；
- 评测质量趋势。

Audit只保存操作者/系统身份、动作、目标ID、时间和安全摘要，不保存完整敏感日志。

## 15. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| 新能力形成第二套Agent | 架构分裂 | 强制复用ToolLoopRunner、Evidence和Report |
| 指纹碰撞或过度聚合 | 不同根因被合并 | 算法版本、样本回放、人工拆分和Deployment上下文 |
| 并发重复Incident | 重复模型费用 | 原子聚合、唯一约束、幂等键 |
| 模型自信但错误 | 错误快路径 | Evidence/Citation硬门禁和置信度校准 |
| 自动发现造成模型风暴 | 成本和限流 | 新指纹触发、服务级预算、有界并发和Job队列 |
| 日志含敏感内容 | 数据泄漏 | 入库前脱敏、Trace摘要、模型数据策略 |
| 日志与代码不一致 | 错误根因 | deployed commit和代码快照 |
| 错误报告进入知识/召回 | 长期污染 | Confirmation和candidate审核 |
| RabbitMQ Appender影响业务 | 业务风险 | 异步不阻塞、本地文件兜底、优先评估采集Agent |
| 外部方案范围过大 | 个人项目烂尾 | 4A～4D为主线，4E/4F条件进入 |

## 16. 原始文档处置规则

当前外部方案包括：

- `docs/design/基于日志的 Agent Bug 检测系统设计_v2.md`；
- `docs/design/日志研判Agent-V0实施计划.md`；
- `docs/design/日志研判Agent-V1实施计划.md`；
- `docs/design/日志研判Agent-V1.5实施计划.md`。

在本规格评审确认前，不直接删除或提交为正式基线。确认后按以下规则二选一：

### 方案A：作为外部方案归档（推荐）

适用条件：希望保留方案比较、架构取舍和AI辅助设计过程。

建议移动到：

```text
docs/99-archive/external-log-discovery-proposal/
```

并新增README声明：

- 文档由外部模型生成；
- 未按原计划实施；
- 仅作为设计输入和对比材料；
- 正式实施以本Phase 4规格为准；
- 其中的目录、代码片段和验收状态不代表当前项目事实。

### 方案B：只保留融合后的正式版本

适用条件：仓库只希望保留有效工程基线，不保留设计过程材料。

执行前提：

- 本规格通过人工评审；
- 吸收点全部进入Phase 4任务；
- 有价值的风险、指标和故障案例已迁移；
- Git历史或外部备份能够追溯原方案。

### 推荐决策

推荐选择方案A。该项目兼具学习和面试复盘目标，保留“外部提案→代码事实比对→融合决策”的过程，能够展示开发者没有盲从AI方案，而是进行了架构审核和范围收敛。

归档应在Phase 4A开始前单独提交，避免与业务代码混在同一commit。

## 17. Phase 4 总体验收定义

Phase 4不能以“RabbitMQ收到日志”或“模型返回答案”作为完成标准。至少满足：

1. 新日志可以通过File/Replay路径被主动发现；
2. 重复故障能够确定性聚合，并记录次数和时间；
3. 新指纹能够触发且只触发一个活跃Diagnosis；
4. 自动触发仍然遵守服务资源范围、Evidence和Citation规则；
5. 敏感内容在持久化和入模前完成脱敏；
6. 模型不能直接产生confirmed知识或confirmed诊断；
7. 人工反馈能够形成待标注评测候选；
8. 固定评测集可以比较模型、Prompt、策略和工具版本；
9. Java Lab至少覆盖四类故障和多种上下文深度；
10. 服务摘要能展示新指纹、高频故障和待确认诊断；
11. 外部MQ、Redis、GitLab未配置时，本地闭环仍可运行；
12. `uv run ruff check .`和全量`uv run pytest`通过；
13. 每个子阶段形成实现规格、验收记录和开发总结；
14. 文档、代码和演示不得把条件阶段包装成已完成能力。

## 18. 建议的第一项开发任务

Phase 4不要从RabbitMQ或LangGraph开始。第一项任务应为：

> 扩展版本化EvaluationCase与质量指标，并将Java Lab补充到至少8个有ground truth的故障案例，建立Phase 4实施前的质量基线。

原因：

- 没有评测基线，就无法证明主动发现和快慢路径是否改善系统；
- Java Lab可以验证真实日志、源码、配置和相关日志工具；
- 本任务不改变现有生产主链，风险最低；
- 它能先产出简历中最缺少的量化质量证据；
- 完成后再开发Fingerprint与Incident，后续每次改造都有可回归的评价尺子。

第一项任务暂不实现：

- RabbitMQ；
- Redis；
- LangGraph；
- bge-m3/FAISS；
- 钉钉/企微；
- 自动修复；
- 多Agent；
- 企业GitLab真实接入。

## 19. 最终建议

Phase 4应沿着以下顺序演进：

```text
先建立质量尺子
→ 再建立Incident与指纹领域
→ 再用File/Replay完成主动发现闭环
→ 再增加相关日志、摘要和人工回流
→ 最后按真实需要接MQ、Redis、GitLab和语义召回
```

这一顺序既吸收了外部日志研判方案的主动发现价值，又保护了当前项目最难得的可信诊断核心，并符合个人电脑、业余开发和面试展示的实际约束。
