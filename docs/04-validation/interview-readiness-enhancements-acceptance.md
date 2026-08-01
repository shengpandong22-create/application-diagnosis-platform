# 面试收尾增强：服务历史、知识候选与企业演进设计验收

## 1. 验收范围

本次按照严格顺序完成三项交付：

1. 服务历史诊断视图和服务摘要；
2. confirmed Diagnosis 显式生成 Knowledge candidate；
3. 本地诊断 Agent 到企业平台演进设计文档和目标架构图。

每一步相关测试通过后才进入下一步，最后执行全量回归和演示链路。

## 2. 服务历史诊断视图

新增 API：

```text
GET /api/v1/services/{service_id}/diagnoses
GET /api/v1/services/{service_id}/summary
```

摘要包含：

- ServiceProfile；
- total_diagnoses；
- status_counts；
- latest_diagnosis。

验收结果：

- 诊断历史按创建时间倒序；
- 空服务返回总数 0、空状态分布和 null latest；
- 不存在服务返回 404；
- 查询不触发模型调用；
- 无数据库迁移需求。

第一步独立验收：

```text
6 passed
Ruff: All checks passed
全量：201 passed
```

## 3. confirmed Diagnosis → Knowledge candidate

新增 API：

```text
POST /api/v1/diagnoses/{diagnosis_id}/knowledge-candidates
```

强制规则：

- Diagnosis 必须为 CONFIRMED；
- 必须存在结构化 conclusion；
- 不调用 LLM；
- 只生成 candidate；
- 知识 source 记录 Diagnosis ID；
- 使用确定性 entry ID，重复请求返回原条目；
- 生成动作写入 AuditEvent；
- 后续仍需使用现有 status API 人工审核为 confirmed/retired。

第二步独立验收：

```text
2 passed
Ruff: All checks passed
全量：202 passed
```

## 4. 企业演进设计

新增文档：

- [本地诊断 Agent 到企业平台演进设计](../02-specifications/本地诊断Agent到企业平台演进设计.md)
- [企业目标架构 SVG](../01-architecture/enterprise-target-architecture.svg)
- [企业目标架构 Graphviz 源文件](../01-architecture/enterprise-target-architecture.dot)

文档明确区分：

- 当前已实现；
- 个人电脑可以验证；
- 企业基础设施中才能验证；
- 可复用核心；
- 需要扩展或新增的控制面；
- 分阶段实施和验收标准。

文档验收：

```text
本地失效链接：0
SVG XML：有效
浏览器实际渲染：通过
Markdown 代码围栏：完整
git diff --check：通过
```

本机没有安装 Graphviz `dot` 命令，因此 `.dot` 作为可维护语义源保留，SVG 成品使用浏览器进行了实际渲染检查。

## 5. 最终全量回归

执行：

```powershell
uv run ruff check .
uv run python -m pytest
uv run python scripts/demo-phase3-service.py
```

结果：

```text
Ruff: All checks passed
pytest: 202 passed, 1 warning
Phase 3 Service Demo: completed
external_model_called: false
```

演示输出继续包含：

- ServiceProfile；
- Diagnosis；
- application_error_v1 Strategy；
- code__search / code__read ToolRun；
- code_excerpt Evidence；
- DiagnosisPlan；
- Agent Trace；
- Markdown Report。

唯一 warning 来自 FastAPI TestClient 使用的 Starlette/httpx 兼容性弃用提示，不是本次功能回归失败。

## 6. 验收结论

三项交付全部完成并收敛：

```text
服务对象
→ 历史诊断与摘要
→ 人工确认诊断
→ 可审核知识候选
→ 企业化演进边界与目标架构
```

当前项目已经具备面试前建议补齐的最小功能闭环。后续优先进入项目掌握、演示和面试训练，不建议在没有新验证目标的情况下继续堆叠企业基础设施模拟代码。
