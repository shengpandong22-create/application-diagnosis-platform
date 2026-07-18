# Phase 0C 扩展图：评测、报告与极简界面

> [返回文档导航](../README.md)

![Phase 0C 扩展图](./phase0c-extension.svg)

## 与 Phase 0A、0B 的关系

Phase 0C 不改变 Agent Loop 和证据规则，而是在已有闭环外增加三个消费入口：

| 既有基础 | Phase 0C 使用方式 |
|---|---|
| Phase 0A AgentRun / ToolRun / termination reason | 形成可重复评测观察值和运行摘要 |
| Phase 0B Evidence / Citation Policy | 报告再次验证引用归属并展示依据 |
| Phase 0B Confirmation | 报告区分模型结论和人工决定 |
| Phase 0A/0B API | `/ui` 只调用 API，不复制领域规则 |

## 三项新增能力

1. Evaluation：固定 Case 和确定性 Observation 生成机器可读指标，默认不调用真实模型；
2. DiagnosisReport：按需聚合现有数据，输出 JSON/Markdown，不再次调用 LLM；
3. Minimal UI：使用原生 HTML/CSS/JavaScript 完成核心闭环操作，无独立前端构建。

## 深度学习：Phase 0C 为什么不是“补一个页面和报告”

### 1. Phase 0C 的架构定位是消费与验证层

Phase 0A 建立可控执行，Phase 0B 建立证据与人工闭环，Phase 0C 回答另外三个问题：

```text
系统每次修改后，怎样知道核心规则没有退化？       → Evaluation
诊断完成后，怎样把分散记录变成可交付结果？       → DiagnosisReport
没有独立前端团队时，怎样验证完整的人机操作闭环？ → Minimal UI
```

因此 Phase 0C 没有增加新的模型推理能力。它把已经存在的 Diagnosis、Evidence、AgentRun、ToolRun 和 Confirmation 组织成可验证、可阅读、可操作的产品表面。

### 2. 为什么确定性回归与模型质量评测必须分开

两类评测回答的问题不同：

| 类型 | 回答的问题 | 是否应依赖真实模型 | 当前 Phase 0C 覆盖 |
|---|---|---|---|
| 系统规则回归 | Schema、Evidence 引用、工具记录、终止原因是否仍符合约束 | 默认否 | 是 |
| 模型质量评测 | 模型找到的根因、证据和建议是否准确 | 是 | 仅保留扩展位置 |

如果把真实模型直接放进默认回归，模型波动、网络状态和供应商版本会让测试不稳定，也会产生费用。反过来，只用 Fake LLM 又不能证明真实诊断质量。因此当前策略是：默认评测验证确定性基础设施，真实模型验收单独、低频、留痕执行。

### 3. Evaluation Case、Observation 与 Result 为什么分层

评测不是在测试中写几个 `assert` 就结束。三个对象表达不同事实：

| 对象 | 含义 | 示例 |
|---|---|---|
| EvaluationCase | 期望什么 | 必须出现 `log_excerpt`，终止原因为 `completed` |
| EvaluationObservation | 实际发生什么 | 本次 Evidence 类型、工具成功率、根因文本、终止原因 |
| EvaluationResult | 期望与实际的比较 | 通过/失败及每条失败原因 |

这样做的价值是把“采集事实”和“判定标准”分开。同一份 Observation 未来可以用不同门槛重新评分，也可以输出机器可读 JSON 供 CI 使用。

### 4. 当前评测指标能证明什么，不能证明什么

当前指标适合发现工程回归，例如：

- 模型输出不再符合结构化 Schema；
- 结论引用了不存在或不属于当前诊断的 Evidence；
- 必需证据类型没有产生；
- 工具大量失败；
- Agent 没有按预期终止；
- 根因文本缺少固定案例的关键语义。

但关键词命中不等于语义正确，工具成功率高也不等于调查路径合理。一个错误结论可能碰巧包含预期关键词。因此这些指标是最小回归护栏，不是完整的 LLM-as-a-Judge、专家评分或线上效果统计。

### 5. 报告为什么必须是事实投影

报告生成阶段不再调用 LLM，而是读取并聚合已经持久化的数据：

```text
Diagnosis + Conclusion + Evidence + AgentRun + Confirmation
  → 校验引用归属
  → DiagnosisReport DTO
  → JSON / Markdown 表示
```

如果报告阶段再次调用模型，可能出现“数据库中的原结论”和“报告里改写后的结论”不一致，也会产生隐式费用和不可追踪的新事实。事实投影保证报告是闭环记录的一种视图，而不是第二次诊断。

### 6. 为什么报告边界还要再次校验 Evidence

Citation Policy 在结论写入前已经校验引用，但报告属于新的消费边界。数据可能来自旧版本、手工迁移或异常写入，因此不能假设历史数据永远合法。

再次校验遵循防御性读取原则：

- 引用 ID 必须存在；
- Evidence 必须属于当前 Diagnosis；
- 报告不能把其他诊断的内容拼接进来；
- 模型结论与人工决定必须分别呈现。

这不是重复业务逻辑，而是在高价值输出边界重新验证关键不变量。

### 7. 模型结论与人工决定为什么不能互相覆盖

模型的 Conclusion 是某次 AgentRun 的候选判断；Confirmation 是用户随后作出的治理动作。两者代表不同主体、不同时间和不同责任。

若人工确认直接覆盖模型结论，将无法回答：模型当时说了什么、人工为什么改变状态、一次驳回后是否又重新调查。报告必须并列展示这两类事实，审计事件则记录动作发生过程。

### 8. 极简 UI 为什么只调用 API

`/ui` 的价值是验证真实操作顺序：创建、运行、查看 Evidence、补充、确认、驳回、继续调查和读取报告。它不应该在 JavaScript 中复制状态机或 Citation Policy。

```text
浏览器负责：收集输入、调用 API、呈现响应
API/Application 负责：用例与权限边界
Domain/Policy 负责：状态和规则
```

这样未来把原生页面替换成 Vue、React 或其他客户端时，业务规则仍留在后端。当前无构建工具的选择也降低了个人项目的运行负担，但不代表它已经具备正式前端的组件化、测试、认证和可访问性能力。

### 9. Phase 0C 为什么没有数据库迁移

Evaluation 默认读取运行结果并输出文件或标准输出；DiagnosisReport 按需聚合现有记录；Minimal UI 只是已有 API 的客户端。这三项能力都可以基于 Phase 0A/0B 已持久化的数据实现。

不新增表是一个有意识的判断：只有当需要评测历史趋势、报告版本、签名归档或异步生成状态时，才应引入新的持久化模型。不要因为出现一个新页面或 DTO 就自然增加数据库表。

### 10. Phase 0C 与可观测性的区别

AgentRun、ToolRun、结构化日志和 Request ID 帮助解释“系统如何运行”；Evaluation 判断“运行结果是否满足预期”；DiagnosisReport 面向用户解释“本次诊断得到了什么”。三者相关但不等价：

| 能力 | 主要受众 | 核心问题 |
|---|---|---|
| 可观测性 | 开发与运维人员 | 系统在哪里失败、耗时和终止原因是什么 |
| Evaluation | 开发与 CI | 修改后能力是否回归 |
| DiagnosisReport | 诊断使用者 | 结论、依据、运行摘要和人工决定是什么 |

### 11. 当前实现的阶段性妥协

- 固定 Case 数量少，主要验证契约和最小流程；
- 根因关键词断言较粗，尚无语义评分和专家标注集；
- 报告按需生成，不持久化、签名或版本化；
- `/ui` 没有身份认证、RBAC、前端状态管理和端到端浏览器测试；
- 评测结果尚未形成跨版本趋势面板；
- 默认评测使用 Fake LLM，不能替代真实模型质量验收。

准确定位应当是：

> Phase 0C 把诊断闭环变成可回归、可交付、可手工操作的本地最小产品形态，而不是完整评测平台、报告中心或企业前端。

## 常见说法校准

| 容易产生误解的说法 | 更准确的说法 |
|---|---|
| Phase 0C 增加了模型评测平台 | Phase 0C 建立了确定性离线回归基线，并为模型质量评测保留扩展点 |
| 评测通过说明诊断一定正确 | 通过说明预设契约与最小语义条件满足，不代表未知故障泛化质量 |
| Markdown 报告是模型生成的 | 报告由确定性代码投影已有事实，不再次调用模型 |
| 报告只要展示数据库内容即可 | 报告边界仍需校验引用归属并区分模型结论与人工决定 |
| `/ui` 是完整前端 | `/ui` 是无构建工具的本地闭环验证入口 |
| Phase 0C 没有迁移说明架构没变化 | 它新增消费和验证能力，但复用了已有持久化事实 |

## 推荐的代码阅读路径

1. [Evaluation Models](../../src/app_diagnosis/evaluation/models.py)：Case、Observation、Result 和 Suite 的边界；
2. [Evaluation Runner](../../src/app_diagnosis/evaluation/runner.py)：如何比较期望与实际；
3. [Evaluation CLI](../../src/app_diagnosis/evaluation/cli.py)：如何输出机器可读结果；
4. [Phase 0C Baseline](../../evals/cases/phase0c-baseline.json)：固定案例如何表达验收标准；
5. [Report Domain](../../src/app_diagnosis/domain/report/models.py)：报告聚合了哪些事实；
6. [Report Application](../../src/app_diagnosis/application/reports.py)：聚合与防御性引用校验；
7. [Report Routes](../../src/app_diagnosis/api/routes/reports.py)：同一报告如何输出 JSON/Markdown；
8. [UI Route](../../src/app_diagnosis/api/routes/ui.py)：极简客户端如何只依赖 API；
9. [Report and UI Integration Tests](../../tests/integration/test_report_and_ui.py)：输出边界如何验收；
10. [Evaluation Tests](../../tests/unit/evaluation/test_runner.py)：确定性评测规则如何回归；
11. [Phase 0C Acceptance Script](../../scripts/verify-phase0c.ps1)：阶段验收如何被一键组织。

## 回顾时应该能回答的问题

1. 为什么 Phase 0C 不需要增加新的 LLM 能力？
2. 系统规则回归与真实模型质量评测有什么区别？
3. EvaluationCase、Observation 和 Result 为什么要拆分？
4. 当前关键词指标能发现什么，不能证明什么？
5. 为什么报告生成不能隐式再次调用模型？
6. Citation Policy 已校验过，报告边界为什么还要校验？
7. 为什么人工 Confirmation 不能覆盖模型 Conclusion？
8. `/ui` 为什么不能复制后端状态机规则？
9. Phase 0C 为什么没有新增数据库表？
10. 可观测性、Evaluation 和 Report 分别服务谁？
11. 如果未来保存报告版本，需要新增哪些领域概念？
12. 如果未来建立真实模型评测集，哪些结果必须与确定性回归分开记录？

## 边界

- 当前评测是确定性系统回归基线，不等于真实模型质量排行榜；
- 报告是事实投影，不持久化、不签名、不生成新的模型结论；
- UI 是本地学习和联调入口，不包含认证、RBAC 和企业审批体验；
- Phase 0C 没有新增数据库迁移。

## 重新生成

```powershell
dot -Tsvg phase0c-extension.dot -o phase0c-extension.svg
```
