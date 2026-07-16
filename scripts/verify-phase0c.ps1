param([switch]$SkipSync)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$acceptance = [System.IO.Path]::GetFullPath((Join-Path $root '.phase0c-acceptance'))
if (-not $acceptance.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Invalid acceptance path' }

function Invoke-Uv {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & uv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "uv command failed: uv $($Arguments -join ' ')" }
}

Push-Location $root
$previousDatabaseUrl = $env:APP_DATABASE_URL
try {
    if (-not $SkipSync) { Invoke-Uv sync --extra dev }
    Invoke-Uv run ruff check .
    Invoke-Uv run pytest
    New-Item -ItemType Directory -Path $acceptance -Force | Out-Null
    Invoke-Uv run python -m app_diagnosis.evaluation.cli --cases evals/cases/phase0c-baseline.json --output (Join-Path $acceptance 'evaluation.json')
    $database = (Join-Path $acceptance 'acceptance.db').Replace('\', '/')
    $env:APP_DATABASE_URL = "sqlite+aiosqlite:///$database"
    Invoke-Uv run alembic upgrade head
    Invoke-Uv run alembic check
    Invoke-Uv run python -c "from app_diagnosis.api.app import create_app; p=create_app().openapi()['paths']; r={'/ui','/api/v1/diagnoses/{diagnosis_id}/report','/api/v1/diagnoses/{diagnosis_id}/report.md'}; m=r-set(p); assert not m,m; print('Phase 0C OpenAPI contract: passed')"
    Invoke-Uv run python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); assert d['total']==d['passed'] and d['citation_valid_rate']==1.0; print('Phase 0C evaluation contract: passed')" (Join-Path $acceptance 'evaluation.json')
    Write-Host 'Phase 0C acceptance: PASSED' -ForegroundColor Green
}
finally {
    if ($null -eq $previousDatabaseUrl) { Remove-Item Env:APP_DATABASE_URL -ErrorAction SilentlyContinue } else { $env:APP_DATABASE_URL = $previousDatabaseUrl }
    if (Test-Path -LiteralPath $acceptance) { Remove-Item -LiteralPath $acceptance -Recurse -Force }
    Pop-Location
}
