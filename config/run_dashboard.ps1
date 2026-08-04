param(
    [int] $Port = 8765
)

# Keep the local dashboard running without opening a terminal or browser.
# This wrapper is intended for the Windows logon scheduled task.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Executable = Join-Path $ProjectRoot "app\Internship Search.exe"
$LogDir = Join-Path $ProjectRoot "data\scheduled_run_output"
$LogFile = Join-Path $LogDir "dashboard_task.log"
$DashboardUrl = "http://127.0.0.1:$Port"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

function Write-DashboardTaskLog {
    param([string] $Message)

    $Timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    "[$Timestamp] $Message" | Add-Content -LiteralPath $LogFile -Encoding UTF8
}

function Test-DashboardHealth {
    try {
        $Response = Invoke-WebRequest `
            -Uri "$DashboardUrl/api/dashboard" `
            -UseBasicParsing `
            -TimeoutSec 5
        return $Response.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $Executable)) {
    Write-DashboardTaskLog "Dashboard executable is missing: $Executable"
    throw "Dashboard executable is missing. Rebuild it with config\build_windows_app.ps1."
}

$env:INTERNSHIP_APP_PORT = "$Port"
$env:INTERNSHIP_APP_OPEN_BROWSER = "false"

if (Test-DashboardHealth) {
    Write-DashboardTaskLog "Dashboard is already healthy at $DashboardUrl; monitoring without starting a duplicate."
    while (Test-DashboardHealth) {
        Start-Sleep -Seconds 15
    }
    Write-DashboardTaskLog "The previously running dashboard stopped responding; starting the managed process."
}

while ($true) {
    Write-DashboardTaskLog "Starting dashboard at $DashboardUrl."
    try {
        $Process = Start-Process `
            -FilePath $Executable `
            -WorkingDirectory $ProjectRoot `
            -WindowStyle Hidden `
            -PassThru

        Wait-Process -Id $Process.Id
        $Process.Refresh()
        $ExitCode = if ($null -ne $Process.ExitCode) { $Process.ExitCode } else { 1 }
        Write-DashboardTaskLog "Dashboard process exited with code $ExitCode; restarting in 10 seconds."
    } catch {
        Write-DashboardTaskLog "Dashboard process failed: $($_.Exception.Message); restarting in 10 seconds."
    }
    Start-Sleep -Seconds 10
}
