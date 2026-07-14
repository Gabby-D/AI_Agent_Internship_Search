from internship_search.job_collector import JobPosting
from internship_search.posting_metadata import (
    clear_posting_metadata_cache,
    company_name_from_board_slug,
    enrich_job_posting,
    infer_company_from_posting_url,
    infer_location_from_snippet,
    merge_posting_metadata,
    parse_greenhouse_url,
    parse_job_board_title,
    parse_lever_url,
)


def make_posting(**kwargs) -> JobPosting:
    defaults = {
        "title": "Untitled posting",
        "company": "Unknown Company",
        "location": "Unknown",
        "posting_url": "https://example.com/jobs/1",
        "date_collected": "2026-07-13",
        "source_url": "https://example.com/careers",
    }
    defaults.update(kwargs)
    return JobPosting(**defaults)


def test_parse_job_board_title_splits_greenhouse_application_titles():
    title, company = parse_job_board_title(
        "Job Application for 2027 Internship - Quant Research (Undergrad) at Virtu Financial",
        "https://job-boards.greenhouse.io/virtu/jobs/8142539002",
    )

    assert title == "2027 Internship - Quant Research (Undergrad)"
    assert company == "Virtu Financial"


def test_parse_job_board_title_uses_url_slug_when_company_is_truncated():
    title, company = parse_job_board_title(
        "Job Application for Software Engineer, Intern (Summer 2027) at ...",
        "https://job-boards.greenhouse.io/aquaticcapitalmanagement/jobs/8489233002",
    )

    assert title == "Software Engineer, Intern (Summer 2027)"
    assert company == "Aquatic Capital Management"


def test_infer_company_from_posting_url_handles_greenhouse_and_lever():
    assert (
        infer_company_from_posting_url("https://job-boards.greenhouse.io/virtu/jobs/8142539002")
        == "Virtu Financial"
    )
    assert infer_company_from_posting_url("https://jobs.lever.co/palantir/abc123") == "Palantir"


def test_infer_location_from_snippet_extracts_city():
    assert infer_location_from_snippet("Summer 2027 internship in New York, NY for analysts.") == "New York, NY"


def test_enrich_job_posting_uses_greenhouse_api_payload(monkeypatch):
    clear_posting_metadata_cache()

    def fake_fetch(url: str) -> dict:
        assert "boards-api.greenhouse.io" in url
        return {
            "title": "2027 Internship - Quant Research (Undergrad)",
            "company_name": "Virtu Financial",
            "location": {"name": "New York"},
        }

    posting = make_posting(
        title="Job Application for 2027 Internship - Quant Research (Undergrad) at ...",
        company="...",
        location="Unknown",
        posting_url="https://job-boards.greenhouse.io/virtu/jobs/8142539002",
    )

    enriched = enrich_job_posting(posting, fetch_json=fake_fetch)

    assert enriched.title == "2027 Internship - Quant Research (Undergrad)"
    assert enriched.company == "Virtu Financial"
    assert enriched.location == "New York"


def test_enrich_job_posting_uses_lever_api_payload(monkeypatch):
    clear_posting_metadata_cache()

    def fake_fetch(url: str) -> dict:
        assert "api.lever.co" in url
        return {
            "text": "Forward Deployed Software Engineer, Internship - US Government",
            "categories": {"location": "Honolulu, HI"},
        }

    posting = make_posting(
        title="Forward Deployed Software Engineer, Internship - US Government at Palantir",
        company="Unknown Company",
        location="Unknown",
        posting_url="https://jobs.lever.co/palantir/315f695d-04d1-4a9a-848e-cb2bec7a997e",
    )

    enriched = enrich_job_posting(posting, fetch_json=fake_fetch)

    assert enriched.company == "Palantir"
    assert enriched.location == "Honolulu, HI"


def test_merge_posting_metadata_prefers_known_location():
    primary = make_posting(location="Unknown", company="Virtu Financial")
    secondary = make_posting(location="New York", company="...")

    merged = merge_posting_metadata(primary, secondary)

    assert merged.location == "New York"
    assert merged.company == "Virtu Financial"


def test_parse_greenhouse_and_lever_urls():
    assert parse_greenhouse_url("https://job-boards.greenhouse.io/virtu/jobs/8142539002") == (
        "virtu",
        "8142539002",
    )
    assert parse_lever_url("https://jobs.lever.co/palantir/abc-123") == ("palantir", "abc-123")


def test_company_name_from_board_slug_handles_known_and_unknown_slugs():
    assert company_name_from_board_slug("virtu") == "Virtu Financial"
    assert company_name_from_board_slug("newco-labs") == "Newco Labs"
