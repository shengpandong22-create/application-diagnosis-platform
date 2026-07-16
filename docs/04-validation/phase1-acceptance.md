# Phase 1 验收记录

日期：2026-07-17

## 自动验收

- Java Lab：3 个故障场景测试通过；
- Java Lab Jar 真实启动后，NPE、连接失败、超时三个 HTTP 入口均返回预期的 500，且日志文件成功生成；
- Python：Ruff 通过，153 个测试通过；
- 本地代码检索：支持类名、方法名、配置键文本检索；
- 安全读取：路径穿越被拒绝，构建输出被忽略，行数受限；
- Evidence：`code__read` 产生正式 `code_excerpt`；
- 迁移：Alembic `0007` 支持 `code_excerpt/local_code`；
- 联合演示：应由 `scripts/demo-phase1-code.py` 验证。

## 能力边界

当前结论是“日志和静态代码共同支持的候选根因”。运行时变量值仍需 IDEA 调试、测试或修复后复现结果确认。
