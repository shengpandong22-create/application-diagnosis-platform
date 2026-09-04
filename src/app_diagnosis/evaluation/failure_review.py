"""Render human-readable failure reviews for real-model evaluation runs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def render_failure_review(*, summary: dict[str, Any], scored_case: dict[str, Any]) -> str:
    case_id = str(summary.get("case_id") or scored_case.get("case_id") or "unknown")
    termination = str(summary.get("termination_reason") or "unknown")
    failures = [str(item) for item in scored_case.get("failures", [])]
    tool_trace = [item for item in summary.get("tool_trace", []) if isinstance(item, dict)]
    evidence = [item for item in summary.get("evidence", []) if isinstance(item, dict)]
    repeated_failures = _repeated_failed_tool_calls(tool_trace)
    first_success_after_failures = _first_success_after_failures(tool_trace)

    lines = [
        f"# 失败诊断复盘：{case_id}",
        "",
        "## 1. 结果摘要",
        "",
        f"- 终止原因：`{termination}`",
        f"- 模型：`{summary.get('model') or 'unknown'}`",
        f"- 轮次 / 工具调用：`{summary.get('round_count')}` / `{summary.get('tool_call_count')}`",
        f"- 耗时：`{summary.get('elapsed_ms')}` ms",
        f"- Token：输入 `{summary.get('input_tokens')}`，输出 `{summary.get('output_tokens')}`",
        f"- 评测失败项：{_inline_code_list(failures) if failures else '无'}",
        "",
        "## 2. 证据完整性",
        "",
        f"- 已产生 Evidence：{_evidence_summary(evidence)}",
        f"- 期望 Evidence 类型：{_inline_code_list(summary.get('expected_evidence_types', []))}",
        f"- 期望根因关键词：{_inline_code_list(summary.get('expected_root_cause_keywords', []))}",
        "",
        "## 3. 工具调用复盘",
        "",
        "| 顺序 | 工具 | 状态 | 参数摘要 | 错误码 |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for index, item in enumerate(tool_trace, 1):
        lines.append(
            "| "
            f"{index} | "
            f"`{item.get('name')}` | "
            f"`{item.get('status')}` | "
            f"{_arguments_summary(item.get('arguments'))} | "
            f"`{item.get('error_code') or ''}` |"
        )

    lines.extend(
        [
            "",
            "## 4. 失败模式判断",
            "",
            *_failure_pattern_lines(
                termination=termination,
                repeated_failures=repeated_failures,
                first_success_after_failures=first_success_after_failures,
                failures=failures,
            ),
            "",
            "## 5. 建议修复方向",
            "",
            *_recommendation_lines(
                repeated_failures=repeated_failures,
                first_success_after_failures=first_success_after_failures,
            ),
            "",
        ]
    )
    return "\n".join(lines)


def load_case_review(result_dir: Path, *, case_id: str) -> str:
    suite = _load_json(result_dir / "suite.json")
    observations = _load_json(result_dir / "observations.json")
    scored_case = _find_scored_case(suite, case_id)
    summary = _find_summary(observations, case_id)
    return render_failure_review(summary=summary, scored_case=scored_case)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_scored_case(suite: dict[str, Any], case_id: str) -> dict[str, Any]:
    for item in suite.get("results", []):
        if isinstance(item, dict) and item.get("case_id") == case_id:
            return item
    raise ValueError(f"case not found in suite: {case_id}")


def _find_summary(observations: dict[str, Any], case_id: str) -> dict[str, Any]:
    for item in observations.get("runs", []):
        if isinstance(item, dict) and item.get("case_id") == case_id:
            summary = item.get("summary")
            if isinstance(summary, dict):
                return summary
    raise ValueError(f"case not found in observations: {case_id}")


def _repeated_failed_tool_calls(tool_trace: list[dict[str, Any]]) -> list[tuple[str, int]]:
    failures: Counter[str] = Counter()
    for item in tool_trace:
        if item.get("status") != "failed":
            continue
        failures[_tool_signature(item)] += 1
    return [(signature, count) for signature, count in failures.items() if count > 1]


def _first_success_after_failures(tool_trace: list[dict[str, Any]]) -> str | None:
    failed_tools: set[str] = set()
    for item in tool_trace:
        name = str(item.get("name") or "")
        if item.get("status") == "failed":
            failed_tools.add(name)
        elif item.get("status") == "success" and name in failed_tools:
            return name
    return None


def _tool_signature(item: dict[str, Any]) -> str:
    return json.dumps(
        {
            "name": item.get("name"),
            "arguments": item.get("arguments"),
            "error_code": item.get("error_code"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _inline_code_list(values: Any) -> str:
    if not isinstance(values, list | tuple):
        return "`unknown`"
    return ", ".join(f"`{item}`" for item in values) if values else "无"


def _evidence_summary(evidence: list[dict[str, Any]]) -> str:
    counts = Counter(str(item.get("type") or "unknown") for item in evidence)
    return ", ".join(f"`{name}` x {count}" for name, count in sorted(counts.items())) or "无"


def _arguments_summary(arguments: Any) -> str:
    if not isinstance(arguments, dict):
        return "`无`"
    if "path" in arguments:
        return f"`path={arguments['path']}`"
    if "query" in arguments:
        return f"`query={str(arguments['query'])[:80]}`"
    return f"`{json.dumps(arguments, ensure_ascii=False, sort_keys=True)[:100]}`"


def _failure_pattern_lines(
    *,
    termination: str,
    repeated_failures: list[tuple[str, int]],
    first_success_after_failures: str | None,
    failures: list[str],
) -> list[str]:
    lines: list[str] = []
    if termination == "max_rounds_reached":
        lines.append("- Agent 没有模型异常或工具异常，而是在预算内未能收敛。")
    if repeated_failures:
        lines.append("- 存在重复失败工具调用，说明模型在已知无效参数上继续消耗轮次。")
    if first_success_after_failures:
        lines.append(
            f"- `{first_success_after_failures}` 曾失败后又成功，说明问题更像资源提示不足，"
            "不是工具能力缺失。"
        )
    if "root_cause_mismatch" in failures:
        lines.append("- 最终没有形成符合期望关键词的根因判断。")
    if "information_sufficiency_mismatch" in failures:
        lines.append("- 证据已经具备一定完整性，但模型没有正确判断信息是否足够。")
    return lines or ["- 未识别到明确失败模式，需要人工查看完整 Trace。"]


def _recommendation_lines(
    *,
    repeated_failures: list[tuple[str, int]],
    first_success_after_failures: str | None,
) -> list[str]:
    lines: list[str] = []
    if repeated_failures:
        lines.append("- 对同一 AgentRun 内重复失败的同名同参工具调用做确定性去重。")
    if first_success_after_failures:
        lines.append("- 在模型上下文中显式提供授权配置候选路径，优先使用真实存在的配置文件。")
    lines.append("- 不建议单纯提高轮次或超时时间，否则会掩盖工具选择低效问题。")
    return lines
