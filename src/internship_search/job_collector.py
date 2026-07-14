"""Collect job posting candidates from company career sources."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from internship_search.internship_listing import is_specific_internship_listing
from internship_search.source_registry import CompanySource, read_source_registry


FetchPage = Callable[[str], str]

SLOW_SOURCE_TIMEOUT_SECONDS = {
    "mckinsey.com": 60,
    "www.mckinsey.com": 60,
}
DEFAULT_FETCH_TIMEOUT_SECONDS = 20

TEXT_JOB_KEYWORDS = {
    "analyst",
    "associate consultant",
    "graduate",
    "intern",
    "internship",
    "job",
    "opening",
    "opportunities",
    "opportunity",
    "position",
    "program",
    "role",
    "student",
    "summer",
}

URL_JOB_KEYWORDS = {
    "/job/",
    "/jobs/",
    "jobid=",
    "requisition",
}

EXCLUDED_URL_FRAGMENTS = (
    "/blog",
    "blog-",
)

EXCLUDED_TITLES = {
    "benefits",
    "blog: inside bain",
    "career stories",
    "careers",
    "contact us",
    "privacy notice",
}

EXCLUDED_LINK_PREFIXES = ("#", "mailto:", "tel:", "javascript:")


@dataclass(frozen=True)
class JobPosting:
    title: str
    company: str
    location: str
    posting_url: str
    date_collected: str
    source_url: str


@dataclass(frozen=True)
class CollectionError:
    company: str
    source_url: str
    message: str


@dataclass(frozen=True)
class CollectionResult:
    postings: list[JobPosting]
    errors: list[CollectionError]
    output_path: Path


@dataclass(frozen=True)
class LinkCandidate:
    text: str
    href: str


def collect_from_registry_file(
    registry_path: Path | str = "data/source_registry.json",
    output_path: Path | str = "data/postings.jsonl",
    errors_output_path: Path | str | None = "data/collection_errors.jsonl",
    fetch_page: FetchPage | None = None,
    collected_on: date | None = None,
    include_job_boards: bool = False,
    job_board_output_path: Path | str | None = "data/job_board_postings.jsonl",
    target_year: str = "2027",
) -> CollectionResult:
    """Collect job posting candidates from a source registry JSON file."""

    sources = read_source_registry(registry_path)
    return collect_from_sources(
        sources=sources,
        output_path=output_path,
        errors_output_path=errors_output_path,
        fetch_page=fetch_page or fetch_url,
        collected_on=collected_on,
        include_job_boards=include_job_boards,
        job_board_output_path=job_board_output_path,
        target_year=target_year,
    )


def collect_from_sources(
    sources: list[CompanySource],
    output_path: Path | str = "data/postings.jsonl",
    errors_output_path: Path | str | None = "data/collection_errors.jsonl",
    fetch_page: FetchPage | None = None,
    collected_on: date | None = None,
    include_job_boards: bool = False,
    job_board_output_path: Path | str | None = "data/job_board_postings.jsonl",
    target_year: str = "2027",
) -> CollectionResult:
    """Fetch each source and write deduplicated posting candidates."""

    collected_date = (collected_on or date.today()).isoformat()
    postings: list[JobPosting] = []
    errors: list[CollectionError] = []
    page_fetcher = fetch_page or fetch_url

    for source in sources:
        source_postings, source_errors = collect_postings_for_source_urls(
            source=source,
            page_fetcher=page_fetcher,
            collected_date=collected_date,
        )
        postings.extend(source_postings)
        errors.extend(source_errors)

    if include_job_boards:
        from internship_search.job_board_search import search_job_boards

        board_response = search_job_boards(
            target_year=target_year,
            output_path=job_board_output_path,
            searched_at=f"{collected_date}T00:00:00+00:00",
        )
        board_postings = [
            to_job_posting_from_board(posting, collected_on=collected_on or date.today())
            for posting in board_response.postings
        ]
        postings = merge_posting_candidates(postings, board_postings)
        errors.extend(
            CollectionError(
                company=f"Job Board ({board_response.provider})",
                source_url=board_response.query,
                message=error,
            )
            for error in board_response.errors
        )
        errors.extend(
            CollectionError(
                company="Job Board",
                source_url=board_response.provider,
                message=limitation,
            )
            for limitation in board_response.limitations
        )

    output = write_postings_jsonl(postings=postings, output_path=output_path)
    if errors_output_path is not None:
        from internship_search.monitored_companies import write_collection_errors_jsonl

        write_collection_errors_jsonl(errors, errors_output_path)
    return CollectionResult(postings=postings, errors=errors, output_path=output)


def to_job_posting_from_board(
    posting: "JobBoardPosting",
    *,
    collected_on: date,
) -> JobPosting:
    from internship_search.job_board_search import to_job_posting

    return to_job_posting(posting, collected_on=collected_on)


def collect_postings_for_source_urls(
    *,
    source: CompanySource,
    page_fetcher: FetchPage,
    collected_date: str,
) -> tuple[list[JobPosting], list[CollectionError]]:
    """Fetch one or more careers URLs for a source and extract posting candidates."""

    from internship_search.career_collectors import collect_postings_for_source

    urls_to_try = deduplicate_urls(
        [source.careers_url, *source.alternate_careers_urls],
    )
    postings_by_url: dict[str, JobPosting] = {}
    errors: list[CollectionError] = []
    fetch_failures = 0
    last_warning = ""

    for careers_url in urls_to_try:
        if "/job/" in careers_url.lower():
            direct_source = CompanySource(
                company=source.company,
                website=source.website,
                careers_url=careers_url,
                source_type=source.source_type,
                origin=source.origin,
                has_connection=source.has_connection,
                notes=source.notes,
                alternate_careers_urls=source.alternate_careers_urls,
                collector="direct_job_url",
            )
            outcome = collect_postings_for_source(
                source=direct_source,
                html="",
                collected_date=collected_date,
            )
            for posting in outcome.postings:
                postings_by_url.setdefault(posting.posting_url, posting)
            if outcome.warning:
                last_warning = outcome.warning
            continue

        try:
            from internship_search.retry import retry_call

            html = retry_call(lambda: page_fetcher(careers_url), max_attempts=2)
        except Exception as error:  # noqa: BLE001 - preserve source-level failures.
            fetch_failures += 1
            errors.append(
                CollectionError(
                    company=source.company,
                    source_url=careers_url,
                    message=str(error),
                )
            )
            continue

        fetch_source = CompanySource(
            company=source.company,
            website=source.website,
            careers_url=careers_url,
            source_type=source.source_type,
            origin=source.origin,
            has_connection=source.has_connection,
            notes=source.notes,
            alternate_careers_urls=source.alternate_careers_urls,
            collector=source.collector,
        )
        outcome = collect_postings_for_source(
            source=fetch_source,
            html=html,
            collected_date=collected_date,
        )
        for posting in outcome.postings:
            postings_by_url.setdefault(posting.posting_url, posting)
        if outcome.warning:
            last_warning = outcome.warning

    if not postings_by_url and fetch_failures < len(urls_to_try):
        errors.append(
            CollectionError(
                company=source.company,
                source_url=source.careers_url,
                message=last_warning
                or "No posting candidates extracted from configured careers URLs.",
            )
        )

    return list(postings_by_url.values()), errors


def deduplicate_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in urls:
        cleaned = url.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def fetch_url(url: str, timeout_seconds: int | None = None) -> str:
    """Fetch a URL as text using the standard library."""

    timeout = timeout_seconds or timeout_for_url(url)
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
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def timeout_for_url(url: str) -> int:
    host = urlparse(url).netloc.lower()
    return SLOW_SOURCE_TIMEOUT_SECONDS.get(host, DEFAULT_FETCH_TIMEOUT_SECONDS)


def extract_postings_from_html(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Extract likely job posting links from a career page."""

    parser = LinkExtractor()
    parser.feed(html)

    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for link in parser.links:
        if not is_likely_job_link(link):
            continue

        posting_url = normalize_link(source.careers_url, link.href)
        if not posting_url or posting_url in seen_urls:
            continue

        title = clean_title(link.text)
        if not is_specific_internship_listing(title, posting_url):
            continue

        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location="Unknown",
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )

    return postings


def merge_posting_candidates(
    primary: list[JobPosting],
    secondary: list[JobPosting] | None = None,
) -> list[JobPosting]:
    """Merge posting lists, preferring career-page sources for duplicate roles."""

    from internship_search.posting_history import deduplicate_current_postings
    from internship_search.posting_metadata import enrich_job_posting_local, merge_posting_metadata

    by_key: dict[str, JobPosting] = {}
    for posting in [*primary, *(secondary or [])]:
        key = canonical_posting_url(posting.posting_url) or posting.posting_url.lower()
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = posting
            continue
        by_key[key] = merge_posting_metadata(existing, posting)

    enriched = [enrich_job_posting_local(posting) for posting in by_key.values()]
    deduped = deduplicate_current_postings(enriched)
    return sorted(
        deduped.postings_by_id.values(),
        key=lambda posting: (posting.company.lower(), posting.title.lower(), posting.posting_url),
    )


def write_postings_jsonl(
    postings: list[JobPosting],
    output_path: Path | str = "data/postings.jsonl",
) -> Path:
    """Write current postings to JSONL while deduplicating by canonical posting URL."""

    from internship_search.posting_metadata import enrich_job_posting

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    merged = merge_posting_candidates(postings)
    enriched = [enrich_job_posting(posting, use_remote_apis=True) for posting in merged]
    lines = [json.dumps(asdict(posting), sort_keys=True) for posting in enriched]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def canonical_posting_url(url: str) -> str:
    from internship_search.job_board_listings import canonical_aggregator_job_url

    aggregator = canonical_aggregator_job_url(url)
    if aggregator:
        return aggregator

    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip().lower()

    tracking_params = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "ref",
        "source",
        "gh_src",
    }
    query_values = parse_qs(parsed.query, keep_blank_values=False)
    filtered_query = {
        key: values
        for key, values in query_values.items()
        if key.lower() not in tracking_params
    }
    normalized_query = urlencode(filtered_query, doseq=True)
    normalized = parsed._replace(query=normalized_query, fragment="").geturl().lower()
    return normalized.rstrip("/")


def read_postings_jsonl(path: Path | str) -> list[JobPosting]:
    postings_path = Path(path)
    if not postings_path.exists():
        return []

    postings: list[JobPosting] = []
    for line in postings_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            postings.append(JobPosting(**json.loads(line)))
    return postings


def summarize_collection(result: CollectionResult) -> str:
    lines = [
        "Job collection summary",
        "======================",
        f"Posting candidates collected: {len(result.postings)}",
        f"Source errors: {len(result.errors)}",
        f"Wrote postings to: {result.output_path}",
    ]

    if result.postings:
        lines.append("")
        lines.append("Companies with posting candidates:")
        company_counts: dict[str, int] = {}
        for posting in result.postings:
            company_counts[posting.company] = company_counts.get(posting.company, 0) + 1
        lines.extend(
            f"- {company}: {count}"
            for company, count in sorted(company_counts.items())
        )

    if result.errors:
        lines.append("")
        lines.append("Source warnings and errors:")
        lines.extend(
            f"- {error.company} ({error.source_url}): {error.message}"
            for error in result.errors
        )

    return "\n".join(lines)


def is_likely_job_link(link: LinkCandidate) -> bool:
    href = link.href.strip()
    if not href or href.lower().startswith(EXCLUDED_LINK_PREFIXES):
        return False

    text = link.text.strip().lower()
    href_lower = href.lower()
    if text in EXCLUDED_TITLES:
        return False

    text_matches = any(keyword in text for keyword in TEXT_JOB_KEYWORDS)
    url_matches = any(keyword in href_lower for keyword in URL_JOB_KEYWORDS)
    if any(fragment in href_lower for fragment in EXCLUDED_URL_FRAGMENTS):
        return False
    return text_matches or url_matches


def normalize_link(base_url: str, href: str) -> str:
    href = href.strip()
    if not href or href.lower().startswith(EXCLUDED_LINK_PREFIXES):
        return ""

    normalized = urljoin(base_url, href)
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return normalized


def clean_title(title: str) -> str:
    cleaned = " ".join(title.split())
    return cleaned or "Untitled posting"


class LinkExtractor(HTMLParser):
    """Extract anchor text and href values from simple HTML pages."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[LinkCandidate] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if not href:
            return

        self._current_href = href
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._current_href:
            return

        self.links.append(
            LinkCandidate(
                text=clean_title(" ".join(self._current_text)),
                href=self._current_href,
            )
        )
        self._current_href = None
        self._current_text = []
