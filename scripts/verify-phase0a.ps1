param([switch]$SkipSync)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$acceptance = [System.IO.Path]::GetFullPath((Join-Path $root '.phase0a-acceptance'))
$expected = [System.IO.Path]::GetFullPath((Join-Path $root '.phase0a-acceptance'))
if ($acceptance -ne $expected -or -not $acceptance.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Acceptance directory path validation failed'
}

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
    $database = (Join-Path $acceptance 'acceptance.db').Replace('\', '/')
    $env:APP_DATABASE_URL = "sqlite+aiosqlite:///$database"
    Invoke-Uv run alembic upgrade head
    Invoke-Uv run alembic check
    Invoke-Uv run python -c "from app_diagnosis.api.app import create_app; paths=create_app().openapi()['paths']; required={'/health/live','/health/ready','/api/v1/diagnoses','/api/v1/diagnoses/{diagnosis_id}','/api/v1/diagnoses/{diagnosis_id}/runs','/api/v1/diagnoses/{diagnosis_id}/cancel'}; missing=required-set(paths); assert not missing, missing; print('OpenAPI contract: passed')"
    Write-Host 'Phase 0A acceptance: PASSED' -ForegroundColor Green
}
finally {
    if ($null -eq $previousDatabaseUrl) { Remove-Item Env:APP_DATABASE_URL -ErrorAction SilentlyContinue } else { $env:APP_DATABASE_URL = $previousDatabaseUrl }
    if (Test-Path -LiteralPath $acceptance) { Remove-Item -LiteralPath $acceptance -Recurse -Force }
    Pop-Location
}
