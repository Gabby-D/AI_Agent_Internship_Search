from datetime import date

from internship_search.job_collector import (
    JobPosting,
    collect_from_sources,
    discover_career_navigation_urls,
    extract_postings_from_html,
    is_probable_direct_source_url,
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
    sources = [
        make_source("Good Co"),
        CompanySource(
            company="Broken Co",
            website="https://broken.example",
            careers_url="https://broken.example/careers",
            source_type="company_careers_page",
            origin="seed",
            has_connection=False,
            notes="Test source",
        ),
    ]

    def fetch_page(url: str) -> str:
        if "example.com" in url and "broken.example" not in url:
            return '<a href="/jobs/2027-summer-intern">2027 Summer Intern</a>'
        raise RuntimeError("fetch failed")

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


def test_collect_from_sources_reuses_shared_board_pages(tmp_path):
    first = make_source("First Co")
    second = make_source("Second Co")
    calls: list[str] = []

    def fetch_page(url: str) -> str:
        calls.append(url)
        return "<html><body>No internships</body></html>"

    collect_from_sources(
        sources=[first, second],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=fetch_page,
        collected_on=date(2026, 7, 22),
    )

    assert calls == ["https://example.com/careers/"]


def test_plural_jobs_url_is_treated_as_a_direct_posting():
    assert is_probable_direct_source_url(
        "https://careers.example.com/en/jobs/r-555860/"
        "2027-finance-summer-internship/"
    )


def test_collect_from_sources_follows_every_paginated_career_page(tmp_path):
    pages = {
        "https://example.com/careers/": """
            <a href="/jobs/intern-1">Summer Intern One</a>
            <a href="?page=2" rel="next">Next</a>
        """,
        "https://example.com/careers/?page=2": """
            <a href="/jobs/intern-2">Summer Intern Two</a>
            <button data-load-more-url="?page=3" aria-label="Next page">Load more</button>
        """,
        "https://example.com/careers/?page=3": """
            <a href="/jobs/intern-3">Summer Intern Three</a>
            <a href="?page=2">Previous</a>
        """,
    }
    fetched: list[str] = []

    def fetch_page(url: str) -> str:
        fetched.append(url)
        return pages[url]

    result = collect_from_sources(
        sources=[make_source()],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=fetch_page,
        collected_on=date(2026, 7, 22),
    )

    assert {posting.title for posting in result.postings} == {
        "Summer Intern One",
        "Summer Intern Two",
        "Summer Intern Three",
    }
    assert fetched == list(pages)
    assert result.errors == []


def test_blackrock_scans_unfiltered_results_and_finds_internship_on_later_page(tmp_path):
    source = CompanySource(
        company="BlackRock",
        website="https://www.blackrock.com",
        careers_url="https://careers.blackrock.com/search-jobs",
        source_type="company_careers_search",
        origin="seed",
        has_connection=False,
        notes="Scan the complete public jobs search.",
        collector="blackrock_jobs",
    )
    pages = {
        "https://careers.blackrock.com/search-jobs": """
            <a href="/job/new-york/portfolio-manager/45831/1">Portfolio Manager</a>
            <form action="/job"><button>Search jobs</button></form>
            <a href="/job">Search jobs</a>
            <a href="/search-jobs&amp;p=2" aria-label="Next Page">Next</a>
        """,
        "https://careers.blackrock.com/search-jobs?p=2": """
            <a href="/job/new-york/2027-summer-analyst/45831/2">
                2027 Summer Analyst Internship
            </a>
        """,
        "https://careers.blackrock.com/job/new-york/2027-summer-analyst/45831/2": """
            <h1>2027 Summer Analyst Internship</h1>
            <p>Location: New York Additional Locations: San Francisco See More</p>
            <p>Team: Students and Graduates Job Requisition #: 2 Date posted: July 1</p>
            <a href="/apply">Apply now</a>
        """,
    }
    fetched: list[str] = []

    def fetch_page(url: str) -> str:
        fetched.append(url)
        return pages[url]

    result = collect_from_sources(
        sources=[source],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=fetch_page,
        collected_on=date(2026, 7, 22),
    )

    assert fetched == list(pages)
    assert [posting.title for posting in result.postings] == [
        "2027 Summer Analyst"
    ]
    assert result.postings[0].location == "New York | San Francisco"
    assert result.errors == []


def test_generic_pipeline_opens_program_details_and_excludes_closed_programs(tmp_path):
    source = CompanySource(
        company="Example Consulting",
        website="https://consulting.example",
        careers_url="https://consulting.example/careers/internships-programs/",
        source_type="company_careers_page",
        origin="seed",
        has_connection=False,
        notes="",
    )
    pages = {
        source.careers_url: """
            <span>Associate Consultant Internship</span>
            <a href="/careers/internships-programs/associate-consultant-internship/">
              Learn more
            </a>
            <a href="/careers/internships-programs/summer-associate/">
              Summer Associate
            </a>
            <a href="/careers/internships-programs/closed-internship/">
              Marketing Consulting Internship
            </a>
            <a href="/fr/careers/">Careers</a>
        """,
        (
            "https://consulting.example/careers/internships-programs/"
            "associate-consultant-internship/"
        ): """
            <h1>Associate Consultant Internship</h1>
            <p>Job ID 10403</p><p>Employment type Temporary Full-Time</p>
            <p>Location(s) New York | Preferred City | Seattle</p>
            <a href="/apply">Apply now</a>
            <h2>Description &amp; Requirements</h2>
        """,
        (
            "https://consulting.example/careers/internships-programs/"
            "summer-associate/"
        ): """
            <h1>Summer Associate</h1>
            <p>Job ID 10463</p><p>Employment type Intern (Full-Time)</p>
            <p>Location(s) Boston | Preferred City</p>
            <a href="/apply">Apply now</a>
            <h2>Description &amp; Requirements</h2>
        """,
        (
            "https://consulting.example/careers/internships-programs/"
            "closed-internship/"
        ): """
            <h1>Marketing Consulting Internship</h1>
            <p>Employment type Program</p><p>Location(s) London</p>
            <p>Our applications are now closed.</p>
        """,
    }
    fetched: list[str] = []

    def fetch_page(url: str) -> str:
        fetched.append(url)
        return pages[url]

    result = collect_from_sources(
        sources=[source],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=fetch_page,
        collected_on=date(2026, 7, 22),
    )

    assert {posting.title for posting in result.postings} == {
        "Associate Consultant Internship",
        "Summer Associate",
    }
    assert all("Preferred City" in posting.location for posting in result.postings)
    assert "https://consulting.example/fr/careers/" not in fetched
    assert result.errors == []


def test_discover_career_navigation_urls_follows_job_indexes_but_not_job_details():
    html = """
        <a href="/jobs">View jobs</a>
        <a href="/jobs/software-engineer-123">Software Engineer</a>
        <a href="https://jobs.lever.co/example">All openings</a>
        <a href="https://unrelated.example/jobs">All jobs</a>
    """

    urls = discover_career_navigation_urls(
        html,
        current_url="https://example.com/careers",
        root_url="https://example.com/careers",
    )

    assert urls == [
        "https://example.com/jobs",
        "https://jobs.lever.co/example",
    ]


def test_discover_career_navigation_urls_does_not_follow_unrelated_more_links():
    html = """
        <a class="read-more" href="/company-history">Read more</a>
        <a class="pagination-next" href="?page=2">Continue</a>
    """

    urls = discover_career_navigation_urls(
        html,
        current_url="https://example.com/careers",
        root_url="https://example.com/careers",
    )

    assert urls == ["https://example.com/careers?page=2"]


def test_discover_career_navigation_urls_follows_embedded_public_ats_board():
    html = """
        <script src="https://boards.greenhouse.io/embed/job_board/js?for=example"></script>
        <script src="https://cdn.example.com/site.js"></script>
    """

    urls = discover_career_navigation_urls(
        html,
        current_url="https://example.com/careers",
        root_url="https://example.com/careers",
    )

    assert urls == [
        "https://boards.greenhouse.io/embed/job_board/js?for=example"
    ]


def test_collect_from_sources_reports_when_pagination_safety_limit_is_reached(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr("internship_search.job_collector.MAX_CAREER_PAGES_PER_SOURCE_URL", 2)

    def fetch_page(url: str) -> str:
        page = int(url.split("page=")[-1]) if "page=" in url else 1
        return (
            f'<a href="/jobs/intern-{page}">Summer Intern {page}</a>'
            f'<a href="?page={page + 1}" rel="next">Next</a>'
        )

    result = collect_from_sources(
        sources=[make_source()],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=fetch_page,
        collected_on=date(2026, 7, 22),
    )

    assert len(result.postings) == 2
    assert len(result.errors) == 1
    assert "safety limit of 2 pages" in result.errors[0].message


def test_collect_from_sources_uses_complete_ats_api_when_html_is_blocked(
    tmp_path,
    monkeypatch,
):
    source = CompanySource(
        company="Example Co",
        website="https://example.com",
        careers_url="https://jobs.lever.co/example",
        source_type="job_board",
        origin="seed",
        has_connection=False,
        notes="",
    )
    monkeypatch.setattr(
        "internship_search.career_collectors.get_public_json",
        lambda url: [
            {
                "id": "intern-1",
                "text": "2027 Summer Product Intern",
                "hostedUrl": "https://jobs.lever.co/example/intern-1",
                "categories": {"location": "Remote"},
            }
        ],
    )

    result = collect_from_sources(
        sources=[source],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=lambda url: (_ for _ in ()).throw(RuntimeError("HTML blocked")),
        collected_on=date(2026, 7, 22),
    )

    assert len(result.postings) == 1
    assert result.errors == []


def test_teamtailor_complete_page_with_no_internships_is_not_an_access_error(tmp_path):
    source = CompanySource(
        company="Example Co",
        website="https://example.com",
        careers_url="https://example.na.teamtailor.com/jobs",
        source_type="job_board",
        origin="seed",
        has_connection=False,
        notes="",
    )
    html = """
        <html><body>
          <p>Applicant tracking system by Teamtailor</p>
          <h1>Current job openings</h1><p>3 jobs</p><div>Job filters</div>
          <a href="/jobs/1-hardware-technician">Hardware Technician</a>
          <a href="/jobs/2-senior-engineer">Senior Engineer</a>
        </body></html>
    """

    result = collect_from_sources(
        sources=[source],
        output_path=tmp_path / "postings.jsonl",
        fetch_page=lambda url: html,
        collected_on=date(2026, 7, 22),
    )

    assert result.postings == []
    assert result.errors == []
