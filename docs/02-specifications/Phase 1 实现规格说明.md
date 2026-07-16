# Phase 1 实现规格说明：日志与源码联合诊断

## 1. 目标

在 Phase 0 的 Evidence、受控 Tool Loop、人工反馈和报告能力上，增加一个本地 Java 故障实验室，以及对预先授权源码目录的受控检索能力。

主链路：

```text
Java Lab 产生真实错误日志
→ 用户提交日志
→ Agent 提取栈帧或配置键
→ code__search 定位候选文件
→ code__read 读取有限行区间
→ code_excerpt Evidence 落库
→ 模型形成 possible/probable 候选结论
→ 人工调试、修复与确认
```

## 2. 安全边界

- 代码工作区必须通过 `APP_CODE_WORKSPACE_PATH` 预先配置，模型不能指定根目录；
- 只允许 `.java/.yml/.yaml/.properties/.xml`；
- 忽略 `.git/.idea/target/build/.gradle`；
- 单文件不超过 256 KiB；
- 单次最多读取 120 行；
- 解析后的真实路径必须仍位于授权根目录中；
- 工具只读，不执行源码、构建脚本或 Git 命令；
- 代码作为不可信 Evidence，不因静态命中自动确认运行时根因。

## 3. 交付范围

- 独立 `diagnosis-java-lab` Git 工程；
- NPE、下游连接失败、超时三个可重复场景；
- `CodeWorkspace` Domain 和 `CodeRepository` Port；
- `LocalCodeRepository` Adapter；
- `code__search`、`code__read`；
- `code_excerpt/local_code` Evidence 与 Alembic `0007`；
- 离线日志到源码联合演示；
- 路径穿越、构建目录隔离、Evidence 生成测试。

## 4. 当前非目标

- 代码向量库或全量 Code RAG；
- 自动扫描电脑上的工程；
- 远程 GitHub 仓库拉取；
- 自动修复和提交业务代码；
- Loki、Elasticsearch、OpenTelemetry 日志接入；
- 将静态代码可疑点直接标记为 confirmed。

## 5. 验收命令

Java Lab：

```powershell
cd D:\AgentStudy\diagnosis-java-lab
mvn test
```

诊断平台：

```powershell
cd D:\AgentStudy\application-diagnosis-platform
uv run ruff check .
uv run pytest
uv run python scripts/demo-phase1-code.py
```
