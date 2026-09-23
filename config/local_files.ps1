# Live gitignored files for this project.
# Python code reads the same path from internship_search.paths.

$InternshipSearchFilesRoot = "G:\My Drive\none_git_files\AI_Agent_Internship_Search"
$InternshipSearchDataDir = Join-Path $InternshipSearchFilesRoot "data"
$InternshipSearchPrivateDir = Join-Path $InternshipSearchFilesRoot "private"
$InternshipSearchEnvFile = Join-Path $InternshipSearchFilesRoot ".env"

function Wait-InternshipSearchFiles {
    param(
        [int] $TimeoutSeconds = 300,
        [int] $PollSeconds = 5
    )

    $waitForever = $TimeoutSeconds -le 0
    $deadline = if ($waitForever) { [datetime]::MaxValue } else { (Get-Date).AddSeconds($TimeoutSeconds) }
    while (
        -not (Test-Path -LiteralPath $InternshipSearchFilesRoot) -or
        -not (Test-Path -LiteralPath $InternshipSearchPrivateDir)
    ) {
        if ((Get-Date) -ge $deadline) {
            throw "Google Drive runtime files are not available at $InternshipSearchFilesRoot. Sign in to Drive for desktop and wait for G: to finish syncing."
        }
        Start-Sleep -Seconds $PollSeconds
    }
}

function Invoke-InternshipSearchCli {
    param(
        [Parameter(Mandatory = $true)]
        [string] $ProjectRoot,
        [Parameter(Mandatory = $true)]
        [string[]] $CliArgs,
        [Parameter(Mandatory = $true)]
        [string] $LogFile
    )

    $Pythonw = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
    if (-not (Test-Path -LiteralPath $Pythonw)) {
        throw "Project Python environment not found at $Pythonw."
    }

    $Command = @("-m", "internship_search") + $CliArgs
    "Command: $Pythonw $($Command -join ' ')" | Tee-Object -FilePath $LogFile -Append
    & $Pythonw @Command *>&1 | Tee-Object -FilePath $LogFile -Append
    return $LASTEXITCODE
}
