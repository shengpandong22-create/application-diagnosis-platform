$ErrorActionPreference = "Stop"

uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest `
  tests/unit/adapters/log_events `
  tests/unit/domain/incident `
  tests/integration/test_active_discovery_api.py `
  tests/integration/persistence/test_incident_repository.py `
  tests/integration/persistence/test_incident_migration.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/demo-phase4c.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "Phase 4C acceptance: PASSED"
