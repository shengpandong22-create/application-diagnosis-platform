# Phase 0A 验收记录

> [返回文档导航](../README.md)

## 验收日期

2026-07-16

## 自动验收

执行命令：

```powershell
.\scripts\verify-phase0a.ps1 -SkipSync
```

结果：PASSED。

- Ruff：通过；
- pytest：87 passed；
- Alembic 从空 SQLite 数据库升级到 `0002`：通过；
- Alembic Schema 差异检查：通过；
- OpenAPI 必需路径检查：通过；
- 验收临时数据库：已清理。

存在一个 FastAPI TestClient/httpx 第三方弃用警告，不影响 Phase 0A 功能。

## 真实模型联调

状态：PASSED。

联调环境：DeepSeek OpenAI-compatible API，模型 `deepseek-v4-pro`。

联调结果：

- DeepSeek Chat Completions 返回 HTTP 200；
- Agent 完成两轮模型调用；
- `knowledge__search` 实际被调用；
- `json_object` 输出通过本地 `DiagnosisConclusion` Schema 校验；
- 结构化结论成功持久化；
- AgentRun 和 ToolRun 可通过 API 查询；
- 临时 API 进程已停止；
- API Key 未写入日志或验收记录。

为兼容 DeepSeek，`APP_LLM_RESPONSE_FORMAT=auto` 会根据 Base URL 自动使用 `json_object`；完整输出 Schema 同时写入系统提示，由本地 Pydantic 继续执行严格校验。其他 OpenAI-compatible 服务默认保留 `json_schema`。

配置完成并启动 API 后执行：

```powershell
.\scripts\real-model-smoke.ps1
```

通过标准：真实模型运行以 `completed` 结束、形成并持久化结构化结论、至少调用一次 `knowledge__search`，且 AgentRun/ToolRun 可查询。脚本不会输出 API Key。
