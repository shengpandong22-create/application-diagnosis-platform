from app_diagnosis.evaluation.failure_review import render_failure_review


def test_failure_review_identifies_repeated_failures_and_late_success() -> None:
    summary = {
        "case_id": "timeout",
        "termination_reason": "max_rounds_reached",
        "model": "deepseek-v4-pro",
        "round_count": 6,
        "tool_call_count": 8,
        "elapsed_ms": 78562,
        "input_tokens": 28631,
        "output_tokens": 5841,
        "expected_evidence_types": ["log_excerpt", "config_excerpt"],
        "expected_root_cause_keywords": ["timeout", "inventory", "50"],
        "evidence": [
            {"id": "e1", "type": "log_excerpt"},
            {"id": "e2", "type": "config_excerpt"},
        ],
        "tool_trace": [
            {
                "name": "config__read",
                "status": "failed",
                "arguments": {"path": "application.properties"},
                "error_code": "config_read_filenotfounderror",
            },
            {
                "name": "config__read",
                "status": "failed",
                "arguments": {"path": "application.properties"},
                "error_code": "config_read_filenotfounderror",
            },
            {
                "name": "config__read",
                "status": "success",
                "arguments": {"path": "src/main/resources/application.yml"},
                "error_code": None,
            },
        ],
    }
    scored_case = {
        "case_id": "timeout",
        "failures": ["root_cause_mismatch", "information_sufficiency_mismatch"],
    }

    review = render_failure_review(summary=summary, scored_case=scored_case)

    assert "失败诊断复盘：timeout" in review
    assert "存在重复失败工具调用" in review
    assert "`config__read` 曾失败后又成功" in review
    assert "不建议单纯提高轮次或超时时间" in review
