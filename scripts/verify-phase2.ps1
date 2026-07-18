param([switch]$SkipSync)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$acceptance = [System.IO.Path]::GetFullPath((Join-Path $root '.phase2-acceptance'))
if (-not $acceptance.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Invalid acceptance path'
}

function Invoke-Uv {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & uv @Arguments
    if ($LASTEXITCODE -ne 0) { throw "uv command failed: uv $($Arguments -join ' ')" }
}

Push-Location $root
$previousDatabaseUrl = $env:APP_DATABASE_URL
try {
    Write-Host 'Phase 2 acceptance uses Fake LLM only; no external model will be called.'
    if (-not $SkipSync) { Invoke-Uv sync --extra dev }
    Invoke-Uv run ruff check .
    Invoke-Uv run pytest
    New-Item -ItemType Directory -Path $acceptance -Force | Out-Null
    $database = (Join-Path $acceptance 'acceptance.db').Replace('\', '/')
    $env:APP_DATABASE_URL = "sqlite+aiosqlite:///$database"
    Invoke-Uv run alembic upgrade head
    Invoke-Uv run alembic check
    Invoke-Uv run python scripts/demo-phase2.py
    Invoke-Uv run python -c "from app_diagnosis.api.app import create_app; p=create_app().openapi()['paths']; r={'/ui','/api/v1/diagnoses/{diagnosis_id}/trace'}; m=r-set(p); assert not m,m; print('Phase 2 OpenAPI contract: passed')"
    Write-Host 'Phase 2 acceptance: PASSED' -ForegroundColor Green
}
finally {
    if ($null -eq $previousDatabaseUrl) {
        Remove-Item Env:APP_DATABASE_URL -ErrorAction SilentlyContinue
    } else {
        $env:APP_DATABASE_URL = $previousDatabaseUrl
    }
    if (Test-Path -LiteralPath $acceptance) {
        Remove-Item -LiteralPath $acceptance -Recurse -Force
    }
    Pop-Location
}
