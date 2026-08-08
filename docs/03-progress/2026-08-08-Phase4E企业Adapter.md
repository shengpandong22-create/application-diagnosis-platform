# 2026-08-08：Phase 4E 企业 Adapter

## 1. 定位

Phase 4E 将已经稳定的本地主动发现闭环扩展为企业接入形态，但不把“写出 Adapter”和“真实企业环境联调通过”混为一谈。

```text
RabbitMQ / DLQ
  → Broker Port
  → LogEvent
  → Redis Lua 幂等声明
  → Phase 4C Discovery
  → 固定 commit GitLab / GitHub Snapshot
  → 可选 SMTP / 钉钉 / 企微通知
```

默认 `create_app()` 不装配这些组件，`APP_ENTERPRISE_ENABLED=false` 时本地模式完全不依赖外部中间件。

## 2. RabbitMQ 消费语义

- 提供兼容 aio-pika `RobustQueue`/`IncomingMessage` 的薄 Adapter；
- Schema 错误或超大消息 reject，由 RabbitMQ DLX 进入 DLQ；
- 处理成功后才 ack；
- 临时处理失败 nack/requeue；
- Worker 取消时先安全 requeue；
- Broker 不可用返回安全 Worker 结果，不影响 Java 业务请求或默认 API。

RabbitMQ exchange、queue、DLX 和连接生命周期属于部署配置，不硬编码在领域层。

## 3. Redis 原子去重

`RedisDeduplicationStore` 使用单条 Lua 脚本执行 `SET ... PX ... NX`。声明与过期时间在 Redis 内原子完成，不采用存在检查后写入的竞态方案。TTL 到期后键由 Redis 自动清理。

## 4. GitLab deployed commit 快照

- 项目必须在 `allowed_projects`；
- commit 必须是允许的 7～40 位十六进制 SHA；
- tree 和 raw API 始终携带同一 commit ref；
- 文件数量、后缀、大小和读取行数受限；
- 禁止绝对路径和 `..`；
- 远程 HTTP/超时失败可以降级到已授权本地快照。

因此诊断引用的是部署版本，而不是可能已经变化的默认分支。

## 5. 通知降级

Webhook 与 SMTP 主机必须在白名单内，正文发送前脱敏。SMTP 还限制收件人数、地址格式、连接超时，并禁止同时启用 SSL 和 STARTTLS。通知发生在消息 ack 之后；通知失败仅记录安全错误类型，不回滚 Incident、Diagnosis 或重新消费消息。

## 6. 验收边界

默认验收通过 Fake Broker、Fake Redis、HTTP MockTransport 和 Fake SMTP 验证协议与失败语义。另使用 Docker Compose 对 RabbitMQ 和 Redis 完成本地真实协议验收。这里的“真实”指实际中间件行为，不等同于生产集群容量、权限、TLS 与故障切换验收。

GitHub Java Lab 使用只读 Fine-grained Token 完成固定 commit 真实读取；Tree 与 Contents API 始终携带同一个 SHA，源码搜索和指定行读取均已通过。SMTP 已使用本地凭据完成真实发送，服务端接受邮件且用户确认收件箱到达；凭据不进入仓库。钉钉/企微按当前范围只保留契约测试。

## 7. 验收结果

```text
Ruff: passed
Full pytest: 244 passed, 1 dependency deprecation warning
Phase 4E focused contract tests: 13 passed
Phase 4E contract acceptance: PASSED
RabbitMQ + Redis local real integration: PASSED
GitHub fixed commit real integration: PASSED
SMTP real notification: PASSED (server accepted and inbox delivery confirmed)
DingTalk / WeCom real integration: OUT OF SCOPE (contract only)
```
