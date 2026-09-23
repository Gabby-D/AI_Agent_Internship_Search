param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $DiscoveryArgs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "local_files.ps1")
Wait-InternshipSearchFiles
$LogDir = Join-Path $InternshipSearchDataDir "scheduled_run_output"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "company_discovery_$Timestamp.log"
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

    "[$Timestamp] Starting recommended-company discovery in $ProjectRoot" | Tee-Object -FilePath $LogFile
    $ExitCode = Invoke-InternshipSearchCli `
        -ProjectRoot $ProjectRoot `
        -CliArgs (@("discover-companies") + $DiscoveryArgs) `
        -LogFile $LogFile

    "[$((Get-Date).ToString('yyyyMMdd_HHmmss'))] Finished with exit code $ExitCode" | Tee-Object -FilePath $LogFile -Append
} finally {
    if ($HasLock) {
        $AutomationLock.ReleaseMutex()
    }
    $AutomationLock.Dispose()
}
exit $ExitCode
