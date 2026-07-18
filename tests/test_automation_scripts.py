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
