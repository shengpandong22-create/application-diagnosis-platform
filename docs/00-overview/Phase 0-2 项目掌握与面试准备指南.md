# Phase 0～2 项目掌握与面试准备指南

> 这不是一份功能清单，也不是背诵式面试题库。它试图以项目开发者的身份回答四个问题：为什么做、为什么这样做、代码怎样实现、我是否真的掌握。

## 1. 使用方式

建议按以下顺序使用本文：

1. 先理解项目背景和问题定义，不急着背技术名词；
2. 再复盘 Phase 0A～Phase 2 为什么逐层出现；
3. 按第一轮代码走读路线亲自打开代码、打断点和运行案例；
4. 用“掌握度验收”检查自己能否脱离文档讲清楚；
5. 最后才使用面试表达和追问题库。

本文描述的是当前真实实现。设计目标与当前能力不一致的地方会明确标注，不把规划包装成已经完成的功能。

---

## 2. 为什么要开发这个项目

### 2.1 背景：大模型带来了新的排障交互方式

传统应用排障依赖开发者手工完成一条长链路：阅读错误日志、搜索历史案例、定位源码、检查配置和下游状态，再把零散信息组织成根因判断。这个过程高度依赖经验，信息分散，而且重复性很强。

大模型的价值不只是“解释一段异常”，而是可以在受控工具的帮助下循环完成：

```text
理解现象
→ 提出待验证方向
→ 选择最小取证动作
→ 读取日志、源码、配置、知识或健康状态
→ 根据新证据继续调查
→ 输出结论、依据和待确认信息
```

这让“自发现式 BUG 定位”成为可能：用户不需要预先告诉系统应该查哪个类、哪段配置，Agent 可以根据现场信息自主选择下一步。

### 2.2 但“模型会分析”不等于“诊断系统可信”

如果只把日志粘贴给模型，系统仍有几个根本问题：

- 模型可能给出听起来合理但没有依据的根因；
- 模型可能引用不存在或属于其他诊断的证据；
- 日志和源码可能包含密码、Token 与提示注入文本；
- Agent 可能无限循环、反复调用模型或越权读取文件；
- 模型的结论、人工判断和真实修复结果可能被混为一谈；
- 一次偶然成功无法证明系统能够稳定工作；
- 更换模型、数据库或知识实现可能牵动核心流程。

因此，本项目真正解决的不是“如何调用大模型”，而是：

> 如何把概率性的模型推理放进一个有边界、可追踪、可验证、可人工接管的工程系统中。

### 2.3 项目目标

项目希望形成以下闭环：

```text
真实故障输入
→ 受控取证
→ 脱敏 Evidence
→ 模型提出结构化结论
→ 本地规则校验证据引用
→ 人工确认、驳回或继续调查
→ Trace、审计和报告保留过程
→ 后续把已验证经验沉淀为知识
```

这里有三个关键词：

- **自发现**：Agent 根据现象动态选择工具，不要求用户提前给出完整排查步骤；
- **证据驱动**：事实和根因必须引用系统实际持有的 Evidence；
- **人机闭环**：模型只能提出候选判断，最终确认权仍在人或后续修复验证。

### 2.4 为什么使用 Java Lab + Python Agent

项目不是凭空生成一段模拟日志。Java Lab 提供可重复触发的 NPE、连接拒绝和超时故障，Python 平台负责诊断。这一组合有三层价值：

1. 日志来自真实 Spring Boot 执行路径，而不是为了迎合模型临时编写；
2. 可以验证日志行号、异常类型与 Java 源码是否一致；
3. 展示 Java 后端经验如何迁移到 Python Agent 工程，而不是抛弃原有能力。

---

## 3. 项目不是一开始就长成现在这样

### 3.1 最初的选择：复用思路，不复用运行时

早期讨论围绕 ITOps Agent Platform 展开。最终没有直接在 TypeScript 项目中继续堆功能，而是建立独立 Python 项目：

- ITOps 代码作为架构、边界和反例参考；
- 新项目不 import ITOps 源码，不共享数据库和全局单例；
- 外部模型、知识、持久化和未来 ITOps 集成通过 Port/Adapter 隔离；
- 优先满足一台 16GB 笔记本上的单机开发和离线验收。

这个决定服务于学习目标：既能练习 Python Agent 开发，又能理解一个系统为什么需要稳定核心和可替换基础设施。

### 3.2 为什么不一开始做 RAG、多 Agent 或自动修复

这些能力看起来更“像 AI”，但无法回答最基本的问题：

- 一次诊断是否能够结束？
- 工具调用是否受控？
- 结论引用的证据是否真实存在？
- 敏感信息是否已经在入库前脱敏？
- 模型失败后系统状态是否仍正确？
- 自动测试是否会偷偷产生模型费用？

因此项目采用纵向闭环策略：先让最小流程真实可运行，再逐层补可信性、评测、现场信息和可观测性。

---

## 4. Phase 0A～Phase 2 的决策演进

### 4.1 Phase 0A：先证明最小 Agent Loop 可控运行

#### 当时的问题

只有模型调用还不是 Agent。系统需要允许模型选择工具，同时防止无限循环、越权调用和非结构化结果污染领域状态。

#### 做出的选择

- `DiagnosisCase` 表达诊断状态，而不是用几个 API 字段拼流程；
- `LLMClient` Port 隔离 DeepSeek/OpenAI-compatible 实现；
- Strategy 负责提示和工具白名单；
- Registry 在执行边界再次校验工具、权限、问题类型和参数 Schema；
- ToolLoopRunner 负责消息协议、轮次、工具次数和总时间预算；
- AgentRun/ToolRun 记录实际执行和终止原因；
- Fake LLM 负责默认测试，真实模型只做显式低频联调。

#### 形成的认识

Prompt 只能引导模型，不能承担权限控制。真正的安全边界必须由确定性代码执行。

### 4.2 Phase 0B：从“模型给答案”升级到“证据驱动结论”

#### Phase 0A 暴露的问题

结构化 JSON 只能证明格式正确，不能证明内容真实。模型仍可能给出无依据结论或伪造引用。

#### 做出的选择

- 引入 Evidence Domain，区分用户陈述、日志、知识等来源；
- EvidenceDraft 落库后才产生可引用的正式 ID；
- Redaction 在持久化和进入模型之前执行；
- Citation Policy 检查引用归属和可信度规则；
- `probable` 需要日志或用户事实，只有知识条目最多为 `possible`；
- `confirmed` 保留给人工确认；
- Supplement、Confirmation 和 Audit 采用追加记录，不覆盖模型原结论。

#### 形成的认识

LLM 负责提出候选判断，本地 Policy 负责不可妥协的业务约束。人工确认是新的事实，不是对历史事实的覆盖。

### 4.3 Phase 0C：从“能运行”升级到“能评测、能交付”

#### Phase 0B 暴露的问题

一次演示成功无法证明质量，数据库中的结果也不适合直接交付给用户。

#### 做出的选择

- 固定评测案例和期望结果；
- 报告从已持久化事实生成，不再次调用模型；
- 报告聚合时重新检查引用，不盲信历史数据；
- 极简 UI 只调用 API，不在浏览器重新实现业务规则；
- 一键验收明确禁止默认调用外部模型。

#### 形成的认识

测试通过、模型质量和用户可读性是三个不同问题，必须分别验证。

### 4.4 Phase 1：从粘贴日志走向真实日志与源码联合诊断

#### Phase 0 暴露的问题

只有日志和预置知识时，系统常常只能给出通用候选原因，无法证明具体代码位置为什么出错。

#### 做出的选择

- 建立独立 Java 故障实验室；
- 固定日志文件和可重复触发的故障案例；
- 日志读取只允许授权目录和有限事件窗口；
- 源码搜索/读取只允许配置工作区、相对路径、有限后缀和行数；
- 日志形成 Log Evidence，源码形成 Code Evidence；
- 低频使用真实模型验证 NPE、连接拒绝和超时，失败后先分析轨迹再复验。

#### 形成的认识

真实模型失败不一定是“模型不会推理”。失败可能发生在日志边界、代码检索、Schema、Evidence ID 回传或最终引用修正的任一环节。

### 4.5 Phase 2：让 Agent 可观察、有选择、能感知更多现场信息

#### Phase 1 暴露的问题

工具增多后，使用者很难快速回答：选了什么策略、调用了哪些工具、每个工具产生了哪些证据、为什么最终结束。

#### 做出的选择

- Agent Trace 从 AgentRun、ToolRun、Evidence 构造确定性时间线；
- Tool 产生 Evidence 后，把正式 Evidence ID 写回 ToolRun；
- 增加受限的配置读取、日志搜索和本地健康检查；
- Strategy Router 用确定性规则选择 Application、Network、Configuration 或 Generic；
- 路由不额外调用 LLM，信号并列或无命中时安全回退；
- 仍不增加 Shell、自动修复和任意 URL。

#### 形成的认识

“只读”不等于“没有风险”：配置可能泄密、文件可能越界、健康检查可能形成 SSRF。Agent Trace 也只能展示持久化过的事实，不能为了好看伪造逐轮事件。

### 4.6 一张因果表

| 阶段 | 上一阶段留下的核心问题 | 新增的确定性能力 |
|---|---|---|
| 0A | 模型和工具会不会失控 | 状态机、Registry、预算、结构化输出 |
| 0B | 结构化结论是否有真实依据 | Evidence、脱敏、引用策略、人工确认 |
| 0C | 如何证明可重复、如何交付 | 评测、报告、极简 UI、一键验收 |
| 1 | 如何从通用判断走到具体代码 | 真实日志、受限源码、Java Lab |
| 2 | 如何看见过程并扩大安全决策空间 | Trace、Router、配置/日志/健康工具 |

---

## 5. 当前架构：确定性系统包围概率性模型

理解本项目最重要的不是记住“五层架构”，而是看清职责分布：

```text
FastAPI Route
→ DiagnosisApplicationService
→ DiagnosisStrategyRouter
→ ToolLoopRunner
   ├→ LLMClient Port → OpenAI-compatible/Fake LLM
   ├→ Tool Registry → Diagnostic Tool → Port → Adapter
   ├→ EvidenceStore → Evidence
   └→ Citation Policy
→ DiagnosisCase 状态收敛
→ Trace / Report / Confirmation
```

其中 LLM 负责：

- 理解非结构化现象；
- 选择当前允许的工具；
- 综合工具结果；
- 提出结构化候选结论。

确定性代码负责：

- 状态是否合法；
- 哪些工具可见和可调用；
- 参数是否合法、路径是否越界；
- 是否超出轮次、工具数和时间预算；
- Evidence 是否真实存在并属于当前 Diagnosis；
- 模型是否越权使用 `confirmed`；
- 最终结果应该完成、等待输入还是 inconclusive。

一句话概括：

> 不是相信模型永远做对，而是确保模型犯错时，系统仍能受控失败并留下证据。

---

## 6. 第一轮真实代码架构走读

### 6.1 本轮目标

本轮只跟踪“一次诊断从 HTTP 请求到可信结论”的主干。完成后应能回答：

- 谁负责接收请求，谁负责业务编排？
- Strategy 和 Registry 为什么都要限制工具？
- 一次 LLM Tool Calling 如何进入下一轮？
- Evidence ID 何时产生，为什么不能提前产生？
- 最终结论在哪两层校验？
- 诊断状态何时改变？
- 失败时为什么不会伪装成成功？

### 6.2 第 0 站：先看装配，不从 API 猜依赖

文件：`src/app_diagnosis/bootstrap/container.py`

关注 `build_diagnosis_service`：

1. 根据 Settings 决定哪些工具真正注册；
2. Local Adapter 被注入 Tool；
3. Registry、EvidenceStore、CitationPolicy 被注入 ToolLoopRunner；
4. 多个 Strategy 和 Router 被注入 ApplicationService；
5. 默认 LLM 可以替换为 Fake LLM。

要理解的设计点：工具“代码存在”、工具“已注册”、Strategy“允许使用”和调用者“拥有权限”是四个不同条件。

当前走读待复核项：容器当前向 `DiagnosisApplicationService` 传入 `redactor`，而已读取到的构造函数签名中没有该参数。已有最小报告/UI 集成测试没有覆盖这一默认装配路径；应以离线演示或专门容器装配测试确认。这是学习材料中的真实发现，不应在未验证前把它写成已修复问题。

### 6.3 第 1 站：HTTP 入口保持薄

文件：`src/app_diagnosis/api/routes/diagnoses.py`

先读两个接口：

- `create_diagnosis`：DTO 转成应用服务参数；
- `run_diagnosis`：传入 actor、environment、request ID 和工具输出上限。

Route 不应该：

- 直接操作 SQLAlchemy；
- 自己调用 LLM；
- 自己推进状态机；
- 自己判断 Evidence 引用是否可信。

面试追问“为什么薄 API”时，不要只说解耦。更具体的答案是：未来把同步 HTTP 触发换成 Worker 消费任务时，应用用例仍可复用。

### 6.4 第 2 站：Application Service 编排一次用例

文件：`src/app_diagnosis/application/diagnoses.py`

沿 `run` 阅读：

1. `_active_tasks` 防止同一 Diagnosis 在单进程内重复运行；
2. `_start_investigation` 检查状态、推进状态并写审计；
3. Router 每次 Run 重新选择 Strategy；
4. 构造 ToolLoopContext，明确权限和输出限制；
5. 调用 ToolLoopRunner；
6. `_apply_result` 只在 `COMPLETED + conclusion` 时记录初步结论，否则进入 `INCONCLUSIVE`；
7. CancelledError 被转换成领域取消状态。

必须诚实理解的当前妥协：ApplicationService 目前直接依赖 SQLAlchemy Session 和具体 Repository Adapter。这说明项目具备 Ports & Adapters 的主要方向，但还不是“应用层完全不依赖基础设施”的纯六边形实现。未来服务目录或 Worker 改造时，可以再抽 Unit of Work / Repository Port；面试中不要声称核心层零基础设施依赖。

### 6.5 第 3 站：Router 选择调查方法

文件：`src/app_diagnosis/agent/strategies/router.py`

`select` 把标题、现象和日志合并，按规则计算三个策略得分：

- NPE、异常栈、HTTP 500 → Application；
- 连接拒绝、Timeout、DNS → Network；
- 配置缺失、占位符解析失败 → Configuration；
- 无命中或最高分并列 → Generic。

为什么不用 LLM 路由：

- 避免每次诊断增加一次费用和延迟；
- 规则结果可测试、可解释；
- 不确定时回退 Generic，不伪造确定性。

当前边界：这是调查策略路由，不是完整的五类业务问题模型。`ProblemType` 目前仍以 generic 为主。

### 6.6 第 4 站：ToolLoopRunner 是 Agent Runtime 核心

文件：`src/app_diagnosis/agent/runtime/tool_loop.py`

建议分五段阅读。

#### A. 启动 Run

- 要求 Diagnosis 已是 `INVESTIGATING`；
- 创建并持久化 AgentRun；
- 从 Strategy 得到允许工具；
- Registry 只向模型暴露通过校验的 ToolDefinition；
- 构造系统提示、结构化 Schema 和现有 Evidence 目录。

#### B. 调用模型

- 每轮受总时间预算约束；
- 记录模型、Token 和轮次；
- LLM 错误和超时转换为明确 termination reason。

#### C. 执行工具

- assistant 原始 `tool_calls` 进入消息历史；
- Registry 再校验名称、启用状态、Strategy、ProblemType、权限和参数；
- Tool 有独立超时和输出限制；
- 工具结果不会直接被视为可信系统指令。

#### D. Evidence 生命周期

```text
ToolExecutionResult
→ EvidenceDraft / Candidate
→ Redaction + Repository
→ 正式 Evidence ID
→ 写入 ToolRun.result_json
→ 回传模型上下文
```

这条顺序解决了两个问题：模型只能引用真实落库 ID；Trace 可以准确知道哪个 ToolRun 产生了哪些 Evidence。

#### E. 结论收敛

- 首先用 Pydantic 解析结构化结论；
- 格式不合法时只进行有限纠错；
- Citation Policy 校验引用，失败时进行有限引用纠错；
- 工具全部失败、预算耗尽、持续不合法时返回 inconclusive；
- 只有校验通过才以 `COMPLETED` 结束。

### 6.7 第 5 站：Registry 是执行边界，不是工具列表

文件：`src/app_diagnosis/tools/registry.py`

重点查看 `resolve` 和 `parse_arguments`。一次工具调用必须同时满足：

```text
工具已注册
AND 工具已启用
AND Strategy 允许
AND 支持当前 ProblemType
AND 调用上下文具有权限
AND JSON 参数符合 Pydantic Schema
```

Strategy 白名单解决“当前诊断应该让模型看到什么”；Registry 解决“即使模型请求了，也是否真的允许执行”。两者不是重复设计，而是决策层和执行层的双重边界。

### 6.8 第 6 站：Citation Policy 限制模型能说到什么程度

文件：`src/app_diagnosis/agent/policies/evidence_citations.py`

重点规则：

- 引用 ID 必须存在于当前 Diagnosis 的 Evidence 集合；
- 模型不能输出 `confirmed`；
- `probable` 需要用户陈述或日志等直接证据；
- `insufficient_evidence` 不能伪造引用；
- possible 需要验证建议。

Citation Policy 能证明的是“引用合法、结论等级满足规则”，不能证明“模型的因果推理一定正确”。最终正确性仍需要真实评测和人工/修复验证。

### 6.9 第 7 站：DiagnosisCase 保证状态不会被 API 随意改写

文件：`src/app_diagnosis/domain/diagnosis/case.py`

关注 `_ALLOWED_TRANSITIONS`、`record_initial_conclusion` 和 `_transition_to`：

- 状态变化只能走领域方法；
- 非法跳转立即失败；
- 每次状态变化更新 UTC 时间和 version；
- 有缺失信息进入 `WAITING_FOR_INPUT`；
- 有初步结论进入 `WAITING_FOR_CONFIRMATION`；
- 人工确认和模型结论是不同阶段。

### 6.10 本轮主链路复述

完成走读后，应能不看本文复述：

```text
POST /diagnoses/{id}/runs
→ ApplicationService 防重复并推进 investigating
→ Router 选择 Strategy
→ Runner 创建 AgentRun 并获取允许工具
→ LLM 返回 tool_calls
→ Registry 做确定性校验
→ Tool 通过 Port/Adapter 读取受限现场
→ 脱敏结果落为 Evidence
→ 正式 Evidence ID 写入 ToolRun 并回传模型
→ LLM 输出结构化结论
→ Pydantic + Citation Policy 校验
→ ApplicationService 推动 DiagnosisCase 收敛
→ Trace、Report 和人工 Confirmation 使用已持久化事实
```

---

## 7. 开发过程中遇到的问题，以及它们改变了什么

### 7.1 SQLite 首次迁移失败

测试临时目录已经存在，掩盖了真实首次安装时父目录缺失的问题。修复不仅是创建目录，更重要的经验是：测试环境的便利条件可能隐藏生产初始化缺陷。

### 7.2 DeepSeek 结构化输出返回 400 或 Schema 不合格

问题不是简单换 Prompt，而是 Provider 能力存在差异。项目增加响应格式能力配置，同时仍以本地 Pydantic Schema 作为最终边界。经验是：供应商声明的兼容协议不等于行为完全一致。

### 7.3 未完成运行错误推进状态

早期路径可能把非完整运行当成有效结论。修复后只有 `COMPLETED + valid conclusion` 才推进等待确认，其他情况明确收敛为 inconclusive。经验是：Agent 的成功不能用“函数没有抛异常”定义。

### 7.4 日志窗口混入后续异常

固定行数截取会把下一个异常事件混入同一 Evidence，既浪费 Token，也可能误导模型。后来按事件边界提取最近一次相关异常。经验是：输入质量问题经常被误判成模型推理问题。

### 7.5 超时案例真实模型遗漏日志 Evidence

模型已经成功读取日志和源码，但最终引用修正时遗漏已有日志 ID，导致结论未通过 Policy。解决方式不是反复调用碰运气，而是补齐最终 Evidence 目录、拆分结构纠错与引用纠错，再低频复验。

### 7.6 ToolRun 与 Evidence 无法准确关联

如果先保存 ToolRun 再保存 Evidence，Trace 无法获得正式 ID，只能按时间猜测。Phase 2 调整为 Evidence 先落库、ID 再写回 ToolRun。经验是：可观测性不是最后加一个页面，而会反向影响数据生命周期设计。

### 7.7 一键验收环境变量污染临时数据库

Phase 2 demo 单独成功，嵌入总验收后却受外层 `APP_DATABASE_URL` 影响。修复为在临时迁移期间隔离并恢复环境变量。经验是：脚本也是产品代码，组合执行能发现单脚本无法发现的问题。

### 7.8 第一轮走读发现的覆盖盲区

当前容器装配参数存在待复核的一致性疑点，而最小报告/UI 测试仍能通过，说明测试可能绕过默认启动路径。这里应采取的开发者动作是：

1. 不凭阅读片段直接宣布缺陷；
2. 找到覆盖默认 container 的测试或运行离线 demo；
3. 如果确认失败，先补一个会失败的装配测试；
4. 再做最小修复并执行全量验收；
5. 把根因记录为“测试覆盖与真实启动路径错位”。

---

## 8. 当前实现的诚实边界

面试中主动说明边界，比把项目包装成生产平台更有说服力：

- 当前是单机工程骨架，没有独立 Worker 和可靠任务队列；
- `_active_tasks` 只解决单进程并发，不解决多实例分布式互斥；
- 当前 Agent Trace 是执行记录投影，不是真实 OTel 分布式 Trace；
- Router 是确定性关键词路由，不是完整的五类业务策略；
- 代码工作区是本地授权快照，尚未绑定真实 deployed commit；
- 没有服务目录，日志、源码、配置和健康目标仍主要来自配置；
- Citation Policy 校验引用规则，不保证因果结论绝对正确；
- Fake LLM 验证工程流程，不能替代真实模型质量评估；
- Application 层仍直接使用 SQLAlchemy Session 和具体 Repository，是当前 MVP 妥协；
- 没有自动修复、任意 Shell、自动 confirmed 知识，这是刻意保留的安全边界。

下一步服务目录的价值，正是把 service、environment、log source、repository、deployed commit、config 和 health target 统一绑定，而不是简单再增加 CRUD。

---

## 9. 从项目理解到面试表达

### 9.1 30 秒版本

> 我开发了一个证据驱动的应用诊断 Agent。它可以读取真实 Java 应用产生的故障日志，并在授权范围内搜索源码、配置和健康状态。系统不是直接相信模型结论，而是把工具结果脱敏后持久化为 Evidence，通过本地引用策略校验结论，再由人工确认、驳回或继续调查，最终生成 Agent Trace 和诊断报告。

### 9.2 3 分钟版本

建议采用“问题—设计—验证—边界”结构：

1. **问题**：普通日志问答无法保证结论有依据，也无法控制工具权限和成本；
2. **设计**：使用 Diagnosis 状态机、Strategy/Registry、有界 ToolLoopRunner、Evidence 和 Citation Policy；
3. **真实化**：Java Lab 产生 NPE、连接拒绝和超时，Agent 读取日志和源码联合诊断；
4. **可信闭环**：脱敏、人工确认、审计、报告和 Trace；
5. **验证**：Fake LLM 做确定性回归，真实模型只对固定案例低频验收；
6. **边界**：当前仍是单机实现，下一步需要服务目录和 deployed commit 绑定。

### 9.3 10 分钟版本

不要逐个报功能。按 Phase 的因果关系展开：

```text
0A 解决失控
→ 0B 解决无依据
→ 0C 解决不可评测与不可交付
→ 1 解决缺少真实现场和代码定位
→ 2 解决过程不可见与策略单一
```

每个阶段只讲一个核心矛盾、一个关键设计和一个真实问题。

---

## 10. 高频面试问题与回答要点

### 10.1 这和直接把日志发给 ChatGPT 有什么区别？

直接问答主要依靠输入上下文和模型自律。本项目拥有受控工具、执行预算、证据持久化、引用校验、状态机、人工确认和审计。模型可以提出候选结论，但不能绕过确定性规则把猜测变成 confirmed。

### 10.2 为什么不用 LangGraph？

当前核心流程是一个有界 Tool Calling Loop，自己实现能直接掌握消息协议、tool_call_id、预算、持久化和引用纠错。LangGraph 适合更复杂的图状态、分支和持久恢复；在没有证明当前循环成为瓶颈前引入，会增加抽象和学习成本。未来出现多阶段 Planner 或 Worker 恢复需求时可以重新评估。

### 10.3 这是 ReAct 吗？

它接近工具调用式 ReAct：模型根据观察选择下一工具，再根据结果继续推理。但当前没有显式持久化 Thought，也没有 Plan-then-Execute。项目更准确的描述是有界、可持久化的 Tool Calling Agent Loop。

### 10.4 Strategy 白名单和 Registry 校验是否重复？

不重复。Strategy 决定当前调查方法应该向模型暴露哪些工具；Registry 是执行时安全边界，即使模型伪造调用，也要验证注册、启用、白名单、问题类型、权限和参数。

### 10.5 如何防 Prompt Injection？

不依赖一句“忽略恶意指令”的 Prompt。日志和工具结果标记为不可信内容；模型只看到 Strategy 授权工具；Registry 执行确定性权限和参数校验；文件路径和健康目标在 Adapter 层再次限制；输出还要经过结构化和引用 Policy 校验。

### 10.6 Evidence 为什么不能在工具执行前生成 ID？

工具结果可能失败、被脱敏、被截断或去重。只有持久化完成后才能确定系统真正持有的 Evidence。提前生成并回传会让模型引用一个可能不存在的对象。

### 10.7 Citation Policy 是否能消除幻觉？

不能。它能阻止未知 Evidence ID、不符合可信度规则的结论等级以及模型自行 confirmed，但无法证明引用证据和根因之间的因果关系一定成立。还需要固定评测、真实模型验收和人工/修复验证。

### 10.8 为什么默认测试不用真实模型？

真实模型有费用、网络和非确定性，无法作为稳定单元测试依赖。Fake LLM 用于验证协议、状态、工具调用和引用流程；固定真实案例用于低频评估模型综合能力。两者验证对象不同。

### 10.9 如何控制 Agent 成本和失控风险？

限制最大轮次、工具调用数、总时间、单工具超时和输出字节；工具不可用时不暴露；结构和引用纠错次数有限；预算耗尽或持续失败返回 inconclusive，而不是无限重试。

### 10.10 Memory 在哪里？

当前有三类持久信息，但不应都叫 Memory：Diagnosis/Evidence 是单次案件状态，KnowledgeEntry 是跨案件可复用知识，AgentRun/ToolRun 是执行历史。当前没有自动长期经验学习，candidate 到 confirmed 仍需人工审核。

### 10.11 为什么下一步不是 Planner？

当前还没有固定复杂案例证明 ReAct 无法完成任务。相比之下，服务、环境、日志源和 deployed commit 尚未绑定，这是诊断准确性的现实缺口。先解决诊断对象身份，再用复杂案例观察是否真的需要 Planner。

### 10.12 如果上生产还缺什么？

服务目录、部署 commit 映射、远程日志/Trace/指标 Adapter、Worker 与可靠队列、分布式锁或租约、认证与 RBAC、PostgreSQL、高可用、密钥管理、模型质量统计、数据保留策略和安全审计。

---

## 11. 掌握度验收

### 11.1 不看文档完成

- 画出 API → Application → Router → Runner → Registry → Tool → Evidence → Policy → Domain 的主链路；
- 解释 Phase 0A～2 每一步解决了上一阶段什么问题；
- 用 3 分钟讲清项目，且不把规划说成已完成；
- 说明 Agent Trace 与分布式 Trace 的区别；
- 说明 Citation Policy 能保证什么、不能保证什么。

### 11.2 看代码完成

- 从 `/runs` Route 跟到 `DiagnosisCase.record_initial_conclusion`；
- 找到 Strategy 工具白名单和 Registry 执行校验；
- 找到 Evidence 落库、正式 ID 写回 ToolRun 的顺序；
- 找到结构纠错和引用纠错的次数边界；
- 找到三个受限工具的路径/目标安全规则；
- 找到一个当前架构妥协，并说明未来如何演进。

### 11.3 动手完成

1. 亲自触发 Java Lab NPE；
2. 使用离线 Phase 1 脚本生成日志和代码 Evidence；
3. 在 Trace 中找到 ToolRun 与 Evidence ID；
4. 在报告中核对引用；
5. 修改一个 Router 规则并先补测试；
6. 运行 Ruff、全量 pytest 和一键验收；
7. 复核走读中发现的默认容器装配疑点。

### 11.4 通过标准

满足以下条件后再进入服务目录开发：

- 能独立解释主链路，而不是照着架构图念；
- 能讲出至少三个真实问题、根因、修复和经验；
- 能区分模型问题、检索问题、引用问题和工程问题；
- 能完成一个带测试的小修改；
- 能诚实说明至少五项当前边界；
- 面对追问时能够回到代码或数据生命周期，而不是只回答概念。

---

## 12. 建议学习安排

| 学习日 | 内容 | 产出 |
|---|---|---|
| 1 | 项目背景、边界和 Phase 演进 | 手绘架构与阶段因果表 |
| 2 | 第一轮主链路代码走读 | 一份自己的调用链笔记 |
| 3 | Evidence、Redaction、Citation、Confirmation | 可信性边界说明 |
| 4 | Tool、Port、Adapter 与安全限制 | 工具威胁模型表 |
| 5 | 测试、Fake LLM、真实模型评测 | 测试分层说明 |
| 6 | Java Lab 演示与问题复盘 | 3 分钟项目演示 |
| 7 | 模拟面试与小改动 | 掌握度验收记录 |

完成这一轮后，再进入服务目录。届时由你先给出领域草图和验收标准，再借助 AI 评审与实现，才能把服务目录变成学习成果，而不只是新增代码。

---

## 13. 延伸阅读路线

- 总体边界：[独立应用诊断闭环平台设计文档](../02-specifications/独立应用诊断闭环平台设计文档.md)
- Phase 0A：[独立骨架与最小 Agent Loop](../01-architecture/phase0a-framework.md)
- Phase 0B：[Evidence 与人工闭环](../01-architecture/phase0b-extension.md)
- Phase 0C：[评测、报告与极简界面](../01-architecture/phase0c-extension.md)
- Phase 1：[真实日志与受限源码](../01-architecture/phase1-extension.md)
- Phase 2：[可观测、多策略与现场工具](../01-architecture/phase2-extension.md)
- 真实问题复盘：[Phase 1 当前能力总结](../03-progress/2026-07-17-Phase1当前能力总结.md)
- 最新阶段总结：[Phase 2 开发总结](../03-progress/2026-07-18-Phase2开发总结.md)

本文是第一版掌握指南。后续每轮代码走读不应继续无限扩充同一篇文档，而应形成独立走读记录，并在这里维护学习顺序与掌握状态。
