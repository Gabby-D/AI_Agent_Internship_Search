param(
    [ValidateSet("Daily", "Weekly")]
    [string] $Frequency = "Weekly",
    [string] $At = "09:00",
    [string] $TaskName = "AI Agent Internship Search",
    [string[]] $CollectionArgs = @(),
    [switch] $RegisterAll
)

# Registers local Windows scheduled tasks for the internship search workflow.
#
# Recommended setup for this project:
#   powershell -ExecutionPolicy Bypass -File config/register_scheduled_tasks.ps1
#
# That registers:
# - Daily collection at 9:00 AM
# - Weekly email send on Monday at 10:00 AM
# Both use StartWhenAvailable so missed runs start when the computer next turns on.
#
# This legacy script still supports registering a single task directly.

if ($RegisterAll) {
    & (Join-Path $PSScriptRoot "register_scheduled_tasks.ps1") @PSBoundParameters
    return
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$WrapperScript = Join-Path $PSScriptRoot "run_scheduled_collection.ps1"
$ArgumentList = @("-ExecutionPolicy", "Bypass", "-File", "`"$WrapperScript`"")
if ($CollectionArgs.Count -gt 0) {
    $ArgumentList += $CollectionArgs
}

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($ArgumentList -join " ") `
    -WorkingDirectory $ProjectRoot

if ($Frequency -eq "Daily") {
    $Trigger = New-ScheduledTaskTrigger -Daily -At $At
} else {
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $At
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Run the local internship search workflow. Missed runs start when the computer next becomes available." `
    -Force

Write-Host "Registered scheduled task '$TaskName' ($Frequency at $At, StartWhenAvailable enabled)."
Write-Host "Wrapper script: $WrapperScript"
Write-Host "Structured run log: $(Join-Path $ProjectRoot 'data/scheduled_collection_runs.jsonl')"
