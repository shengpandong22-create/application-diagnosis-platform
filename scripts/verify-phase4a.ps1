param(
    [switch]$SkipSync,
    [switch]$SkipJava,
    [string]$JavaLabPath = ""
)

$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$acceptance = [System.IO.Path]::GetFullPath((Join-Path $root '.phase4a-acceptance'))
if (-not $acceptance.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Invalid acceptance path'
}
if (-not $JavaLabPath) {
    $JavaLabPath = [System.IO.Path]::GetFullPath((Join-Path $root '..\diagnosis-java-lab'))
}

function Invoke-Uv {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & $uv.Source @Arguments
    }
    else {
        & python -m uv @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "uv command failed: uv $($Arguments -join ' ')"
    }
}

Push-Location $root
try {
    if (-not $SkipSync) {
        Invoke-Uv sync --extra dev
    }
    Invoke-Uv run ruff check .
    Invoke-Uv run pytest

    New-Item -ItemType Directory -Path $acceptance -Force | Out-Null
    Invoke-Uv run python -m app_diagnosis.evaluation.cli `
        --cases evals/cases/phase4a-quality-baseline.json `
        --output (Join-Path $acceptance 'evaluation.json')
    Invoke-Uv run python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); assert d['dataset_versions']==['phase4a-v1']; assert d['total']==d['passed']==2; assert d['category_accuracy']==1.0; assert d['citation_precision']==d['citation_recall']==1.0; assert d['unsupported_claim_rate']==0.0; print('Phase 4A quality metrics: passed')" (Join-Path $acceptance 'evaluation.json')
    Invoke-Uv run python -c "import json; d=json.load(open('evals/cases/phase4a-java-lab-cases.json',encoding='utf-8')); c=d['cases']; assert len(c)==8; assert {x['expected_category'] for x in c}=={'code_bug','config','dependency','external'}; assert 'related_logs' in {x['expected_context_depth'] for x in c}; print('Phase 4A Java Lab catalog: passed')"

    if (-not $SkipJava) {
        if (-not (Test-Path -LiteralPath (Join-Path $JavaLabPath 'pom.xml'))) {
            throw "Java Lab not found: $JavaLabPath"
        }
        Push-Location $JavaLabPath
        try {
            & mvn test
            if ($LASTEXITCODE -ne 0) {
                throw 'Java Lab tests failed'
            }
        }
        finally {
            Pop-Location
        }
    }

    Write-Host 'Phase 4A acceptance: PASSED' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $acceptance) {
        Remove-Item -LiteralPath $acceptance -Recurse -Force
    }
    Pop-Location
}
