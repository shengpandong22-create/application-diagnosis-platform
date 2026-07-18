# Phase 2 验收记录

## 验收范围

- Trace Domain、投影、API 与极简 UI；
- ToolRun 到正式 Evidence ID 的关联；
- `config__read`、`log__search`、`health__check`；
- 配置、日志和健康目标安全边界；
- Application、Network、Configuration、Generic Strategy 路由；
- Alembic `0008`；
- Phase 2 Fake LLM 离线演示。

## 自动验收

```powershell
.\scripts\verify-phase2.ps1 -SkipSync
```

脚本执行 Ruff、全量 pytest、空库迁移、Alembic check、Phase 2 离线演示和 OpenAPI 契约检查。脚本只使用 Fake LLM，不访问外部模型。

## 离线演示通过条件

- 实际 Strategy 为 `configuration_diagnosis_v1`；
- `config__read` 创建 `config_excerpt`；
- 密码没有进入 ToolRun、Evidence 或 Trace；
- Trace 的 tool event 引用正式 Evidence ID；
- termination reason 为 `completed`；
- `external_model_called=false`。
