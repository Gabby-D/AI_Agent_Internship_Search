param(
    [switch] $Force,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $EmailArgs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "data\scheduled_run_output"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "weekly_email_$Timestamp.log"
$StateFile = Join-Path $ProjectRoot "data\weekly_email_task_state.json"
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
$ExitCode = 1

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

    # The Windows task runs daily as a recovery trigger, but a successful summary
    # must be sent only once per Monday-based week. Re-read the state after taking
    # the shared lock so overlapping catch-up tasks cannot send duplicates.
    $Now = Get-Date
    $DaysSinceMonday = (([int] $Now.DayOfWeek + 6) % 7)
    $WeekStart = $Now.Date.AddDays(-$DaysSinceMonday).ToString("yyyy-MM-dd")
    $LastSuccessfulWeek = ""
    if (Test-Path $StateFile) {
        try {
            $State = Get-Content -LiteralPath $StateFile -Raw | ConvertFrom-Json
            $LastSuccessfulWeek = [string] $State.last_successful_week
        } catch {
            "[$Timestamp] Could not read weekly state; a fresh send will be attempted: $($_.Exception.Message)" |
                Tee-Object -FilePath $LogFile -Append
        }
    }

    if (-not $Force -and $LastSuccessfulWeek -eq $WeekStart) {
        "[$Timestamp] Weekly email already sent for week starting $WeekStart; nothing to do." |
            Tee-Object -FilePath $LogFile -Append
        $ExitCode = 0
        return
    }

    "[$Timestamp] Starting fresh weekly collection and email send in $ProjectRoot" | Tee-Object -FilePath $LogFile
    "Command: uv $($Command -join ' ')" | Tee-Object -FilePath $LogFile -Append

    & uv @Command *>&1 | Tee-Object -FilePath $LogFile -Append
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -eq 0) {
        @{
            last_successful_week = $WeekStart
            sent_at = (Get-Date).ToUniversalTime().ToString("o")
        } | ConvertTo-Json | Set-Content -LiteralPath $StateFile -Encoding UTF8
        "[$((Get-Date).ToString('yyyyMMdd_HHmmss'))] Recorded successful weekly send for $WeekStart" |
            Tee-Object -FilePath $LogFile -Append
    }

    "[$((Get-Date).ToString('yyyyMMdd_HHmmss'))] Finished with exit code $ExitCode" | Tee-Object -FilePath $LogFile -Append
} finally {
    if ($HasLock) {
        $AutomationLock.ReleaseMutex()
    }
    $AutomationLock.Dispose()
}
exit $ExitCode
