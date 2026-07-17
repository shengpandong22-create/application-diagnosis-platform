from pathlib import Path

import pytest

from app_diagnosis.adapters.logs.local_file import InvalidLogRead, LocalLogFileReader
from app_diagnosis.adapters.redaction import LocalRuleRedactor


def test_extracts_latest_matching_excerpt_with_bounds(tmp_path: Path) -> None:
    log = tmp_path / "application.log"
    lines = ["2026-07-17 10:00:00.000 ERROR first NullPointerException", " first stack"]
    lines += ["2026-07-17 10:00:01.000 INFO between events"]
    lines += ["2026-07-17 10:00:02.000 ERROR latest NullPointerException", " latest stack"]
    log.write_text("\n".join(lines), encoding="utf-8")

    excerpt = LocalLogFileReader(tmp_path, max_excerpt_lines=12).read_latest(
        relative_path="application.log", keyword="NullPointerException"
    )

    assert "latest NullPointerException" in excerpt.content
    assert "first NullPointerException" not in excerpt.content
    assert len(excerpt.content.splitlines()) <= 12
    assert excerpt.source_reference.startswith("application.log:")


def test_stops_at_next_timestamped_log_event(tmp_path: Path) -> None:
    (tmp_path / "application.log").write_text(
        "\n".join(
            [
                "2026-07-17 10:00:00.000 ERROR NPE happened",
                "java.lang.NullPointerException",
                "\tat app.OrderService.create(OrderService.java:8)",
                "2026-07-17 10:00:01.000 ERROR connection refused",
                "java.net.ConnectException: Connection refused",
            ]
        ),
        encoding="utf-8",
    )

    excerpt = LocalLogFileReader(tmp_path).read_latest(
        relative_path="application.log", keyword="NullPointerException"
    )

    assert "OrderService.java:8" in excerpt.content
    assert "connection refused" not in excerpt.content
    assert excerpt.source_reference == "application.log:1-3"


@pytest.mark.parametrize("path", ["../outside.log", "absolute.txt", "."])
def test_rejects_unsafe_or_unsupported_paths(tmp_path: Path, path: str) -> None:
    (tmp_path / "absolute.txt").write_text("error", encoding="utf-8")
    with pytest.raises(InvalidLogRead):
        LocalLogFileReader(tmp_path).read_latest(relative_path=path, keyword="error")


def test_reads_only_bounded_tail(tmp_path: Path) -> None:
    log = tmp_path / "large.log"
    log.write_text(
        "SECRET-OUTSIDE-TAIL\n" + ("padding\n" * 400) + "ERROR timeout\n", encoding="utf-8"
    )

    excerpt = LocalLogFileReader(tmp_path, max_tail_bytes=1024).read_latest(
        relative_path="large.log", keyword="timeout"
    )

    assert "timeout" in excerpt.content
    assert "SECRET-OUTSIDE-TAIL" not in excerpt.content


def test_extracted_log_can_be_redacted_before_persistence(tmp_path: Path) -> None:
    secret = "sk-1234567890abcdef1234567890"
    (tmp_path / "application.log").write_text(
        f"ERROR NullPointerException Authorization: Bearer {secret}\n",
        encoding="utf-8",
    )

    excerpt = LocalLogFileReader(tmp_path).read_latest(
        relative_path="application.log", keyword="NullPointerException"
    )
    safe = LocalRuleRedactor().redact(excerpt.content)

    assert secret not in safe.content
    assert "[REDACTED]" in safe.content
