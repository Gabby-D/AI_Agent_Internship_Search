from internship_search.job_board_listings import (
    canonical_aggregator_job_url,
    is_indeed_listing_url,
    is_linkedin_listing_url,
    is_public_aggregator_listing_url,
    normalize_indeed_job_url,
    normalize_linkedin_job_url,
)


def test_normalize_linkedin_job_url_strips_tracking_and_subdomains():
    url = "https://www.linkedin.com/jobs/view/12345?utm_source=ddg&trk=public"
    assert normalize_linkedin_job_url(url) == "https://www.linkedin.com/jobs/view/12345"


def test_normalize_indeed_job_url_uses_jk_parameter():
    url = "https://www.indeed.com/viewjob?jk=ABC123&from=serp"
    assert normalize_indeed_job_url(url) == "https://www.indeed.com/viewjob?jk=abc123"


def test_canonical_aggregator_job_url_returns_none_for_career_pages():
    assert canonical_aggregator_job_url("https://boards.greenhouse.io/example/jobs/1") is None


def test_is_public_aggregator_listing_url_rejects_search_pages():
    assert is_public_aggregator_listing_url("https://www.linkedin.com/jobs/view/12345")
    assert is_public_aggregator_listing_url("https://www.indeed.com/viewjob?jk=abc123")
    assert not is_public_aggregator_listing_url("https://www.linkedin.com/jobs/search?keywords=intern")
    assert not is_public_aggregator_listing_url("https://www.indeed.com/jobs?q=intern")


def test_listing_url_detectors():
    assert is_linkedin_listing_url("https://www.linkedin.com/jobs/view/999")
    assert is_indeed_listing_url("https://www.indeed.com/viewjob?jk=abc123")
    assert not is_linkedin_listing_url("https://www.linkedin.com/jobs/search")
