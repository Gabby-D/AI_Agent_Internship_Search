from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_weekly_company_discovery_is_registered_before_collection_and_email():
    registration = (PROJECT_ROOT / "config/register_scheduled_tasks.ps1").read_text(
        encoding="utf-8"
    )
    verification = (PROJECT_ROOT / "config/verify_automation.ps1").read_text(
        encoding="utf-8"
    )
    wrapper = (PROJECT_ROOT / "config/run_company_discovery.ps1").read_text(
        encoding="utf-8"
    )

    assert "AI Agent Internship Company Discovery" in registration
    assert 'CompanyDiscoveryAt = "08:30"' in registration
    assert "-Weekly -DaysOfWeek Monday -At $CompanyDiscoveryAt" in registration
    assert "AI Agent Internship Company Discovery" in verification
    assert '"discover-companies"' in wrapper
    assert '"company_discovery_$Timestamp.log"' in wrapper
    assert "local_files.ps1" in wrapper
    assert "InternshipSearchDataDir" in wrapper
    assert r"G:\My Drive\none_git_files\AI_Agent_Internship_Search" in (
        PROJECT_ROOT / "config/local_files.ps1"
    ).read_text(encoding="utf-8")


def test_scheduled_tasks_wake_retry_serialize_and_refresh_before_email():
    registration = (PROJECT_ROOT / "config/register_scheduled_tasks.ps1").read_text(
        encoding="utf-8"
    )
    wrappers = [
        (PROJECT_ROOT / f"config/{name}").read_text(encoding="utf-8")
        for name in (
            "run_company_discovery.ps1",
            "run_scheduled_collection.ps1",
            "run_weekly_email.ps1",
        )
    ]
    weekly = wrappers[-1]
    silent_launcher = (PROJECT_ROOT / "config/run_silent.vbs").read_text(encoding="utf-8")
    local_files = (PROJECT_ROOT / "config/local_files.ps1").read_text(encoding="utf-8")

    assert "-WakeToRun" in registration
    assert "-RestartCount 3" in registration
    assert "-RestartCount 999" in registration
    assert "-RepetitionInterval (New-TimeSpan -Minutes 15)" in registration
    assert "-RestartInterval (New-TimeSpan -Minutes 5)" in registration
    assert "-MultipleInstances IgnoreNew" in registration
    assert "$Settings.Hidden = $true" in registration
    assert "$DashboardSettings.Hidden = $true" in registration
    assert '-Execute "wscript.exe"' in registration
    assert "run_silent.vbs" in registration
    assert "shell.Run command, 0, True" in silent_launcher
    assert "pythonw.exe" in local_files
    assert "Invoke-InternshipSearchCli" in local_files
    assert all("Invoke-InternshipSearchCli" in wrapper for wrapper in wrappers)
    assert all("Local\\AI_Agent_Internship_Automation" in wrapper for wrapper in wrappers)
    assert all("InternshipSearchDataDir" in wrapper for wrapper in wrappers)
    assert all("Wait-InternshipSearchFiles" in wrapper for wrapper in wrappers)
    assert '"run-scheduled-collection"' in weekly
    assert '"--send-email"' in weekly
    assert '"--include-job-boards"' in weekly
    assert "last_successful_week" in weekly
    assert "-Daily -At $WeeklyEmailAt" in registration
    dashboard = (PROJECT_ROOT / "config/run_dashboard.ps1").read_text(encoding="utf-8")
    assert "Wait-InternshipSearchFiles -TimeoutSeconds 0" in dashboard
