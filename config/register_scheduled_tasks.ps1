param(
    [string] $CollectionTaskName = "AI Agent Internship Search",
    [string] $CompanyDiscoveryTaskName = "AI Agent Internship Company Discovery",
    [string] $WeeklyEmailTaskName = "AI Agent Internship Weekly Email",
    [string] $CompanyDiscoveryAt = "08:30",
    [string] $CollectionAt = "09:00",
    [string] $WeeklyEmailAt = "10:00",
    [string[]] $CompanyDiscoveryArgs = @(),
    [string[]] $CollectionArgs = @("--include-job-boards"),
    [string[]] $WeeklyEmailArgs = @()
)

# Registers local Windows scheduled tasks for:
# - Recommended-company discovery on Monday at 8:30 AM
# - Daily collection at 9:00 AM (includes --include-job-boards for LinkedIn, Indeed, and ATS boards)
# - Weekly email send on Monday at 10:00 AM
#
# All tasks use StartWhenAvailable so a missed run starts when the computer
# next becomes available (for example, after the machine is turned on).

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$CompanyDiscoveryWrapper = Join-Path $PSScriptRoot "run_company_discovery.ps1"
$CollectionWrapper = Join-Path $PSScriptRoot "run_scheduled_collection.ps1"
$WeeklyEmailWrapper = Join-Path $PSScriptRoot "run_weekly_email.ps1"

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

function Build-WrapperArguments {
    param(
        [string] $WrapperScript,
        [string[]] $ExtraArgs
    )

    $ArgumentList = @("-ExecutionPolicy", "Bypass", "-File", "`"$WrapperScript`"")
    if ($ExtraArgs.Count -gt 0) {
        $ArgumentList += $ExtraArgs
    }
    return $ArgumentList -join " "
}

$CompanyDiscoveryAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument (Build-WrapperArguments -WrapperScript $CompanyDiscoveryWrapper -ExtraArgs $CompanyDiscoveryArgs) `
    -WorkingDirectory $ProjectRoot

$CompanyDiscoveryTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $CompanyDiscoveryAt

Register-ScheduledTask `
    -TaskName $CompanyDiscoveryTaskName `
    -Action $CompanyDiscoveryAction `
    -Trigger $CompanyDiscoveryTrigger `
    -Settings $Settings `
    -Description "Refresh recommended companies every Monday. Missed runs start when the computer next becomes available." `
    -Force | Out-Null

$CollectionAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument (Build-WrapperArguments -WrapperScript $CollectionWrapper -ExtraArgs $CollectionArgs) `
    -WorkingDirectory $ProjectRoot

$CollectionTrigger = New-ScheduledTaskTrigger -Daily -At $CollectionAt

Register-ScheduledTask `
    -TaskName $CollectionTaskName `
    -Action $CollectionAction `
    -Trigger $CollectionTrigger `
    -Settings $Settings `
    -Description "Run the local internship search workflow daily. Missed runs start when the computer next becomes available." `
    -Force | Out-Null

$WeeklyEmailAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument (Build-WrapperArguments -WrapperScript $WeeklyEmailWrapper -ExtraArgs $WeeklyEmailArgs) `
    -WorkingDirectory $ProjectRoot

$WeeklyEmailTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At $WeeklyEmailAt

Register-ScheduledTask `
    -TaskName $WeeklyEmailTaskName `
    -Action $WeeklyEmailAction `
    -Trigger $WeeklyEmailTrigger `
    -Settings $Settings `
    -Description "Send the weekly internship email summary on Monday. Missed runs start when the computer next becomes available." `
    -Force | Out-Null

Write-Host "Registered company-discovery task '$CompanyDiscoveryTaskName' (Monday at $CompanyDiscoveryAt, StartWhenAvailable enabled)."
Write-Host "Registered collection task '$CollectionTaskName' (Daily at $CollectionAt, StartWhenAvailable enabled)."
Write-Host "Registered weekly email task '$WeeklyEmailTaskName' (Monday at $WeeklyEmailAt, StartWhenAvailable enabled)."
Write-Host "Company-discovery wrapper: $CompanyDiscoveryWrapper"
Write-Host "Collection wrapper: $CollectionWrapper"
Write-Host "Weekly email wrapper: $WeeklyEmailWrapper"
Write-Host "Console logs: $(Join-Path $ProjectRoot 'data/scheduled_run_output')"
Write-Host "Structured run log: $(Join-Path $ProjectRoot 'data/scheduled_collection_runs.jsonl')"
