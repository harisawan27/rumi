param([switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create desktop\.venv and install requirements-lock.txt first. See desktop\README.md.' }
if (-not $SkipFrontend) {
    Push-Location (Join-Path $repo 'frontend')
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
    } finally { Pop-Location }
}
$ui = Join-Path $repo 'frontend\out'
$icon = Join-Path $repo 'frontend\public\favicon.ico'
if (-not (Test-Path -LiteralPath (Join-Path $ui 'desktop-local\index.html'))) { throw 'Native UI export missing' }
Push-Location $repo
try {
    & $python -m PyInstaller --noconfirm --windowed --onedir --name RumiDesktop --distpath desktop/dist --workpath desktop/build --specpath desktop/build --paths backend --add-data "$ui;ui" --icon $icon desktop/main.py
    if ($LASTEXITCODE -ne 0) { throw 'Windows packaging failed' }
    & $python desktop/write_notices.py
    if ($LASTEXITCODE -ne 0) { throw 'Dependency notice collection failed' }
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination (Join-Path $PSScriptRoot 'dist\RumiDesktop\README.md')
    Compress-Archive -LiteralPath (Join-Path $PSScriptRoot 'dist\RumiDesktop') -DestinationPath (Join-Path $PSScriptRoot 'dist\RumiDesktop-Windows.zip') -Force
    Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'dist\RumiDesktop-Windows.zip') -Algorithm SHA256
} finally { Pop-Location }
