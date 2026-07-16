# ADR-0002：供应商无关的 LLM Runtime

> [返回文档导航](../README.md)

## 状态

Accepted

## 决策

Agent Runtime 只依赖项目自有的 `LLMClient`、消息、工具和响应类型。第一个生产 Adapter 使用 OpenAI-compatible Chat Completions `POST /chat/completions`，后续可以新增 Responses API 或其他供应商 Adapter。

## 协议约束

- assistant 消息完整保存模型返回的 `tool_calls`；
- tool 消息保存对应 `tool_call_id`；
- 支持同轮多个工具调用；
- 工具参数保留为原始 JSON 字符串，由 Tool Runtime 校验；
- API Key 不进入异常、日志和运行记录；
- Fake LLM 只存在于测试代码，不得在生产 bootstrap 中装配。

## 参考

- OpenAI Chat Completions API：`https://developers.openai.com/api/reference/resources/chat`
- ITOps Agent Platform `llmService/toolCalling.ts`：仅参考请求流程；
- ITOps Agent Platform `llmService/providerAdapters.ts`：仅参考消息和 Tool Call 类型。

本实现没有复用 ITOps Repository、Settings、执行记录、全局熔断器和默认模型回退策略。
