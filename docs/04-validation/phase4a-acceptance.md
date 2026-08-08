# Phase 4A 验收记录

## 验收日期

2026-08-08

## 验收范围

- 版本化EvaluationCase；
- 分类、根因、Evidence、工具、成本和延迟指标；
- 旧Phase 0C案例兼容；
- Java Lab 8类故障及ground truth；
- 配置异常路由回归；
- Phase 4A一键验收脚本；
- 少量真实模型质量与成本基线。

## 自动验收命令

```powershell
.\scripts\verify-phase4a.ps1 -SkipSync
```

## 自动验收结果

```text
Ruff: passed
pytest: 210 passed, 1 warning
Phase 4A quality evaluation: 2/2 passed
Phase 4A Java Lab catalog: passed
Java Lab Maven: 8 tests, 0 failures, 0 errors
Phase 4A acceptance: PASSED
```

已知warning来自FastAPI TestClient对Starlette/httpx兼容层的弃用提示，不是本次改动引入的功能失败。

## 指标契约验收

固定`phase4a-v1`数据集结果：

| 指标 | 结果 |
|---|---:|
| pass rate | 100% |
| category accuracy | 100% |
| root cause Top-1/Top-3 | 100% / 100% |
| citation precision/recall | 100% / 100% |
| information sufficiency accuracy | 100% |
| tool selection accuracy | 100% |
| unsupported claim rate | 0% |
| high-confidence error rate | 0% |
| total tokens（固定样本元数据） | 415 |

这些数字用于验证评测器计算与输出契约，不代表真实模型在全部8类故障上的准确率。真实诊断质量必须使用实际运行观察填充EvaluationCase后重新计算。

## Java Lab验收

8类故障均可通过Java 8单元测试确定性复现，覆盖：

- code_bug；
- config；
- dependency；
- external；
- class、cross_file、config和related_logs四种上下文深度。

`related_logs`目前只建立故障和ground truth，工具实现属于Phase 4D。

## 真实模型验收

共调用4次，符合单场景低频复验约束。

| 场景 | 结果 | 说明 |
|---|---|---|
| ConcurrentModificationException | 通过 | 正确引用日志和源码；4轮、8工具、18,658 Token |
| 缺失配置，旧验收 | 文本结论通过但证据门禁不足 | 未要求config Evidence，不作为最终通过 |
| 缺失配置，严格验收1 | 未通过 | 未调用config工具 |
| 缺失配置，严格验收2 | 未通过 | 定位到宽泛application路由信号干扰 |

最后一次调用后已移除宽泛`exception`/`HTTP 500`路由规则，并增加离线回归。根据真实模型测试策略，本轮不继续第5次调用，配置Evidence闭环状态为“代码修复、离线通过、待下次低频真实复验”。

## 结论

Phase 4A工程验收通过，原因是：

1. 质量评测契约、指标和版本绑定已实现；
2. Java Lab 8类ground truth已形成并可重复测试；
3. 一键验收和全量回归通过；
4. 真实模型基线既记录成功，也保留失败和成本事实；
5. 失败暴露的确定性路由缺陷已经由离线测试收敛；
6. 未把待复验配置场景包装为已通过。

Phase 4B可以开始，但下次真实模型窗口应优先复验缺失配置，而不是批量调用全部案例。
