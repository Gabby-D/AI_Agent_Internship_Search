param(
    [switch] $Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$EntryPoint = Join-Path $PSScriptRoot "windows_app_entry.py"
$AppDir = Join-Path $ProjectRoot "app"
$WorkDir = Join-Path $ProjectRoot ".pyinstaller-build"

if (-not (Test-Path $Python)) {
    throw "Project Python environment not found at $Python. Run 'uv sync --dev' first."
}

if ($Clean) {
    Remove-Item -Recurse -Force -Path $AppDir, $WorkDir -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Force -Path $AppDir, $WorkDir | Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name "Internship Search" `
    --paths (Join-Path $ProjectRoot "src") `
    --distpath $AppDir `
    --workpath $WorkDir `
    --specpath $WorkDir `
    $EntryPoint

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

$Executable = Join-Path $AppDir "Internship Search.exe"
Write-Host "Built app: $Executable"
Write-Host "The executable reads private data from: $(Join-Path $ProjectRoot 'private')"
Write-Host "The executable reads generated data from: $(Join-Path $ProjectRoot 'data')"
