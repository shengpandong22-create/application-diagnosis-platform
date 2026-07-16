# 2026-07-16 开发总结：Phase 0B 完成情况与 Phase 0C 计划

> [返回文档导航](../README.md)

## 1. 阶段结论

Phase 0B 已经完成证据驱动诊断闭环的核心实现，并通过现有离线一键验收：

- Ruff：通过；
- pytest：`146 passed`；
- Alembic 可从空 SQLite 数据库升级到 `0006`；
- Alembic Schema 漂移检查通过；
- Phase 0B OpenAPI 必需路径检查通过；
- Evidence、Knowledge、Confirmation 和 Audit 数据表检查通过；
- 验收过程不读取 API Key、不调用外部模型、不产生模型费用；
- 存在 1 条 Starlette TestClient/httpx 第三方弃用警告，不影响当前功能。

当前系统已经从 Phase 0A 的：

```text
模型调用工具 → 给出结构化初步结论
```

扩展为：

```text
用户描述 / 日志
  → 入库前脱敏
  → Evidence 持久化
  → Agent 调查与知识检索
  → Tool EvidenceDraft 落库
  → 真实 Evidence ID 回传模型
  → 结论引用规则校验
  → 用户确认 / 驳回 / 继续调查
  → 补充信息形成新 Evidence
  → 显式启动新的 AgentRun
```

对照 Phase 0A 总结中列出的 Phase 0B 原始六批清单，Knowledge 状态变更、审计和验收缺口已经在本次收尾中补齐。

因此当前状态可以准确表述为：

> Phase 0B 原始六批清单全部完成，并通过离线一键验收，可以正式进入 Phase 0C。

---

## 2. Phase 0B 原始清单逐项比对

| 批次 | 原始目标 | 当前结果 | 状态 |
|---|---|---|---|
| 第一批 | Evidence Domain、Repository、SQLAlchemy Adapter、Alembic `0003` | 实体、hash、完整性、大小限制、诊断归属、去重、Repository 和迁移测试均已实现 | 完成 |
| 第二批 | 入库前脱敏、用户陈述与日志 Evidence、不可信内容隔离 | Redaction Port、LocalRuleRedactor、日志安全分片、Prompt Injection 数据隔离均已实现 | 完成 |
| 第三批 | KnowledgeEntry、SQLite Repository、种子导入和检索 | Domain、Repository、`0004`、幂等种子导入和关键词检索已实现；Tool 契约未改变 | 完成 |
| 第四批 | EvidenceDraft 落库和证据引用规则 | 真实 Evidence ID 回传、引用归属和可信度规则、一次纠错均已实现 | 完成 |
| 第五批 | 补充信息、Evidence 查询、人工确认和 Knowledge API | 五个计划 API 均已实现；Confirmation 追加保存；继续调查后允许显式新 Run | 完成 |
| 第六批 | 最小审计事件和一键验收 | Evidence、补充、运行、人工动作、Knowledge 创建和状态变更均已审计 | 完成 |

### 2.1 第一批：Evidence Domain 与持久化

已完成：

- Evidence 类型：`user_statement`、`log_excerpt`、`knowledge_entry`；
- reliability：`low/medium/high`；
- redaction status：`not_required/redacted/rejected`；
- 16 KB UTF-8 内容大小限制；
- SHA-256 content hash 和完整性校验；
- 同一 Diagnosis 下 `(diagnosis_id, content_hash)` 去重；
- EvidenceRepository Port；
- SQLAlchemy Adapter；
- Alembic `0003`；
- Domain、Repository 和 Migration 测试。

验收要求均满足：Evidence 必须属于 Diagnosis，Domain 不依赖 SQLAlchemy，敏感样例不会原样保存。

### 2.2 第二批：输入脱敏与 Evidence 生成

已完成：

- Redaction Port 与 LocalRuleRedactor；
- Bearer Token、API Key、密码、`sk-` Key、JWT、连接串和常见 JSON 密钥识别；
- 创建诊断时将用户描述转换为 `user_statement` Evidence；
- 日志按 UTF-8 字节安全拆分为 `log_excerpt` Evidence；
- 原始输入在业务持久化和进入模型前完成脱敏；
- 用户输入和日志以不可信数据处理；
- Prompt Injection 文本不会成为系统指令；
- 诊断案例和初始 Evidence 在同一事务中保存。

### 2.3 第三批：SQLite Knowledge Repository

已完成：

- KnowledgeEntry Domain；
- `candidate/confirmed/retired` 状态值；
- KnowledgeRepository Port 与 SQLAlchemy Adapter；
- Alembic `0004`；
- JSON 知识种子幂等导入；
- SQLite 关键词加权检索；
- 运行时从 JSON Adapter 切换到 SQLite Adapter；
- 原 JSON Adapter 保留为实现参考与兼容入口；
- `knowledge__search` Tool 名称、输入输出契约保持不变；
- 知识种子覆盖 NPE、HTTP 500、timeout、OOM、ConnectionRefused、连接池耗尽、配置缺失和下游异常。

这次替换没有要求修改 ToolLoopRunner、DiagnosisStrategy 和 API Domain DTO，验证了 Port/Adapter 边界确实发挥作用。

### 2.4 第四批：证据引用规则

已完成：

- ToolExecutionResult 的 EvidenceDraft 在脱敏后落库；
- 去重后取得真实 Evidence ID；
- Evidence ID 写回 Tool Message，进入下一轮模型上下文；
- EvidenceCitationPolicy 校验证据属于当前 Diagnosis；
- `probable` 必须引用用户事实或日志直接证据；
- 只引用知识证据时不能达到 `probable`；
- `possible` 必须提供验证建议；
- `insufficient_evidence` 不能伪造 Evidence ID；
- Phase 0 中模型不能直接输出人工 `confirmed`；
- 首次引用违规时允许一次模型纠错，仍违规则以 `invalid_evidence_citations` 收敛。

### 2.5 第五批：补充信息与人工确认

已实现 API：

- `POST /api/v1/diagnoses/{id}/supplements`；
- `GET /api/v1/diagnoses/{id}/evidence`；
- `POST /api/v1/diagnoses/{id}/confirmation`；
- `GET /api/v1/knowledge`；
- `POST /api/v1/knowledge`。

已完成行为：

- `confirm/reject/continue_investigation` 三类人工动作；
- Confirmation 以追加记录保存，不覆盖模型初始结论；
- 人工备注在持久化前脱敏；
- 补充信息创建新 Evidence；
- Diagnosis 可从 `waiting_for_input` 重新进入 `investigating`；
- 新 AgentRun 通过显式 `/runs` 请求启动，不因补充信息自动产生模型费用；
- 新建 Knowledge 一律为 `candidate`；
- candidate 不进入正式知识检索；
- Knowledge 标题和摘要在入库前脱敏；
- 重复 Knowledge ID 返回 `409 knowledge_conflict`；
- Alembic `0005` 创建 Confirmation 记录。

### 2.6 第六批：审计事件与验收

已记录审计动作：

- `evidence.created`；
- `diagnosis.supplemented`；
- `diagnosis.run_started`；
- `diagnosis.confirmed`；
- `diagnosis.rejected`；
- `diagnosis.reopened`；
- `knowledge.created`。
- `knowledge.status_changed`。

已完成：

- AuditEvent Domain；
- AuditRepository Port 与 SQLAlchemy Adapter；
- Alembic `0006`；
- 审计只保存操作者、动作、目标、时间、Correlation ID 和固定安全摘要；
- 审计不保存完整日志、Prompt、用户输入和密钥；
- `scripts/verify-phase0b.ps1` 离线一键验收；
- `docs/04-validation/phase0b-acceptance.md` 验收记录。

本次收尾已完成：

- Knowledge 状态变更 Application Use Case；
- `PATCH /api/v1/knowledge/{entry_id}/status`；
- Repository 状态更新调用；
- `knowledge.status_changed` 审计事件；
- candidate → confirmed、candidate → retired、confirmed → retired 和非法逆向转换测试；
- 相同状态幂等处理，不重复写审计；
- 一键验收对 Knowledge 状态变更 OpenAPI 契约的检查。

---

## 3. Phase 0B 分层交付结果

### 3.1 Domain

- Evidence；
- KnowledgeEntry；
- Confirmation；
- AuditEvent；
- EvidenceCitationPolicy 使用的结论引用约束。

### 3.2 Ports

- Redaction；
- EvidenceRepository / EvidenceStore；
- KnowledgeRepository / KnowledgeSearch；
- ConfirmationRepository；
- AuditRepository。

### 3.3 Adapters

- LocalRuleRedactor；
- Evidence、Knowledge、Confirmation、Audit SQLAlchemy Adapters；
- SQLite Knowledge Search；
- JSON Knowledge Seed Loader。

### 3.4 Application 与 API

- 创建诊断时脱敏并创建初始 Evidence；
- Evidence 查询和用户补充；
- 人工确认、驳回和继续调查；
- Knowledge 创建和查询；
- 显式重新运行诊断；
- 安全审计事件。

### 3.5 数据库迁移

- `0003`：Evidence；
- `0004`：KnowledgeEntry；
- `0005`：Confirmation；
- `0006`：AuditEvent。

---

## 4. Phase 0B 开发经验沉淀

### 4.1 脱敏必须发生在持久化边界之前

如果先保存原文再异步清洗，即使最终业务查询只返回脱敏内容，数据库、WAL、备份和异常日志仍可能留下敏感信息。

经验：Redaction 应作为进入持久化和模型上下文前的强制边界，而不是后处理工具。

### 4.2 Evidence ID 只能在落库后产生

Tool 只能返回 EvidenceDraft，不能自行编造正式 Evidence ID。正式 ID 必须由 Evidence Store 在脱敏、校验和去重后生成，再回传模型。

经验：草稿、持久化实体和模型引用是三个不同生命周期，不能混用同一个 DTO。

### 4.3 模型引用必须由确定性规则校验

Prompt 可以要求模型引用证据，但不能保证引用存在、属于当前诊断或足以支持相应置信度。

经验：LLM 负责提出候选结论，EvidenceCitationPolicy 负责执行确定性业务约束；一次纠错是兼容机制，不是正确性边界。

### 4.4 Adapter 替换应验证稳定契约是否真实稳定

从 JSON Knowledge Adapter 切换到 SQLite Knowledge Search 时，ToolLoopRunner、Strategy 和 Tool Contract 没有修改。

经验：判断架构是否可扩展，不能只看是否定义了 Port，而要看替换实现时上层调用方是否保持不变。

### 4.5 人工确认不能覆盖模型原结论

如果直接把模型结论状态改为 confirmed，将无法回答“模型当时说了什么、谁在什么时候确认或驳回”。

经验：模型判断和人工判断属于两类事实，Confirmation 应追加保存，审计事件也应独立记录。

### 4.6 补充信息不应隐式触发模型费用

用户补充信息后，系统只创建 Evidence 并改变状态；是否重新调用模型由显式 `/runs` 决定。

经验：任何可能产生费用、外部副作用或较长延迟的操作，都应有清晰的显式触发边界。

### 4.7 “状态枚举存在”不等于“状态流程完成”

KnowledgeEntry 已定义 `candidate/confirmed/retired`，但当前没有应用用例和 API 驱动状态转换，也没有状态变更审计。

经验：清单验收必须沿 Domain → Repository → Application → API → Audit → Test 完整追踪，不能仅凭领域模型字段判断功能已经完成。

---

## 5. Phase 0B 收尾结果

Knowledge 最小状态闭环已经完成：

1. Domain 限制 `candidate → confirmed/retired`、`confirmed → retired`，`retired` 为终态；
2. 相同状态按幂等成功处理；
3. KnowledgeApplicationService 在单事务中完成读取、转换、保存和审计；
4. 新增 `PATCH /api/v1/knowledge/{entry_id}/status`；
5. 有效转换记录 `knowledge.status_changed`，摘要只包含前后状态；
6. 非法转换和不存在条目分别返回 409 和 404；
7. Phase 0B 一键验收覆盖新增 OpenAPI 路径并以 `146 passed` 通过。

本次收尾没有增加复杂审批流、角色权限系统、知识版本树或新数据库迁移，保持了 Phase 0 的最小范围。

---

## 6. 下一阶段：Phase 0C

Phase 0C 的核心目标是让当前诊断闭环变得可重复评估、可阅读交付和可进行最小人工操作：

> 用固定案例衡量诊断质量，生成可追踪的诊断报告，并通过极简界面完成创建、调查、补充和确认。

### 6.1 第一批：评测基线

1. 定义 EvalCase、期望事实、允许根因和必要 Evidence 类型；
2. 建立不调用外部模型的 Fake LLM 回归集；
3. 建立少量可手工触发的真实模型评测集；
4. 评估结构化输出合法率、Evidence 引用合法率、工具调用成功率和终止原因；
5. 区分确定性系统测试与非确定性模型质量评测；
6. 输出机器可读评测结果。

### 6.2 第二批：诊断报告

1. 定义 DiagnosisReport Domain DTO；
2. 聚合 Diagnosis、Conclusion、Evidence、AgentRun 和 Confirmation；
3. 输出 Markdown 或 HTML 报告；
4. 明确区分事实、候选根因、验证建议和人工结论；
5. 报告引用真实 Evidence ID；
6. 报告生成不再次调用模型；
7. 确保报告不泄漏已脱敏内容的原文。

### 6.3 第三批：极简界面

1. 优先采用服务端模板或极少量原生 JavaScript；
2. 支持创建诊断、查看状态、查看 Evidence 和启动 Run；
3. 支持补充信息、确认、驳回和继续调查；
4. 支持查看最终诊断报告；
5. 不引入独立前端工程、复杂状态管理和大型组件库；
6. 保持 16 GB 笔记本可以轻量运行。

### 6.4 第四批：Phase 0C 一键验收

至少验证：

- 固定评测案例可以重复运行；
- 报告中的 Evidence 引用均属于当前 Diagnosis；
- 报告不会把知识建议伪装成已证实事实；
- 极简界面的核心路径可通过集成测试；
- 默认自动验收不调用外部模型；
- 外部真实模型评测必须显式开启并提示费用。

---

## 7. 下一项具体任务

下一项不建议立即铺开完整 Phase 0C。应先编写独立的《Phase 0C 实现规格说明》，明确评测数据结构、报告契约和极简界面的范围，避免边写代码边扩大功能边界。

---

## 8. 当前项目注意事项

- `.env` 含真实 DeepSeek API Key，不得提交或分享；
- 默认自动测试继续使用 Fake LLM，不访问外部网络；
- 真实模型评测必须显式触发并控制费用；
- Evidence 和报告继续遵守入库前脱敏规则；
- 不为 Phase 0C 提前引入向量数据库、远程日志接入、Worker 或任务队列；
- 当前仓库尚未创建首次提交，形成阶段基线前应先审核全部文件。
