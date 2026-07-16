# ADR-0003：有界诊断工具与显式 Registry

> [返回文档导航](../README.md)

## 状态

Accepted

## 决策

所有诊断工具实现统一的 `DiagnosticTool` 契约，声明输入/输出 Schema、风险、超时、权限和适用问题类型。`DiagnosticToolRegistry` 负责唯一注册、启停、策略白名单、权限过滤和参数解析，但不负责 Agent 循环。

Phase 0A 的 `knowledge__search` 只读取启动时配置的本地 JSON 目录。模型不能指定文件路径，知识内容作为不可信数据返回。

## 扩展结果

- Phase 1 日志和代码工具复用同一契约；
- Tool Loop 统一负责调用超时、取消、预算和 ToolRun 持久化；
- Phase 0B 将 JSON Knowledge Adapter 替换为 SQLite 实现，工具名称和输出契约保持不变；
- LLM、Workflow 或 API 通过 Adapter 使用同一工具实现。

## ITOps 参考

- `ProviderRegistry.ts`：仅参考元数据注册；
- `providers/types.ts`：仅参考 Provider 描述；
- `workflowProviderRegistry.ts`：仅参考按名称查找。

未复用全局副作用、模拟 Provider、任意字符串分发和两套业务工具实现。
