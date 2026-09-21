param(
    [int] $Port = 8765
)

# Keep the local dashboard running without opening a terminal or browser.
# This wrapper is intended for the Windows logon scheduled task.
# Cursor is not required. The task should keep http://127.0.0.1:8765 available
# whenever this Windows account is logged in.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "local_files.ps1")
$Executable = Join-Path $ProjectRoot "app\Internship Search.exe"
$FallbackLogDir = Join-Path $ProjectRoot "app"
$FallbackLogFile = Join-Path $FallbackLogDir "dashboard_task.log"
$DashboardUrl = "http://127.0.0.1:$Port"
$LogFile = $FallbackLogFile

function Write-DashboardTaskLog {
    param([string] $Message)

    $Timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    $Line = "[$Timestamp] $Message"
    try {
        $LogParent = Split-Path -Parent $LogFile
        New-Item -ItemType Directory -Force -Path $LogParent | Out-Null
        $Line | Add-Content -LiteralPath $LogFile -Encoding UTF8
    } catch {
        try {
            New-Item -ItemType Directory -Force -Path $FallbackLogDir | Out-Null
            $Line | Add-Content -LiteralPath $FallbackLogFile -Encoding UTF8
        } catch {
        }
    }
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

function Use-DriveLogs {
    $LogDir = Join-Path $InternshipSearchDataDir "scheduled_run_output"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $script:LogFile = Join-Path $LogDir "dashboard_task.log"
}

Set-Location $ProjectRoot
Write-DashboardTaskLog "Dashboard supervisor starting. Waiting for Google Drive if needed."
Wait-InternshipSearchFiles -TimeoutSeconds 0 -PollSeconds 10
Use-DriveLogs
Write-DashboardTaskLog "Google Drive runtime files are available."

$env:INTERNSHIP_APP_PORT = "$Port"
$env:INTERNSHIP_APP_OPEN_BROWSER = "false"

while ($true) {
    if (-not (Test-Path -LiteralPath $Executable)) {
        Write-DashboardTaskLog "Dashboard executable is missing: $Executable. Rebuild it with config\build_windows_app.ps1. Retrying in 30 seconds."
        Start-Sleep -Seconds 30
        continue
    }

    if (Test-DashboardHealth) {
        Write-DashboardTaskLog "Dashboard is healthy at $DashboardUrl; monitoring without starting a duplicate."
        while (Test-DashboardHealth) {
            Start-Sleep -Seconds 15
        }
        Write-DashboardTaskLog "The previously running dashboard stopped responding; starting the managed process."
    }

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
