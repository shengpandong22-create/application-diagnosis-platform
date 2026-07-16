# ADR-0001：使用独立 Python 项目

> [返回文档导航](../README.md)

## 状态

Accepted

## 决策

应用诊断平台使用独立 Python 仓库、数据库、配置和运行时。ITOps Agent Platform 仅作为设计和实现参考，未来通过版本化 Adapter 集成。

## 原因

- 保持诊断领域模型独立；
- 聚焦 Agent Runtime、工具契约、证据与评测；
- 避免继承 ITOps 的数据库、服务单例和工作流耦合；
- 允许平台在不安装 ITOps 时完整运行。

## 约束

- 不 import ITOps 源码；
- 不连接 ITOps SQLite；
- 不共享 ITOps Secret；
- 参考或改写代码时记录来源与差异。
