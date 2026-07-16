from app_diagnosis.bootstrap.settings import Settings


def test_default_agent_budgets_are_bounded() -> None:
    settings = Settings(_env_file=None)

    assert settings.agent_max_rounds == 6
    assert settings.agent_max_tool_calls == 8
    assert settings.agent_total_timeout_seconds == 120


def test_deepseek_auto_selects_json_object_response_format() -> None:
    settings = Settings(_env_file=None, llm_base_url="https://api.deepseek.com")

    assert settings.resolved_llm_response_format == "json_object"


def test_explicit_response_format_overrides_provider_detection() -> None:
    settings = Settings(
        _env_file=None,
        llm_base_url="https://api.deepseek.com",
        llm_response_format="json_schema",
    )

    assert settings.resolved_llm_response_format == "json_schema"
