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
