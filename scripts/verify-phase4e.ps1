$ErrorActionPreference = "Stop"
uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest `
  tests/unit/adapters/enterprise `
  tests/unit/adapters/code/test_gitlab_snapshot.py `
  tests/unit/adapters/notifications/test_webhook.py `
  tests/integration/test_active_discovery_api.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "Phase 4E contract acceptance: PASSED"
Write-Output "External RabbitMQ/Redis/GitLab integration: NOT RUN (optional environment required)"
