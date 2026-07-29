# Phase 3 实现规格说明

Phase 3 的目标是把当前诊断闭环从“能运行”推进到“能解释、能复盘、能围绕服务持续演进”。

本阶段不追求大平台化，也不引入自动处置。核心路线是：

```text
先把当前诊断闭环讲深
→ 再用 Trace 和轻量 DiagnosisPlan 增强 Agent 可解释性
→ 最后用服务目录把诊断对象从“一次请求”升级为“一个真实服务”
```

## Phase 3A：讲深当前诊断闭环

Phase 3A 聚焦已有能力的可读性、可讲解性和可复盘性。

### 实施内容

- 为关键源码增加接手型中文注释；
- 整理主调用链路学习文档；
- 固定架构图可视化风格；
- 确认 Report / Trace 可以解释 Evidence、工具调用、状态收敛和人工反馈。

### 验收标准

- 新同事可以从注释理解 API、ApplicationService、ToolLoopRunner、Registry、Evidence、CitationPolicy、DiagnosisCase 的边界；
- 主链路文档能讲清一次诊断从创建到人工确认的流转；
- 架构图颜色、节点和拆图方式符合 `docs/01-architecture/visual-style-guide.md`；
- 不改变现有诊断行为；
- `uv run ruff check .` 通过；
- `uv run pytest` 通过。

## Phase 3B：轻量 DiagnosisPlan

Phase 3B 增加规则版 `DiagnosisPlan`。第一版 Plan 不改变 Agent Loop 行为，也不额外调用真实模型。它用于解释“系统准备如何调查”，并作为 Report / Trace 的可解释资产。

### 领域模型

`DiagnosisPlan` 包含：

- `id`;
- `diagnosis_id`;
- `agent_run_id`;
- `summary`;
- `hypotheses`;
- `steps`;
- `expected_evidence`;
- `allowed_tools`;
- `status`;
- `created_at`。

`PlanStep` 包含：

- `order`;
- `title`;
- `description`;
- `tool_name`;
- `expected_evidence`。

### 生成策略

第一版采用规则生成：

- 基于当前 `DiagnosisCase`;
- 基于选中的 `DiagnosisStrategy`;
- 基于该 Strategy 实际允许暴露给模型的工具白名单；
- 生成稳定、可测试、可展示的步骤。

Plan 只解释诊断路线，不参与工具调度决策。

### API

新增：

```text
GET /api/v1/diagnoses/{id}/plan
```

行为：

- 诊断不存在：返回 `diagnosis_not_found`;
- 诊断存在但尚未运行：返回 `diagnosis_plan_not_found`;
- 诊断已运行：返回最新 Plan。

### Report / Trace 集成

- Report JSON 增加 `plans`;
- Markdown 报告增加“诊断计划”章节；
- Trace 的每个 AgentRun 增加关联 Plan。

### 验收标准

- 每次 `POST /api/v1/diagnoses/{id}/runs` 后生成一条 Plan；
- Plan 必须同时关联 Diagnosis 和 AgentRun；
- Plan 至少包含 summary、hypotheses、steps、expected_evidence、allowed_tools、status；
- Plan 不改变 LLM 调用轮次、工具执行逻辑和 DiagnosisCase 状态机；
- API、Report、Trace 均可查看 Plan；
- 单元测试和集成测试默认使用 Fake LLM；
- `uv run ruff check .` 通过；
- `uv run pytest` 通过。

## Phase 3C：最小服务目录

Phase 3C 的目标是把诊断对象从一次请求升级为一个真实服务。为避免一次性重构
工具上下文，本阶段拆成 3C-1 和 3C-2。

### Phase 3C-1：服务目录元数据闭环

第一批实现服务档案的创建、查询和基于服务创建诊断。

领域模型：

```text
ServiceProfile
- id
- name
- description
- environment
- code_workspace_path
- log_directory
- config_workspace_path
- health_targets
- tags
- created_at
- updated_at
```

API：

```text
POST /api/v1/services
GET /api/v1/services
GET /api/v1/services/{id}
POST /api/v1/services/{id}/diagnoses
```

行为边界：

- 只保存用户显式传入的路径和健康检查目标；
- 不扫描用户电脑；
- 不校验路径是否真实存在；
- 不改变当前 ToolLoopRunner 和 Adapter 的工具访问范围；
- 基于服务创建的 Diagnosis 会记录 `service_id`；
- 普通 `POST /api/v1/diagnoses` 继续可用，且 `service_id = null`；
- Report 展示关联服务信息。

### Phase 3C-2：按服务驱动工具上下文

下一批再让服务目录真正影响工具访问范围：

```text
service.code_workspace_path
service.log_directory
service.config_workspace_path
service.health_targets
→ 诊断运行时动态影响 ToolExecutionContext / Adapter 可访问范围
```

3C-2 需要重点设计安全边界，不能让 Agent 自动扫描任意目录。

## 真实模型验收策略

自动化回归测试默认使用 Fake LLM。关键端到端能力允许少量真实模型验收：

- 每个代表性场景最多 3 次真实调用；
- 每次失败必须记录失败原因；
- 不在无代码、prompt 或上下文调整的情况下盲目连续重试；
- 真实模型验收用于质量判断，不替代自动化测试。
