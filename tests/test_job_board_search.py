from datetime import date

from internship_search.internet_search import SearchResult
from internship_search.job_board_search import (
    DUCKDUCKGO_JOB_BOARD_QUERIES,
    DuckDuckGoJobBoardProvider,
    get_job_board_provider,
    infer_company_from_job_board_result,
    is_public_job_board_listing_url,
    job_board_posting_from_search_result,
    search_job_boards,
)
from internship_search.job_collector import (
    JobPosting,
    canonical_posting_url,
    collect_from_sources,
    merge_posting_candidates,
)


def test_duckduckgo_job_board_provider_filters_to_job_board_results():
    class MockDuckDuckGo:
        name = "duckduckgo_html"

        def search(self, query: str, max_results: int = 5):
            return [
                SearchResult(
                    title="2027 Summer Analyst Intern at Example Capital",
                    url="https://boards.greenhouse.io/example/jobs/12345",
                    snippet="Internship posting",
                    provider=self.name,
                    query=query,
                    date_searched="2026-07-09T00:00:00+00:00",
                ),
                SearchResult(
                    title="Example Capital Careers Overview",
                    url="https://example.com/careers",
                    snippet="General careers page",
                    provider=self.name,
                    query=query,
                    date_searched="2026-07-09T00:00:00+00:00",
                ),
            ]

    provider = DuckDuckGoJobBoardProvider(search_provider=MockDuckDuckGo())
    postings = provider.search(
        "summer 2027 internship site:greenhouse.io",
        searched_at="2026-07-09T00:00:00+00:00",
    )

    assert len(postings) == 1
    assert postings[0].company == "Example Capital"


def test_job_board_posting_from_search_result_parses_greenhouse_application_title():
    posting = job_board_posting_from_search_result(
        SearchResult(
            title="Job Application for Fundamental Equities Intern (Summer 2027) at Walleye Capital",
            url="https://job-boards.greenhouse.io/walleyecapital-external-students/jobs/4677152006",
            snippet="Location: Boston, MA",
            provider="duckduckgo_job_board",
            query="summer 2027 internship site:greenhouse.io",
            date_searched="2026-07-13T00:00:00+00:00",
        ),
        searched_at="2026-07-13T00:00:00+00:00",
        provider="duckduckgo_job_board",
    )

    assert posting.title == "Fundamental Equities Intern (Summer 2027)"
    assert posting.company == "Walleye Capital"
    assert posting.location == "Boston, MA"


def test_job_board_posting_from_search_result_builds_stable_id():
    posting = job_board_posting_from_search_result(
        SearchResult(
            title="2027 Summer Analyst Intern",
            url="https://boards.greenhouse.io/example/jobs/12345?utm_source=ddg",
            snippet="",
            provider="duckduckgo_job_board",
            query="summer 2027 internship",
            date_searched="2026-07-09T00:00:00+00:00",
        ),
        searched_at="2026-07-09T00:00:00+00:00",
        provider="duckduckgo_job_board",
    )

    assert posting.posting_id == canonical_posting_url(posting.posting_url)


def test_merge_posting_candidates_deduplicates_tracking_params():
    company_posting = JobPosting(
        title="2027 Summer Analyst Intern",
        company="Example Capital",
        location="New York",
        posting_url="https://boards.greenhouse.io/example/jobs/12345",
        date_collected="2026-07-09",
        source_url="https://example.com/careers",
    )
    board_posting = JobPosting(
        title="2027 Summer Analyst Intern",
        company="Example Capital",
        location="Unknown",
        posting_url="https://boards.greenhouse.io/example/jobs/12345?utm_source=job-board",
        date_collected="2026-07-09",
        source_url="job-board://duckduckgo_job_board?query=summer%202027%20internship",
    )

    merged = merge_posting_candidates([company_posting], [board_posting])

    assert len(merged) == 1
    assert merged[0].source_url == "https://example.com/careers"


def test_merge_posting_candidates_prefers_career_page_over_linkedin_for_same_role():
    career_posting = JobPosting(
        title="2027 Summer Analyst Intern",
        company="BlackRock",
        location="New York, NY",
        posting_url="https://boards.greenhouse.io/blackrock/jobs/12345",
        date_collected="2026-07-09",
        source_url="https://careers.blackrock.com",
    )
    linkedin_posting = JobPosting(
        title="2027 Summer Analyst Intern",
        company="BlackRock",
        location="New York, NY",
        posting_url="https://www.linkedin.com/jobs/view/99999?utm_source=ddg",
        date_collected="2026-07-09",
        source_url="job-board://duckduckgo_job_board?query=summer%202027%20internship",
    )

    merged = merge_posting_candidates([career_posting], [linkedin_posting])

    assert len(merged) == 1
    assert "greenhouse.io" in merged[0].posting_url
    assert merged[0].source_url == "https://careers.blackrock.com"


def test_search_job_boards_writes_output_with_mock_provider(tmp_path):
    class MockProvider:
        name = "mock_job_board"

        def search(self, query: str, *, target_year: str = "2027", max_results: int = 20, searched_at=None):
            from internship_search.job_board_search import JobBoardPosting

            return [
                JobBoardPosting(
                    title="2027 Technology Summer Intern",
                    company="Example Co",
                    location="Remote",
                    posting_url="https://boards.greenhouse.io/example/jobs/777",
                    posting_id="777",
                    snippet="Internship",
                    provider=self.name,
                    query=query,
                    date_searched=searched_at or "2026-07-09T00:00:00+00:00",
                )
            ]

    output_path = tmp_path / "job_board_postings.jsonl"
    response = search_job_boards(
        provider=MockProvider(),
        output_path=output_path,
        searched_at="2026-07-09T00:00:00+00:00",
    )

    assert response.postings[0].title == "2027 Technology Summer Intern"
    assert output_path.exists()


def test_collect_from_sources_can_merge_job_board_results(tmp_path, monkeypatch):
    import internship_search.job_board_search as job_board_search

    class MockProvider:
        name = "mock_job_board"

        def search(self, query: str, *, target_year: str = "2027", max_results: int = 20, searched_at=None):
            from internship_search.job_board_search import JobBoardPosting

            return [
                JobBoardPosting(
                    title="2027 Operations Summer Intern",
                    company="Board Co",
                    location="Bay Area",
                    posting_url="https://boards.greenhouse.io/board/jobs/42",
                    posting_id="42",
                    snippet="",
                    provider=self.name,
                    query=query,
                    date_searched=searched_at or "2026-07-09T00:00:00+00:00",
                )
            ]

    monkeypatch.setattr(job_board_search, "search_job_boards", lambda **kwargs: job_board_search.JobBoardSearchResponse(
        query="summer 2027 internship",
        provider="mock_job_board",
        postings=MockProvider().search("summer 2027 internship", searched_at="2026-07-09T00:00:00+00:00"),
        output_path=tmp_path / "job_board_postings.jsonl",
        errors=[],
    ))

    result = collect_from_sources(
        sources=[],
        output_path=tmp_path / "postings.jsonl",
        include_job_boards=True,
        collected_on=date(2026, 7, 9),
    )

    assert len(result.postings) == 1
    assert result.postings[0].company == "Board Co"


def test_get_job_board_provider_returns_duckduckgo():
    provider = get_job_board_provider()

    assert isinstance(provider, DuckDuckGoJobBoardProvider)
    assert provider.name == "duckduckgo_job_board"


def test_default_job_board_queries_include_linkedin_and_indeed():
    joined = " ".join(DUCKDUCKGO_JOB_BOARD_QUERIES)
    assert "linkedin.com/jobs/view" in joined
    assert "indeed.com/viewjob" in joined
    assert joined.count("linkedin.com/jobs/view") >= 2
    assert joined.count("indeed.com/viewjob") >= 2


def test_is_public_job_board_listing_url_accepts_listings_not_search_pages():
    assert is_public_job_board_listing_url("https://www.linkedin.com/jobs/view/12345")
    assert is_public_job_board_listing_url("https://www.indeed.com/viewjob?jk=abc123")
    assert not is_public_job_board_listing_url("https://www.linkedin.com/jobs/search?keywords=intern")
    assert not is_public_job_board_listing_url("https://www.indeed.com/jobs?q=intern")


def test_infer_company_from_job_board_result_parses_linkedin_and_indeed_titles():
    linkedin = SearchResult(
        title="2027 Summer Analyst Intern at BlackRock | LinkedIn",
        url="https://www.linkedin.com/jobs/view/12345",
        snippet="",
        provider="duckduckgo_job_board",
        query="summer 2027 internship site:linkedin.com/jobs/view",
        date_searched="2026-07-09T00:00:00+00:00",
    )
    indeed = SearchResult(
        title="BlackRock - 2027 Summer Analyst Intern | Indeed.com",
        url="https://www.indeed.com/viewjob?jk=abc123",
        snippet="",
        provider="duckduckgo_job_board",
        query="summer 2027 internship site:indeed.com/viewjob",
        date_searched="2026-07-09T00:00:00+00:00",
    )

    assert infer_company_from_job_board_result(linkedin) == "BlackRock"
    assert infer_company_from_job_board_result(indeed) == "BlackRock"


def test_duckduckgo_job_board_provider_includes_linkedin_results():
    class MockDuckDuckGo:
        name = "duckduckgo_html"

        def search(self, query: str, max_results: int = 5):
            if "linkedin.com" in query:
                return [
                    SearchResult(
                        title="2027 Summer Analyst Intern at Example Capital | LinkedIn",
                        url="https://www.linkedin.com/jobs/view/12345",
                        snippet="Internship posting",
                        provider=self.name,
                        query=query,
                        date_searched="2026-07-09T00:00:00+00:00",
                    ),
                    SearchResult(
                        title="Internship search results | LinkedIn",
                        url="https://www.linkedin.com/jobs/search?keywords=intern",
                        snippet="Search page",
                        provider=self.name,
                        query=query,
                        date_searched="2026-07-09T00:00:00+00:00",
                    ),
                ]
            return []

    provider = DuckDuckGoJobBoardProvider(search_provider=MockDuckDuckGo())
    postings = provider.search("summer 2027 internship", searched_at="2026-07-09T00:00:00+00:00")

    assert len(postings) == 1
    assert postings[0].company == "Example Capital"
    assert postings[0].posting_url == "https://www.linkedin.com/jobs/view/12345"


def test_duckduckgo_job_board_provider_runs_all_default_queries():
    class MockDuckDuckGo:
        name = "duckduckgo_html"
        queries_seen: list[str] = []

        def search(self, query: str, max_results: int = 5):
            self.queries_seen.append(query)
            if "greenhouse.io" in query:
                return [
                    SearchResult(
                        title=f"Intern at Co {len(self.queries_seen)}",
                        url=f"https://boards.greenhouse.io/co/jobs/{len(self.queries_seen)}",
                        snippet="Internship",
                        provider=self.name,
                        query=query,
                        date_searched="2026-07-09T00:00:00+00:00",
                    )
                ]
            return []

    mock = MockDuckDuckGo()
    provider = DuckDuckGoJobBoardProvider(search_provider=mock)
    postings = provider.search("summer 2027 internship", searched_at="2026-07-09T00:00:00+00:00")

    assert len(mock.queries_seen) == len(DUCKDUCKGO_JOB_BOARD_QUERIES)
    assert len(postings) >= 1


def test_search_job_boards_includes_linkedin_indeed_limitations(tmp_path):
    class MockProvider:
        name = "duckduckgo_job_board"

        def search(self, query: str, *, target_year: str = "2027", max_results: int = 20, searched_at=None):
            from internship_search.job_board_search import JobBoardPosting

            return [
                JobBoardPosting(
                    title="2027 Technology Summer Intern",
                    company="Example Co",
                    location="Remote",
                    posting_url="https://boards.greenhouse.io/example/jobs/777",
                    posting_id="777",
                    snippet="Internship",
                    provider=self.name,
                    query=query,
                    date_searched=searched_at or "2026-07-09T00:00:00+00:00",
                )
            ]

    response = search_job_boards(
        provider=MockProvider(),
        output_path=tmp_path / "job_board_postings.jsonl",
        searched_at="2026-07-09T00:00:00+00:00",
    )

    assert response.limitations
    assert any("LinkedIn" in limitation for limitation in response.limitations)
    assert any("No LinkedIn listing URLs" in limitation for limitation in response.limitations)
