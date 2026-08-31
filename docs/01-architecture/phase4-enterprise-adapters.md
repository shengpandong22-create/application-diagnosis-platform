# Phase 4E 企业 Adapter 与真实联调边界

![Phase 4E 企业 Adapter 与真实联调边界](./phase4-enterprise-adapters.svg)

## 图中的实线和虚线

- 实线是已经存在的企业消费调用链：RabbitMQ → 解码 → Enterprise Consumer → Active Discovery → ACK/重试 → 可选 SMTP；
- 虚线是已经实现并真实验证、但尚未进入默认装配的能力：Redis 原子声明、GitHub 固定 commit 源码 Adapter；
- `create_app()` 默认仍运行本地模式，不要求 RabbitMQ、Redis 或企业凭据存在。

## 已真实验证

- RabbitMQ：ACK、一次重投、poison message 经 DLX 进入 DLQ；
- Redis：50 个并发声明只有一个成功，毫秒 TTL 与过期重领正常；
- GitHub：只读 Fine-grained Token 读取私有 Java Lab 固定 commit；
- SMTP：服务端接受且人工确认收件箱到达。

## 当前工程边界

`RedisDeduplicationStore` 和 `GitHubSnapshotRepository` 是可替换 Adapter，不应画成默认 API 主链路已经自动使用。项目也还没有独立部署、长期运行、自动重连和水平扩容的生产 Worker。Phase 4E 证明的是 Port/Adapter 契约和真实协议可行，不是生产集群 SLA。

## 源码锚点

- `src/app_diagnosis/application/enterprise_consumer.py`
- `src/app_diagnosis/adapters/enterprise/rabbitmq.py`
- `src/app_diagnosis/adapters/enterprise/redis_deduplication.py`
- `src/app_diagnosis/adapters/code/github_snapshot.py`
- `src/app_diagnosis/adapters/notifications/email.py`
