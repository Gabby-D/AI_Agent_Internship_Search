"""Search the internet for company and careers pages."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Protocol
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from internship_search.env_loader import get_env, load_env_into_process


FetchText = Callable[[str, str, bytes | None], str]
PostText = Callable[[str, str, bytes], str]
GetText = Callable[[str], str]

GOOGLE_CUSTOM_SEARCH_API_BASE = "https://www.googleapis.com/customsearch/v1"

CAREER_URL_KEYWORDS = {
    "career",
    "careers",
    "intern",
    "internship",
    "job",
    "jobs",
    "student",
    "students",
    "graduate",
    "university",
    "campus",
}
BLOCKED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "wikipedia.org",
}


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    provider: str
    query: str
    date_searched: str
    relevance_score: int = 0


@dataclass(frozen=True)
class SearchResponse:
    query: str
    provider: str
    results: list[SearchResult]
    output_path: Path | None
    errors: list[str]


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        ...


class RateLimiter:
    def __init__(self, min_interval_seconds: float = 1.0) -> None:
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()


def search_internet(
    query: str,
    *,
    provider: SearchProvider | None = None,
    company: str = "",
    max_results: int = 5,
    output_path: Path | str | None = "data/internet_search_results.jsonl",
    searched_at: str | None = None,
) -> SearchResponse:
    load_env_into_process()
    active_provider = provider or get_search_provider()
    searched_on = searched_at or datetime.now(timezone.utc).isoformat()
    errors: list[str] = []
    results: list[SearchResult] = []

    try:
        raw_results = active_provider.search(query=query, max_results=max_results)
        results = rank_search_results(raw_results, company=company, searched_at=searched_on)
    except Exception as error:  # noqa: BLE001 - preserve provider failures for CLI output.
        errors.append(str(error))

    if hasattr(active_provider, "provider_errors"):
        errors.extend(active_provider.provider_errors)

    path = None
    if output_path is not None:
        path = write_search_results_jsonl(results, output_path)

    return SearchResponse(
        query=query,
        provider=active_provider.name,
        results=results,
        output_path=path,
        errors=errors,
    )


def search_company_careers(
    company: str,
    *,
    target_year: str = "2027",
    provider: SearchProvider | None = None,
    max_results: int = 5,
    output_path: Path | str | None = "data/internet_search_results.jsonl",
    searched_at: str | None = None,
) -> SearchResponse:
    query = f"{company} summer {target_year} internship careers"
    return search_internet(
        query=query,
        provider=provider,
        company=company,
        max_results=max_results,
        output_path=output_path,
        searched_at=searched_at,
    )


def get_search_provider(provider_name: str | None = None) -> SearchProvider:
    load_env_into_process()
    selected = (provider_name or get_env("INTERNET_SEARCH_PROVIDER", "auto")).lower()
    google_api_key = get_env("GOOGLE_CUSTOM_SEARCH_API_KEY")
    google_cse_id = get_env("GOOGLE_CSE_ID")
    tavily_key = get_env("TAVILY_API_KEY")

    if selected == "duckduckgo_html":
        return DuckDuckGoHtmlProvider()
    if selected == "google_custom_search":
        if not google_api_key or not google_cse_id:
            raise ValueError(
                "GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CSE_ID are required "
                "when INTERNET_SEARCH_PROVIDER=google_custom_search."
            )
        return GoogleCustomSearchProvider(api_key=google_api_key, cse_id=google_cse_id)
    if selected == "tavily":
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY is required when INTERNET_SEARCH_PROVIDER=tavily.")
        return TavilySearchProvider(api_key=tavily_key)
    if selected == "auto":
        return build_failover_search_provider(
            google_api_key=google_api_key,
            google_cse_id=google_cse_id,
        )
    raise ValueError(
        f"Unsupported INTERNET_SEARCH_PROVIDER={selected!r}. "
        "Use auto, duckduckgo_html, google_custom_search, or tavily."
    )


def build_failover_search_provider(
    *,
    google_api_key: str | None,
    google_cse_id: str | None,
) -> SearchProvider:
    providers: list[SearchProvider] = [DuckDuckGoHtmlProvider()]
    if google_api_key and google_cse_id:
        providers.append(
            GoogleCustomSearchProvider(api_key=google_api_key, cse_id=google_cse_id)
        )
    if len(providers) == 1:
        return providers[0]
    return FailoverSearchProvider(providers)


class FailoverSearchProvider:
    name = "auto"

    def __init__(self, providers: list[SearchProvider]) -> None:
        self.providers = providers
        self.provider_errors: list[str] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.provider_errors = []
        for provider in self.providers:
            try:
                results = provider.search(query=query, max_results=max_results)
            except Exception as error:  # noqa: BLE001 - try the next search provider.
                self.provider_errors.append(f"{provider.name}: {error}")
                continue
            if results:
                return results
            self.provider_errors.append(f"{provider.name}: returned no results")
        return []


class DuckDuckGoHtmlProvider:
    name = "duckduckgo_html"

    def __init__(
        self,
        fetch_post: PostText | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.fetch_post = fetch_post or post_text
        self.rate_limiter = rate_limiter or RateLimiter()

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.rate_limiter.wait()
        body = urlencode({"q": query}).encode("utf-8")
        html = self.fetch_post(
            "https://html.duckduckgo.com/html/",
            "application/x-www-form-urlencoded",
            body,
        )
        return parse_duckduckgo_html(html, query=query, provider=self.name, max_results=max_results)


class TavilySearchProvider:
    name = "tavily"

    def __init__(
        self,
        api_key: str,
        fetch_post: PostText | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.api_key = api_key
        self.fetch_post = fetch_post or post_text
        self.rate_limiter = rate_limiter or RateLimiter()

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.rate_limiter.wait()
        payload = json.dumps(
            {
                "api_key": self.api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            }
        ).encode("utf-8")
        raw = self.fetch_post("https://api.tavily.com/search", "application/json", payload)
        return parse_tavily_json(raw, query=query, provider=self.name, max_results=max_results)


class GoogleCustomSearchProvider:
    name = "google_custom_search"

    def __init__(
        self,
        api_key: str,
        cse_id: str,
        fetch_get: GetText | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.api_key = api_key
        self.cse_id = cse_id
        self.fetch_get = fetch_get or get_text
        self.rate_limiter = rate_limiter or RateLimiter()

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.rate_limiter.wait()
        params = urlencode(
            {
                "key": self.api_key,
                "cx": self.cse_id,
                "q": query,
                "num": str(min(max_results, 10)),
            }
        )
        url = f"{GOOGLE_CUSTOM_SEARCH_API_BASE}?{params}"
        try:
            raw = self.fetch_get(url)
        except HTTPError as error:
            raise ValueError(describe_google_custom_search_http_error(error)) from error
        return parse_google_custom_search_json(
            raw,
            query=query,
            provider=self.name,
            max_results=max_results,
        )


def parse_duckduckgo_html(
    html: str,
    *,
    query: str,
    provider: str,
    max_results: int,
    searched_at: str | None = None,
) -> list[SearchResult]:
    parser = DuckDuckGoResultParser()
    parser.feed(html)
    searched_on = searched_at or datetime.now(timezone.utc).isoformat()
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for item in parser.results:
        normalized_url = normalize_result_url(item.url)
        if not normalized_url or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        results.append(
            SearchResult(
                title=clean_text(item.title),
                url=normalized_url,
                snippet=clean_text(item.snippet),
                provider=provider,
                query=query,
                date_searched=searched_on,
            )
        )
        if len(results) >= max_results:
            break
    return results


def parse_tavily_json(
    raw: str,
    *,
    query: str,
    provider: str,
    max_results: int,
    searched_at: str | None = None,
) -> list[SearchResult]:
    payload = json.loads(raw)
    searched_on = searched_at or datetime.now(timezone.utc).isoformat()
    results: list[SearchResult] = []
    for item in payload.get("results", [])[:max_results]:
        url = normalize_result_url(str(item.get("url", "")))
        if not url:
            continue
        results.append(
            SearchResult(
                title=clean_text(str(item.get("title", ""))),
                url=url,
                snippet=clean_text(str(item.get("content", ""))),
                provider=provider,
                query=query,
                date_searched=searched_on,
            )
        )
    return results


def parse_google_custom_search_json(
    raw: str,
    *,
    query: str,
    provider: str,
    max_results: int,
    searched_at: str | None = None,
) -> list[SearchResult]:
    payload = json.loads(raw)
    searched_on = searched_at or datetime.now(timezone.utc).isoformat()
    results: list[SearchResult] = []
    for item in payload.get("items", [])[:max_results]:
        url = normalize_result_url(str(item.get("link", "")))
        if not url:
            continue
        results.append(
            SearchResult(
                title=clean_text(str(item.get("title", ""))),
                url=url,
                snippet=clean_text(str(item.get("snippet", ""))),
                provider=provider,
                query=query,
                date_searched=searched_on,
            )
        )
    return results


def rank_search_results(
    results: list[SearchResult],
    *,
    company: str,
    searched_at: str,
) -> list[SearchResult]:
    ranked = [
        SearchResult(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            provider=result.provider,
            query=result.query,
            date_searched=searched_at,
            relevance_score=score_result(result, company=company),
        )
        for result in results
    ]
    return sorted(ranked, key=lambda result: (-result.relevance_score, result.title))


def score_result(result: SearchResult, company: str = "") -> int:
    score = 0
    searchable = " ".join([result.title, result.url, result.snippet]).lower()
    domain = urlparse(result.url).netloc.lower()

    if is_blocked_domain(domain):
        return -100

    if any(keyword in searchable for keyword in CAREER_URL_KEYWORDS):
        score += 20

    company_tokens = [token for token in re.split(r"[^a-z0-9]+", company.lower()) if len(token) > 2]
    if company_tokens and any(token in domain for token in company_tokens):
        score += 25

    if domain.count(".") <= 2:
        score += 5

    if "official" in result.snippet.lower():
        score += 3

    return score


def is_blocked_domain(domain: str) -> bool:
    return any(blocked in domain for blocked in BLOCKED_DOMAINS)


def normalize_result_url(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith("//"):
        cleaned = f"https:{cleaned}"
    parsed = urlparse(cleaned)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        redirect_target = parse_qs(parsed.query).get("uddg", [""])[0]
        if redirect_target:
            cleaned = unquote(redirect_target)
            parsed = urlparse(cleaned)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return parsed._replace(fragment="").geturl()


def write_search_results_jsonl(
    results: list[SearchResult],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(result), sort_keys=True) for result in results]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def summarize_search_response(response: SearchResponse) -> str:
    lines = [
        "Internet search summary",
        "=======================",
        f"Query: {response.query}",
        f"Provider: {response.provider}",
        f"Results: {len(response.results)}",
    ]
    if response.output_path:
        lines.append(f"Wrote results to: {response.output_path}")

    if response.results:
        lines.append("")
        lines.append("Top results:")
        for result in response.results[:5]:
            lines.append(
                f"- [{result.relevance_score}] {result.title} -> {result.url}"
            )

    if response.errors:
        lines.append("")
        lines.append("Warnings and errors:")
        lines.extend(f"- {error}" for error in response.errors)

    return "\n".join(lines)


def get_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def describe_google_custom_search_http_error(error: HTTPError) -> str:
    if error.code == 403:
        return (
            "Google Custom Search denied the request (403). "
            "Check API key permissions, billing, and the 100 queries/day free quota."
        )
    if error.code == 400:
        return (
            "Google Custom Search rejected the request (400). "
            "Check GOOGLE_CUSTOM_SEARCH_API_KEY and GOOGLE_CSE_ID in .env."
        )
    if error.code == 429:
        return "Google Custom Search rate limit reached (429). Retry later."
    return f"Google Custom Search API error ({error.code}): {error.reason}"


def post_text(url: str, content_type: str, body: bytes) -> str:
    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": content_type,
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        },
    )
    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def clean_text(value: str) -> str:
    return " ".join(value.split())


@dataclass
class ParsedSearchItem:
    title: str
    url: str
    snippet: str


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[ParsedSearchItem] = []
        self._capture_title = False
        self._capture_snippet = False
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        class_value = attrs_dict.get("class", "") or ""
        if tag == "a" and "result__a" in class_value:
            self._capture_title = True
            self._current_url = attrs_dict.get("href", "") or ""
            self._current_title = []
        if tag == "a" and "result__snippet" in class_value:
            self._capture_snippet = True
            self._current_snippet = []

    def handle_data(self, data: str) -> None:
        if self._capture_title:
            self._current_title.append(data)
        if self._capture_snippet:
            self._current_snippet.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_title:
            self.results.append(
                ParsedSearchItem(
                    title=clean_text("".join(self._current_title)),
                    url=self._current_url,
                    snippet="",
                )
            )
            self._capture_title = False
        if tag == "a" and self._capture_snippet:
            if self.results:
                self.results[-1] = ParsedSearchItem(
                    title=self.results[-1].title,
                    url=self.results[-1].url,
                    snippet=clean_text("".join(self._current_snippet)),
                )
            self._capture_snippet = False
