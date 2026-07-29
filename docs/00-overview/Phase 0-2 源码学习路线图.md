# Phase 0～2 源码学习路线图

> [返回文档导航](../README.md) · [项目掌握与面试准备指南](./Phase%200-2%20项目掌握与面试准备指南.md)

## 1. 路线目标

这份路线图的目标不是让你记住所有源文件，而是让你具备以下开发者能力：

```text
看得懂整体架构
→ 讲得清一次诊断主链路
→ 找得到关键业务规则
→ 分得清模型能力与确定性约束
→ 遇到失败知道从哪里定位
→ 能独立完成一个小修改并验证
```

完成路线后，你不必脱离 IDE 默写代码，但应能回答：

- 一个请求怎样进入 Agent Loop，又怎样形成最终状态？
- LLM、Strategy、Registry、Tool、Port、Adapter 分别负责什么？
- Tool Result 怎样成为 Evidence，模型为什么不能随便引用 ID？
- 如何限制模型权限、费用、循环次数、路径和敏感信息？
- Fake LLM、单元测试、集成测试和真实模型评测分别证明什么？
- 当前架构有哪些合理妥协，下一步为什么是服务目录？

---

## 2. 最快掌握源码的方法

### 2.1 不按目录顺序通读

不要从 `src/app_diagnosis/__init__.py` 开始逐个文件阅读。采用一条真实 NPE 诊断作为线索：

```text
系统如何装配
→ 请求如何进入
→ 用例如何编排
→ Agent 如何循环
→ 工具如何受控执行
→ Evidence 如何产生
→ 结论如何校验
→ 状态如何收敛
→ Trace 和 Report 如何投影
```

### 2.2 每个核心模块使用“四步学习法”

#### 第一步：预测

打开实现前，先用 Java 后端经验预测它应该承担什么职责。

#### 第二步：读主路径

第一遍只读正常成功路径，暂时跳过大量异常分支和 DTO 转换。

#### 第三步：用测试反证

配套阅读一个测试，确认哪些规则是作者真正要求必须成立的，而不是自己的猜测。

#### 第四步：运行或修改

打断点、增加临时观察点或完成一个小修改。只看懂但不能操作，还不算掌握。

### 2.3 每个文件只回答七个问题

建立自己的笔记，不要复制源码：

```markdown
## 文件 / 类名

1. 它解决什么问题？
2. 谁调用它？
3. 它调用谁？
4. 关键输入和输出是什么？
5. 哪条业务或安全规则必须放在这里？
6. 如果删除这一层，会发生什么？
7. 当前实现有什么妥协或改进空间？
```

### 2.4 三种掌握深度

| 深度 | 要求 | 典型模块 |
|---|---|---|
| A：深入掌握 | 能按方法级讲解并定位规则 | Domain、Application、ToolLoopRunner、Registry、Citation Policy |
| B：理解接口 | 知道职责、输入输出和安全边界 | Tools、Adapters、Trace、Report、Knowledge |
| C：按需查询 | 知道存在及用途，需要时能找到 | Migration、重复 CRUD、Schema 映射、Graphviz、测试 Fixture |

---

## 3. 学习前准备

### 3.1 先粗读两份文档

1. [Phase 0～2 项目掌握与面试准备指南](./Phase%200-2%20项目掌握与面试准备指南.md)
2. [Phase 2 架构与学习总结](../01-architecture/phase2-extension.md)

此时不要求记忆，只需要形成三个印象：项目解决什么问题、当前有哪些层、主链路大致往哪里走。

### 3.2 建立学习笔记

建议自行新建一份个人笔记，按以下结构记录：

```text
01-架构手绘
02-主链路
03-Evidence 生命周期
04-工具安全边界
05-失败与收敛
06-测试分层
07-问题与改进
08-面试表达
```

笔记必须用自己的语言。原文复制得越多，越难判断是否真正理解。

### 3.3 准备 Java 类比

| 当前项目 | Java 后端类比 |
|---|---|
| FastAPI Route | Spring Controller |
| ApplicationService | 应用服务 / Facade |
| DiagnosisCase | 聚合根 |
| Pydantic Model | DTO + Bean Validation |
| Port | Java Interface |
| Adapter | Interface 实现 |
| Bootstrap Container | Spring Configuration / Bean 装配 |
| SQLAlchemy Repository | JPA Repository 实现 |
| ToolLoopRunner | Agent 专用工作流编排器 |

类比是帮助入门，不代表两边实现细节完全相同。

---

## 4. 总路线

建议按 8 个学习单元推进。每个单元约 1～2 小时；工作日时间不足时，一个单元可以拆成两晚。

| 单元 | 主题 | 最终产出 |
|---|---|---|
| 0 | 项目定位与架构地图 | 一张手绘架构图 |
| 1 | 系统装配与 HTTP 入口 | 依赖装配图和请求入口说明 |
| 2 | Diagnosis 领域与应用编排 | 状态图和用例时序 |
| 3 | Strategy、Registry 与 Tool Contract | 工具授权检查表 |
| 4 | ToolLoopRunner 主循环 | 一次 Agent Run 时序图 |
| 5 | Evidence、脱敏、引用与人工确认 | Evidence 生命周期图 |
| 6 | 真实工具、Port 与 Adapter | 工具威胁模型表 |
| 7 | Trace、Report、评测与测试体系 | 测试分层图和失败定位表 |
| 8 | 综合演示、小修改与模拟面试 | 可运行演示、代码修改、3 分钟介绍 |

---

## 5. 单元 0：项目定位与架构地图

### 阅读范围

- `README.md`
- `docs/00-overview/项目介绍.md`
- `docs/00-overview/Phase 0-2 项目掌握与面试准备指南.md`
- `docs/01-architecture/phase2-extension.md`

### 学习任务

不看架构图，自己画出：

```text
API
→ Application
→ Router / Strategy
→ ToolLoopRunner
→ Registry / Tool
→ Port / Adapter
→ Evidence / Repository
→ Citation Policy
→ Domain State
→ Trace / Report / Confirmation
```

在图上用不同颜色标出：

- 概率性模型决策；
- 确定性业务约束；
- 外部基础设施；
- 持久化事实。

### 验收标准

- [ ] 能用一句话说明项目解决的问题；
- [ ] 能解释为什么它不是普通日志问答；
- [ ] 能说出 Phase 0A～2 各自解决的核心矛盾；
- [ ] 能指出当前至少五个未完成的生产能力；
- [ ] 架构图中没有把 Agent Trace 画成分布式 Trace。

未通过时：重新阅读“项目掌握指南”的第 2、4、5、8 节，不进入代码细节。

---

## 6. 单元 1：系统装配与 HTTP 入口

### A 级阅读

- `src/app_diagnosis/bootstrap/container.py`
- `src/app_diagnosis/bootstrap/settings.py`
- `src/app_diagnosis/api/routes/diagnoses.py`

### B 级浏览

- `src/app_diagnosis/api/app.py`
- `src/app_diagnosis/api/middleware.py`
- `src/app_diagnosis/api/errors.py`
- `src/app_diagnosis/api/schemas/diagnoses.py`

### 阅读顺序

1. 从 `build_diagnosis_service` 看对象怎样被组合；
2. 找出真实 LLM 和 Fake LLM 的替换点；
3. 找出哪些 Settings 决定工具是否注册；
4. 再看 `/diagnoses` 和 `/runs` 如何调用 ApplicationService；
5. 找到 Request ID、environment、工具输出上限从哪里进入运行上下文。

### 动手任务

- 列出 `DiagnosisApplicationService` 构造依赖；
- 对每个依赖标注 Domain、Port、Adapter 或 Runtime；
- 使用 IDE 的 Find Usages 查找 `build_diagnosis_service`；
- 复核项目掌握指南中记录的 `redactor` 装配疑点，暂不凭猜测修改。

### 验收标准

- [ ] 能解释为什么 Route 应保持薄；
- [ ] 能找到 LLM、Registry、EvidenceStore、Router 的装配位置；
- [ ] 能说明“工具代码存在”和“工具实际可用”不是一回事；
- [ ] 能说明未来改成 Worker 后哪些层可以复用；
- [ ] 能指出默认装配路径应由什么测试覆盖。

---

## 7. 单元 2：Diagnosis 领域与应用编排

### A 级阅读

- `src/app_diagnosis/domain/diagnosis/case.py`
- `src/app_diagnosis/domain/diagnosis/enums.py`
- `src/app_diagnosis/application/diagnoses.py`

### 配套测试

- `tests/unit/domain/diagnosis/`
- 搜索 `DiagnosisRunConflict`、`mark_inconclusive`、`record_initial_conclusion` 对应测试。

### 学习任务

画出当前真实状态机：

```text
CREATED
→ INVESTIGATING
→ WAITING_FOR_INPUT / WAITING_FOR_CONFIRMATION / INCONCLUSIVE / CANCELLED
→ CONFIRMED / REJECTED / 重新 INVESTIGATING
```

沿 `DiagnosisApplicationService.run` 标注：

- 领域状态在哪改变；
- 审计在哪写入；
- Strategy 在哪选择；
- Runner 在哪调用；
- 什么条件才记录初步结论；
- 取消如何处理。

### 必须理解的妥协

ApplicationService 当前直接使用 SQLAlchemy Session 和具体 Repository Adapter。不要把项目描述成完全纯净的六边形架构。思考未来 Unit of Work / Repository Port 能解决什么。

### 验收标准

- [ ] 能从 `run` 口述一次正常状态变化；
- [ ] 能解释为什么只有 `COMPLETED + conclusion` 才能进入等待确认；
- [ ] 能说明 `version` 与乐观并发控制的意图；
- [ ] 能区分领域状态和 AgentRun 执行状态；
- [ ] 能指出 `_active_tasks` 只解决单进程并发；
- [ ] 能解释 Application 层当前的基础设施依赖妥协。

---

## 8. 单元 3：Strategy、Registry 与 Tool Contract

### A 级阅读

- `src/app_diagnosis/agent/strategies/base.py`
- `src/app_diagnosis/agent/strategies/router.py`
- `src/app_diagnosis/agent/strategies/specialized.py`
- `src/app_diagnosis/tools/contracts.py`
- `src/app_diagnosis/tools/registry.py`

### 配套测试

- `tests/unit/agent/strategies/test_router.py`
- 搜索 Registry 的注册、权限和参数校验测试。

### 学习任务

制作一张工具授权检查表：

| 检查 | 谁负责 | 防止什么问题 |
|---|---|---|
| 工具是否注册 | Registry | 幻觉工具名 |
| 是否启用 | Registry/Bootstrap | 配置未授权能力 |
| Strategy 是否允许 | Strategy + Registry | 调查范围越界 |
| ProblemType 是否支持 | Registry | 工具用错场景 |
| Permission 是否满足 | Registry | 调用者越权 |
| 参数是否符合 Schema | Registry/Pydantic | 非法或注入参数 |
| 路径/目标是否安全 | Adapter | 目录穿越或 SSRF |

### 动手任务

任选一个 Router 测试，先预测结果再运行。然后自己构造一个同时命中两类策略的输入，验证为什么回退 Generic。

### 验收标准

- [ ] 能解释 Strategy 白名单和 Registry 校验为什么不重复；
- [ ] 能完整说出 Registry 的六层执行校验；
- [ ] 能解释 Router 为什么暂时不用 LLM；
- [ ] 能区分 Strategy 与 ProblemType；
- [ ] 能说明模型即使伪造 Tool Call，为什么也不能直接执行。

---

## 9. 单元 4：ToolLoopRunner 主循环

### A 级阅读

- `src/app_diagnosis/agent/runtime/tool_loop.py`
- `src/app_diagnosis/agent/runtime/models.py`
- `src/app_diagnosis/ports/llm/types.py`
- `src/app_diagnosis/agent/schemas/diagnosis.py`

### 阅读方法

不要一次读完全部分支。分四遍：

1. AgentRun 创建到第一次 LLM Response；
2. 有 `tool_calls` 时怎样执行并回传；
3. 无 `tool_calls` 时怎样解析和校验结论；
4. 最后再看超时、预算、结构纠错、引用纠错和工具失败。

### 学习任务

自己画一次消息历史变化：

```text
system
user
assistant(tool_calls)
tool(tool_call_id + result + evidence IDs)
assistant(final JSON)
```

再画一次状态变化：

```text
AgentRun RUNNING
→ model response count/token
→ tool call count
→ ToolRun
→ COMPLETED / INCONCLUSIVE / *_BUDGET_EXHAUSTED / MODEL_ERROR
```

### 配套测试

在测试目录搜索：

- `TOOL_BUDGET_EXHAUSTED`；
- `TIME_BUDGET_EXHAUSTED`；
- `invalid_structured_output`；
- `invalid_evidence_citations`；
- `all_tools_failed`。

每种只选一个测试阅读，不需要一次读完所有 Runner 测试。

### 验收标准

- [ ] 能不看代码讲清一次 Tool Calling 正常循环；
- [ ] 能解释为什么保留 assistant 原始 tool_calls 和 tool_call_id；
- [ ] 能指出轮次、工具次数、总时间和输出大小分别在哪里限制；
- [ ] 能区分结构纠错与引用纠错；
- [ ] 能说明为什么持续失败必须收敛为 inconclusive；
- [ ] 能在代码中定位 Evidence 持久化与 ToolRun 记录顺序。

这是核心关卡。未通过前不要急着阅读所有 Adapter。

---

## 10. 单元 5：Evidence、脱敏、引用与人工确认

### A 级阅读

- `src/app_diagnosis/domain/evidence/models.py`
- `src/app_diagnosis/ports/evidence_store.py`
- `src/app_diagnosis/adapters/persistence/evidence_store.py`
- `src/app_diagnosis/adapters/redaction/local_rules.py`
- `src/app_diagnosis/agent/policies/evidence_citations.py`

### B 级阅读

- `src/app_diagnosis/domain/confirmation/models.py`
- `src/app_diagnosis/application/evidence_diagnoses.py`
- `src/app_diagnosis/api/routes/diagnoses.py` 中 supplement/confirmation 部分。

### 学习任务

画出 Evidence 生命周期：

```text
不可信原始输入/工具结果
→ 大小与类型检查
→ Redaction
→ hash / 去重
→ Evidence 持久化
→ 正式 Evidence ID
→ 模型引用
→ Citation Policy
→ 人工确认或继续调查
```

制作引用规则表：

| 结论状态 | Evidence 要求 |
|---|---|
| probable | 至少需要用户或日志等直接证据 |
| possible | 必须给出验证建议 |
| insufficient_evidence | 不得伪造 Evidence ID |
| confirmed | 模型无权产生，只能人工确认 |

### 验收标准

- [ ] 能解释 EvidenceDraft 与正式 Evidence 的区别；
- [ ] 能解释为什么先脱敏再持久化；
- [ ] 能解释 hash 的去重和完整性作用；
- [ ] 能说明 Citation Policy 能保证什么、不能保证什么；
- [ ] 能说明 Confirmation 为什么追加保存而不是覆盖模型结论；
- [ ] 能说明补充信息为什么不应该隐式触发模型费用。

---

## 11. 单元 6：真实工具、Port 与 Adapter

### 第一条纵向切片：源码工具，深入阅读

- `src/app_diagnosis/tools/code.py`
- `src/app_diagnosis/ports/code_repository.py`
- `src/app_diagnosis/adapters/code/local_workspace.py`
- `src/app_diagnosis/domain/code_workspace.py`

沿着 `Tool → Port → Adapter` 读完整切片。

### 其余工具：比较阅读

- `tools/log_search.py` → `ports/log_reader.py` → `adapters/logs/local_file.py`
- `tools/config.py` → `ports/config_repository.py` → `adapters/config/local_workspace.py`
- `tools/health.py` → `ports/health_check.py` → `adapters/health/http_client.py`
- `tools/knowledge_search.py` → Knowledge Port/Adapter。

对其余工具不必逐行阅读，只比较：输入 Schema、Evidence 类型、超时、输出限制和安全边界。

### 学习任务

制作工具威胁模型：

| 工具 | 主要风险 | 关键约束 |
|---|---|---|
| code | 任意文件读取、超大输出 | 授权根目录、相对路径、后缀、行数 |
| log | 跨目录、混入其他事件、敏感信息 | 授权目录、事件边界、脱敏 |
| config | 密码泄漏、目录穿越 | 后缀、路径解析、行数、脱敏 |
| health | SSRF、重定向、长等待 | 配置别名、loopback、HTTP、无重定向、超时 |
| knowledge | 错误经验被当成事实 | 状态、可靠性、引用等级限制 |

### 配套测试

每种工具至少阅读一个安全失败测试，例如：

- `..` 或绝对路径；
- 非允许后缀；
- 非 loopback URL；
- 日志事件边界；
- 密码脱敏。

### 验收标准

- [ ] 能完整解释一个 Tool → Port → Adapter 调用链；
- [ ] 能说明为什么路径安全不能只靠 Pydantic；
- [ ] 能说明“READ_ONLY”为什么仍要威胁建模；
- [ ] 能列出四种工具各自最关键的安全边界；
- [ ] 能解释为什么当前不用任意 Shell 和任意 URL。

---

## 12. 单元 7：Trace、Report、评测与测试体系

### 阅读范围

- `src/app_diagnosis/application/traces.py`
- `src/app_diagnosis/domain/trace/models.py`
- `src/app_diagnosis/application/reports.py`
- `src/app_diagnosis/evaluation/runner.py`
- `tests/unit/application/test_traces.py`
- `tests/integration/test_report_and_ui.py`
- `scripts/demo-phase2.py`
- `scripts/verify-phase2.ps1`

### 学习任务一：区分三种视图

- Trace：一次 AgentRun 怎样执行；
- Report：诊断事实怎样面向用户交付；
- Audit：谁在什么时候对什么目标做了什么动作。

它们使用相同事实，但服务于不同问题，不应该混成一张表。

### 学习任务二：建立测试金字塔

```text
Domain Unit Test
→ Policy / Registry / Tool Unit Test
→ Adapter Safety Test
→ Repository / Migration Integration Test
→ API Test
→ Fake LLM Demo
→ 低频真实模型固定案例
```

为每层写下“能证明什么”和“不能证明什么”。

### 学习任务三：失败定位矩阵

| 现象 | 优先检查 |
|---|---|
| 未调用工具 | Router、Strategy 白名单、LLM tool_calls |
| 工具被拒绝 | Registry、Permission、Schema |
| 搜到错误上下文 | Adapter 事件边界/路径/关键词 |
| 模型有结论但 Run 失败 | Schema、Citation Policy、Evidence ID |
| 离线通过真实模型失败 | Prompt、Provider 差异、模型非确定性 |
| 单脚本通过总验收失败 | 环境变量、临时数据库、组合状态 |

### 验收标准

- [ ] 能区分 Agent Trace 与分布式 Trace；
- [ ] 能解释报告为什么不再次调用模型；
- [ ] 能解释 Fake LLM 和真实模型的不同职责；
- [ ] 能说明 `187 passed` 为什么不等于诊断准确率；
- [ ] 能根据一次失败判断应先看 ToolRun、Evidence、Schema 还是 Citation；
- [ ] 能说明一键验收脚本为什么也属于工程代码。

---

## 13. 单元 8：综合验收

### 13.1 运行一次完整演示

建议先使用 Fake LLM，不产生模型费用：

```powershell
cd D:\AgentStudy\application-diagnosis-platform
uv run python scripts/demo-phase1-log-code.py --keyword NullPointerException
uv run python scripts/demo-phase2.py
```

检查：

- Diagnosis ID；
- AgentRun strategy 和 termination reason；
- Log/Code/Config Evidence；
- ToolRun 中的 Evidence ID；
- Trace 时间线；
- 报告中的引用。

### 13.2 完成一个小修改

推荐任选一个：

1. 为 Router 增加一个明确但不冲突的关键词，并先写测试；
2. 为 Trace 增加一个来自现有持久化事实的安全摘要字段；
3. 为某个受限 Adapter 增加一个边界测试；
4. 为默认 Container 装配增加一个最小测试并复核 `redactor` 疑点。

修改流程必须是：

```text
写出预期
→ 补测试或复现
→ 最小修改
→ 相关测试
→ 全量 pytest / Ruff
→ 记录为什么这样改
```

### 13.3 完成三种表达

- 30 秒：项目定位；
- 3 分钟：问题、架构、真实链路、验证和边界；
- 10 分钟：Phase 演进、关键决策和真实问题复盘。

### 最终验收标准

#### 架构掌握

- [ ] 能脱离文档画出主架构；
- [ ] 能从 `/runs` 找到最终状态收敛位置；
- [ ] 能完整解释一次 Tool Calling 消息和数据生命周期；
- [ ] 能指出至少两项真实架构妥协。

#### 可信性掌握

- [ ] 能解释预算、白名单、Registry、Adapter 安全和 Citation Policy 的不同作用；
- [ ] 能解释 Evidence 与人工确认闭环；
- [ ] 能指出模型仍然可能犯错的地方。

#### 工程掌握

- [ ] 能运行离线演示和测试；
- [ ] 能根据 Trace/ToolRun/Evidence 定位一次失败；
- [ ] 能独立完成一个带测试的小修改；
- [ ] 能说明自动测试与真实模型评测的边界。

#### 面试掌握

- [ ] 3 分钟介绍不夸大为生产平台；
- [ ] 能回答为什么不用 LangGraph、向量库和多 Agent；
- [ ] 能解释下一步为什么优先服务目录；
- [ ] 能讲出至少三个“问题—根因—修复—经验”案例；
- [ ] 遇到不会的问题能明确当前边界和验证方案，而不是编造答案。

全部通过后，才建议开始服务目录开发。

---

## 14. 卡住时怎样提问

遇到不确定问题时，建议带着以下信息来沟通：

```text
我正在学习：单元 X / 文件 Y / 方法 Z
我认为它的职责是：……
调用方和被调用方是：……
我不确定的是：……
我的两个猜测是：A……；B……
对应测试或运行现象是：……
```

这种提问方式能让讨论直接进入设计和代码，而不是重新概括整份项目。

---

## 15. 学习进度记录模板

复制下面的表到个人笔记中：

| 单元 | 阅读完成 | 图/表产出 | 能口述 | 动手验证 | 遗留问题 |
|---|---|---|---|---|---|
| 0 项目地图 |  |  |  |  |  |
| 1 装配与入口 |  |  |  |  |  |
| 2 领域与编排 |  |  |  |  |  |
| 3 Strategy/Registry |  |  |  |  |  |
| 4 ToolLoopRunner |  |  |  |  |  |
| 5 Evidence 闭环 |  |  |  |  |  |
| 6 Tool/Port/Adapter |  |  |  |  |  |
| 7 Trace/测试 |  |  |  |  |  |
| 8 综合验收 |  |  |  |  |  |

不要用“看过”作为完成标准。至少同时满足“能口述”和“完成产出”，才将一个单元标记为完成。
