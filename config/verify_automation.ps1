# Quick local checks for email configuration and Windows scheduled tasks.
# Does not print secret values.

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== Email environment ==="
uv run python -c @"
from internship_search.env_loader import load_env_into_process, get_env
load_env_into_process()
keys = [
    'EMAIL_FROM', 'EMAIL_TO', 'EMAIL_SMTP_PASSWORD',
    'EMAIL_SMTP_HOST', 'EMAIL_SMTP_PORT', 'EMAIL_SMTP_USER',
]
defaults = {
    'EMAIL_SMTP_HOST': 'smtp.gmail.com',
    'EMAIL_SMTP_PORT': '587',
}
for key in keys:
    value = get_env(key)
    if value:
        print(f'{key}: SET')
    elif key in defaults:
        print(f'{key}: DEFAULT ({defaults[key]})')
    else:
        print(f'{key}: MISSING')
"@

Write-Host ""
Write-Host "=== Scheduled tasks ==="
$TaskNames = @(
    "AI Agent Internship Company Discovery",
    "AI Agent Internship Search",
    "AI Agent Internship Weekly Email"
)
foreach ($TaskName in $TaskNames) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($null -eq $Task) {
        Write-Host "$TaskName : NOT REGISTERED"
        continue
    }
    $Info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "$TaskName : $($Task.State) | Last run: $($Info.LastRunTime) | Last result: $($Info.LastTaskResult)"
}

Write-Host ""
Write-Host "=== Recent automation logs ==="
$LogDir = Join-Path $ProjectRoot "data\scheduled_run_output"
if (Test-Path $LogDir) {
    Get-ChildItem $LogDir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 5 |
        Format-Table Name, LastWriteTime, Length -AutoSize
} else {
    Write-Host "No wrapper logs yet at $LogDir"
}

$RunsLog = Join-Path $ProjectRoot "data\scheduled_collection_runs.jsonl"
if (Test-Path $RunsLog) {
    $LastLine = Get-Content $RunsLog -Tail 1
    if ($LastLine) {
        Write-Host ""
        Write-Host "Latest structured run (tail):"
        Write-Host $LastLine
    }
}
