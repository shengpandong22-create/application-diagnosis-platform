# Phase 1 Java Lab 多故障评测

## 目的

检验诊断能力是否能处理不同故障类别，而不是只适用于 NPE 演示。每个案例都要求真实日志、
受限源码读取、Evidence 引用和结构化结论同时成立。

## 案例

| Case | 日志关键词 | 必须命中的源码 | 诊断边界 |
|---|---|---|---|
| `npe` | `NullPointerException` | `OrderService.java` 或 `FailureController.java` | 证明空值传播与解引用，不得直接标记 confirmed |
| `connection-refused` | `ConnectException` | `PaymentClient.java` | 证明调用目标被拒绝；下游为何未监听仍需额外验证 |
| `timeout` | `TimeoutException` | `InventoryClient.java` | 证明超时发生和本地超时设置；不能仅凭此确认下游根因 |

案例定义位于 `evals/cases/phase1-java-lab-cases.json`。真实脚本根据 case 自动检查：

- Run 为 completed；
- 成功检索并读取源码；
- 结论引用 `log_excerpt` 与 `code_excerpt`；
- 至少一条代码 Evidence 指向预期源码；
- 根因陈述包含允许的场景关键词。

## 低频真实验收

在 Java Lab 已产生对应日志后，分别执行一次：

```powershell
uv run python scripts/diagnose-java-log-real.py --case connection-refused
uv run python scripts/diagnose-java-log-real.py --case timeout
```

不连续重试。失败时先检查生成的 `demo-summary.json` 与报告，再决定是否修改离线逻辑。

## 2026-07-17 真实模型记录

| Case | 结果 | 说明 |
|---|---|---|
| `connection-refused` | 通过 | 4 轮、4 次工具；读取 `PaymentClient.java` 与 `FailureController.java`；日志与代码 Evidence 联合引用。 |
| `timeout` | 待复验 | 已正确读取 `InventoryClient.java` 与 `FailureController.java`，但最终以 `invalid_evidence_citations` 结束。 |

超时失败暴露了引用修正提示的矛盾：修正阶段此前只允许“工具结果”中的 ID，忽略了首轮
已有的日志 Evidence ID。该提示已改为同时允许“已有 Evidence 目录”与“工具结果”中的 ID。
修复先经过离线测试；不在同一轮连续重试真实模型。
