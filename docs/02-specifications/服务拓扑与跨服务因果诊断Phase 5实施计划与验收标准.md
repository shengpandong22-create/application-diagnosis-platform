# 服务拓扑与跨服务因果诊断：Phase 5 实施计划与验收标准

> 文档状态：已设计、暂缓实施
>
> 启动原则：当前优先掌握 Phase 0～4；当岗位方向、学习计划或产品演进需要跨服务诊断时，再按本文启动 Phase 5。
>
> 核心目标：融合服务目录、网关路由、Nacos 实例与运行时 Trace，使诊断平台能够区分入口服务、现象服务、根因候选服务和受影响服务，并形成可引用的跨服务故障传播链。

## 1. 文档目的

本文不是开发完成声明，而是一份可立即启动的实施基线，解决四个问题：

1. Phase 5 为什么值得做，以及它解决 Phase 0～4 的什么不足；
2. 哪些现有能力直接复用，哪些领域对象、Port 和 Adapter 需要新增；
3. 如何在 16GB 个人电脑上分阶段完成，而不陷入基础设施堆叠；
4. 每个阶段怎样验收，什么情况下必须停止扩张并先收敛质量。

## 2. 当前基线与核心缺口

Phase 0～4 已形成以下闭环：

```text
LogEvent → ErrorFingerprint → Incident → Diagnosis
    → ToolLoopRunner → ToolRun → Evidence → CitationPolicy
    → Report / Confirmation → Knowledge candidate
```

当前 `Diagnosis` 主要围绕一个 `ServiceProfile` 调查。它能够深入分析单服务日志、源码、配置和健康状态，但无法可靠回答：

- 报错服务是否只是故障现象的暴露点；
- 本次请求实际调用了哪些下游服务和接口；
- 某个下游服务“存在”“可能被调用”和“本次确实被调用”有什么区别；
- 多个服务同期异常是否属于同一个 Incident；
- 根因候选服务与受影响服务分别是谁。

Phase 5 的质变不是增加 Nacos 等技术名词，而是将诊断对象从“一个服务”升级为“一次跨服务故障传播链”。

## 3. 范围与非目标

### 3.1 Phase 5 目标

- 建立服务、实例、接口、依赖和运行调用的统一领域模型；
- 使用 Gateway 路由确定外部请求的入口服务；
- 使用 Nacos 提供逻辑服务、实例、健康状态和版本元数据；
- 使用 Trace Span 证明一次请求实际发生的跨服务调用；
- 允许 Agent 在确定性策略约束下逐跳调查下游服务；
- 将拓扑、调用、下游日志和源码转换为正式 Evidence；
- 报告区分 `entry_service`、`symptom_service`、`root_cause_candidate` 和 `affected_services`；
- 保持现有 Tool Loop、Evidence、Citation、Report 和 Confirmation 闭环不被替换。

### 3.2 非目标

Phase 5 暂不实现：

- 自动修复和生产变更执行；
- 无限深度拓扑遍历；
- 完整 CMDB、Service Mesh 或 Kubernetes 服务发现；
- Prometheus、ELK、SkyWalking 等全套生产基础设施；
- 大规模 Trace 存储和查询平台；
- 多 Agent 协作；
- 仅凭调用先后关系自动确认根因；
- 多租户、完整 RBAC 和生产 SLA；
- 将 Nacos 注册关系误认为调用关系。

## 4. 四类事实必须分离

| 信息层级 | 典型来源 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| 路由事实 | Gateway 配置 | 外部路径应进入哪个服务 | 内部服务调用是否发生 |
| 注册事实 | Nacos | 服务和实例在某时刻存在及健康状态 | 谁调用了该服务的哪个接口 |
| 静态依赖 | Feign、配置、人工目录 | 上游服务可能调用某下游 | 本次请求实际执行了调用 |
| 运行调用 | Trace Span | 本次请求实际调用的服务、接口、实例和结果 | 被调用方必然是最终根因 |

强制原则：

```text
配置上可能调用
≠ 服务注册存在
≠ 本次请求真实调用
≠ 已证明的故障因果关系
```

LLM 可以依据这些事实提出因果候选，但只有确定性 CitationPolicy 和人工确认能够推动可信度收敛。

## 5. 目标架构

```text
Gateway Route ─┐
Nacos Registry ─┼→ Service Topology / Snapshot
Static Relation ┤              │
Runtime Trace ──┘              ▼
                         Topology Tools
                              │
Incident → Diagnosis → ToolLoopRunner
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
       当前服务 Evidence  下游服务 Evidence  RuntimeCall Evidence
             └────────────────┼────────────────┘
                              ▼
                    Citation / Causal Policy
                              ▼
                Cross-service Diagnosis Report
                              ▼
                    Human Confirmation
```

拓扑只负责提供受控调查范围；Trace 提供运行事实；Evidence 提供引用依据；LLM 提出根因候选；人工确认产生最终事实。

## 6. 与当前代码的映射

### 6.1 保持不变并直接复用

| 当前能力 | 复用方式 |
|---|---|
| `ServiceProfile` | 继续作为逻辑服务身份，不直接塞入实例和调用记录 |
| `ToolResourceContext` | 扩展为能够按授权服务解析下游资源 |
| `DiagnosisApplicationService` | 继续负责编排调查与领域状态收敛 |
| `ToolLoopRunner` | 不改变循环语义，只增加受控拓扑工具和上下文 |
| `DiagnosticToolRegistry` | 继续执行工具白名单、参数、风险和预算校验 |
| `EvidenceStore` | 保存拓扑、运行调用及下游诊断 Evidence |
| `CitationPolicy` | 增加跨服务因果引用规则，不允许模型仅凭拓扑宣称根因 |
| `AgentRun` / `ToolRun` / Trace | 继续记录每次拓扑扩展和工具执行 |
| `Incident` | 作为跨服务故障关联的入口事实，后续可扩展影响范围 |
| GitHub 固定 commit Adapter | 根据服务实例版本读取对应源码快照 |

### 6.2 新增领域模块建议

建议新增 `domain/topology`，而不是把所有字段堆进 `ServiceProfile`：

- `ServiceInstance`：服务实例、地址、端口、集群、版本、健康状态和观测时间；
- `ServiceEndpoint`：服务拥有的 HTTP/RPC 接口；
- `ServiceDependency`：上游、下游、依赖类型、来源、有效期和可信等级；
- `RuntimeCall`：一次真实调用的 trace/span、服务、接口、实例、耗时和结果；
- `TopologySnapshot`：诊断发生时间点使用的最小拓扑快照；
- `DependencyType`：HTTP、RPC、MQ、DATABASE、REDIS；
- `TopologySource`：MANUAL、GATEWAY、NACOS、STATIC_CODE、TRACE；
- `CausalRole`：ENTRY、SYMPTOM、ROOT_CAUSE_CANDIDATE、AFFECTED。

### 6.3 新增 Port 建议

- `GatewayRouteRepository`：按外部路径解析入口服务；
- `ServiceRegistry`：查询服务、实例、健康和版本元数据；
- `ServiceTopologyRepository`：保存静态依赖和时间版本；
- `RuntimeCallRepository`：按 trace、服务和时间窗查询真实调用；
- `TopologySnapshotStore`：冻结本次诊断实际使用的拓扑事实。

### 6.4 Adapter 规划

| Port | Phase 5 Lite | Phase 5 Full |
|---|---|---|
| GatewayRouteRepository | 内存/SQLite 固定路由 | Spring Cloud Gateway 配置 Adapter |
| ServiceRegistry | Fake/Replay | Nacos HTTP/OpenAPI Adapter |
| ServiceTopologyRepository | SQLite | SQLite 起步，企业版可替换 |
| RuntimeCallRepository | JSON Trace Replay | OpenTelemetry/Zipkin Adapter |
| 源码快照 | 本地 Git 或固定 commit | 复用 GitHub Snapshot Adapter |

## 7. 受控调查规则

Agent 不得一次获取完整企业拓扑。Phase 5 至少执行以下确定性约束：

1. 从 Diagnosis 的入口服务开始；
2. 默认最多展开一跳下游；
3. 只有存在失败 RuntimeCall、异常日志或健康异常 Evidence 时，才允许继续下一跳；
4. 最大调查深度、最大服务数和最大 Trace Span 数计入预算；
5. 静态依赖只允许支持“可能相关”，不能单独支持 `probable` 根因；
6. Nacos 实例存在只证明注册事实；
7. 根因候选至少引用 RuntimeCall 与根因服务本地事实中的两类 Evidence；
8. 跨服务 `confirmed` 仍只能由人工确认产生；
9. 每次拓扑扩展必须形成 ToolRun 和 TraceEvent；
10. 所有源码必须绑定服务运行版本对应的固定 commit。

## 8. Evidence 与结论规则

建议新增 Evidence 类型或等价来源标记：

- `gateway_route`；
- `service_instance`；
- `service_dependency`；
- `runtime_call`；
- `topology_snapshot`；
- `downstream_log_excerpt`；
- `downstream_code_excerpt`。

跨服务结论必须区分：

```text
entry_service
symptom_services
root_cause_candidates
confirmed_root_cause_service
 affected_services
propagation_path
```

其中 `confirmed_root_cause_service` 只能在人工确认记录中产生，不由模型直接输出。

最低引用门槛：

| 结论 | 最低证据要求 |
|---|---|
| 下游可能相关 | 静态依赖或 Gateway/Nacos 事实 |
| 本次发生调用 | RuntimeCall/Trace Evidence |
| 下游是根因候选 | 失败 RuntimeCall + 下游日志、健康、配置或源码事实 |
| 跨服务 `probable` | 运行调用 + 根因服务本地事实 + 合法传播路径 |
| `confirmed` | 人工确认记录 |

## 9. 固定故障实验室

建议在 Java Lab 增加最小微服务链：

```text
Spring Cloud Gateway
        ↓
order-service
        ↓ HTTP
inventory-service
        ↓
模拟数据库连接池超时
```

固定案例应产生：

- Gateway 返回 5xx 或超时；
- OrderService 记录下游调用失败；
- Trace 证明调用 `inventory-service` 的具体接口和实例；
- InventoryService 记录连接池获取超时；
- 运行版本可以映射到固定 Git commit；
- 最终报告区分入口、现象、根因候选和影响范围。

## 10. 分阶段实施计划

### Phase 5A：拓扑领域与静态依赖

实现范围：

1. 定义 `ServiceInstance`、`ServiceEndpoint`、`ServiceDependency` 和值类型；
2. 建立 Repository Port 与 SQLite Adapter；
3. 增加迁移、领域测试和 Repository 集成测试；
4. 建立服务依赖查询 API；
5. 提供手工/固定数据导入方式；
6. 不接入 Nacos、Gateway 或真实 Trace。

验收标准：

- 同一环境中的依赖方向可明确查询；
- 服务不存在时不能创建悬空依赖；
- 依赖包含来源、有效时间和类型；
- 环境、版本和服务身份不能串用；
- Repository 不向 Domain 泄漏 SQLAlchemy 类型；
- Phase 0～4 全量回归不受影响。

### Phase 5B：Gateway 路由与 Nacos 实例

实现范围：

1. 建立 Gateway Route 和 Nacos Registry Port；
2. 先实现 Fake/Replay Adapter，再实现真实 Adapter；
3. 同步服务实例、健康状态、集群、版本和观测时间；
4. 将外部路径解析为入口服务；
5. 记录同步摘要、错误和审计事件。

验收标准：

- 给定外部路径能够确定唯一入口服务，歧义时受控失败；
- Nacos 服务上下线能更新实例快照；
- 不把 Nacos 服务注册自动写成调用依赖；
- 网络失败不会删除最近一次有效快照；
- 密钥、鉴权头和内部敏感元数据不进入日志；
- Fake 和真实 Adapter 通过相同契约测试。

### Phase 5C：运行时 Trace 与 RuntimeCall

实现范围：

1. 定义 `RuntimeCall` 和 Trace 查询 Port；
2. 支持 JSON Replay，之后接轻量 OpenTelemetry/Zipkin；
3. 解析 trace/span 的父子关系、服务、接口、实例、耗时和状态；
4. 建立 Trace 与服务版本的关联；
5. 将实际调用转换为 `runtime_call` Evidence。

验收标准：

- 能重建 `gateway → order → inventory` 的真实调用顺序；
- 重复 Span 可幂等写入；
- 缺失父 Span、乱序和部分 Trace 不导致错误因果链；
- 静态依赖与 RuntimeCall 在数据模型和报告中明确区分；
- Trace 内容经过大小限制与脱敏；
- 固定回放结果确定且不调用真实模型。

### Phase 5D：跨服务调查与因果候选

实现范围：

1. 新增 `topology__downstream`、`topology__upstream`、`trace__get` 等只读工具；
2. 扩展 ToolResourceContext，按服务和跳数授权资源；
3. 实现调查深度、服务数量、Span 数量和总预算；
4. 下游日志、健康、配置和源码形成所属服务明确的 Evidence；
5. 扩展 CitationPolicy 和报告；
6. 增加跨服务人工确认；
7. 建立固定离线案例并进行少量真实模型复验。

验收标准：

- Agent 不能读取拓扑之外或未授权服务资源；
- 报告能区分入口服务、现象服务、根因候选和受影响服务；
- 仅凭 Nacos 或静态依赖不能产生 `probable` 根因；
- 失败 RuntimeCall 必须与下游本地事实共同支持根因候选；
- 模型伪造服务、Span 或 Evidence ID 时被确定性校验拦截；
- 达到深度或预算上限时受控收敛并保留已取得 Evidence；
- 人工确认追加记录，不覆盖模型原始结论；
- Phase 0～4 单服务诊断行为保持兼容。

## 11. Phase 5 Lite 快速启动方案

如果目的只是概念验证或近期岗位需要，可先启动 Lite，但不得另造一次性架构。

Lite 只实现：

- 两个业务服务和一个固定依赖；
- SQLite 拓扑；
- JSON Trace Replay；
- 一跳下游调查；
- 下游日志 Evidence；
- 跨服务报告。

Lite 暂不实现：

- 真实 Nacos；
- 真实 Gateway 配置同步；
- OpenTelemetry Collector；
- 多实例和拓扑历史；
- 多跳递归调查。

Lite 验收通过后，Full 版本只能替换 Adapter 和扩展预算，不能修改核心工具契约与领域语义。

## 12. 测试策略

### 12.1 自动测试

- 领域测试：依赖方向、有效期、实例身份、调用父子关系；
- Port 契约测试：Fake 与真实 Adapter 行为一致；
- Repository 集成测试：唯一约束、幂等、时间查询；
- Tool 测试：权限、参数、深度、预算和超时；
- Citation 测试：弱证据不能越级；
- API 测试：拓扑查询与错误响应；
- 回归测试：Phase 0～4 全量测试继续通过。

### 12.2 真实联调

真实联调按顺序进行，失败后先定位，不连续高频重试：

1. Java Lab 固定跨服务故障；
2. Gateway 路由读取；
3. Nacos 注册、上下线和健康状态；
4. Trace 传播与回放一致性；
5. Fake LLM 端到端闭环；
6. 允许 1～4 次真实模型复验固定案例。

真实模型主要验证工具选择、跨服务上下文理解和引用完整性，不替代自动测试。

## 13. 资源与本地运行约束

针对 16GB 个人电脑：

- 默认只运行 Gateway、两个业务服务、Nacos 和必要数据库；
- Trace 优先 JSON Replay，真实 Collector 在 5C 单独启动；
- 不同时启动 ELK、Prometheus、Grafana 和完整消息集群；
- Python 平台与 Java Lab 分开启动；
- Docker 组件按阶段启停；
- 每次联调保留固定输入和结果，减少重复真实模型调用。

## 14. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| 把注册关系误作调用关系 | 四类事实分离，字段和 Evidence 类型不同 |
| Trace 关系被误作因果 | 根因候选必须结合下游本地事实 |
| Agent 遍历范围失控 | 最大跳数、服务数、Span 数和总预算 |
| 读取错误版本源码 | 实例版本映射固定 commit |
| 拓扑随时间变化 | 保存观测时间和本次 TopologySnapshot |
| 基础设施掩盖业务目标 | 先 Fake/Replay，再接真实 Adapter |
| 上下文和 Token 膨胀 | 一跳展开、摘要、按 Evidence 请求最小片段 |
| 跨服务权限扩大 | 按服务授权，默认拒绝，ToolRun 与 Audit 留痕 |
| 个人电脑资源不足 | 分阶段启停，不引入非必要全家桶 |

## 15. 启动门禁与暂停条件

### 15.1 启动 Phase 5 前必须满足

- Phase 0～4 主分支测试通过；
- 能运行当前单服务 Demo；
- 能讲清 ServiceProfile、ToolResourceContext、Evidence 和 CitationPolicy；
- Java Lab 工作区和版本状态明确；
- 确认本次启动 Lite 还是 Full；
- 为每个子阶段建立独立验收记录。

### 15.2 必须暂停扩张的情况

- Phase 0～4 回归不稳定；
- 静态依赖、运行调用和因果结论在模型中混淆；
- 无法固定复现跨服务故障；
- 工具权限不能限制到服务和跳数；
- 真实基础设施占用大量时间但尚未形成 RuntimeCall Evidence；
- 仅为了增加技术名词而继续接入组件。

## 16. Phase 5 总体验收定义

Phase 5 Full 只有满足以下条件才能宣称完成：

- [ ] Gateway 路由能确定外部请求入口服务；
- [ ] Nacos 能提供服务实例、健康、集群和版本事实；
- [ ] Trace 能证明一次真实跨服务调用链；
- [ ] 静态依赖、注册事实、运行调用和因果候选明确分离；
- [ ] Agent 只能在授权拓扑范围内调查；
- [ ] 跨服务工具执行形成 ToolRun、TraceEvent 和 Evidence；
- [ ] 根因候选引用失败调用与下游本地事实；
- [ ] 报告区分入口、现象、根因候选和受影响服务；
- [ ] 人工确认才能产生最终根因事实；
- [ ] 固定故障案例可重复回放；
- [ ] Fake LLM 自动回归通过；
- [ ] 少量真实模型端到端复验通过；
- [ ] Phase 0～4 原有诊断链路无回归；
- [ ] 文档、架构图、Demo 和验收记录同步完成。

不能因为 Nacos、Gateway 或 Trace 单独连通，就宣称 Phase 5 完成。

## 17. 启动后的第一项开发任务

未来正式启动时，第一项任务固定为：

> 实现 `ServiceInstance`、`ServiceEndpoint`、`ServiceDependency` 领域模型、Repository Port、SQLite Adapter、迁移及领域/集成测试，并用手工拓扑证明 `order-service → inventory-service` 的一跳查询。

第一项任务暂不包含：

- 真实 Nacos；
- 真实 Gateway；
- Trace Collector；
- LLM 调用；
- 跨服务报告；
- 多跳调查。

完成 5A 的领域和持久化验收后，才允许进入外部 Adapter 联调。

## 18. 最终决策

Phase 5 对项目长期发展有明确价值，但对当前面试不是阻塞项。因此当前决策是：

```text
设计完成并归档
→ 暂不开发
→ 先掌握 Phase 0～4
→ 岗位或产品路线需要时启动
→ 优先 Lite 验证领域语义
→ 再按 5A～5D 完成 Full
```

这使项目既保留清晰的企业化演进方向，又避免在当前阶段因功能扩张削弱对既有系统的掌握。