# Phase 1 真实日志与源码联合诊断验收

## 目标

将 Java Lab 产生的真实异常日志，以受限、脱敏的方式交给 Python 诊断平台，并复用现有源码工具和 Evidence 闭环。

## 验收标准

1. Java Lab 的 NPE、连接拒绝、超时接口均返回 HTTP 500；`logs/diagnosis-java-lab.log` 包含三类异常及堆栈。
2. `LocalLogFileReader` 只读取预授权根目录内的相对 `.log` 文件，拒绝路径穿越、目录和其他扩展名。
3. Reader 只读取文件尾部最多 256 KiB，并返回最近一次关键词匹配附近最多 120 行。
4. 摘要通过创建诊断用例进入既有 `LocalRuleRedactor`，敏感信息在持久化前替换。
5. 演示结果同时包含 `log_excerpt` 和 `code_excerpt` Evidence；代码 Evidence 带文件与行号引用。
6. 演示使用 Fake LLM，不访问外部模型；Python 静态检查和测试、Java 测试全部通过。

## 手工端到端验收

启动 Java Lab 后依次请求：

```text
GET http://localhost:18080/lab/orders/npe
GET http://localhost:18080/lab/payments/connection-refused
GET http://localhost:18080/lab/inventory/timeout
```

随后执行：

```powershell
cd D:\AgentStudy\application-diagnosis-platform
uv run python scripts/demo-phase1-log-code.py --keyword NullPointerException
```

成功摘要应至少包含：`termination_reason=completed`、`log_evidence_count>=1`、`code_evidence_count>=1`、日志来源范围和 Java 源码范围。

## 边界

本阶段不自动监听日志、不执行 Java 源码、不扫描未授权工程，也不引入 ELK、消息队列或向量代码库。

## 2026-07-17 验收结果

| 检查项 | 结果 |
|---|---|
| Java 单元测试 | 3 passed |
| 三个故障接口 | NPE / connection-refused / timeout 均返回 HTTP 500 |
| 固定日志内容 | 三类异常及堆栈均存在 |
| Reader 安全与脱敏测试 | 6 passed |
| Python 静态检查 | Ruff passed |
| Python 全量测试 | 159 passed，1 个既有依赖弃用警告 |
| 联合演示 | completed；1 条 log Evidence；1 条 code Evidence |
| 外部模型调用 | false |

联合演示读取 `diagnosis-java-lab.log` 的有界行区间，代码定位为
`src/main/java/dev/agentstudy/lab/OrderService.java:1-22`。演示输出位于被 Git 忽略的
`demo-output/phase1-log-code/`，不作为源码提交。
