# Phase 0B 扩展图：证据驱动的人工诊断闭环

> [返回文档导航](../README.md)

> 阶段目标：在 Phase 0A 最小 Agent Loop 上，把“模型给出答案”升级为“系统基于可追踪证据提出结论，并允许用户补充、确认、驳回或继续调查”。

![Phase 0B 扩展图](./phase0b-extension.svg)

## 这张图表达什么

Phase 0A 的蓝色、紫色和青绿色模块保持原有职责，表示直接复用；Phase 0B 新增模块统一使用绿色。橙色虚线表示人工参与形成的反馈链路。

### 复用的 Phase 0A 骨架

- FastAPI 诊断 API 和请求治理；
- `DiagnosisApplicationService` 的事务及运行编排；
- `DiagnosisStrategy`、`ToolLoopRunner` 和 Tool Registry；
- LLM、Tool、Diagnosis 和 Execution Ports；
- DeepSeek / Fake LLM 与 SQLite + SQLAlchemy Adapters；
- `knowledge__search` 的 Tool 名称、输入输出契约和运行方式。

### Phase 0B 新增能力

- Redaction Port 与 LocalRuleRedactor，在持久化和进入模型前完成脱敏；
- Evidence Domain、Evidence Repository 和 Evidence Store；
- EvidenceDraft 落库，并将真实 Evidence ID 回传模型；
- EvidenceCitationPolicy 校验证据归属、可信度和结论引用规则；
- KnowledgeEntry Domain、Knowledge Repository 和 SQLite Knowledge Search；
- Supplement、Confirmation 和 Knowledge Application Use Cases；
- Confirmation 追加式记录，不覆盖原始模型结论；
- Audit Event 记录安全摘要，不保存完整敏感内容。

## 三条新增闭环

### 1. 证据闭环

```text
用户描述 / 日志
  → 入库前脱敏
  → Evidence 持久化
  → Agent 调查与工具 EvidenceDraft
  → 真实 Evidence ID 回传模型
  → 结构化结论引用
  → Citation Policy 校验
```

### 2. 人工反馈闭环

```text
有依据的初步结论
  → confirm：人工确认
  → reject：人工驳回
  → continue_investigation：继续调查
       → 用户补充信息
       → 新 Evidence
       → 显式启动新 AgentRun
```

### 3. 知识实现演进

```text
Phase 0A：knowledge__search → JSON Knowledge Adapter
Phase 0B：knowledge__search → Knowledge Search Port → SQLite Knowledge Adapter
```

替换 Adapter 时，没有修改 ToolLoopRunner、DiagnosisStrategy 和 API Domain DTO。这验证了 Phase 0A 稳定契约的扩展价值。

这里需要限定范围：上面的“不修改 ToolLoopRunner”只针对 JSON Knowledge Adapter 替换为 SQLite Knowledge Adapter。Phase 0B 为了增加 Evidence 落库、ID 回传和引用校验，确实对 ToolLoopRunner 做了有控制的扩展。

## 深度学习：Phase 0B 如何从 Phase 0A 生长出来

### 1. 两个阶段解决的问题不同

Phase 0A 主要回答：

> 怎样让一个诊断 Agent 在明确预算和工具边界内完成一次可持久化运行？

Phase 0B 继续回答：

> 模型的结论依据是什么，依据是否属于当前诊断，用户如何补充或推翻结论，整个过程怎样留下安全审计？

因此 Phase 0B 没有重新实现 Agent，而是在 Phase 0A 的四个关键控制点上增加闭环：

| Phase 0A 已有能力 | Phase 0A 尚未解决的问题 | Phase 0B 扩展 | 得到的系统保证 |
|---|---|---|---|
| Diagnosis 输入 | 用户描述和日志可能包含密钥或 Prompt Injection | Redaction + 初始 Evidence | 敏感内容在持久化和进入模型前处理，输入被标记为不可信 |
| ToolLoopRunner + Tool Result | 工具结果只存在于运行上下文，不能稳定引用 | EvidenceDraft → Evidence Store | 工具事实拥有正式、可追踪的 Evidence ID |
| DiagnosisConclusion Schema | JSON 合法不代表结论有依据 | EvidenceCitationPolicy | 引用必须存在、属于当前 Diagnosis，并满足结论状态规则 |
| waiting_for_input / waiting_for_confirmation | 状态存在，但用户没有完整反馈动作 | Supplement + Confirmation | 用户可以补充、确认、驳回或要求继续调查 |
| AgentRun / ToolRun | 能回答“系统运行了什么”，不能回答“谁做了什么人工动作” | AuditEvent + Confirmation | 执行事实、人工判断和安全审计被分别保存 |
| JSON Knowledge Adapter | 知识是静态文件，没有候选、确认和退休生命周期 | KnowledgeEntry + SQLite Repository | 知识可以受控创建、确认、检索和退休 |

这个映射是理解 Phase 0B 的主线：绿色模块不是附加功能清单，而是在 Phase 0A 已有链路上补足可信度和反馈能力。

### 2. Phase 0A 哪些部分被复用，哪些部分被修改

#### 直接复用

- FastAPI 应用工厂、Request ID、统一异常和结构化日志；
- DiagnosisCase 及 `waiting_for_input`、`waiting_for_confirmation` 等状态；
- DiagnosisApplicationService 的运行编排和活动 Run 冲突保护；
- DiagnosisStrategy 的系统提示与工具白名单；
- Tool Registry 的工具、权限和参数强制校验；
- LLM Client Port、DeepSeek Adapter 和 Fake LLM；
- AgentRun / ToolRun 及其执行预算；
- `knowledge__search` 的名称、输入输出 Schema 和 Tool 调用方式。

#### 有控制地扩展

- 创建 Diagnosis 时，同时脱敏并创建初始 Evidence；
- ToolLoopRunner 将 EvidenceDraft 落库，并把正式 Evidence ID 回传模型；
- ToolLoopRunner 在接受结论前调用 EvidenceCitationPolicy；
- Application 增加补充信息、人工动作和 Knowledge 管理用例；
- API 增加 Evidence、Supplement、Confirmation 和 Knowledge 路径；
- SQLite 增加 Evidence、Knowledge、Confirmation 和 Audit 表。

#### 替换实现但保持上层契约

```text
Phase 0A
knowledge__search → JSON Knowledge Adapter

Phase 0B
knowledge__search → Knowledge Search Port → SQLite Knowledge Search
```

真正值得学习的不是“Phase 0B 完全没有修改旧代码”，而是：修改集中在需要承担新职责的边界，没有迫使 LLM Port、Strategy、Registry 或 Tool Contract 一起重写。

## Evidence 生命周期

### 1. Evidence 从哪里产生

Phase 0B 有三类 Evidence：

| EvidenceType | 典型来源 | 当前 reliability | 用途 |
|---|---|---|---|
| `user_statement` | 创建诊断时的症状描述、用户补充 | medium | 记录用户陈述的事实或现象 |
| `log_excerpt` | 用户提交日志及其分片 | high | 提供更直接的运行现象和错误信息 |
| `knowledge_entry` | `knowledge__search` 工具结果 | 由 Evidence Store 按工具草稿构造 | 提供排查经验和候选解释 |

这里的 reliability 是系统对来源类型的当前评级，不等于内容已经被证明真实。例如用户提交的日志被评为 high，但仍在 metadata 中标记 `untrusted_input=true`。这是两个不同维度：

- reliability：这种来源通常对诊断有多大参考价值；
- trust boundary：内容是否来自系统控制边界之外，能否被当成指令执行。

### 2. 创建 Diagnosis 时的生命周期

```text
原始 symptom / submitted_log
  → LocalRuleRedactor
  → 得到安全文本、脱敏次数和命中类别
  → 日志按 UTF-8 字节边界分片
  → 创建 user_statement / log_excerpt Evidence
  → 计算 SHA-256 content_hash
  → 同一 Diagnosis 内按 hash 去重
  → Diagnosis + Evidence + evidence.created AuditEvent 同事务保存
```

这里有三个重要边界：

1. 原始敏感文本不能先入库再脱敏，否则数据库、WAL、备份或异常记录可能保留原文；
2. 日志大小按 UTF-8 字节计算，不能直接按字符数截断，否则中文和多字节字符可能越界；
3. Diagnosis 与初始 Evidence 同事务保存，避免出现“诊断已创建但证据丢失”的半完成状态。

### 3. Tool EvidenceDraft 如何变成正式 Evidence

Tool 不应该自己生成可以长期引用的 Evidence ID。它只能返回 EvidenceDraft：

```text
knowledge__search 执行
  → 返回结构化 Tool Result + EvidenceDraft
  → ToolLoopRunner 调用 Evidence Store
  → 脱敏、校验、去重、持久化
  → 数据库生成或确认正式 Evidence
  → ToolLoopRunner 取得真实 Evidence ID
  → 写入 tool message
  → 下一轮模型只能引用这些正式 ID
```

EvidenceDraft 和 Evidence 的区别是生命周期：

| 对象 | 是否持久化 | 是否有正式 ID | 是否可被结论引用 |
|---|---|---|---|
| EvidenceDraft | 否 | 否 | 否 |
| Evidence | 是 | 是 | 是 |

### 4. hash 能保证什么，不能保证什么

`content_hash` 当前使用 SHA-256，主要用于：

- 同一 Diagnosis 内内容去重；
- 读取实体时检查 content 与 hash 是否一致；
- 防止同一工具结果反复创建完全相同的 Evidence。

它不能证明：

- 内容来自可信系统；
- 日志没有在进入平台前被人为修改；
- 某个用户真的拥有该信息；
- Evidence 在外部采集链路中具有法律意义上的完整保全。

因此不能把内容 hash 描述成来源真实性或数字签名。Phase 0B 实现的是应用内部完整性和去重，不是完整的取证系统。

### 5. Supplement 如何继续 Evidence 生命周期

补充信息只允许在 `waiting_for_input` 状态提交：

```text
waiting_for_input
  → 用户提交 supplement
  → 入库前脱敏
  → 创建或复用同 hash Evidence
  → Diagnosis 重新进入 investigating
  → 记录 diagnosis.supplemented
  → 用户显式调用 /runs
  → 创建新的 AgentRun
```

补充信息不会自动调用模型。这是费用和副作用边界：保存新事实与启动外部模型运行是两个不同用例。

## 引用可信度

### 1. 结构化输出合法，不代表结论可信

Phase 0A 的 Pydantic Schema 可以保证：

- JSON 字段存在；
- 类型正确；
- status 使用允许的枚举；
- Evidence ID 字段具有 UUID 格式。

但 Schema 无法保证：

- UUID 真的存在；
- Evidence 属于当前 Diagnosis；
- 一条知识建议足以支持 probable；
- 模型没有把“证据不足”与伪造引用同时输出。

因此 Phase 0B 增加 EvidenceCitationPolicy，在 Schema 校验之后执行确定性业务规则。

### 2. 当前引用规则

| 结论情况 | 当前规则 |
|---|---|
| 任意引用 ID | 必须存在于当前 Diagnosis 的 Evidence 集合中 |
| fact 且不是 `insufficient_evidence` | 至少引用一个 Evidence ID |
| `probable` | 至少包含 user_statement 或 log_excerpt 直接证据 |
| 只引用 knowledge_entry | 不能达到 `probable`，最多作为 possible 候选解释 |
| 任意 `possible` finding | 整个结论必须包含至少一条验证建议 |
| `insufficient_evidence` | 不能携带 Evidence ID |
| `confirmed` | Phase 0 中模型禁止产生，保留给人工动作 |

需要准确理解一个当前实现细节：Policy 对 facts 强制要求 Evidence；对 root causes 允许在非 probable 情况下暂时没有 Evidence，只要其他规则满足。因此“所有候选根因必须有证据”并不是当前实现事实。

### 3. 一次纠错的意义

引用违规后，系统不是立即接受或静默删除引用，而是把违规原因反馈给模型，允许一次纠错：

```text
模型输出结论
  → Schema 校验
  → Citation Policy 校验
  → 发现未知 ID / probable 无直接证据等违规
  → 把确定性错误反馈模型
  → 允许一次修正
  → 仍违规：以 invalid_evidence_citations 收敛
```

一次纠错是兼容模型非确定性的策略，不是可信边界。最终可信边界仍然是本地 Policy；系统不会因为模型“坚持原结论”就放宽规则。

### 4. 当前可信度模型的边界

Phase 0B 已经做到“有引用规则”，但还不是完整事实推理系统：

- reliability 字段目前没有参与所有置信度计算；
- Policy 主要按 EvidenceType 判断直接证据；
- 没有自动判断日志片段是否真的语义支持某个 finding；
- 没有多来源交叉验证；
- 没有证据冲突检测；
- 没有自动计算概率或统计置信区间。

因此 `probable` 表示满足当前系统规则的候选根因，不表示数学概率，也不表示已经人工确认。

## 人工反馈闭环

### 1. 为什么 Confirmation 不能覆盖模型结论

模型结论和人工判断是两类不同事实：

```text
模型结论：某次 AgentRun 在当时 Evidence 下给出的判断
人工判断：某位操作者在某个时间对该判断采取的动作
```

如果直接把模型结论原记录改成 confirmed，就无法回答：

- 模型原来输出了什么；
- 谁进行了确认；
- 何时确认；
- 是否曾经驳回或要求继续调查。

因此 Confirmation 使用追加记录，Diagnosis 状态可以变化，但模型原始结论不会被覆盖。

### 2. 三种人工动作

| 动作 | Diagnosis 状态效果 | 含义 |
|---|---|---|
| `confirm` | `waiting_for_confirmation → confirmed` | 人工接受当前结论 |
| `reject` | `waiting_for_confirmation → rejected` | 人工明确否定当前结论 |
| `continue_investigation` | `waiting_for_confirmation → investigating` | 当前证据或结论不足，继续调查 |

人工动作只允许从 `waiting_for_confirmation` 进入，不能在任意状态下修改 Diagnosis。状态转换仍由 DiagnosisCase 约束，API 不直接赋值状态字段。

### 3. continue_investigation 与 supplement 不是同一动作

- `continue_investigation` 表示人工认为当前结论不足，需要继续调查；
- `supplement` 表示系统正在等待输入，用户提供了新的事实或日志。

两者都可能让 Diagnosis 回到 investigating，但前置状态、业务语义和审计动作不同。不能只因为最终状态相同就合并成一个通用“修改状态”接口。

### 4. 人工确认的当前边界

Phase 0B 的 actor 当前是本地 API 用户标识，还没有完整身份认证、角色授权或多级审批。因此“人工确认”表示系统区分了模型判断与外部操作者动作，不代表已经具备企业审批合规能力。

## 审计：Evidence、Execution、Confirmation 和 Audit 的区别

### 1. 四类记录回答不同问题

| 记录 | 回答的问题 |
|---|---|
| Evidence | 结论依据是什么？ |
| AgentRun / ToolRun | 系统运行了什么、调用了什么工具、为何结束？ |
| Confirmation | 人工对诊断结论做了什么判断？ |
| AuditEvent | 谁在什么时候对哪个目标执行了什么业务动作？ |

如果把这四类信息混进一张表，会导致生命周期、查询方式和安全策略相互污染。

### 2. 当前审计动作

- `evidence.created`；
- `diagnosis.supplemented`；
- `diagnosis.run_started`；
- `diagnosis.confirmed`；
- `diagnosis.rejected`；
- `diagnosis.reopened`；
- `knowledge.created`；
- `knowledge.status_changed`。

### 3. 为什么审计只保存安全摘要

AuditEvent 保存：

- actor；
- action；
- target type / target ID；
- created_at；
- correlation ID；
- 固定、有限的安全摘要。

它不保存完整用户输入、日志、Prompt、API Key 或 Knowledge 正文。审计的目标是证明动作发生，而不是复制业务内容。否则每增加一条审计记录，就会额外制造一份敏感数据副本。

### 4. Correlation ID 的作用

Request ID 从 API 入口进入日志和部分审计事件，用于把一次 HTTP 请求与内部动作关联起来。它不是业务主键，也不能代替 Diagnosis ID、AgentRun ID 或 Evidence ID。

当前部分 AuditEvent 仍没有完整贯穿 correlation ID，审计也没有独立查询 API。这些属于后续可观测性和管理能力扩展点，不应把当前最小审计描述成完整审计平台。

## Knowledge 生命周期与 Evidence 的关系

### 1. KnowledgeEntry 不是 Evidence

KnowledgeEntry 是可复用知识资产；Evidence 是某次 Diagnosis 中实际进入推理上下文、可被结论引用的证据实例。

```text
confirmed KnowledgeEntry
  → knowledge__search 命中
  → Tool 返回 EvidenceDraft
  → 保存为当前 Diagnosis 的 knowledge_entry Evidence
  → 结论引用该 Evidence ID
```

不能让结论直接引用全局 Knowledge ID，因为这样无法记录某次诊断实际使用了哪段内容，也无法保证引用属于当前 Diagnosis。

### 2. Knowledge 状态闭环

```text
candidate → confirmed → retired
    └────────→ retired
```

- 新建 Knowledge 一律为 candidate；
- 只有 confirmed 进入 `knowledge__search`；
- retired 为终态，不再进入检索；
- 有效状态变化记录 `knowledge.status_changed`；
- 相同状态重复请求按幂等成功处理，不重复写审计。

这解决的是知识治理，不是 Evidence 可信度自动提升。即使知识已经 confirmed，它在具体诊断中仍只能提供候选解释，不能替代日志或用户事实直接支持 probable。

## Phase 0B 的架构边界与阶段性妥协

Phase 0B 已完成最小证据闭环，但需要保留以下边界意识：

- Application 仍直接实例化部分 SQLAlchemy Repository，不是严格六边形架构；
- Evidence reliability 主要按类型设置，尚未形成可配置评分模型；
- Citation Policy 验证引用合法性，不验证自然语言语义是否真正支持 finding；
- LocalRuleRedactor 是规则型脱敏，无法识别所有企业自定义敏感格式；
- 用户提交日志仍是外部不可信内容，high reliability 不等于来源已认证；
- Confirmation actor 尚未接入真实身份认证和 RBAC；
- AuditEvent 没有完整管理查询和导出能力；
- SQLite Knowledge Search 是关键词加权检索，不是向量检索或混合检索；
- AgentRun 仍在同步请求中执行，没有 Worker、队列和崩溃恢复；
- Phase 0B 自动测试验证确定性规则，不代表真实模型诊断准确率。

因此 Phase 0B 的准确定位是：

> 在本地最小 Agent 骨架上完成了可追踪 Evidence、确定性引用校验和人工反馈的最小闭环，但尚不是完整企业诊断或合规审计平台。

## 常见说法校准

| 容易产生误解的说法 | 更准确的说法 |
|---|---|
| Phase 0B 给模型增加了更强能力 | 重点不是增强模型，而是增加证据、规则和人工控制边界 |
| 有 Evidence ID 就说明结论真实 | ID 只能证明引用对象存在并属于当前 Diagnosis，不能自动证明语义正确 |
| content hash 能证明证据来源真实 | hash 用于应用内部完整性和去重，不是数字签名或来源认证 |
| log_excerpt 是 high，所以日志一定可信 | high 表示当前来源类型评级；用户日志仍是 untrusted input |
| Citation Policy 会判断根因是否正确 | Policy 判断引用是否合法、是否满足规则，不理解完整因果语义 |
| confirmed 可以由模型输出 | Phase 0 中 confirmed 保留给人工动作 |
| KnowledgeEntry 就是 Evidence | Knowledge 是全局资产，Evidence 是某次 Diagnosis 的引用实例 |
| continue_investigation 等于 supplement | 两者前置状态和业务语义不同，只是都可能重新进入 investigating |
| Audit 保存的信息越多越好 | dot -Tsvg phase0a-framework.dot -o phase0a-framework.svgdot -Tsvg phase0a-agent-loop.dot -o phase0a-agent-loop.svgdot -Tsvg phase0a-ports-adapters.dot -o phase0a-ports-adapters.svgpowershell |
| Phase 0B 只新增 Adapter，没有修改核心 | Knowledge 替换保持 Tool 契约，但 Evidence 闭环确实扩展了 ToolLoopRunner 和 Application |

## 推荐的代码阅读路径

建议先沿 Evidence 生命周期阅读，再沿人工反馈和审计阅读：

1. [Evidence Domain](../../src/app_diagnosis/domain/evidence/models.py)：类型、来源、reliability、hash 和大小约束；
2. [LocalRuleRedactor](../../src/app_diagnosis/adapters/redaction/local_rules.py)：敏感内容如何在边界前处理；
3. [Evidence-aware Application Service](../../src/app_diagnosis/application/evidence_diagnoses.py)：初始 Evidence、Supplement、Confirmation 和事务；
4. [Evidence Repository Port](../../src/app_diagnosis/ports/evidence_repository.py) 与 [Evidence Store Port](../../src/app_diagnosis/ports/evidence_store.py)：应用持久化与 Tool Runtime 持久化为何分成两个入口；
5. [Tool Contracts](../../src/app_diagnosis/tools/contracts.py)：EvidenceDraft 如何从工具产生；
6. [ToolLoopRunner](../../src/app_diagnosis/agent/runtime/tool_loop.py)：EvidenceDraft 落库、ID 回传、引用纠错；
7. [EvidenceCitationPolicy](../../src/app_diagnosis/agent/policies/evidence_citations.py)：确定性引用规则；
8. [DiagnosisConclusion Schema](../../src/app_diagnosis/agent/schemas/diagnosis.py)：finding status 和 evidence_ids 如何表达；
9. [Confirmation Domain](../../src/app_diagnosis/domain/confirmation/models.py)：人工动作为什么追加保存；
10. [AuditEvent Domain](../../src/app_diagnosis/domain/audit/models.py)：安全审计的最小字段；
11. [Knowledge Application Service](../../src/app_diagnosis/application/knowledge.py)：candidate 创建、状态转换和审计；
12. [SQLite Knowledge Search](../../src/app_diagnosis/adapters/knowledge/sqlite_search.py)：为什么只有 confirmed Knowledge 可检索；
13. [Diagnosis API](../../src/app_diagnosis/api/routes/diagnoses.py) 与 [Knowledge API](../../src/app_diagnosis/api/routes/knowledge.py)：闭环如何暴露给调用方；
14. [Bootstrap Container](../../src/app_diagnosis/bootstrap/container.py)：Redactor、Evidence Store、Citation Policy 和 SQLite Search 如何接入 Phase 0A 主干。

## 回顾时应该能回答的问题

1. 为什么原始输入必须在持久化和进入模型之前脱敏？
2. EvidenceDraft 与 Evidence 为什么不能使用同一个生命周期？
3. content hash 能证明什么，不能证明什么？
4. high reliability 与 untrusted input 为什么可以同时存在？
5. Pydantic Schema 与 EvidenceCitationPolicy 分别校验什么？
6. 为什么 probable 必须具有 user_statement 或 log_excerpt？
7. 为什么 confirmed 不能由模型直接产生？
8. Confirmation 为什么不能覆盖模型初始结论？
9. Supplement 为什么不会自动启动新 AgentRun？
10. Evidence、AgentRun、Confirmation 和 AuditEvent 各自回答什么问题？
11. KnowledgeEntry 为什么不能直接作为某次诊断的 Evidence ID？
12. Phase 0B 哪些模块直接复用 Phase 0A，哪些地方实际修改了 Runtime？
13. 当前 Citation Policy 为什么还不能证明自然语言根因真的正确？
14. Phase 0B 距离企业级证据和审计平台还缺少什么？

## 图例

| 颜色或线型 | 含义 |
|---|---|
| 蓝色 | Phase 0A 接入、应用与领域基础 |
| 紫色 | Phase 0A Agent Runtime 和稳定 Ports |
| 青绿色 | Phase 0A 已有 Adapters |
| 绿色 | Phase 0B 新增能力和新增调用关系 |
| 橙色实线 | 复用的诊断主执行路径 |
| 橙色虚线 | 人工反馈和重新调查路径 |
| 灰色删除线 | 已被替换但仍保留参考价值的实现 |

## 源文件与重新生成

源文件为 `phase0b-extension.dot`。在本目录执行：

```powershell
dot -Tsvg phase0b-extension.dot -o phase0b-extension.svg
```
