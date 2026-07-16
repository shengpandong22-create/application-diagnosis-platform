from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+aiosqlite:///./data/app_diagnosis.db"
    knowledge_directory: str = "samples/knowledge"
    code_workspace_path: str = ""
    code_workspace_name: str = "local-application"
    llm_base_url: str = "https://example.invalid/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    llm_response_format: Literal["auto", "json_schema", "json_object", "none"] = "auto"
    llm_timeout_seconds: float = Field(default=30, gt=0, le=300)
    agent_max_rounds: int = Field(default=6, gt=0, le=20)
    agent_max_tool_calls: int = Field(default=8, gt=0, le=50)
    agent_total_timeout_seconds: float = Field(default=120, gt=0, le=900)
    tool_output_max_bytes: int = Field(default=32_768, ge=1024, le=1_048_576)
    input_log_max_bytes: int = Field(default=262_144, ge=1024, le=10_485_760)

    @property
    def docs_enabled(self) -> bool:
        return self.env != "production"

    @property
    def resolved_llm_response_format(self) -> Literal["json_schema", "json_object", "none"]:
        if self.llm_response_format != "auto":
            return self.llm_response_format
        if "api.deepseek.com" in self.llm_base_url.casefold():
            return "json_object"
        return "json_schema"


@lru_cache
def get_settings() -> Settings:
    return Settings()
