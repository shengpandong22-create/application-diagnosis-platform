$ErrorActionPreference = "Stop"

uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run pytest `
  tests/unit/domain/incident `
  tests/integration/persistence/test_incident_repository.py `
  tests/integration/persistence/test_incident_migration.py `
  tests/integration/test_incident_api.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Output "Phase 4B acceptance: PASSED"
