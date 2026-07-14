"""Search external job boards for internship posting candidates."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from internship_search.env_loader import load_env_into_process
from internship_search.internship_listing import is_specific_internship_listing
from internship_search.internet_search import (
    SearchResult,
    get_search_provider,
    normalize_result_url,
)
from internship_search.job_collector import (
    JobPosting,
    canonical_posting_url,
    clean_title,
    merge_posting_candidates,
    write_postings_jsonl,
)


DEFAULT_TARGET_YEAR = "2027"

JOB_BOARD_DOMAINS = (
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "icims.com",
    "smartrecruiters.com",
    "ashbyhq.com",
    "workday.com",
    "job-board",
    "jobs.",
    "linkedin.com",
    "indeed.com",
)

DUCKDUCKGO_JOB_BOARD_QUERIES = (
    "summer {target_year} internship site:greenhouse.io",
    "summer {target_year} internship site:jobs.lever.co",
    "summer {target_year} internship site:myworkdayjobs.com",
    "summer {target_year} internship site:linkedin.com/jobs/view",
    '"summer intern" {target_year} site:linkedin.com/jobs/view',
    "internship {target_year} site:linkedin.com/jobs/view",
    "summer {target_year} internship site:indeed.com/viewjob",
    '"summer intern" {target_year} site:indeed.com/viewjob',
    "internship analyst {target_year} site:indeed.com/viewjob",
)

DUCKDUCKGO_RESULTS_PER_QUERY = 8


@dataclass(frozen=True)
class JobBoardPosting:
    title: str
    company: str
    location: str
    posting_url: str
    posting_id: str
    snippet: str
    provider: str
    query: str
    date_searched: str


@dataclass(frozen=True)
class JobBoardSearchResponse:
    query: str
    provider: str
    postings: list[JobBoardPosting]
    output_path: Path | None
    errors: list[str]
    limitations: tuple[str, ...] = ()
    platform_counts: tuple[tuple[str, int], ...] = ()


class JobBoardProvider(Protocol):
    name: str

    def search(
        self,
        query: str,
        *,
        target_year: str = DEFAULT_TARGET_YEAR,
        max_results: int = 20,
        searched_at: str | None = None,
    ) -> list[JobBoardPosting]:
        ...


def search_job_boards(
    *,
    query: str | None = None,
    target_year: str = DEFAULT_TARGET_YEAR,
    provider: JobBoardProvider | None = None,
    max_results: int = 20,
    output_path: Path | str | None = "data/job_board_postings.jsonl",
    searched_at: str | None = None,
) -> JobBoardSearchResponse:
    load_env_into_process()
    active_provider = provider or get_job_board_provider()
    searched_on = searched_at or datetime.now(timezone.utc).isoformat()
    search_query = query or build_default_job_board_query(target_year=target_year)
    errors: list[str] = []
    postings: list[JobBoardPosting] = []

    try:
        postings = active_provider.search(
            search_query,
            target_year=target_year,
            max_results=max_results,
            searched_at=searched_on,
        )
    except Exception as error:  # noqa: BLE001 - preserve provider failures for CLI output.
        errors.append(str(error))

    path = None
    if output_path is not None:
        path = write_job_board_postings_jsonl(postings, output_path)

    from internship_search.job_board_listings import (
        build_linkedin_indeed_limitations,
        count_job_board_platforms,
    )

    platform_counts = count_job_board_platforms(postings)
    limitations = tuple(
        build_linkedin_indeed_limitations(postings, provider_name=active_provider.name)
    )

    return JobBoardSearchResponse(
        query=search_query,
        provider=active_provider.name,
        postings=postings,
        output_path=path,
        errors=errors,
        limitations=limitations,
        platform_counts=tuple(sorted(platform_counts.items())),
    )


def search_job_boards_file(
    output_path: Path | str = "data/job_board_postings.jsonl",
    *,
    query: str | None = None,
    target_year: str = DEFAULT_TARGET_YEAR,
    provider: JobBoardProvider | None = None,
    max_results: int = 20,
) -> JobBoardSearchResponse:
    return search_job_boards(
        query=query,
        target_year=target_year,
        provider=provider,
        max_results=max_results,
        output_path=output_path,
    )


def get_job_board_provider() -> JobBoardProvider:
    """Return the DuckDuckGo job-board search provider."""

    return DuckDuckGoJobBoardProvider()


class DuckDuckGoJobBoardProvider:
    name = "duckduckgo_job_board"

    def __init__(self, search_provider=None) -> None:
        self.search_provider = search_provider or get_search_provider()

    def search(
        self,
        query: str,
        *,
        target_year: str = DEFAULT_TARGET_YEAR,
        max_results: int = 20,
        searched_at: str | None = None,
    ) -> list[JobBoardPosting]:
        searched_on = searched_at or datetime.now(timezone.utc).isoformat()
        postings_by_id: dict[str, JobBoardPosting] = {}
        default_query = build_default_job_board_query(target_year=target_year)
        if query and query != default_query:
            queries = [query]
        else:
            queries = [
                template.format(target_year=target_year)
                for template in DUCKDUCKGO_JOB_BOARD_QUERIES
            ]

        per_query_limit = (
            DUCKDUCKGO_RESULTS_PER_QUERY
            if len(queries) > 1
            else max_results
        )

        for board_query in queries:
            raw_results = self.search_provider.search(
                query=board_query,
                max_results=per_query_limit,
            )
            for result in raw_results:
                if not is_job_board_search_result(result):
                    continue
                if not is_public_job_board_listing_url(result.url):
                    continue
                posting = job_board_posting_from_search_result(
                    result,
                    searched_at=searched_on,
                    provider=self.name,
                )
                if not is_specific_internship_listing(posting.title, posting.posting_url):
                    continue
                postings_by_id.setdefault(posting.posting_id, posting)

        ordered = sorted(postings_by_id.values(), key=lambda posting: posting.title.lower())
        if len(queries) > 1:
            return ordered[: max(max_results, len(DUCKDUCKGO_JOB_BOARD_QUERIES) * 2)]
        return ordered[:max_results]


def job_board_posting_from_search_result(
    result: SearchResult,
    *,
    searched_at: str,
    provider: str,
) -> JobBoardPosting:
    from internship_search.posting_metadata import infer_company_from_posting_url, parse_job_board_title

    from internship_search.job_board_listings import canonical_aggregator_job_url

    title = clean_title(result.title)
    posting_url = normalize_result_url(result.url)
    canonical_aggregator = canonical_aggregator_job_url(posting_url)
    if canonical_aggregator:
        posting_url = canonical_aggregator
    parsed_title, parsed_company = parse_job_board_title(title, posting_url)
    company = parsed_company or infer_company_from_job_board_result(result)
    if not company:
        company = infer_company_from_posting_url(posting_url) or "Unknown Company"
    location = infer_location_from_job_board_result(result)
    posting_id = stable_posting_id(posting_url, title=parsed_title or title, provider=provider)
    return JobBoardPosting(
        title=parsed_title or title,
        company=company,
        location=location,
        posting_url=posting_url,
        posting_id=posting_id,
        snippet=clean_title(result.snippet),
        provider=provider,
        query=result.query,
        date_searched=searched_at,
    )


def to_job_posting(
    posting: JobBoardPosting,
    *,
    collected_on: date | None = None,
) -> JobPosting:
    from internship_search.posting_metadata import enrich_job_posting

    collected_date = (collected_on or date.today()).isoformat()
    enriched = enrich_job_posting(
        JobPosting(
            title=posting.title,
            company=posting.company,
            location=posting.location,
            posting_url=posting.posting_url,
            date_collected=collected_date,
            source_url=job_board_source_url(posting),
        ),
        snippet=posting.snippet,
        use_remote_apis=False,
    )
    return enriched


def infer_location_from_job_board_result(result: SearchResult) -> str:
    from internship_search.posting_metadata import infer_location_from_snippet

    return infer_location_from_snippet(result.snippet) or "Unknown"


def job_board_postings_to_job_postings(
    postings: list[JobBoardPosting],
    *,
    collected_on: date | None = None,
) -> list[JobPosting]:
    return [to_job_posting(posting, collected_on=collected_on) for posting in postings]


def build_default_job_board_query(*, target_year: str = DEFAULT_TARGET_YEAR) -> str:
    return f"summer {target_year} internship"


def is_job_board_search_result(result: SearchResult) -> bool:
    searchable = f"{result.title} {result.url} {result.snippet}".lower()
    domain = urlparse(result.url).netloc.lower()
    if any(board_domain in domain for board_domain in JOB_BOARD_DOMAINS):
        return True
    return any(
        keyword in searchable
        for keyword in ("intern", "internship", "summer analyst", "/jobs/", "/job/")
    )


def is_public_job_board_listing_url(url: str) -> bool:
    from internship_search.job_board_listings import is_public_aggregator_listing_url

    lowered = url.lower()
    if "linkedin.com" in lowered or "indeed.com" in lowered:
        return is_public_aggregator_listing_url(url)
    return True


def infer_company_from_job_board_result(result: SearchResult) -> str:
    from internship_search.posting_metadata import (
        infer_company_from_posting_url,
        parse_job_board_title,
    )

    title = result.title
    url = result.url.lower()

    if "linkedin.com" in url:
        if " at " in title:
            company = title.split(" at ", maxsplit=1)[1]
            return clean_title(company.split(" | ", maxsplit=1)[0])
        if " | " in title:
            return clean_title(title.split(" | ", maxsplit=1)[0])

    if "indeed.com" in url:
        if " - " in title:
            return clean_title(title.split(" - ", maxsplit=1)[0])
        if " at " in title:
            company = title.split(" at ", maxsplit=1)[1]
            return clean_title(company.split(" | ", maxsplit=1)[0])

    _, parsed_company = parse_job_board_title(title, result.url)
    if parsed_company:
        return parsed_company

    inferred = infer_company_from_posting_url(result.url)
    if inferred:
        return inferred

    if " at " in title:
        return clean_title(title.split(" at ", maxsplit=1)[1])
    if " | " in title:
        return clean_title(title.split(" | ", maxsplit=1)[0])
    domain = urlparse(result.url).netloc.lower().removeprefix("www.")
    slug = domain.split(".", maxsplit=1)[0]
    if slug in {"jobs", "boards", "careers"}:
        return "Unknown Company"
    return clean_title(slug.replace("-", " "))


def stable_posting_id(url: str, *, title: str, provider: str) -> str:
    canonical = canonical_posting_url(url)
    if canonical:
        return canonical
    normalized_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{provider}:{normalized_title}"


def job_board_source_url(posting: JobBoardPosting) -> str:
    return f"job-board://{posting.provider}?query={posting.query}"


def write_job_board_postings_jsonl(
    postings: list[JobBoardPosting],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    by_id: dict[str, JobBoardPosting] = {}
    for posting in postings:
        by_id.setdefault(posting.posting_id, posting)
    ordered = sorted(by_id.values(), key=lambda posting: (posting.company.lower(), posting.title.lower()))
    lines = [json.dumps(asdict(posting), sort_keys=True) for posting in ordered]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def read_job_board_postings_jsonl(path: Path | str) -> list[JobBoardPosting]:
    postings_path = Path(path)
    if not postings_path.exists():
        return []

    postings: list[JobBoardPosting] = []
    for line in postings_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            postings.append(JobBoardPosting(**json.loads(line)))
    return postings


def summarize_job_board_search(response: JobBoardSearchResponse) -> str:
    provider_counts = count_postings_by_provider(response.postings)
    lines = [
        "Job board search summary",
        "========================",
        f"Query: {response.query}",
        f"Provider: {response.provider}",
        f"Posting candidates: {len(response.postings)}",
    ]
    if provider_counts:
        lines.append(
            "Result sources: "
            + ", ".join(f"{name}={count}" for name, count in sorted(provider_counts.items()))
        )
    if response.output_path:
        lines.append(f"Wrote postings to: {response.output_path}")
    if response.postings:
        lines.append("")
        lines.append("Top posting candidates:")
        for posting in response.postings[:5]:
            lines.append(f"- {posting.company}: {posting.title} -> {posting.posting_url}")
    if response.platform_counts:
        lines.append("")
        lines.append("Platform counts:")
        lines.extend(f"- {platform}: {count}" for platform, count in response.platform_counts)
    if response.limitations:
        lines.append("")
        lines.append("Provider limitations:")
        lines.extend(f"- {limitation}" for limitation in response.limitations)
    if response.errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in response.errors)
    return "\n".join(lines)


def count_postings_by_provider(postings: list[JobBoardPosting]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for posting in postings:
        counts[posting.provider] = counts.get(posting.provider, 0) + 1
    return counts
