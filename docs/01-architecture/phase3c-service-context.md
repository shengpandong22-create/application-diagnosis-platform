# Phase 3C 架构图：服务目录驱动的受限工具上下文

![Phase 3C 服务目录驱动的受限工具上下文](./phase3c-service-context.svg)

> 可维护源文件：[Graphviz DOT](./phase3c-service-context.dot)

## 这张图解决什么问题

Phase 1 之后，平台已经可以完成“日志 + 受限源码”的联合诊断；Phase 2 又补上了 Trace、多 Strategy、配置读取、日志检索和健康检查。

但在 Phase 2 中，这些工具主要来自全局 `.env` 配置。也就是说，系统知道“可以读一个源码目录”，但还不知道“这次诊断对象是哪一个服务”。Phase 3C 的核心变化是：把诊断对象从一次孤立请求升级为一个明确的 `ServiceProfile`。

## 主链路

1. 用户或演示脚本通过 `Service API` 创建服务；
2. 服务保存显式授权的源码、日志、配置和健康检查目标；
3. 用户通过 `/api/v1/services/{id}/diagnoses` 创建绑定服务的诊断；
4. `DiagnosisCase` 持久化 `service_id`；
5. 运行诊断时，`ToolResourceResolver` 根据 `service_id` 构建本次 `ToolResourceContext`；
6. `Strategy` 根据本次可用资源决定向 LLM 暴露哪些工具；
7. `ToolLoopRunner` 通过 `ToolExecutionContext` 把服务级 Adapter 传给工具；
8. 工具仍复用原有受限 Adapter，只能访问服务显式授权的范围；
9. 工具结果继续进入 Evidence、Trace 和 Report。

## 复用与新增

| 类型 | 内容 | 说明 |
|---|---|---|
| 复用 | Diagnosis API、ToolLoopRunner、Registry、Evidence、Trace、Report | Phase 0～2 的诊断闭环不重写 |
| 复用 | `code__search`、`code__read`、`log__search`、`config__read`、`health__check` | 工具契约保持不变 |
| 复用 | LocalCodeRepository、LocalLogFileReader、LocalConfigRepository、HttpHealthCheckClient | 路径边界和 loopback 限制继续生效 |
| 新增 | ServiceProfile | 描述服务级源码、日志、配置、健康目标 |
| 新增 | `DiagnosisCase.service_id` | 将一次诊断绑定到一个服务 |
| 新增 | ToolResourceResolver | 将服务元数据解析为本次运行可用 Adapter |
| 新增 | ToolResourceContext | 表示单次 AgentRun 的工具资源清单 |
| 扩展 | Strategy | 根据本次上下文动态暴露工具白名单 |
| 扩展 | ToolExecutionContext | 携带服务级 Adapter 给工具执行层 |

## 关键边界

服务目录不是本机自动发现，也不是任意目录扫描。

它只保存用户显式登记的服务元数据，并在单次诊断运行时把这些元数据转换成受限工具上下文。真正读文件、读日志、读配置、检查健康状态时，仍然由确定性 Adapter 执行边界校验。

这意味着：

- LLM 只能看到本次允许的工具；
- LLM 不能绕过 Registry 和 ToolExecutionContext；
- 工具只能访问服务配置的授权范围；
- Evidence ID 仍由系统生成；
- 最终结论仍要接受引用校验和人工确认。

## 学习时应该抓住的一句话

> Phase 3C 把“Agent 可以使用哪些工具”从全局配置升级为“由当前服务对象决定的单次运行上下文”，让诊断从一次请求走向真实服务。

