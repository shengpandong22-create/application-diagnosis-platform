# 2026-07-16 开发总结：Phase 0A 完成与 Phase 0B 计划

> [返回文档导航](../README.md)

## 1. 今日结论

Application Diagnosis Platform 的 Phase 0A 已完成，并通过离线自动验收和 DeepSeek 真实模型外部联调。

当前系统已经形成一条完整的最小纵向链路：

```text
创建诊断案例
  → 状态进入 investigating
  → 诊断策略生成提示和工具白名单
  → Agent Loop 调用真实模型
  → 模型调用 knowledge__search
  → 保存 AgentRun / ToolRun
  → 校验结构化 DiagnosisConclusion
  → 保存初步结论
  → 状态进入 waiting_for_confirmation 或 waiting_for_input
  → API 查询诊断、结论和执行审计
```

Phase 0A 的最终验证结果：

- Ruff：通过；
- pytest：90 passed；
- Alembic 可从空 SQLite 数据库升级到最新版本；
- Alembic Schema 差异检查通过；
- OpenAPI 必需路径检查通过；
- 一键验收脚本执行通过；
- DeepSeek `deepseek-v4-pro` 真实模型联调通过；
- 真实模型完成两轮调用并实际调用 `knowledge__search`；
- 结构化结论、AgentRun 和 ToolRun 均成功持久化；
- API Key 未写入源码、日志或验收记录；
- 联调临时服务已停止，8000 端口无遗留进程。

---

## 2. 已完成工作：第一层——独立项目与工程基础

### 2.1 独立 Python 项目

- 创建独立工程 `D:\AgentStudy\application-diagnosis-platform`；
- 与原 ITOps TypeScript 项目完全解除运行时依赖；
- ITOps 代码只作为职责划分和实现思路参考；
- 使用 Python 3.12、`uv`、`src` layout 和独立 Git 仓库；
- 建立 `.env.example`、`.gitignore`、`pyproject.toml` 和 `uv.lock`；
- `.env`、API Key、SQLite 数据库及 WAL/SHM 文件均被排除提交。

### 2.2 Web 与配置基础

- 建立 FastAPI 应用工厂；
- 提供 `/health/live` 和 `/health/ready`；
- 使用 Pydantic Settings 读取强类型配置；
- 生产环境关闭 OpenAPI 文档；
- 运行时不自动建业务表，数据库结构由 Alembic 管理。

### 2.3 数据库基础

- 使用 SQLAlchemy Async 与 `aiosqlite`；
- 建立短事务 Repository Adapter；
- 建立 Alembic `0001`、`0002` 迁移；
- 修复首次迁移时 SQLite 父目录不存在的问题；
- Diagnosis 更新使用乐观锁，避免静默覆盖并发修改。

---

## 3. 已完成工作：第二层——诊断领域模型

### 3.1 DiagnosisCase

已实现：

- Diagnosis ID、标题、问题类型、症状和用户日志；
- 结构化初步结论；
- UTC 创建和更新时间；
- 乐观锁版本号；
- 字段值和时间合法性校验。

### 3.2 诊断状态机

已支持状态：

- `created`；
- `investigating`；
- `waiting_for_input`；
- `waiting_for_confirmation`；
- `confirmed`；
- `rejected`；
- `inconclusive`；
- `cancelled`。

所有状态转换由领域模型约束，Application Use Case 负责触发；LLM、Tool 和 API 不得直接修改状态。

### 3.3 状态收敛规则

- 正常完成且结论信息充分：`waiting_for_confirmation`；
- 模型明确要求补充信息：`waiting_for_input`；
- 模型错误、预算耗尽、超时或无有效结论：`inconclusive`；
- 即使失败路径携带候选答案，也不能错误推进到等待确认；
- Phase 0A 中模型不能直接将结论标记为人工确认完成。

---

## 4. 已完成工作：第三层——供应商无关的 LLM Runtime

### 4.1 LLM Port

建立了供应商无关的：

- ChatMessage；
- ToolCall；
- ToolDefinition；
- ResponseFormat；
- LLMRequest / LLMResponse；
- Token Usage；
- 超时、传输、HTTP 和协议错误类型。

Domain 和 Application 不依赖具体模型 SDK。

### 4.2 OpenAI-compatible Adapter

已实现：

- Chat Completions 请求序列化；
- assistant `tool_calls` 历史；
- tool `tool_call_id` 对应关系；
- 多工具调用响应解析；
- HTTP、超时和协议异常转换；
- API Key 只通过 Authorization Header 发送；
- Adapter 生命周期关闭。

### 4.3 DeepSeek 兼容能力

真实联调发现 DeepSeek 与完整 OpenAI `json_schema` 行为存在差异，因此增加：

- `APP_LLM_RESPONSE_FORMAT=auto`；
- DeepSeek Base URL 自动选择 `json_object`；
- 其他 OpenAI-compatible Provider 默认使用 `json_schema`；
- 可显式选择 `json_schema`、`json_object` 或 `none`；
- 完整 DiagnosisConclusion Schema 同时写入系统提示；
- 无论 Provider 是否原生强制 Schema，最终都由本地 Pydantic 严格校验。

---

## 5. 已完成工作：第四层——诊断工具与知识检索

### 5.1 Tool Contract 与 Registry

每个工具必须声明：

- 唯一工具名；
- 描述；
- 输入和输出 Schema；
- 风险级别；
- 超时时间；
- 所需权限；
- 支持的问题类型。

Registry 负责：

- 重复注册检查；
- 启用和禁用；
- 策略白名单；
- 权限校验；
- 问题类型校验；
- JSON 与 Pydantic 参数校验。

模型不能绕过 Registry 直接执行任意工具。

### 5.2 knowledge__search

- 使用本地 JSON 知识数据；
- 当前包含 Java 常见异常样例；
- 模型不能提交文件路径、Shell 或 URL；
- 工具输出有字节限制和截断标记；
- 工具返回结构化结果和 EvidenceDraft，为 Phase 0B 留出扩展接口。

---

## 6. 已完成工作：第五层——有界 Agent Loop

### 6.1 执行预算

Tool Loop 同时受以下预算约束：

- 最大模型轮次；
- 最大工具调用次数；
- 单工具超时；
- 总执行时间。

### 6.2 循环行为

- 支持无工具直接输出；
- 支持单工具和同轮多工具调用；
- 处理所有同轮工具，而不是只处理第一个；
- 单个工具失败不丢弃其他成功结果；
- 未知工具、非法 JSON 和 Schema 错误作为工具失败回传模型；
- 保留 assistant tool_calls 与 tool_call_id 对话历史；
- 模型结构化输出失败后只允许一次纠错；
- 取消操作持久化后继续传播取消信号；
- 每种停止路径都有标准 termination reason。

### 6.3 执行审计

AgentRun 记录：

- 策略；
- 模型；
- 状态和终止原因；
- 模型轮次和工具次数；
- Token 用量；
- 开始和结束时间；
- 安全错误码。

ToolRun 记录：

- 工具调用 ID 和工具名；
- 校验后的参数；
- 状态和有限大小的结果；
- 执行耗时；
- 安全错误码。

完整提示词历史暂不入库，降低敏感信息和存储风险。

---

## 7. 已完成工作：第六层——Application Use Case 与 API 闭环

### 7.1 Application Use Case

已实现：

- 创建诊断；
- 查询诊断；
- 启动同步诊断 Run；
- 应用 Tool Loop 结果；
- 查询 AgentRun 与 ToolRun；
- 取消诊断；
- 同一诊断活动 Run 冲突保护；
- 输入日志字节数限制。

应用接口没有假设必须运行在 HTTP 请求中，后续可迁移到 Worker。

### 7.2 API

- `POST /api/v1/diagnoses`；
- `POST /api/v1/diagnoses/{id}/runs`；
- `GET /api/v1/diagnoses/{id}`；
- `GET /api/v1/diagnoses/{id}/runs`；
- `POST /api/v1/diagnoses/{id}/cancel`。

### 7.3 统一错误契约

所有 API 错误统一返回：

```json
{
  "error": {
    "code": "diagnosis_not_found",
    "message": "Diagnosis not found",
    "request_id": "request-id"
  }
}
```

已覆盖：

- 参数校验错误；
- Diagnosis 不存在；
- 状态和运行冲突；
- 非法领域值；
- HTTP 错误；
- 未预期内部错误。

---

## 8. 已完成工作：第七层——可观测性、安全与验收

### 8.1 结构化日志

- 应用访问日志使用单行 JSON；
- 记录 request_id、方法、路径、状态码和耗时；
- 不记录请求体、Authorization、API Key 或完整提交日志；
- 外部模型 HTTP 调用日志可以通过同一个 request_id 关联。

### 8.2 请求关联 ID

- 接收安全格式的 `X-Request-ID`；
- 未提供或格式不安全时生成 UUID；
- 写回响应 Header；
- 注入日志 ContextVar；
- 传入 ToolLoopContext 审计上下文。

### 8.3 自动验收

新增：

- `scripts/verify-phase0a.ps1`：离线一键验收；
- `scripts/real-model-smoke.ps1`：真实模型全链路联调；
- `docs/validation/phase0a-acceptance.md`：验收记录。

一键验收覆盖：

- 依赖同步；
- Ruff；
- pytest；
- 空库迁移；
- Schema 差异；
- OpenAPI 路径；
- 临时数据库安全清理。

---

## 9. 今日修复问题与开发经验沉淀

### 9.1 问题：SQLite 首次迁移无法创建数据库

现象：

```text
sqlite3.OperationalError: unable to open database file
```

根因：默认数据库位于 `./data`，但 Alembic 在应用启动前执行，此时 Database.start 尚未创建父目录。

修复：Alembic 在线迁移前识别 SQLite URL，并安全创建数据库父目录。

经验：

- README 中的首次启动命令必须在真正的空环境执行一次；
- 应用启动路径和迁移路径是两条独立入口，不能假设一方已经完成初始化；
- 测试临时目录通常自动存在，可能掩盖真实首次安装问题。

### 9.2 问题：异步调用写进普通生成式表达式

现象：查询运行摘要时出现：

```text
TypeError: 'async_generator' object is not iterable
```

根因：在普通 tuple generator 中直接使用 `await`，表达式被解释为异步生成器。

修复：使用清晰的 `for` 循环逐项 await，再构造 tuple。

经验：

- 异步代码优先选择显式循环，可读性和异常定位优于追求一行表达式；
- N+1 查询当前数据量可接受，但 Phase 1 应考虑 Repository 批量查询。

### 9.3 问题：不完整运行错误推进了诊断状态

现象：Tool Loop 以 `inconclusive` 结束但携带候选结论时，案例可能进入 `waiting_for_confirmation`。

根因：应用层只判断 conclusion 是否存在，没有同时判断 termination reason。

修复：只有 `completed + valid conclusion` 才能推进等待确认；其他路径统一收敛为 `inconclusive`。

经验：

- Agent 输出内容和执行状态是两个不同维度；
- “模型给了答案”不代表系统运行成功；
- 状态推进必须由应用规则决定，不能由模型输出是否非空决定。

### 9.4 问题：结构化日志测试捕获不到记录

根因：Alembic 的 `fileConfig` 会禁用已存在的应用 Logger；随后只重设 Root Handler，没有恢复 Logger 的 disabled 状态。

修复：configure_logging 显式恢复 `app_diagnosis.*` Logger。

经验：

- 第三方日志配置可能修改全局 Logger 状态；
- 测试“输出格式”时应给目标 Logger 安装独立 Handler，而不是依赖全局 stdout 捕获；
- 结构化日志必须测试字段，不只测试“有日志”。

### 9.5 问题：DeepSeek 首次返回 HTTP 400

根因：项目最初发送 OpenAI 严格 `json_schema`，DeepSeek JSON Output 更适合 `json_object`。

修复：增加 Provider 能力配置和自动选择策略。

经验：

- “OpenAI-compatible”不代表所有可选参数完全一致；
- Port 应表达业务需要，Adapter 应处理 Provider 能力差异；
- 供应商差异应通过显式配置和测试固化，不能散落 `if deepseek` 到业务代码中。

### 9.6 问题：切换 json_object 后结构化结果仍不通过

根因：`json_object` 只保证输出是 JSON，不会把 Pydantic Schema 自动传递给模型；原提示词只说“遵守 Schema”，却没有包含 Schema 内容。

修复：将完整 DiagnosisConclusion JSON Schema 放入系统提示和纠错提示，最终继续由 Pydantic 校验。

经验：

- Provider 约束与本地校验必须双层存在；
- Schema 是契约，应同时服务于 Provider 原生约束、Prompt 指导和本地校验；
- 降级兼容不能等于降低业务正确性。

### 9.7 问题：Windows 后台启动遗留 Uvicorn 子进程

根因：通过 `uv run` 或可执行启动器启动时会产生父子进程，只停止父进程不能保证子进程退出。

修复：按端口、命令行和项目路径校验进程身份，停止确认属于本次联调的进程；最终再次检查 8000 端口。

经验：

- 自动化脚本启动服务时必须拥有明确的进程生命周期；
- 停止进程前同时校验 PID、命令行和工作目录，避免误杀；
- 验收结束应检查端口，而不是只相信 Stop-Process 成功。

### 9.8 问题：SQLite WAL/SHM 文件出现在 Git 状态

根因：原 `.gitignore` 只忽略 `*.db`，没有覆盖 `*.db-wal` 和 `*.db-shm`。

修复：增加 `*.db-*`。

经验：运行时生成物的忽略规则要覆盖主文件和边车文件，真实运行后必须再次检查 `git status`。

---

## 10. 明日目标：Phase 0B

Phase 0B 的核心目标不是增加更多模型能力，而是把“模型给出答案”升级为：

> 系统基于可追踪证据提出结论，并允许用户补充、确认、驳回或要求继续调查。

## 11. 明日建议实施顺序

### 11.1 第一批：Evidence Domain 与持久化

优先完成：

1. 定义 Evidence 实体和值类型；
2. 支持 `user_statement`、`log_excerpt`、`knowledge_entry`；
3. 定义 reliability 与 redaction status；
4. 对 content 计算 hash，用于去重和完整性校验；
5. 建立 EvidenceRepository Port；
6. 建立 SQLAlchemy Adapter；
7. 新增 Alembic `0003` 迁移；
8. 完成领域、Repository 和迁移测试。

验收重点：

- Evidence 必须属于一个 Diagnosis；
- 内容有大小上限；
- 相同诊断下可按 hash 去重；
- Repository 不泄漏 SQLAlchemy 类型到 Domain；
- API Key、Token 和密码样例不能原样保存。

### 11.2 第二批：输入脱敏与 Evidence 生成

1. 建立 Redaction Port 和本地规则实现；
2. 识别 API Key、Bearer Token、密码和常见连接串；
3. 创建诊断时将用户描述转为 user_statement Evidence；
4. 将日志拆分为有限大小的 log_excerpt Evidence；
5. 标记用户和日志内容为不可信数据；
6. 确保 Prompt Injection 文本不会改变系统指令；
7. 增加脱敏和不可信内容隔离测试。

设计原则：原始敏感文本不应先入库再脱敏，应在持久化和进入模型前完成处理。

### 11.3 第三批：SQLite Knowledge Repository

1. 定义 KnowledgeEntry Domain；
2. 支持 `candidate/confirmed/retired`；
3. 建立 KnowledgeRepository Port 与 SQLite Adapter；
4. 将现有 JSON 知识种子导入数据库；
5. 实现关键词或 SQLite FTS 检索；
6. 保持 `knowledge__search` Tool 契约不变，只替换 Adapter；
7. 覆盖 NPE、HTTP 500、timeout、OOM、ConnectionRefused、连接池耗尽、配置缺失和下游异常。

验收重点：替换 JSON Adapter 后，不修改 ToolLoopRunner、Strategy 和 API Domain DTO。

### 11.4 第四批：证据引用规则

1. ToolExecutionResult 的 EvidenceDraft 落库；
2. 将实际 Evidence ID 回传模型上下文；
3. 校验结论引用的 Evidence 属于当前 Diagnosis；
4. `probable` 至少引用日志或用户事实证据；
5. 只引用知识条目时最多为 `possible`；
6. `possible` 必须包含验证建议；
7. `insufficient_evidence` 不得伪造 Evidence ID；
8. Phase 0 中 `confirmed` 只允许人工确认后产生。

### 11.5 第五批：补充信息与人工确认

新增用例和 API：

- `POST /api/v1/diagnoses/{id}/supplements`；
- `GET /api/v1/diagnoses/{id}/evidence`；
- `POST /api/v1/diagnoses/{id}/confirmation`；
- `GET /api/v1/knowledge`；
- `POST /api/v1/knowledge`。

人工确认需要追加 Confirmation 记录，不能覆盖原始模型结论。动作包括：

- confirm；
- reject；
- continue_investigation。

补充信息后创建新 Evidence，并允许从 `waiting_for_input` 重新进入 `investigating`，生成新的 AgentRun。

### 11.6 第六批：最小审计事件与 Phase 0B 验收

至少记录：

- Evidence 创建；
- 用户补充；
- 诊断重新运行；
- 人工确认；
- 人工驳回；
- 要求继续调查；
- Knowledge 创建和状态变更。

审计中只保存操作者、动作、目标 ID、时间和安全摘要，不保存密钥和完整敏感日志。

---

## 12. 明日第一项具体开发任务

明日建议不要同时铺开全部 Phase 0B。第一项任务明确为：

> 实现 Evidence Domain、EvidenceRepository Port、SQLAlchemy Adapter、Alembic 0003 迁移，以及相应领域和集成测试。

暂不在第一项任务中实现：

- Confirmation；
- Knowledge 管理 API；
- SQLite FTS；
- 前端；
- 向量数据库；
- 远程日志接入；
- Worker 和任务队列。

完成 Evidence 基础后，再逐层接入脱敏、知识迁移、结论引用和人工确认，可以减少一次性修改 Agent Loop 带来的风险。

---

## 13. 当前项目注意事项

- `.env` 包含真实 DeepSeek API Key，不得提交或分享；
- 本地 `data` 目录包含真实联调产生的诊断记录，但已被 Git 忽略；
- 当前所有项目文件尚未形成首次 Git commit，后续可在确认审核后创建基线提交；
- 真实模型调用会产生费用，默认自动测试仍全部使用 Fake LLM，不访问外部网络；
- 进入 Phase 0B 后，应优先保证 Evidence 和脱敏正确性，而不是快速增加更多工具。
