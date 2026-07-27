param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $EmailArgs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "data\scheduled_run_output"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "weekly_email_$Timestamp.log"
$Command = @(
    "run",
    "internship-search",
    "run-scheduled-collection",
    "--send-email",
    "--include-job-boards"
) + $EmailArgs
$AutomationLock = [System.Threading.Mutex]::new(
    $false,
    "Local\AI_Agent_Internship_Automation"
)
$HasLock = $false

Set-Location $ProjectRoot
try {
    try {
        $HasLock = $AutomationLock.WaitOne([TimeSpan]::FromHours(4))
    } catch [System.Threading.AbandonedMutexException] {
        $HasLock = $true
    }
    if (-not $HasLock) {
        throw "Timed out waiting for another internship automation task to finish."
    }

    "[$Timestamp] Starting fresh weekly collection and email send in $ProjectRoot" | Tee-Object -FilePath $LogFile
    "Command: uv $($Command -join ' ')" | Tee-Object -FilePath $LogFile -Append

    & uv @Command *>&1 | Tee-Object -FilePath $LogFile -Append
    $ExitCode = $LASTEXITCODE

    "[$((Get-Date).ToString('yyyyMMdd_HHmmss'))] Finished with exit code $ExitCode" | Tee-Object -FilePath $LogFile -Append
} finally {
    if ($HasLock) {
        $AutomationLock.ReleaseMutex()
    }
    $AutomationLock.Dispose()
}
exit $ExitCode
