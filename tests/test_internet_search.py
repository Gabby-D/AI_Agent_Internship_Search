import json
from pathlib import Path

import pytest

from internship_search.env_loader import load_env_file
from internship_search.internet_search import (
    DuckDuckGoHtmlProvider,
    FailoverSearchProvider,
    GoogleCustomSearchProvider,
    RateLimiter,
    SearchResult,
    TavilySearchProvider,
    describe_google_custom_search_http_error,
    get_search_provider,
    parse_duckduckgo_html,
    parse_google_custom_search_json,
    parse_tavily_json,
    rank_search_results,
    score_result,
    search_company_careers,
    search_internet,
    write_search_results_jsonl,
)


SAMPLE_DDG_HTML = """
<html><body>
<a class="result__a" href="https://careers.blackrock.com/students">BlackRock Students and Graduates</a>
<a class="result__snippet" href="#">Official BlackRock careers page for students and internships.</a>
<a class="result__a" href="https://www.linkedin.com/company/blackrock">BlackRock | LinkedIn</a>
<a class="result__snippet" href="#">Company profile on LinkedIn.</a>
<a class="result__a" href="https://www.blackrock.com/corporate/careers">BlackRock Careers</a>
<a class="result__snippet" href="#">Explore careers at BlackRock.</a>
</body></html>
"""

SAMPLE_TAVILY_JSON = json.dumps(
    {
        "results": [
            {
                "title": "BlackRock Careers",
                "url": "https://www.blackrock.com/corporate/careers",
                "content": "Official careers site for internships and students.",
            },
            {
                "title": "BlackRock on LinkedIn",
                "url": "https://www.linkedin.com/company/blackrock",
                "content": "Social profile.",
            },
        ]
    }
)


SAMPLE_GOOGLE_JSON = json.dumps(
    {
        "items": [
            {
                "title": "BlackRock Careers",
                "link": "https://www.blackrock.com/corporate/careers",
                "snippet": "Official careers site for internships and students.",
            },
            {
                "title": "BlackRock Students",
                "link": "https://careers.blackrock.com/students",
                "snippet": "Student and internship opportunities.",
            },
        ]
    }
)


def test_load_env_file_parses_key_value_pairs(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        'AI_PROVIDER_API_KEY="secret"\n# comment\nEMAIL_TO=\n',
        encoding="utf-8",
    )

    values = load_env_file(env_path)

    assert values["AI_PROVIDER_API_KEY"] == "secret"
    assert values["EMAIL_TO"] == ""


def test_parse_duckduckgo_html_extracts_results():
    results = parse_duckduckgo_html(
        SAMPLE_DDG_HTML,
        query="BlackRock careers",
        provider="duckduckgo_html",
        max_results=5,
        searched_at="2026-07-09T00:00:00+00:00",
    )

    assert len(results) == 3
    assert results[0].title == "BlackRock Students and Graduates"
    assert results[0].url == "https://careers.blackrock.com/students"


def test_parse_tavily_json_extracts_results():
    results = parse_tavily_json(
        SAMPLE_TAVILY_JSON,
        query="BlackRock careers",
        provider="tavily",
        max_results=5,
        searched_at="2026-07-09T00:00:00+00:00",
    )

    assert len(results) == 2
    assert results[0].title == "BlackRock Careers"


def test_score_result_prefers_official_careers_domains():
    careers = SearchResult(
        title="BlackRock Careers",
        url="https://www.blackrock.com/corporate/careers",
        snippet="Official careers page",
        provider="duckduckgo_html",
        query="BlackRock careers",
        date_searched="2026-07-09T00:00:00+00:00",
    )
    social = SearchResult(
        title="BlackRock LinkedIn",
        url="https://www.linkedin.com/company/blackrock",
        snippet="Company profile",
        provider="duckduckgo_html",
        query="BlackRock careers",
        date_searched="2026-07-09T00:00:00+00:00",
    )

    assert score_result(careers, company="BlackRock") > score_result(social, company="BlackRock")


def test_rank_search_results_orders_by_relevance():
    results = parse_duckduckgo_html(
        SAMPLE_DDG_HTML,
        query="BlackRock careers",
        provider="duckduckgo_html",
        max_results=5,
        searched_at="2026-07-09T00:00:00+00:00",
    )
    ranked = rank_search_results(results, company="BlackRock", searched_at="2026-07-09T00:00:00+00:00")

    assert ranked[0].url.startswith("https://careers.blackrock.com/")
    assert ranked[0].relevance_score >= ranked[-1].relevance_score


def test_duckduckgo_provider_uses_mock_fetch():
    def mock_fetch(url: str, content_type: str, body: bytes) -> str:
        assert url == "https://html.duckduckgo.com/html/"
        assert b"BlackRock" in body
        return SAMPLE_DDG_HTML

    provider = DuckDuckGoHtmlProvider(
        fetch_post=mock_fetch,
        rate_limiter=RateLimiter(min_interval_seconds=0),
    )
    results = provider.search("BlackRock summer 2027 internship careers", max_results=3)

    assert len(results) == 3


def test_tavily_provider_uses_mock_fetch():
    def mock_fetch(url: str, content_type: str, body: bytes) -> str:
        assert url == "https://api.tavily.com/search"
        payload = json.loads(body.decode("utf-8"))
        assert payload["query"] == "BlackRock careers"
        return SAMPLE_TAVILY_JSON

    provider = TavilySearchProvider(
        api_key="test-key",
        fetch_post=mock_fetch,
        rate_limiter=RateLimiter(min_interval_seconds=0),
    )
    results = provider.search("BlackRock careers", max_results=2)

    assert len(results) == 2


def test_parse_google_custom_search_json_extracts_results():
    results = parse_google_custom_search_json(
        SAMPLE_GOOGLE_JSON,
        query="BlackRock careers",
        provider="google_custom_search",
        max_results=5,
        searched_at="2026-07-09T00:00:00+00:00",
    )

    assert len(results) == 2
    assert results[0].title == "BlackRock Careers"


def test_google_custom_search_provider_uses_mock_fetch():
    def mock_fetch(url: str) -> str:
        assert "googleapis.com/customsearch/v1" in url
        assert "key=test-key" in url
        assert "cx=test-cse" in url
        return SAMPLE_GOOGLE_JSON

    provider = GoogleCustomSearchProvider(
        api_key="test-key",
        cse_id="test-cse",
        fetch_get=mock_fetch,
        rate_limiter=RateLimiter(min_interval_seconds=0),
    )
    results = provider.search("BlackRock careers", max_results=2)

    assert len(results) == 2
    assert results[0].provider == "google_custom_search"


def test_failover_search_provider_uses_google_when_duckduckgo_fails():
    class FailingDuckDuckGo:
        name = "duckduckgo_html"

        def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
            raise RuntimeError("DuckDuckGo unavailable")

    class MockGoogle:
        name = "google_custom_search"

        def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
            return [
                SearchResult(
                    title="BlackRock Careers",
                    url="https://www.blackrock.com/corporate/careers",
                    snippet="Official careers page",
                    provider=self.name,
                    query=query,
                    date_searched="2026-07-09T00:00:00+00:00",
                )
            ]

    provider = FailoverSearchProvider([FailingDuckDuckGo(), MockGoogle()])
    results = provider.search("BlackRock careers", max_results=1)

    assert len(results) == 1
    assert results[0].provider == "google_custom_search"
    assert provider.provider_errors == ["duckduckgo_html: DuckDuckGo unavailable"]


def test_get_search_provider_uses_failover_when_google_configured(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_CUSTOM_SEARCH_API_KEY", "test-key")
    monkeypatch.setenv("GOOGLE_CSE_ID", "test-cse")
    monkeypatch.setenv("INTERNET_SEARCH_PROVIDER", "auto")

    provider = get_search_provider()

    assert isinstance(provider, FailoverSearchProvider)
    assert [active_provider.name for active_provider in provider.providers] == [
        "duckduckgo_html",
        "google_custom_search",
    ]


def test_describe_google_custom_search_http_error_maps_status_codes():
    from urllib.error import HTTPError

    forbidden = HTTPError(
        url="https://www.googleapis.com/customsearch/v1",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=None,
    )

    assert "403" in describe_google_custom_search_http_error(forbidden)


def test_get_search_provider_defaults_to_duckduckgo_without_tavily_key(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CUSTOM_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    monkeypatch.setenv("INTERNET_SEARCH_PROVIDER", "auto")

    provider = get_search_provider()

    assert provider.name == "duckduckgo_html"


def test_get_search_provider_requires_tavily_key_when_forced(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.setenv("INTERNET_SEARCH_PROVIDER", "tavily")

    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        get_search_provider("tavily")


def test_search_company_careers_writes_jsonl(tmp_path):
    def mock_fetch(url: str, content_type: str, body: bytes) -> str:
        return SAMPLE_DDG_HTML

    provider = DuckDuckGoHtmlProvider(
        fetch_post=mock_fetch,
        rate_limiter=RateLimiter(min_interval_seconds=0),
    )
    output_path = tmp_path / "internet_search_results.jsonl"

    response = search_company_careers(
        "BlackRock",
        provider=provider,
        max_results=3,
        output_path=output_path,
        searched_at="2026-07-09T00:00:00+00:00",
    )

    assert response.query == "BlackRock summer 2027 internship careers"
    assert len(response.results) == 3
    assert output_path.exists()
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first["provider"] == "duckduckgo_html"


def test_search_internet_captures_provider_errors():
    class BrokenProvider:
        name = "broken"

        def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
            raise RuntimeError("provider unavailable")

    response = search_internet(
        query="BlackRock careers",
        provider=BrokenProvider(),
        output_path=None,
    )

    assert response.results == []
    assert response.errors == ["provider unavailable"]


def test_write_search_results_jsonl(tmp_path):
    results = [
        SearchResult(
            title="Example Careers",
            url="https://example.com/careers",
            snippet="Official careers page",
            provider="duckduckgo_html",
            query="Example careers",
            date_searched="2026-07-09T00:00:00+00:00",
            relevance_score=10,
        )
    ]
    output_path = tmp_path / "results.jsonl"

    path = write_search_results_jsonl(results, output_path)

    assert path == Path(output_path)
    payload = json.loads(output_path.read_text(encoding="utf-8").strip())
    assert payload["title"] == "Example Careers"
