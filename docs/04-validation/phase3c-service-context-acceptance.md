# Phase 3C-2 服务目录驱动工具上下文验收记录

## 本阶段目标

Phase 3C-1 只完成了服务元数据登记：服务名、环境、源码目录、日志目录、配置目录和健康检查目标。

Phase 3C-2 的目标是把这些元数据真正接入 Agent 运行链路，使一次诊断在绑定 `ServiceProfile` 后，可以按该服务显式授权的范围使用工具：

- `code_workspace_path` → `code__search` / `code__read`
- `log_directory` → `log__search`
- `config_workspace_path` → `config__read`
- `health_targets` → `health__check`

这一步不是做本机自动扫描，也不是让 Agent 任意读取工程；服务目录只是为单次诊断提供受限工具上下文。

## 当前实现边界

1. 工具在应用启动时注册，但是否暴露给模型由两层共同决定：
   - Strategy 白名单；
   - 本次 `ToolResourceContext` 中是否存在对应受限资源。

2. 没有关联服务的诊断继续使用 `.env` 中的全局工具配置，保证 Phase 1/2 演示链路不被破坏。

3. 关联服务的诊断优先使用服务级资源：
   - 源码、日志、配置仍复用原有本地 Adapter 的路径边界校验；
   - 健康检查仍只允许 loopback HTTP 目标；
   - 工具输出仍经过大小预算、脱敏、Evidence 落库和引用校验。

4. `health_targets` 兼容两种写法：
   - `http://localhost:8080/actuator/health` → 自动生成别名 `target_1`；
   - `app=http://localhost:8080/actuator/health` → 使用显式别名 `app`。

## 已完成验收

- Strategy 在没有服务资源时只暴露 `knowledge__search`。
- Strategy 在本次上下文包含服务级源码/日志资源时，会暴露 `code__search`、`code__read`、`log__search`。
- `CodeReadTool` 即使构造时没有全局源码 Adapter，也可以通过 `ToolExecutionContext.code_repository` 使用服务级源码仓库。
- 通过服务 API 创建诊断后，`code_workspace_path` 可以驱动 `code__read` 成功读取服务级源码并生成 `code_excerpt` Evidence。
- 全量静态检查通过：
  - `uv run ruff check .`
- 全量自动测试通过：
  - `199 passed, 1 warning`
- Phase 3C 服务驱动离线演示通过：
  - `uv run python scripts/demo-phase3-service.py`

## 仍然坚持的安全约束

- ServiceProfile 必须由用户显式创建，不自动扫描本机目录。
- 工具只读取服务配置的根目录内相对路径。
- 原始日志和配置内容进入 Evidence 前仍要脱敏。
- LLM 只能提出工具调用意图，实际工具解析、权限、预算和 Evidence ID 生成仍由确定性代码完成。
