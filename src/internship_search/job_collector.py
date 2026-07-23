"""Collect job posting candidates from company career sources."""

from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from internship_search.internship_listing import (
    is_specific_internship_listing,
    is_specific_program_detail_url,
    mentions_internship,
)
from internship_search.source_registry import CompanySource, read_source_registry


FetchPage = Callable[[str], str]

SLOW_SOURCE_TIMEOUT_SECONDS = {
    "mckinsey.com": 60,
    "www.mckinsey.com": 60,
}
DEFAULT_FETCH_TIMEOUT_SECONDS = 20
MAX_CAREER_PAGES_PER_SOURCE_URL = 100

PAGINATION_QUERY_KEYS = {
    "page",
    "pageindex",
    "pageoffset",
    "pagenumber",
    "page_number",
    "pg",
    "currentpage",
    "resultsfrom",
}
NUMERIC_PAGINATION_QUERY_KEYS = {
    "start",
    "startindex",
    "startrow",
    "offset",
    "from",
}
PAGINATION_TEXT = {
    "next",
    "next page",
    "older",
    "older jobs",
    "more",
    "more jobs",
    "load more",
    "show more",
}
CAREER_LISTING_TEXT = {
    "all jobs",
    "all openings",
    "available jobs",
    "career opportunities",
    "careers",
    "current jobs",
    "current openings",
    "find jobs",
    "job opportunities",
    "jobs",
    "open jobs",
    "open positions",
    "open roles",
    "search jobs",
    "see jobs",
    "view jobs",
    "view openings",
}
TRUSTED_CAREER_HOST_FRAGMENTS = (
    "ashbyhq.com",
    "breezy.hr",
    "greenhouse.io",
    "icims.com",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "successfactors.com",
    "taleo.net",
    "teamtailor.com",
)

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
    eligibility_text: str = ""


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


@dataclass(frozen=True)
class CareerPageLink:
    text: str
    href: str
    rel: str = ""
    aria_label: str = ""
    class_name: str = ""


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
    page_cache: dict[str, str] = {}

    def cached_page_fetcher(url: str) -> str:
        canonical = canonical_navigation_url(url)
        if canonical not in page_cache:
            page_cache[canonical] = page_fetcher(url)
        return page_cache[canonical]

    for source in sources:
        source_postings, source_errors = collect_postings_for_source_urls(
            source=source,
            page_fetcher=cached_page_fetcher,
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
    complete_scan = False

    for careers_url in urls_to_try:
        if is_probable_direct_source_url(careers_url):
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
                store_posting_candidate(postings_by_url, posting)
            if outcome.warning:
                last_warning = outcome.warning
            continue

        page_queue: deque[str] = deque([careers_url])
        queued_urls = {canonical_navigation_url(careers_url)}
        pages_processed = 0
        root_fetched = False

        while page_queue and pages_processed < MAX_CAREER_PAGES_PER_SOURCE_URL:
            page_url = page_queue.popleft()
            pages_processed += 1
            try:
                from internship_search.retry import retry_call

                html = retry_call(lambda: page_fetcher(page_url), max_attempts=2)
            except Exception as error:  # noqa: BLE001 - preserve source-level failures.
                fetch_source = source_for_page(source, page_url, root_url=careers_url)
                api_outcome = collect_postings_for_source(
                    source=fetch_source,
                    html="",
                    collected_date=collected_date,
                )
                if api_outcome.complete:
                    for posting in api_outcome.postings:
                        store_posting_candidate(postings_by_url, posting)
                    complete_scan = True
                    if canonical_navigation_url(page_url) == canonical_navigation_url(careers_url):
                        root_fetched = True
                    continue
                if canonical_navigation_url(page_url) == canonical_navigation_url(careers_url):
                    fetch_failures += 1
                errors.append(
                    CollectionError(
                        company=source.company,
                        source_url=page_url,
                        message=str(error),
                    )
                )
                continue

            if canonical_navigation_url(page_url) == canonical_navigation_url(careers_url):
                root_fetched = True
            fetch_source = source_for_page(source, page_url, root_url=careers_url)
            outcome = collect_postings_for_source(
                source=fetch_source,
                html=html,
                collected_date=collected_date,
            )
            for posting in outcome.postings:
                store_posting_candidate(postings_by_url, posting)
            if outcome.warning:
                last_warning = outcome.warning
                if outcome.postings:
                    errors.append(
                        CollectionError(
                            company=source.company,
                            source_url=page_url,
                            message=outcome.warning,
                        )
                    )
            if outcome.complete:
                complete_scan = True

            navigation_urls = (
                []
                if is_detail_navigation_url(page_url)
                else discover_career_navigation_urls(
                    html,
                    current_url=page_url,
                    root_url=careers_url,
                )
            )
            if outcome.complete and fetch_source.collector == "mckinsey_jobs":
                navigation_urls = []
            if outcome.complete:
                navigation_urls = [
                    url for url in navigation_urls if is_detail_navigation_url(url)
                ]
            for next_url in navigation_urls:
                canonical = canonical_navigation_url(next_url)
                if canonical in queued_urls:
                    continue
                queued_urls.add(canonical)
                page_queue.append(next_url)

        if page_queue:
            errors.append(
                CollectionError(
                    company=source.company,
                    source_url=careers_url,
                    message=(
                        "Career pagination exceeded the safety limit of "
                        f"{MAX_CAREER_PAGES_PER_SOURCE_URL} pages; some later pages may be missing."
                    ),
                )
            )
        if not root_fetched and fetch_failures == 0:
            fetch_failures += 1

    if not postings_by_url and fetch_failures < len(urls_to_try) and not complete_scan:
        errors.append(
            CollectionError(
                company=source.company,
                source_url=source.careers_url,
                message=last_warning
                or "No posting candidates extracted from configured careers URLs.",
            )
        )

    return list(postings_by_url.values()), errors


def source_for_page(
    source: CompanySource,
    page_url: str,
    *,
    root_url: str,
) -> CompanySource:
    """Create a source whose relative links resolve against the current page."""

    root_host = urlparse(root_url).netloc.lower()
    page_host = urlparse(page_url).netloc.lower()
    collector = source.collector
    if page_host != root_host and collector != "auto":
        collector = "auto"
    return CompanySource(
        company=source.company,
        website=source.website,
        careers_url=page_url,
        source_type=source.source_type,
        origin=source.origin,
        has_connection=source.has_connection,
        notes=source.notes,
        collector=collector,
    )


def store_posting_candidate(
    postings_by_url: dict[str, JobPosting],
    posting: JobPosting,
) -> None:
    """Merge list-page and detail-page metadata for the same public posting."""

    existing = postings_by_url.get(posting.posting_url)
    if existing is None:
        postings_by_url[posting.posting_url] = posting
        return
    from internship_search.posting_metadata import merge_posting_metadata

    postings_by_url[posting.posting_url] = merge_posting_metadata(existing, posting)


def discover_career_navigation_urls(
    html: str,
    *,
    current_url: str,
    root_url: str,
) -> list[str]:
    """Find safe pagination and job-listing pages linked from a careers page."""

    parser = CareerPageLinkExtractor()
    parser.feed(html)
    current_host = urlparse(current_url).netloc.lower()
    root_host = urlparse(root_url).netloc.lower()
    discovered: list[str] = []
    seen: set[str] = set()

    for link in parser.links:
        target = normalize_link(current_url, link.href)
        if not target:
            continue
        target = repair_career_pagination_url(target)
        parsed = urlparse(target)
        target_host = parsed.netloc.lower()
        same_career_host = target_host in {current_host, root_host}
        trusted_external = is_trusted_career_host(target_host)
        pagination = is_pagination_link(link, target)
        listing_page = is_career_listing_page_link(link, target)
        detail_page = is_internship_detail_page_link(link, target)
        if is_unrelated_locale_variant(target, root_url):
            continue
        if pagination and not same_career_host:
            continue
        if listing_page and not (same_career_host or trusted_external):
            continue
        if detail_page and not (same_career_host or trusted_external):
            continue
        if not pagination and not listing_page and not detail_page:
            continue

        canonical = canonical_navigation_url(target)
        if canonical in seen or canonical == canonical_navigation_url(current_url):
            continue
        seen.add(canonical)
        discovered.append(target)

    return discovered


def is_pagination_link(link: CareerPageLink, target_url: str) -> bool:
    text = " ".join(link.text.lower().split())
    metadata = " ".join([link.rel, link.aria_label, link.class_name]).lower()
    if "next" in link.rel.lower() or "next" in link.aria_label.lower():
        return True
    if text in PAGINATION_TEXT or text.startswith("next ") or "pagination-next" in metadata:
        return True

    parsed = urlparse(target_url)
    query = parse_qs(parsed.query)
    if any(key.lower() in PAGINATION_QUERY_KEYS for key in query):
        return True
    for key, values in query.items():
        if key.lower() not in NUMERIC_PAGINATION_QUERY_KEYS:
            continue
        if any(value.isdigit() for value in values):
            return True
    path = parsed.path.lower().rstrip("/")
    if text.isdigit() and re.search(r"/(?:careers?|jobs?|openings?|search)", path):
        return not is_probable_job_detail_url(target_url)
    return bool(
        re.search(r"/(?:page|pages|p)/?[-_]?\d+$", path)
        or re.search(r"[-_/](?:page|pg)[-_]?\d+$", path)
    )


def is_career_listing_page_link(link: CareerPageLink, target_url: str) -> bool:
    text = " ".join(link.text.lower().split())
    parsed = urlparse(target_url)
    path = parsed.path.lower().rstrip("/")
    host = parsed.netloc.lower()
    if host == "careers.blackrock.com" and path == "/job":
        # BlackRock uses this as a search-form action, not a browsable job index.
        return False
    if link.rel == "career-embed" and is_trusted_career_host(urlparse(target_url).netloc):
        return True
    if text in CAREER_LISTING_TEXT:
        return True
    parts = [part for part in path.split("/") if part]
    if "lever.co" in host or "ashbyhq.com" in host:
        return len(parts) == 1
    if "greenhouse.io" in host:
        return len(parts) == 1 or (len(parts) == 2 and parts[-1] == "jobs")
    return bool(
        re.search(
            r"/(?:careers?|jobs?|openings?|positions?|search-jobs|job-search)$",
            path,
        )
    )


def is_internship_detail_page_link(link: CareerPageLink, target_url: str) -> bool:
    """Identify named internship records that should be opened for full metadata."""

    text = " ".join(link.text.split())
    path = urlparse(target_url).path.lower().rstrip("/")
    if re.search(r"/internships?-programs/[^/]+$", path):
        # Program indexes often label every link only "Learn more"; the detail
        # page determines whether an internship is open, while the normalized
        # slug prevents unrelated scholarships and exploratory programs from
        # expanding into a large navigation crawl.
        slug_text = path.rsplit("/", maxsplit=1)[-1].replace("-", " ")
        return mentions_internship(text, slug_text)
    return mentions_internship(text, target_url) and is_probable_job_detail_url(
        target_url
    )


def is_detail_navigation_url(url: str) -> bool:
    path = urlparse(url).path.lower().rstrip("/")
    return bool(
        is_probable_job_detail_url(url)
        or re.search(r"/internships?-programs/[^/]+$", path)
    )


def is_unrelated_locale_variant(target_url: str, root_url: str) -> bool:
    """Avoid crawling duplicate translated navigation trees from a global site."""

    locale_pattern = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.IGNORECASE)
    target_parts = [part for part in urlparse(target_url).path.split("/") if part]
    root_parts = [part for part in urlparse(root_url).path.split("/") if part]
    target_locale = (
        target_parts[0].lower()
        if target_parts and locale_pattern.fullmatch(target_parts[0])
        else ""
    )
    root_locale = (
        root_parts[0].lower()
        if root_parts and locale_pattern.fullmatch(root_parts[0])
        else ""
    )
    return bool(target_locale and target_locale != root_locale)


def repair_career_pagination_url(url: str) -> str:
    """Repair known career-site pagination URLs that depend on browser JavaScript."""

    parsed = urlparse(url)
    if parsed.netloc.lower() != "careers.blackrock.com" or parsed.query:
        return url
    match = re.fullmatch(r"(/search-jobs)&(p=\d+)", parsed.path, flags=re.IGNORECASE)
    if not match:
        return url
    return parsed._replace(path=match.group(1), query=match.group(2)).geturl()


def is_probable_job_detail_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower().rstrip("/")
    parts = [part for part in path.split("/") if part]
    if re.search(r"/(?:job|jobs)/(?:[^/]+/)*\d+(?:/|$)", path):
        return True
    if "/job/" in path or "/jobdetails/" in path or "/job-detail/" in path:
        return True
    if "lever.co" in host or "ashbyhq.com" in host:
        return len(parts) >= 2
    return False


def is_probable_direct_source_url(url: str) -> bool:
    """Recognize a source that is itself one job without broadening link crawls."""

    if is_probable_job_detail_url(url):
        return True
    path = urlparse(url).path.lower()
    return bool(re.search(r"/jobs/(?:r[-_]\d+|\d+)(?:/|$)", path))


def is_trusted_career_host(host: str) -> bool:
    normalized = host.lower().split(":", 1)[0]
    return any(
        normalized == domain or normalized.endswith(f".{domain}")
        for domain in TRUSTED_CAREER_HOST_FRAGMENTS
    )


def canonical_navigation_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
    ).geturl().rstrip("/")


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
        if is_specific_program_detail_url(title.lower(), posting_url.lower()):
            # Open the detail page first so closed programs and full locations
            # can be evaluated before a posting is accepted.
            continue
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


class CareerPageLinkExtractor(HTMLParser):
    """Extract links plus navigation attributes used by careers pagination."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[CareerPageLink] = []
        self._current_attrs: dict[str, str] | None = None
        self._current_text: list[str] = []
        self._current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name not in {"a", "button", "iframe", "link", "script"}:
            return
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag_name in {"iframe", "script"}:
            src = attrs_dict.get("src", "")
            if src:
                self.links.append(
                    CareerPageLink(
                        text="",
                        href=src,
                        rel="career-embed",
                    )
                )
            return
        href = next(
            (
                attrs_dict.get(key, "")
                for key in ("href", "data-url", "data-href", "data-next", "data-load-more-url")
                if attrs_dict.get(key)
            ),
            "",
        )
        if not href:
            return
        attrs_dict["href"] = href
        if tag_name == "link":
            if "next" in attrs_dict.get("rel", "").lower():
                self.links.append(
                    CareerPageLink(
                        text="Next",
                        href=href,
                        rel=attrs_dict.get("rel", ""),
                    )
                )
            return
        self._current_attrs = attrs_dict
        self._current_text = []
        self._current_tag = tag_name

    def handle_data(self, data: str) -> None:
        if self._current_attrs is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != self._current_tag or self._current_attrs is None:
            return
        self.links.append(
            CareerPageLink(
                text=clean_title(" ".join(self._current_text)),
                href=self._current_attrs["href"],
                rel=self._current_attrs.get("rel", ""),
                aria_label=self._current_attrs.get("aria-label", ""),
                class_name=self._current_attrs.get("class", ""),
            )
        )
        self._current_attrs = None
        self._current_text = []
        self._current_tag = None
