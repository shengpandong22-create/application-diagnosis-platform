import json
import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app_diagnosis.adapters.persistence import Database
from app_diagnosis.api.app import create_app
from app_diagnosis.bootstrap.container import build_diagnosis_service
from app_diagnosis.bootstrap.settings import Settings
from app_diagnosis.ports.llm import ChatMessage, FinishReason, LLMRequest, LLMResponse, ToolCall

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OfflinePhase2LLM:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            assert "config__read" in {item.name for item in request.tools}
            return LLMResponse(
                ChatMessage.assistant(
                    None,
                    tool_calls=(
                        ToolCall(
                            id="config-read-1",
                            name="config__read",
                            arguments_json=(
                                '{"path":"application.properties","start_line":1,"end_line":3}'
                            ),
                        ),
                    ),
                ),
                "offline-phase2-demo",
                FinishReason.TOOL_CALLS,
            )
        payload = json.loads(request.messages[-1].content or "{}")
        evidence_id = payload["evidence_ids"][0]
        conclusion = {
            "symptom_summary": "Application startup reports a missing downstream URL",
            "facts": [],
            "root_causes": [
                {
                    "statement": "The authorized config excerpt has an empty downstream URL",
                    "status": "possible",
                    "evidence_ids": [evidence_id],
                }
            ],
            "recommendations": ["Verify and supply the downstream URL in the target environment"],
            "missing_information": [],
        }
        return LLMResponse(
            ChatMessage.assistant(json.dumps(conclusion)),
            "offline-phase2-demo",
            FinishReason.STOP,
        )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="app-diagnosis-phase2-") as temporary:
        root = Path(temporary)
        config_root = root / "config"
        config_root.mkdir()
        config_root.joinpath("application.properties").write_text(
            "downstream.url=\npassword=do-not-persist\nfeature.enabled=true\n",
            encoding="utf-8",
        )
        url = f"sqlite+aiosqlite:///{(root / 'demo.db').as_posix()}"
        alembic = Config(str(PROJECT_ROOT / "alembic.ini"))
        alembic.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
        alembic.set_main_option("sqlalchemy.url", url)
        inherited_database_url = os.environ.pop("APP_DATABASE_URL", None)
        try:
            command.upgrade(alembic, "head")
        finally:
            if inherited_database_url is not None:
                os.environ["APP_DATABASE_URL"] = inherited_database_url
        settings = Settings(
            _env_file=None,
            env="test",
            database_url=url,
            knowledge_directory=str(PROJECT_ROOT / "samples" / "knowledge"),
            config_workspace_path=str(config_root),
        )
        database = Database(url)
        service, _ = build_diagnosis_service(
            settings=settings,
            database=database,
            llm_client=OfflinePhase2LLM(),
        )
        with TestClient(
            create_app(settings=settings, database=database, diagnosis_service=service)
        ) as api:
            created = api.post(
                "/api/v1/diagnoses",
                json={
                    "title": "Configuration startup failure",
                    "symptom": "missing property downstream URL during startup configuration",
                },
            )
            created.raise_for_status()
            diagnosis_id = created.json()["id"]
            run = api.post(f"/api/v1/diagnoses/{diagnosis_id}/runs")
            trace = api.get(f"/api/v1/diagnoses/{diagnosis_id}/trace")
            evidence = api.get(f"/api/v1/diagnoses/{diagnosis_id}/evidence")
            run.raise_for_status()
            trace.raise_for_status()
            evidence.raise_for_status()

        trace_body = trace.json()
        config_evidence = [item for item in evidence.json() if item["type"] == "config_excerpt"]
        tool_events = [
            event
            for item in trace_body["runs"]
            for event in item["events"]
            if event["type"] == "tool_call"
        ]
        assert trace_body["runs"][0]["strategy"] == "configuration_diagnosis_v1"
        assert config_evidence and "do-not-persist" not in json.dumps(config_evidence)
        assert tool_events[0]["evidence_ids"] == [config_evidence[0]["id"]]
        print(
            json.dumps(
                {
                    "diagnosis_id": diagnosis_id,
                    "strategy": trace_body["runs"][0]["strategy"],
                    "termination_reason": run.json()["termination_reason"],
                    "trace_event_count": len(trace_body["runs"][0]["events"]),
                    "config_evidence_count": len(config_evidence),
                    "redaction_verified": True,
                    "external_model_called": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
