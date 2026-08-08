# Phase 4E 验收记录

| 验收项 | 结果 |
|---|---|
| 重复 Redis 声明只有一次成功 | 契约测试通过 |
| Redis 声明使用 NX 与毫秒 TTL | 契约测试通过 |
| poison message 进入 DLQ 语义 | 契约测试通过 |
| 处理失败不 ack 并 requeue | 契约测试通过 |
| Broker 不可用安全降级 | 契约测试通过 |
| 成功处理后 ack | 契约测试通过 |
| 通知失败不回滚处理结果 | 契约测试通过 |
| GitLab 项目与 commit 白名单 | HTTP MockTransport 通过 |
| GitLab 始终读取固定 commit | HTTP MockTransport 通过 |
| GitHub 仓库与 40 位 commit 白名单 | HTTP MockTransport 通过 |
| GitHub 始终读取固定 commit | HTTP MockTransport 与私有仓库真实读取均通过 |
| Webhook 主机白名单与脱敏 | HTTP MockTransport 通过 |
| SMTP 主机白名单、收件人限制与脱敏 | 契约测试通过；真实发送待邮箱配置 |
| 未配置企业 Adapter 时本地模式 | 全量测试通过 |

## 一键契约验收

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-phase4e.ps1
```

## 本地真实中间件验收

```powershell
docker compose -f deploy/local/compose.phase4e.yml up -d --wait
uv run python scripts/verify-phase4e-middleware.py
```

验收结果：

- RabbitMQ：真实发布、ack、一次 redelivery、poison message 进入 DLQ 均通过；
- Redis：50 个并发声明只有 1 个成功，毫秒 TTL 与过期后重新声明均通过；
- 两个容器健康检查通过。

## 仍待凭据的真实联调

- GitHub 固定 commit：使用只读 Fine-grained Token，通过 Tree 与 Contents API 真实读取私有 Java Lab 的 `025f335f...` 快照，源码搜索和指定行读取均通过；
- SMTP：真实 SMTP 服务端接受验收邮件，用户已人工确认收件箱到达；Adapter、授权、脱敏、发送和最终投递链路全部通过；
- 钉钉/企业微信：按实施范围只保留契约测试，不做真实联调；
- GitLab：保留企业 Adapter 契约，本轮改用 GitHub Java Lab 做固定 commit 真实读取目标。

SMTP 配置完成后执行：

```powershell
uv run python scripts/verify-phase4e-email.py
```

完成发送并由收件箱确认到达后，才能把 SMTP 标记为真实通过。

本次结果：

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
