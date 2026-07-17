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
| `timeout` | 通过 | 第 3 次低频复验通过；5 轮、6 次工具；读取 `InventoryClient.java` 与 `FailureController.java`；最终结论同时引用 `log_excerpt` 与 `code_excerpt`。 |

超时案例的收敛过程暴露了两个工程问题：

- 修正阶段此前只允许“工具结果”中的 ID，忽略了首轮已有的日志 Evidence ID；
- 单一纠错预算把结构化输出纠错和 Evidence 引用纠错混在一起，真实模型在复杂案例下容易用完机会。

修复后，最终结论阶段会重新附带当前权威 Evidence 目录；Evidence 引用错误拥有独立的引用纠错预算，并明确要求 source-based root cause 同时引用运行日志和相关源码 Evidence。
在第 3 次真实模型复验中，`timeout` 案例以 `completed` 收敛，`acceptance_failures` 为空。
