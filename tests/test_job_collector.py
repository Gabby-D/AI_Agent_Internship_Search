from datetime import date

from internship_search.job_collector import (
    JobPosting,
    collect_from_sources,
    extract_postings_from_html,
    read_postings_jsonl,
    write_postings_jsonl,
)
from internship_search.source_registry import CompanySource


def make_source(company: str = "Example Co") -> CompanySource:
    return CompanySource(
        company=company,
        website="https://example.com",
        careers_url="https://example.com/careers/",
        source_type="company_careers_page",
        origin="seed",
        has_connection=False,
        notes="Test source",
    )


def test_extract_postings_from_html_finds_likely_job_links():
    html = """
    <html>
      <body>
        <a href="/jobs/2027-summer-intern">2027 Summer Intern</a>
        <a href="https://example.com/privacy">Privacy Notice</a>
        <a href="/students">Students and graduates</a>
        <a href="/fr-ca/careers/work-with-us/internships-programs/">Canada</a>
      </body>
    </html>
    """

    postings = extract_postings_from_html(
        source=make_source(),
        html=html,
        collected_date="2026-07-08",
    )

    assert [posting.title for posting in postings] == ["2027 Summer Intern"]
    assert postings[0].posting_url == "https://example.com/jobs/2027-summer-intern"
    assert postings[0].location == "Unknown"


def test_write_postings_jsonl_deduplicates_by_url(tmp_path):
    output_path = tmp_path / "postings.jsonl"
    posting = JobPosting(
        title="2027 Summer Intern",
        company="Example Co",
        location="Unknown",
        posting_url="https://example.com/jobs/1",
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
    )

    write_postings_jsonl([posting], output_path)
    write_postings_jsonl([posting], output_path)

    loaded = read_postings_jsonl(output_path)

    assert len(loaded) == 1
    assert loaded[0].posting_url == "https://example.com/jobs/1"


def test_collect_from_sources_records_warning_when_no_postings_found(tmp_path):
    sources = [make_source("Empty Co")]

    result = collect_from_sources(
        sources=sources,
        output_path=tmp_path / "postings.jsonl",
        fetch_page=lambda url: "<html><body><p>No jobs here</p></body></html>",
        collected_on=date(2026, 7, 8),
    )

    assert result.postings == []
    assert len(result.errors) == 1
    assert "No posting candidates extracted" in result.errors[0].message


def test_collect_from_sources_uses_alternate_careers_urls(tmp_path):
    source = CompanySource(
        company="BlackRock",
        website="https://www.blackrock.com",
        careers_url="https://careers.blackrock.com/en/students-and-graduates",
        source_type="company_careers_search",
        origin="seed",
        has_connection=True,
        notes="",
        alternate_careers_urls=(
            "https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/45831/90628276544",
        ),
        collector="auto",
    )

    result = collect_from_sources(
        sources=[source],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=lambda url: "<html></html>",
        collected_on=date(2026, 7, 8),
    )

    assert len(result.postings) == 1
    assert "2027 Summer Internship Program Amers" in result.postings[0].title


def test_collect_from_sources_continues_after_fetch_error(tmp_path):
    sources = [make_source("Good Co"), make_source("Broken Co")]

    def fetch_page(url: str) -> str:
        if "example.com" in url and fetch_page.calls == 0:
            fetch_page.calls += 1
            return '<a href="/jobs/2027-summer-intern">2027 Summer Intern</a>'
        raise RuntimeError("fetch failed")

    fetch_page.calls = 0

    result = collect_from_sources(
        sources=sources,
        output_path=tmp_path / "postings.jsonl",
        fetch_page=fetch_page,
        collected_on=date(2026, 7, 8),
    )

    assert len(result.postings) == 1
    assert len(result.errors) == 1
    assert result.postings[0].company == "Good Co"
    assert result.output_path.exists()
