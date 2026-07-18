# Phase 2 实现规格说明：可观测、多策略、现场感知的诊断 Agent

> [返回文档导航](../README.md)

## 1. 阶段定位

Phase 2 在 Phase 0A/0B/0C 与 Phase 1 的有界诊断闭环上，增加三类能力：

```text
Phase 2A：Agent Trace
  让开发者和使用者看见一次 AgentRun 如何调用工具、产生 Evidence 并终止

Phase 2B：现场诊断工具
  让 Agent 在授权范围内读取配置、搜索日志并检查本地服务健康状态

Phase 2C：Strategy Router
  根据问题特征选择差异化诊断策略、工具白名单和调查提示
```

本阶段目标不是扩大 Agent 的任意执行权限，而是在最小权限和可审计边界内增加有效决策空间。

## 2. 明确非目标

- 不实现通用 Shell 或任意命令执行；
- 不读取完整进程环境变量；
- 不允许模型指定任意本机目录、文件绝对路径或 URL；
- 不自动修改配置、重启进程或调用修复接口；
- 不实现 Plan-then-Execute；
- 不实现向量代码库、全量 Code RAG 或跨仓库索引；
- 不把 candidate 自动升级为 confirmed；
- 不新增一次 LLM 调用专门做 Strategy 路由；
- 不把 Trace v1 描述为完整的逐轮 LLM 可观测平台。

## 3. 共通安全原则

1. 新工具全部为 `READ_ONLY`；
2. 工具必须经过 Strategy 白名单、Registry、权限、参数 Schema、超时和输出大小限制；
3. 文件类 Adapter 必须解析真实路径并验证仍位于配置根目录；
4. 健康检查只能使用启动时配置的目标别名，模型不能提交 URL；
5. 配置和日志内容必须在形成 Evidence 前脱敏；
6. 工具结果作为不可信 Evidence，不得改变系统指令；
7. Trace 不返回模型 API Key、Authorization、完整敏感配置或未经脱敏的原始日志；
8. `confirmed` 仍只由人工确认产生。

## 4. Phase 2A：Agent Trace

### 4.1 目标

基于现有 `AgentRun`、`ToolRun` 和 Evidence 构造确定性时间线，回答：

- 使用了哪个 Strategy；
- 运行何时开始和结束；
- 模型总轮次、Token、工具次数和终止原因；
- 每个工具的参数安全摘要、状态、耗时和错误；
- 工具产生了哪些正式 Evidence ID；
- 最终 Diagnosis 状态和结论引用了哪些 Evidence。

### 4.2 Trace Domain DTO

新增只读投影模型：

- `DiagnosisTrace`
  - `diagnosis_id`
  - `diagnosis_status`
  - `runs`
- `AgentRunTrace`
  - `agent_run_id`
  - `strategy`
  - `status`
  - `termination_reason`
  - `model`
  - `round_count/tool_call_count/input_tokens/output_tokens`
  - `started_at/finished_at/duration_ms`
  - `events`
- `TraceEvent`
  - `type`: `run_started/tool_call/run_finished`
  - `sequence`
  - `occurred_at`
  - `summary`
  - `tool_name/status/duration_ms/error_code`
  - `evidence_ids`

Trace DTO 不依赖 FastAPI 或 SQLAlchemy。

### 4.3 Evidence 关联

从 Phase 2 起，ToolLoopRunner 调整顺序：

```text
执行 Tool
→ EvidenceDraft 脱敏并落库
→ 获得正式 Evidence ID
→ ToolRun.result_json 保存安全结果与 evidence_ids
→ Evidence ID 回传模型
```

历史 ToolRun 没有关联信息时，Trace 返回空 `evidence_ids`，不得按时间猜测关联。

### 4.4 API 与 UI

- 新增 `GET /api/v1/diagnoses/{id}/trace`；
- `/ui` 增加“查看 Trace”；
- UI 按 Run 展示概览和事件时间线；
- UI 不在浏览器重算业务状态，只呈现 API 投影。

### 4.5 Trace v1 边界

现有持久化没有保存每次 LLM Request/Response 的独立时间戳和 Token，因此 Trace v1 只展示 AgentRun 聚合模型指标，不伪造 Round 级事件。若未来需要逐轮 Prompt、响应与纠错事件，应新增独立持久化模型并制定敏感内容保存策略。

## 5. Phase 2B：现场诊断工具

### 5.1 `config__read`

用途：读取授权配置工作区内的有限配置片段。

输入：

- `relative_path`；
- `start_line`，默认 1；
- `end_line`，最多 120 行。

限制：

- 根目录来自 `APP_CONFIG_WORKSPACE_PATH`；
- 只允许 `.yml/.yaml/.properties/.xml/.json/.toml`；
- 拒绝绝对路径、目录穿越、符号链接越界和超大文件；
- 内容先脱敏再返回和入库；
- 成功读取生成 `config_excerpt` Evidence；
- Evidence source 为 `local_config`；
- reliability 为 `medium`，因为静态配置不证明运行时最终值。

### 5.2 `log__search`

用途：从授权日志目录提取最近一次匹配事件。

输入：

- `relative_path`；
- `keyword`；
- 可选 `max_lines`。

限制：

- 根目录来自 `APP_LOG_DIRECTORY`；
- 只允许 `.log/.txt`；
- 复用 LocalLogFileReader 的目录、大小、关键词和事件边界规则；
- 内容先脱敏再返回和入库；
- 成功读取生成 `log_excerpt` Evidence；
- Evidence source 为 `local_log`；
- 不实现持续占用连接的实时 tail。

### 5.3 `health__check`

用途：对启动时配置的本地服务目标进行有限 HTTP 健康检查。

输入：

- `target`：目标别名，不能是 URL。

配置：

- `APP_HEALTH_TARGETS` 使用 JSON 对象，例如：
  `{"java-lab":"http://127.0.0.1:18080/actuator/health"}`；
- 只允许 `http`；
- Host 只允许 loopback：`127.0.0.1`、`localhost`、`::1`；
- 禁止重定向；
- 固定 GET；
- 超时不超过 5 秒；
- 响应正文只保留受限、脱敏后的文本摘要。

输出：

- target；
- HTTP status 或连接错误类别；
- duration；
- 有界响应摘要；
- 生成 `health_check` Evidence，source 为 `local_service`。

连接失败是有效诊断结果，不作为工具框架异常丢弃；参数、权限或目标不存在才属于工具执行失败。

### 5.4 Ports 与 Adapters

新增：

- `ConfigRepository` Port + `LocalConfigRepository` Adapter；
- 复用 `LogReader` Port，扩展 `LocalLogFileReader` 为工具 Adapter 所需契约；
- `HealthCheckClient` Port + `HttpHealthCheckClient` Adapter。

Tool Contract 不泄漏 `Path`、`httpx.Response` 或 SQLAlchemy 类型。

## 6. Phase 2C：Strategy Router

### 6.1 策略集合

| Strategy | 典型信号 | 工具白名单 |
|---|---|---|
| `ApplicationErrorStrategy` | exception、stack trace、NPE、500 | knowledge、log、code search/read、config |
| `NetworkStrategy` | connection refused、connect timeout、socket、DNS | knowledge、log、config、health |
| `ConfigurationStrategy` | missing property、invalid config、启动配置错误 | knowledge、log、config、health |
| `GenericApplicationErrorStrategy` | 无法明确分类 | knowledge，加上已配置的安全只读工具 |

### 6.2 Router 规则

新增 `DiagnosisStrategyRouter` Port/服务：

```text
显式 ProblemType（未来扩展）
→ 规则信号评分
→ 单一最高分且达到阈值：选择专用 Strategy
→ 并列或无命中：Generic fallback
```

Phase 2 使用确定性规则，不调用 LLM。路由依据仅使用标题、症状和已脱敏日志；规则匹配结果不写入 Prompt。

### 6.3 与 AgentRun 的关系

- Strategy 在每次 Run 开始前选择；
- `AgentRun.strategy` 保存实际策略名；
- 补充信息后重新调查时允许选择不同 Strategy；
- Router 不修改 Diagnosis 状态；
- ToolLoopRunner 继续只接收已选择的一个 Strategy。

为保持现有 Diagnosis 数据兼容，Phase 2 的专用 Strategy 仍服务于 `generic_application_error` ProblemType；策略是调查方法，ProblemType 是领域分类，两者暂不强制一一对应。未来有稳定分类需求时再扩展 ProblemType 和迁移。

## 7. 实施顺序

### 7.1 Phase 2A

1. Trace DTO 与投影服务；
2. ToolRun 保存 Evidence ID；
3. Trace API Schema 和 Route；
4. UI 时间线；
5. Domain、Application 和 API 测试。

### 7.2 Phase 2B

1. Evidence 类型与 source 扩展；
2. Alembic `0008`；
3. Config Port/Adapter/Tool；
4. Log Tool；
5. Health Port/Adapter/Tool；
6. Settings、Bootstrap 和安全测试。

### 7.3 Phase 2C

1. 专用 Strategy；
2. 规则 Router；
3. Application Service 在每次运行时选择 Strategy；
4. 路由和白名单测试；
5. 新增配置、网络固定评测案例。

### 7.4 收尾

1. Phase 2 离线演示脚本；
2. 一键验收脚本；
3. 架构图、开发总结和 README；
4. Ruff、全量 pytest、迁移和演示验收。

## 8. 验收标准

### 8.1 Phase 2A Trace

- [ ] Trace Domain 不导入 FastAPI、SQLAlchemy；
- [ ] 不存在的 Diagnosis 返回统一 404；
- [ ] Trace 按 AgentRun 展示策略、聚合 Token、轮次和终止原因；
- [ ] Tool event 按时间稳定排序；
- [ ] Tool event 展示状态、耗时、错误码和正式 Evidence ID；
- [ ] 历史 ToolRun 无 Evidence 关联时返回空数组，不猜测；
- [ ] Trace 不包含 API Key、Bearer Token 或未脱敏密码；
- [ ] `/ui` 可以查看时间线；
- [ ] 报告、原 `/runs` API 和 Agent Loop 契约不被破坏。

### 8.2 Phase 2B 工具

- [ ] 三个工具均为 `READ_ONLY`；
- [ ] 工具不在 Strategy 白名单时被 Registry 拒绝；
- [ ] `config__read` 拒绝绝对路径、`..`、越界符号链接、禁用后缀、超大文件和超过 120 行；
- [ ] 配置中的密码、Token 和连接串在 ToolRun、Evidence 和 Trace 中均已脱敏；
- [ ] `log__search` 只读取配置目录，且一个 excerpt 不混入后续异常事件；
- [ ] `health__check` 只接受配置别名，不能提交 URL；
- [ ] 健康检查禁止非 loopback、HTTPS 和重定向；
- [ ] 健康检查超时和连接拒绝形成结构化诊断结果；
- [ ] 工具输出受 `max_tool_output_bytes` 约束；
- [ ] 新 Evidence 正确归属当前 Diagnosis，并经过 hash 去重。

### 8.3 Phase 2C Router

- [ ] NPE/异常栈选择 ApplicationErrorStrategy；
- [ ] 连接拒绝选择 NetworkStrategy；
- [ ] 缺少配置选择 ConfigurationStrategy；
- [ ] 无明确命中回退 Generic；
- [ ] 信号并列时回退 Generic；
- [ ] 每个 Strategy 只暴露声明的工具；
- [ ] 工具未配置时不会出现在白名单；
- [ ] `AgentRun.strategy` 保存实际路由结果；
- [ ] 补充信息后重新运行可以重新路由；
- [ ] Router 默认不产生真实模型调用。

### 8.4 阶段总验收

- [ ] `uv run ruff check .` 通过；
- [ ] `uv run pytest` 全量通过；
- [ ] 空库 `alembic upgrade head` 通过；
- [ ] 从 `0007` 升级到 `0008` 通过；
- [ ] Phase 0A/0B/0C/1 既有核心测试不回归；
- [ ] Phase 2 离线演示使用 Fake LLM，不访问外部网络；
- [ ] 一键验收脚本明确标注不会调用真实模型；
- [ ] 真实模型验收最多选择一个新增复杂案例低频执行，不作为默认测试；
- [ ] 文档导航、架构图源文件和 SVG 成品齐全。

## 9. 验收命令

```powershell
uv run ruff check .
uv run pytest
uv run alembic upgrade head
uv run python scripts/demo-phase2.py
.\scripts\verify-phase2.ps1 -SkipSync
```

默认命令不得调用真实模型。

## 10. 完成定义

Phase 2 完成不以“新增了多少工具”为判断标准，而以以下闭环成立为准：

```text
问题进入系统
→ Router 选择差异化 Strategy
→ Agent 只看到该 Strategy 授权的现场工具
→ 工具在受限边界内产生脱敏 Evidence
→ ToolRun 与 Evidence 可在 Trace 中关联
→ Citation Policy 约束最终结论
→ 用户从 Trace 和 Report 理解过程与结果
```
