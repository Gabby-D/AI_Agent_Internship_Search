param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $CollectionArgs
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $ProjectRoot "data\scheduled_run_output"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "run_$Timestamp.log"
$Command = @("run", "internship-search", "run-scheduled-collection") + $CollectionArgs

Set-Location $ProjectRoot
"[$Timestamp] Starting scheduled collection in $ProjectRoot" | Tee-Object -FilePath $LogFile
"Command: uv $($Command -join ' ')" | Tee-Object -FilePath $LogFile -Append

& uv @Command *>&1 | Tee-Object -FilePath $LogFile -Append
$ExitCode = $LASTEXITCODE

"[$((Get-Date).ToString('yyyyMMdd_HHmmss'))] Finished with exit code $ExitCode" | Tee-Object -FilePath $LogFile -Append
exit $ExitCode
