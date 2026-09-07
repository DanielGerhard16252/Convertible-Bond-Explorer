$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$environmentFile = Join-Path $projectRoot ".env"
$specFile = Join-Path $projectRoot "ConvertibleBondExplorer.spec"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Virtual environment not found at $python"
}

if (-not (Test-Path -LiteralPath $environmentFile)) {
    throw "Missing .env. Copy .env.example to .env and add OPENAI_API_KEY."
}

$apiKeyEntry = Get-Content -LiteralPath $environmentFile |
    Where-Object { $_ -match '^\s*OPENAI_API_KEY\s*=\s*\S+' } |
    Select-Object -First 1

if (-not $apiKeyEntry) {
    throw ".env does not contain a non-empty OPENAI_API_KEY."
}

Push-Location $projectRoot
try {
    & $python -m PyInstaller --clean --noconfirm $specFile
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Write-Host "Built dist\ConvertibleBondExplorer.exe"
Write-Warning "The bundled OPENAI_API_KEY can be extracted from the executable."
