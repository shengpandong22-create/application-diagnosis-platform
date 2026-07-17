# Phase 1 真实模型端到端诊断验收

## 验收目标

DeepSeek 基于 Java Lab 的真实 NPE 日志，自主决定搜索词、源码文件和读取范围，最终形成同时引用运行日志与源码 Evidence 的结构化结论。

## 验收门槛

1. 输入来自受限 `LocalLogFileReader`，并在持久化前经既有脱敏流程处理。
2. Agent 首轮能看到当前 Diagnosis 已有 Evidence 的 ID、类型和安全来源摘要。
3. 模型必须成功调用 `code__search` 和 `code__read`，脚本不得预设搜索参数或源码文件。
4. Run 以 `completed` 结束，最终事实或根因引用集合同时包含 `log_excerpt` 与 `code_excerpt`。
5. 输出记录模型名、轮次、工具次数、Token、总耗时、工具轨迹和错误码，但不记录 API Key。
6. 最大 6 轮、8 次工具调用、总预算 120 秒、单次模型调用超时 30 秒。
7. 默认自动测试继续使用 Fake LLM；只有此手工脚本访问外部模型并产生费用。

## 执行命令

```powershell
cd D:\AgentStudy\application-diagnosis-platform
uv run python scripts/diagnose-java-log-real.py --keyword NullPointerException
```

验收输出写入被 Git 忽略的 `demo-output/phase1-real-model/`。

## 2026-07-17 首次验收记录

状态：**未通过，停止继续调用外部模型。**

已验证成功：

- DeepSeek 自主选择并成功执行 3 次 `code__search` 和 2 次 `code__read`；
- 自主读取 `FailureController.java:1-50` 与 `OrderService.java:1-25`；
- 真实日志、日志 Evidence、代码 Evidence、工具审计链路全部正常；
- 正确定位 `OrderService.createOrder` 中 `draft.getCustomer().trim()` 的空值解引用风险。

未通过项：

- 首次严格 5 工具预算在模型继续调查时触发 `tool_budget_exhausted`；
- 恢复默认级别预算并增加收敛提示后，Run 仍以 `inconclusive` 结束；
- 没有形成最终结构化结论，因此未满足日志与代码 Evidence 联合引用门槛。

本次还暴露出验收摘要未记录 AgentRun `error_code` 的可观测性缺口，脚本已补充
`run_error_code` 字段。下次真实调用前，应先针对具体错误码设计离线可测试的收敛策略，
不应通过反复增加预算解决。

## 2026-07-17 收敛修复后验收

状态：**通过。**

针对首次失败实施了两项机制修复：

- 成功执行 `code__read` 后进入无工具结论阶段，防止模型无限调查；
- OpenAI-compatible 请求显式发送 `parallel_tool_calls=false`，使工具预算可预测。

最终结果：

| 指标 | 结果 |
|---|---|
| termination | completed |
| model | deepseek-v4-pro |
| rounds / tools | 4 / 4 |
| input / output tokens | 25,245 / 2,883 |
| elapsed | 42,390 ms |
| code search | `OrderService.createOrder`、`FailureController.npe` |
| code read | `OrderService.java:1-20`、`FailureController.java:20-35` |
| cited evidence | `log_excerpt` + `code_excerpt` |
| acceptance failures | 0 |

模型正确识别：`FailureController.npe` 构造 `OrderDraft(null)`，随后
`OrderService.createOrder` 对空的 `customer` 调用 `trim()`，导致 NPE。结论保持为
`probable`，没有绕过 Phase 0B 的人工确认边界。

后续优化：当前日志窗口可能包含紧随其后的另一段异常，应从固定前后行窗口升级为按
“日志事件起始行 + 堆栈连续行”识别单个异常事件，减少无关 Token 和跨事件干扰。
