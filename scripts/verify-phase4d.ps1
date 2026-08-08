$ErrorActionPreference = "Stop"
uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest `
  tests/unit/tools/test_related_logs.py `
  tests/integration/test_phase4d_operations.py `
  tests/integration/persistence/test_evaluation_candidate_migration.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run python scripts/demo-phase4d.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "Phase 4D acceptance: PASSED"
