# 架构图可视化风格规范

本文定义本项目后续架构图、流程图、学习图的统一风格。目标不是追求“漂亮图”，而是让每张图都能帮助回顾项目演进、解释设计取舍，并经得起源码走读和面试追问。

## 1. 总体原则

架构图优先表达一个问题，不把所有细节塞进一张图。

如果一张图超过 8～10 个主要节点，或者出现三条以上跨层长箭头，应拆成 2～3 张图：

- 总览图：回答“系统分成哪些部分，主链路怎么走”；
- 内部展开图：回答“某个核心模块内部怎么运行”；
- 防线或异常图：回答“失败、越权、证据不足时系统如何处理”。

拆图后，图与图之间要保留共同锚点。例如 `DiagnosisApplicationService`、`ToolLoopRunner`、`Evidence`、`DiagnosisCase` 可以作为跨图关联节点。

## 2. 固定颜色语义

| 颜色 | 用途 | 示例 |
| --- | --- | --- |
| 浅蓝 `#e8f3ff` | 确定性应用骨架 | FastAPI Route、ApplicationService、状态机 |
| 浅紫 `#f0edff` | Agent Runtime / 循环容器 | ToolLoopRunner、ToolLoopResult |
| 珊瑚 `#fff0eb` | 概率性模型能力 | LLMClient Port、LLM 决策、模型反馈 |
| 青绿 `#e2f6ef` | 确定性工具、证据和执行记录 | Tool Registry、Evidence Store、Execution Repo |
| 浅橙 `#fff1dd` | 状态结果或待处理状态 | WAITING_FOR_INPUT、INCONCLUSIVE |
| 浅绿 `#edf7e5` | 查询视图或人工动作入口 | Trace Query、Report Query、Confirmation Command |
| 浅红 `#fff0f0` | 受控失败或风险分支 | 参数非法、引用失败、预算耗尽 |

颜色不是装饰，而是语义。后续图中不要随意把 LLM 画成蓝色，也不要把只读查询画成状态变更。

## 3. 节点命名规则

节点标题优先使用真实代码概念，其次补充中文解释。

推荐：

- `DiagnosisApplicationService`
- `ToolLoopRunner`
- `Evidence Store`
- `Citation Policy`
- `AgentRun / ToolRun`
- `Confirmation Command`

不推荐：

- “智能大脑”
- “AI 中心”
- “万能诊断”
- “确定性容器”

特别注意：`ToolLoopRunner` 不应标为纯“确定性容器”。它内部包含 LLM 调用，更准确的表达是：

> 受控 Agent Runtime：概率性推理 + 确定性约束

## 4. 箭头语义

默认实线箭头表示主调用方向。

虚线箭头表示反馈、循环、失败回流或非主路径依赖。

不要用箭头制造不存在的状态变更。例如：

- `Trace Query` 和 `Report Query` 是只读视图，不推动状态变化；
- `Confirmation Command` 是命令，会追加 Confirmation / Audit，并可能推动状态到 `CONFIRMED`、`REJECTED` 或重新进入 `INVESTIGATING`；
- `Evidence Store` 负责留存 Evidence，但脱敏应发生在入库前。

## 5. 常用拆图模式

### 5.1 主链路图

用于解释完整结构。

建议结构：

```text
FastAPI Route
  → DiagnosisApplicationService
  → 受控 Agent Runtime
  → ToolLoopResult
  → DiagnosisCase 状态收敛
  → 持久化事实
  → Trace / Report / Confirmation
```

主链路图不展开每个工具的细节，只保留核心模块。

### 5.2 Agent Loop 内部图

用于解释 tool-calling 循环。

建议结构：

```text
LLM 决策
  → 确定性校验
  → Tool 执行
  → Evidence 留存
  → tool_result 反馈 LLM
  → 继续循环或进入最终结论校验
```

这里要强调：模型可以提出工具调用，但不能绕过 Registry、工具契约、权限、预算和路径边界。

### 5.3 受控失败图

用于解释安全边界。

建议结构：

```text
LLM 输出
  → 状态合法性
  → 工具 / 参数
  → 预算 / 轮次
  → Evidence / 权限
  → 正常流程

任一关卡失败
  → 受控失败
  → ToolRun / Trace / Audit / inconclusive
```

注意不要写成“任何失败都会生成 Evidence”。参数非法、路径越界这类前置失败不应伪造 Evidence，更适合记录到 ToolRun、Trace 或 Audit。

## 6. SVG 与 Graphviz 使用建议

阶段级架构图优先使用 `Graphviz 源文件 + SVG 成品 + Markdown 说明`。这适合长期维护，也方便以后调整节点和边。

学习型图、讲解型图可以直接使用手写 SVG。因为这类图更重视排版、颜色和表达节奏，不一定适合 Graphviz 自动布局。

建议规则：

| 场景 | 推荐形式 |
| --- | --- |
| 阶段架构图 | `.dot` + `.svg` + `.md` |
| 主链路学习图 | `.svg` + `.md` |
| 大流程拆解 | 2～3 张 `.svg` |
| 临时草图 | Markdown 文本图或 Mermaid，确认后再转 SVG |

## 7. 每张图的验收标准

一张架构图完成后，应检查：

- 是否只回答一个核心问题；
- 是否超过 8～10 个主要节点，超过则拆图；
- 颜色是否符合固定语义；
- 节点名是否能在源码或文档中找到对应概念；
- 箭头是否表达真实调用、反馈、查询或命令关系；
- 是否区分概率性模型输出和确定性工程约束；
- 是否区分 Evidence、Trace、Audit、Report、Confirmation；
- 是否避免“模型直接改状态”“查询推动状态”“失败必然生成 Evidence”等误导。

## 8. 当前推荐风格

当前推荐风格以 `docs/06-byMyself/一、主调用链路：确定性骨架包裹概率性核心.assets` 下的三张 SVG 为参考：

- `phase0-2-main-call-chain.svg`
- `phase0-2-tool-loop.svg`
- `phase0-2-controlled-failure.svg`

后续新增学习图时，优先复用这套颜色和表达方式。
