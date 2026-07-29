from datetime import UTC, datetime

import pytest

from app_diagnosis.domain.service_profile import ServiceProfile


def test_service_profile_normalizes_tags_and_keeps_explicit_paths() -> None:
    service = ServiceProfile.create(
        name=" diagnosis-java-lab ",
        environment=" local ",
        code_workspace_path=r"D:\AgentStudy\diagnosis-java-lab",
        log_directory=r"D:\AgentStudy\diagnosis-java-lab\logs",
        health_targets=(" http://localhost:18080/actuator/health ", ""),
        tags=("java", " lab ", "java"),
        now=datetime(2026, 7, 29, 12, 0, tzinfo=UTC),
    )

    assert service.name == "diagnosis-java-lab"
    assert service.environment == "local"
    assert service.health_targets == ("http://localhost:18080/actuator/health",)
    assert service.tags == ("java", "lab")


def test_service_profile_rejects_parent_path_traversal() -> None:
    with pytest.raises(ValueError, match="parent traversal"):
        ServiceProfile.create(
            name="bad",
            environment="local",
            code_workspace_path=r"D:\AgentStudy\..\secret",
        )
