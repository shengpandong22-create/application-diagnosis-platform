# Phase 0B 验收记录

> [返回文档导航](../README.md)

## 验收目标

Phase 0B 将 Phase 0A 的“模型给出答案”升级为基于可追踪 Evidence 的诊断闭环，并允许用户补充、确认、驳回或要求继续调查。

## 已验收能力

1. Evidence Domain、SQLite 持久化、hash 去重和内容完整性校验；
2. API Key、Bearer Token、密码、JWT 和连接串的入库前脱敏；
3. 用户描述与日志自动转换为 Evidence，日志支持 UTF-8 安全分片；
4. KnowledgeEntry Domain、SQLite Repository、JSON 种子幂等导入和关键词检索；
5. `knowledge__search` Tool 契约保持不变；
6. Tool EvidenceDraft 落库，并向模型返回真实 Evidence ID；
7. probable、possible、confirmed 和 insufficient_evidence 引用规则；
8. 用户补充信息、Evidence 查询、人工确认、驳回和继续调查；
9. Confirmation 追加记录，不覆盖模型原结论；
10. Knowledge 查询和 candidate 创建 API；
11. Knowledge `candidate → confirmed/retired`、`confirmed → retired` 状态闭环；
12. Evidence、补充、运行、人工动作、Knowledge 创建和状态变更的安全审计事件。

## 一键验收

```powershell
.\scripts\verify-phase0b.ps1 -SkipSync
```

脚本执行：

- Ruff 静态检查；
- 全量 pytest；
- 从空 SQLite 数据库升级到 Alembic head；
- Alembic 元数据漂移检查；
- Phase 0B OpenAPI 必需路径检查；
- Evidence、Knowledge、Confirmation 和 Audit 数据表检查；
- 临时验收数据库清理。

脚本不读取或输出模型 API Key，不调用外部模型，不产生模型费用。

## 安全验收

- 原始敏感文本在持久化前脱敏；
- Evidence 和 Confirmation 不保存已识别的密钥明文；
- 审计记录只保存固定安全摘要，不保存完整日志、Prompt 或用户输入；
- Prompt Injection 文本始终作为不可信数据；
- 引用的 Evidence 必须属于当前 Diagnosis；
- Phase 0 中模型不能生成 confirmed 根因。

## Knowledge 状态闭环

- `PATCH /api/v1/knowledge/{entry_id}/status` 提供显式状态变更；
- 允许 `candidate → confirmed`、`candidate → retired` 和 `confirmed → retired`；
- `retired` 为终态，非法逆向转换返回 `409 knowledge_status_conflict`；
- 重复设置相同状态按幂等成功处理，不重复写审计事件；
- 不存在的 Knowledge 返回 `404 knowledge_not_found`；
- 每次有效转换记录 `knowledge.status_changed` 和安全状态摘要。

## 已知非阻塞项

测试环境存在 Starlette TestClient/httpx 第三方弃用警告，不影响 Phase 0B 功能。前端、向量数据库、远程日志、Worker 和任务队列仍按计划推迟。
