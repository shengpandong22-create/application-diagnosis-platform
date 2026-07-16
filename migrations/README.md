# Database migrations

数据库 Schema 只通过 Alembic 管理，运行时不得调用 `metadata.create_all()` 或执行临时建表 SQL。

常用命令：

```powershell
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic check
```

首次迁移 `0001_create_diagnoses.py` 创建 `diagnoses` 表、状态约束和查询索引。测试中的 `metadata.create_all()` 仅用于 Repository Adapter 隔离测试；迁移集成测试会从空 SQLite 数据库执行真实 Alembic upgrade 并检查模型漂移。
