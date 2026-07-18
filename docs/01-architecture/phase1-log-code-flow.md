# Phase 1 链路图：真实日志与受限源码联合诊断

> [返回文档导航](../README.md)

> 本文侧重一次诊断的执行顺序。若要理解 Phase 1 在 Phase 0A/0B/0C 上新增和修改了哪些架构边界，请先阅读[Phase 1 扩展架构与深度学习总结](./phase1-extension.md)。

![Phase 1 链路图](./phase1-log-code-flow.svg)

## 这张图表达什么

这张图不是完整系统大图，而是 Phase 1 最核心的展示链路：

> Java Lab 真实日志 → Log Evidence → code search/read → Code Evidence → 引用校验 → 诊断报告

它说明当前项目已经从“模型基于用户描述和知识库给出候选结论”，推进到“模型基于真实运行日志和受限源码证据完成诊断”。

## 与 Phase 0 的关系

| 来源 | Phase 1 中如何复用 |
|---|---|
| Phase 0A | 继续复用 FastAPI、Application Service、ToolLoopRunner、Strategy、Registry、预算和运行记录 |
| Phase 0B | 继续复用 Evidence、脱敏、Citation Policy、人工确认和审计边界 |
| Phase 0C | 继续复用报告生成、验收脚本和文档化验证方式 |

Phase 1 新增的是 Java Lab 故障实验室、受限日志读取、受限源码搜索读取，以及 `code_excerpt` Evidence。

## 主流程

1. 本地用户通过 Postman 或浏览器触发 Java Lab 故障接口；
2. Spring Boot 应用把真实异常堆栈写入 `logs/diagnosis-java-lab.log`；
3. Python 平台用 `LocalLogFileReader` 读取最近一次匹配关键词的异常事件；
4. 日志先脱敏，再形成 `log_excerpt` Evidence；
5. Agent 启动时拿到已有 Evidence 目录；
6. 模型自主选择 `code__search` 的搜索词；
7. 模型在受限工作区内用 `code__read` 读取关键源码片段；
8. 源码片段落库为 `code_excerpt` Evidence；
9. 最终结论必须引用当前诊断内的日志 Evidence 和源码 Evidence；
10. Citation Policy 通过后，系统生成 JSON 和 Markdown 诊断报告。

## 图中颜色含义

| 颜色 | 含义 |
|---|---|
| 橙色 | Phase 1 主执行路径和 Java Lab |
| 浅蓝 | 真实日志接入与脱敏 |
| 紫色 | Phase 0 复用的诊断闭环 |
| 绿色 | Phase 1 新增的受限源码工具 |
| 青色虚线 | 可替换的真实模型适配器 |

## 当前验收状态

Java Lab 三类真实模型案例已经通过：

| Case | 关键日志 | 关键源码 | 状态 |
|---|---|---|---|
| `npe` | `NullPointerException` | `OrderService.java` | 通过 |
| `connection-refused` | `ConnectException` | `PaymentClient.java` | 通过 |
| `timeout` | `TimeoutException` | `InventoryClient.java` | 通过 |

详见：

- [Phase 1 真实模型端到端诊断验收](../04-validation/phase1-real-model-acceptance.md)
- [Phase 1 Java Lab 多故障评测](../04-validation/phase1-java-lab-evaluation.md)
- [Phase 1 当前能力总结](../03-progress/2026-07-17-Phase1当前能力总结.md)

## 边界

- `code__search` 和 `code__read` 只访问配置的代码工作区；
- 当前不是全量代码 RAG，也不扫描本机任意工程；
- 真实模型验收保持低频，失败后先分析工具轨迹和 Evidence；
- `confirmed` 仍只来自人工确认，不由模型直接产生。

## 重新生成

```powershell
dot -Tsvg phase1-log-code-flow.dot -o phase1-log-code-flow.svg
```
