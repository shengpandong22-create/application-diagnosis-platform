# Phase 6B Agent 失败行为加固验收

> 日期：2026-09-04  
> 范围：重复失败工具调用去重、配置候选资源提示、失败诊断复盘报告  
> 原则：不新增业务功能堆砌，只修复真实模型评测暴露出的行为短板

## 1. 改造背景

D1～D7 真实模型评测暴露了一个具体问题：

Inventory timeout 案例中，模型已经通过 `config__read` 读到了正确的
`src/main/resources/application.yml`，但在此之前和之后仍多次尝试不存在或无效的配置路径，
最终达到最大轮次，没有形成可引用结论。

这说明问题不只是“模型能力不足”，也不是简单提高超时和轮次就能解决。更准确的判断是：

- 工具失败后缺少同一 AgentRun 内的失败记忆；
- 模型不知道授权配置目录下哪些文件真实存在；
- 失败复盘需要人工在多个 JSON 和报告文件之间来回查找。

Phase 6B 因此优先加固 Agent 失败行为，而不是增加新工具或新页面。

## 2. 已完成改造

### 2.1 重复失败工具调用去重

位置：

- `src/app_diagnosis/agent/runtime/tool_loop.py`

行为：

- 同一 AgentRun 内，对同名同参且已经失败过的工具调用生成稳定签名；
- 如果模型再次请求相同失败调用，不再进入具体 Adapter；
- Runner 返回 `duplicate_failed_tool_call` 给模型；
- ToolRun 仍然持久化，因此 Trace 不丢失；
- 成功工具调用不参与去重，避免影响正常重试和收敛。

价值：

- 减少模型在已知无效参数上重复消耗轮次；
- 避免无意义访问文件、网络或外部系统；
- 为后续 Plan-then-Execute 或失败记忆留下确定性基础。

### 2.2 配置候选资源提示

位置：

- `src/app_diagnosis/ports/config_repository.py`
- `src/app_diagnosis/adapters/config/local_workspace.py`
- `src/app_diagnosis/agent/runtime/models.py`
- `src/app_diagnosis/agent/strategies/base.py`
- `src/app_diagnosis/agent/strategies/generic_application_error.py`
- `src/app_diagnosis/application/diagnoses.py`

行为：

- `LocalConfigRepository` 可以列出授权配置目录内的候选配置文件；
- 忽略 `.git`、`.idea`、`target`、`build`、`.gradle`、`__pycache__` 等目录；
- 优先提示常见配置名，例如 `application.yml`、`application.yaml`、`application.properties`；
- `ToolResourceContext` 携带 `config_candidate_paths`；
- Strategy 在用户消息中提示模型优先使用这些真实存在的相对路径。

价值：

- 缩小模型配置探测空间；
- 降低错误路径导致的轮次浪费；
- 保持受限读取边界：模型只知道候选路径，仍必须通过 `config__read` 读取。

### 2.3 失败诊断复盘报告

位置：

- `src/app_diagnosis/evaluation/failure_review.py`
- `scripts/review-failed-eval.py`
- `docs/04-validation/2026-09-04-timeout失败诊断复盘.md`

行为：

- 从真实模型评测结果目录读取 `suite.json` 和 `observations.json`；
- 生成单案例 Markdown 复盘；
- 汇总终止原因、轮次、工具调用、Evidence、失败项；
- 自动识别重复失败工具调用；
- 自动识别“某工具先失败后成功”的资源提示不足模式。

价值：

- 让失败案例能被快速讲清楚；
- 支撑面试时回答“真实模型失败时你怎么分析”；
- 为后续评测报告自动化打基础。

### 2.4 私有评测结果保护

位置：

- `.gitignore`
- `README.md`

行为：

- 保留已提交的 Java Lab 可控公开样本；
- 新增 `evals/results/local-*/` 和 `evals/results/private-*/` 忽略规则；
- README 明确后续真实业务日志只允许提交脱敏摘要、评分和复盘结论。

价值：

- 避免后续接入真实业务日志时误提交敏感评测结果；
- 保持真实模型评测资产可展示，同时不扩大数据泄漏风险。

## 3. 验收结果

### 3.1 局部测试

```powershell
uv run --frozen python -m pytest tests\unit\agent\runtime\test_tool_loop.py -q
uv run --frozen python -m pytest tests\unit\adapters\config\test_local_workspace.py tests\unit\agent\strategies\test_service_tool_context.py tests\unit\agent\runtime\test_tool_loop.py -q
uv run --frozen python -m pytest tests\unit\evaluation\test_failure_review.py -q
```

结果：

- Runtime 去重测试通过；
- Config 候选路径测试通过；
- Strategy 候选提示测试通过；
- 失败复盘生成测试通过。
- 私有评测结果忽略规则已写入 `.gitignore`。

### 3.2 全量质量门禁

```powershell
uv run --frozen ruff check .
uv run --frozen python -m pytest -q
uv run --frozen python -m pytest --collect-only -q
```

结果：

- Ruff：通过；
- Pytest：通过；
- 当前测试数：259；Phase 6C 二轮加固后当前测试项为 260；
- 唯一告警仍是 FastAPI/Starlette TestClient 的第三方弃用提示。

### 3.3 样例复盘生成

```powershell
uv run --frozen python scripts\review-failed-eval.py `
  --result-dir evals\results\real-model-v2-timeout-corrected `
  --case-id timeout `
  --output docs\04-validation\2026-09-04-timeout失败诊断复盘.md
```

结果：

- 已生成 timeout 失败复盘；
- 报告明确指出旧案例存在重复失败配置读取；
- 报告明确指出 `config__read` 曾失败后又成功，问题更像资源提示不足，不是工具能力缺失。

## 4. 未做事项

本阶段刻意没有做：

- 不增加真实模型自动测试；
- 不批量调用 DeepSeek；
- 不引入完整 Plan-then-Execute；
- 不拆分 `ToolLoopRunner` 大类；
- 不新增复杂前端页面；
- 不引入 RBAC、多租户或生产 Worker。

这些可以作为后续阶段继续推进，但不是 Phase 6B 的首要目标。

## 5. 下一步建议

Phase 6C 建议继续沿“可信度加固”方向推进：

1. 将 `ToolLoopRunner` 中的工具执行闸门抽成 `ToolExecutionGate`；
2. 将结构化输出与 Citation 修正抽成 `ConclusionGuard`；
3. 继续保持所有行为由现有测试和评测样例兜底；
4. 如果要真实模型复验，只选择 Inventory timeout 单案例、单次调用，不自动重试。

当前不建议马上进入 Phase 5 跨服务拓扑。先把单服务诊断失败行为打磨扎实，项目会更稳。
