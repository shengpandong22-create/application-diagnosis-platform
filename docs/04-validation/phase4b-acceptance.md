# Phase 4B 验收记录

## 验收范围

- LogEvent、ErrorFingerprint、Incident Domain；
- IncidentRepository 和 DeduplicationStore；
- Alembic `0011`；
- 日志事件摄取与 Incident 查询 API；
- 并发、窗口、乱序、幂等和脱敏语义。

## 自动化命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-phase4b.ps1
```

## 验收标准

| 标准 | 结果 |
|---|---|
| 行号变化不改变同版本指纹 | 通过 |
| 不同服务或环境产生不同指纹 | 通过 |
| 同窗口重复事件只增加 occurrence | 通过 |
| 超过窗口创建新 Incident | 通过 |
| 并发输入不产生重复 Incident | 通过 |
| 乱序输入不破坏 first/last seen | 通过 |
| source_event_id 重放幂等 | 通过 |
| 指纹版本可追踪 | 通过 |
| message 入库前脱敏 | 通过 |
| Repository 不泄漏 SQLAlchemy 类型 | 通过 |
| Alembic 升级和 metadata 一致 | 通过 |
| Ruff 与全量 pytest | 通过 |

## 结论

Phase 4B 的确定性主动发现领域核心验收通过。Phase 4C 可以在此基础上增加 File/Replay Source、服务映射、触发策略和自动 Diagnosis，但不能绕过当前的脱敏、去重和 Incident 聚合边界。

最终执行结果：

```text
Ruff: passed
Full pytest: 219 passed
Phase 4B focused tests: 9 passed
Phase 4B acceptance: PASSED
```
