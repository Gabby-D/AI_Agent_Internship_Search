# Start the local internship review dashboard.
# Keep this PowerShell window open while you use the site.

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

uv run internship-search review-ui @args
