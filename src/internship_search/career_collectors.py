"""Source-specific career page collectors for difficult company sites."""

from __future__ import annotations

import html as html_module
import json
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from internship_search.internship_listing import is_specific_internship_listing
from internship_search.job_collector import (
    JobPosting,
    LinkCandidate,
    clean_title,
    extract_postings_from_html,
    is_likely_job_link,
    normalize_link,
)
from internship_search.source_registry import CompanySource, normalize_company_name


FetchPage = Callable[[str], str]
PostJson = Callable[[str, dict[str, Any]], dict[str, Any]]

BLACKROCK_JOB_PATH_RE = re.compile(r"/job/[^\"'\s<>]+", re.IGNORECASE)
BLACKROCK_SEARCH_RESULT_RE = re.compile(
    r'<a class="section3__search-results-a" href="([^"]+)"[^>]*>\s*'
    r'<h2 class="section3__job-title">(.*?)</h2>.*?'
    r'<span class="section3__job-info">([^<]*)</span>',
    re.IGNORECASE | re.DOTALL,
)
PWC_JOB_PATH_RE = re.compile(r"/job/[^\"'\s<>]+", re.IGNORECASE)
CONSIDER_BOARD_ID_RE = re.compile(
    r"serverInitialData\s*=\s*(\{.*?\})\s*;",
    re.DOTALL,
)
CONSIDER_BOARD_HOSTS = {"jobs.bakarlabs.org"}
CONSIDER_BOARD_DEFAULTS = {
    "jobs.bakarlabs.org": {"id": "bakar-bio-labs", "isParent": True},
}
UNSUPPORTED_LAYOUT_WARNING = (
    "No posting candidates extracted; page may be JavaScript-rendered "
    "or use an unsupported layout."
)

_CONSIDER_BOARD_CACHE: dict[str, list[dict[str, Any]]] = {}
JSON_LD_SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
SERVER_INITIAL_DATA_RE = re.compile(
    r"serverInitialData\s*=\s*(\{.*?\})\s*;",
    re.DOTALL,
)
Y_COMBINATOR_JOB_RECORD_RE = re.compile(
    r'\{[^{}]*"title":"(?P<title>[^"]+)"[^{}]*"url":"(?P<url>[^"]+)"'
    r'[^{}]*"location":"(?P<location>[^"]*)"',
    re.DOTALL,
)

JOB_RECORD_KEYS = {
    "jobs",
    "jobListings",
    "job_listings",
    "openings",
    "postings",
    "results",
    "items",
    "data",
}
JOB_TITLE_KEYS = ("title", "jobTitle", "job_title", "name", "positionTitle")
JOB_URL_KEYS = ("url", "jobUrl", "job_url", "link", "applyUrl", "apply_url", "externalUrl")
JOB_LOCATION_KEYS = ("location", "jobLocation", "job_location", "city")


@dataclass(frozen=True)
class CollectorOutcome:
    postings: list[JobPosting]
    strategies_tried: tuple[str, ...]
    warning: str = ""


def collect_postings_for_source(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> CollectorOutcome:
    """Run source-aware collectors and merge unique posting candidates."""

    strategies = resolve_collector_strategies(source)
    postings_by_url: dict[str, JobPosting] = {}
    strategies_tried: list[str] = []

    for strategy in strategies:
        strategies_tried.append(strategy)
        extracted = run_collector_strategy(
            strategy=strategy,
            source=source,
            html=html,
            collected_date=collected_date,
        )
        for posting in extracted:
            postings_by_url.setdefault(posting.posting_url, posting)

    warning = ""
    if not postings_by_url:
        if "consider_board" in strategies_tried:
            warning = consider_board_empty_warning(source)
        elif "generic_links" in strategies_tried:
            warning = UNSUPPORTED_LAYOUT_WARNING

    return CollectorOutcome(
        postings=sorted(
            postings_by_url.values(),
            key=lambda posting: (posting.title.lower(), posting.posting_url),
        ),
        strategies_tried=tuple(strategies_tried),
        warning=warning,
    )


def resolve_collector_strategies(source: CompanySource) -> tuple[str, ...]:
    if source.collector and source.collector != "auto":
        if source.collector == "blackrock_jobs":
            return ("blackrock_jobs", "json_ld", "embedded_json")
        if source.collector == "pwc_jobs":
            return ("pwc_jobs", "json_ld", "embedded_json")
        if source.collector == "ycombinator_jobs":
            return ("ycombinator_jobs",)
        return (source.collector,)

    normalized_name = normalize_company_name(source.company)
    careers_host = urlparse(source.careers_url).netloc.lower()

    if normalized_name == "blackrock" or "careers.blackrock.com" in careers_host:
        return ("blackrock_jobs", "json_ld", "embedded_json")
    if normalized_name == "bakar bio labs" or "jobs.bakarlabs.org" in careers_host:
        return ("consider_board",)
    if normalized_name == "pwc" or "jobs-us.pwc.com" in careers_host:
        return ("pwc_jobs", "json_ld", "embedded_json", "generic_links")
    if normalized_name == "mckinsey & co" or "mckinsey.com" in careers_host:
        return ("json_ld", "embedded_json", "generic_links")
    if source.source_type == "job_board":
        return ("embedded_json", "generic_links")
    return ("json_ld", "embedded_json", "generic_links")


def run_collector_strategy(
    *,
    strategy: str,
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    if strategy == "blackrock_jobs":
        return collect_blackrock_postings(source, html, collected_date)
    if strategy == "pwc_jobs":
        return collect_pwc_postings(source, html, collected_date)
    if strategy == "json_ld":
        return collect_json_ld_postings(source, html, collected_date)
    if strategy == "embedded_json":
        return collect_embedded_json_postings(source, html, collected_date)
    if strategy == "consider_board":
        return collect_consider_board_postings(source, html, collected_date)
    if strategy == "ycombinator_jobs":
        return collect_ycombinator_postings(source, html, collected_date)
    if strategy == "direct_job_url":
        return collect_direct_job_url_posting(source, collected_date)
    if strategy == "generic_links":
        from internship_search.job_collector import extract_postings_from_html

        return extract_postings_from_html(
            source=source,
            html=html,
            collected_date=collected_date,
        )
    return []


def collect_ycombinator_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Extract posting records from Y Combinator's HTML-escaped job payload."""

    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for match in Y_COMBINATOR_JOB_RECORD_RE.finditer(html_module.unescape(html)):
        posting_url = normalize_link(source.careers_url, match.group("url"))
        title = clean_title(match.group("title"))
        if (
            not posting_url
            or posting_url in seen_urls
            or not is_specific_internship_listing(title, posting_url)
        ):
            continue
        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=clean_title(match.group("location")) or "Unknown",
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )
    return postings


def collect_blackrock_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    postings: list[JobPosting] = []
    seen_urls: set[str] = set()

    for href, title_html, location in BLACKROCK_SEARCH_RESULT_RE.findall(html):
        posting_url = normalize_link(source.careers_url, href)
        if not posting_url or posting_url in seen_urls:
            continue
        if "/blog" in posting_url.lower():
            continue

        title = clean_title(strip_html(title_html))
        if not is_specific_internship_listing(title, posting_url):
            continue

        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=clean_title(location) or location_from_blackrock_job_url(posting_url),
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )

    for href in sorted(set(BLACKROCK_JOB_PATH_RE.findall(html))):
        posting_url = normalize_link(source.careers_url, href)
        if not posting_url or posting_url in seen_urls:
            continue
        if "/blog" in posting_url.lower():
            continue

        title = title_from_blackrock_job_url(posting_url)
        if not is_specific_internship_listing(title, posting_url):
            continue

        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=location_from_blackrock_job_url(posting_url),
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )

    for href in sorted(
        set(re.findall(r"https://careers\.blackrock\.com/job/[^\"'\s<>]+", html, re.IGNORECASE))
    ):
        posting_url = href.strip()
        if posting_url in seen_urls or "/blog" in posting_url.lower():
            continue
        title = title_from_blackrock_job_url(posting_url)
        if not is_specific_internship_listing(title, posting_url):
            continue
        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=location_from_blackrock_job_url(posting_url),
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )

    return postings


def collect_pwc_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    postings: list[JobPosting] = []
    seen_urls: set[str] = set()

    for href in sorted(set(PWC_JOB_PATH_RE.findall(html))):
        posting_url = normalize_link(source.careers_url, href)
        if not posting_url or posting_url in seen_urls:
            continue

        title = title_from_pwc_job_path(href)
        location = location_from_pwc_job_path(href)
        if not is_specific_internship_listing(title, posting_url):
            continue

        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=location,
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )

    return postings


def collect_json_ld_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    postings: list[JobPosting] = []
    seen_urls: set[str] = set()

    for match in JSON_LD_SCRIPT_RE.finditer(html):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        for record in iter_json_ld_job_records(payload):
            title = clean_title(str(record.get("title", "")))
            posting_url = normalize_job_url(
                str(record.get("url") or record.get("sameAs") or ""),
                base_url=source.careers_url,
            )
            if not title or not posting_url or posting_url in seen_urls:
                continue
            if not is_specific_internship_listing(title, posting_url):
                continue

            seen_urls.add(posting_url)
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=extract_json_ld_location(record),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                )
            )

    return postings


def collect_embedded_json_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    payloads: list[Any] = []

    for match in SERVER_INITIAL_DATA_RE.finditer(html):
        try:
            payloads.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue

    for match in re.finditer(
        r"<script[^>]*id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>",
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            payloads.append(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue

    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for payload in payloads:
        for record in walk_job_records(payload):
            title = clean_title(str(record.get("title", "")))
            posting_url = normalize_job_url(
                str(
                    record.get("url")
                    or record.get("jobUrl")
                    or record.get("link")
                    or ""
                ),
                base_url=source.careers_url,
            )
            if not title or not posting_url or posting_url in seen_urls:
                continue
            if not is_specific_internship_listing(title, posting_url):
                continue

            seen_urls.add(posting_url)
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=clean_title(
                        str(
                            record.get("location")
                            or record.get("city")
                            or "Unknown"
                        )
                    ),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                )
            )

    return postings


def collect_consider_board_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    board_jobs = load_consider_board_jobs(source.careers_url, html)
    postings: list[JobPosting] = []
    seen_urls: set[str] = set()

    for job in board_jobs:
        if not consider_job_matches_source(source, job):
            continue

        title = clean_title(str(job.get("title", "")))
        posting_url = normalize_job_url(
            str(job.get("url") or job.get("applyUrl") or ""),
            base_url=source.careers_url,
        )
        if not title or not posting_url or posting_url in seen_urls:
            continue
        if not is_specific_internship_listing(title, posting_url):
            continue

        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=location_from_consider_job(job),
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )

    if postings:
        return postings

    for link in extract_consider_board_links(html):
        posting_url = normalize_link(source.careers_url, link.href)
        if not posting_url:
            continue
        title = clean_title(link.text)
        if not is_specific_internship_listing(title, posting_url):
            continue
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


def clear_consider_board_cache() -> None:
    _CONSIDER_BOARD_CACHE.clear()


def load_consider_board_jobs(
    careers_url: str,
    html: str,
    *,
    post_json: PostJson | None = None,
) -> list[dict[str, Any]]:
    host = urlparse(careers_url).netloc.lower()
    if host not in CONSIDER_BOARD_HOSTS:
        return []

    cache_key = host
    if cache_key in _CONSIDER_BOARD_CACHE:
        return _CONSIDER_BOARD_CACHE[cache_key]

    board = parse_consider_board_config(html, host)
    if board is None:
        _CONSIDER_BOARD_CACHE[cache_key] = []
        return []

    api_base = f"https://{host}"
    jobs = fetch_consider_board_jobs(board=board, api_base=api_base, post_json=post_json)
    _CONSIDER_BOARD_CACHE[cache_key] = jobs
    return jobs


def parse_consider_board_config(html: str, host: str) -> dict[str, Any] | None:
    match = CONSIDER_BOARD_ID_RE.search(html)
    if match:
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            payload = {}
        else:
            board = payload.get("board")
            fixed_board = payload.get("fixedBoard")
            if isinstance(board, dict) and board.get("id"):
                return board
            if isinstance(fixed_board, str) and fixed_board.strip():
                return {"id": fixed_board.strip(), "isParent": True}

    return CONSIDER_BOARD_DEFAULTS.get(host)


def fetch_consider_board_jobs(
    *,
    board: dict[str, Any],
    api_base: str,
    post_json: PostJson | None = None,
) -> list[dict[str, Any]]:
    poster = post_json or post_consider_board_json
    all_jobs: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"size": 60}
    seen_sequences: set[str] = set()

    for _ in range(6):
        response = poster(
            f"{api_base}/api-boards/search-jobs",
            {
                "meta": meta,
                "board": board,
                "query": {},
                "grouped": True,
            },
        )
        groups = response.get("jobs", [])
        if not isinstance(groups, list):
            break

        all_jobs.extend(flatten_consider_board_groups(groups))
        response_meta = response.get("meta") or {}
        sequence = str(response_meta.get("sequence", "")).strip()
        if not sequence or sequence in seen_sequences:
            break
        seen_sequences.add(sequence)
        meta = {
            "sequence": sequence,
            "size": min(int(response_meta.get("size", 60)) * 2, 200),
        }

    return all_jobs


def post_consider_board_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "internship-search/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def flatten_consider_board_groups(groups: list[Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        company = group.get("company") if isinstance(group.get("company"), dict) else {}
        company_name = str(company.get("name", ""))
        jobs = group.get("jobs", [])
        if not isinstance(jobs, list):
            continue
        for job in jobs:
            if isinstance(job, dict):
                flattened.append({**job, "companyName": job.get("companyName") or company_name})
    return flattened


def consider_job_matches_source(source: CompanySource, job: dict[str, Any]) -> bool:
    if normalize_company_name(source.company) == "bakar bio labs":
        return True
    job_company = str(job.get("companyName") or job.get("companyId") or "")
    return company_names_match(source.company, job_company)


def company_names_match(left: str, right: str) -> bool:
    return normalize_company_name(left) == normalize_company_name(right)


def consider_board_empty_warning(source: CompanySource) -> str:
    host = urlparse(source.careers_url).netloc.lower()
    board_jobs = _CONSIDER_BOARD_CACHE.get(host, [])
    if not board_jobs:
        return (
            "Consider job board API returned no jobs; the board may be empty or temporarily unavailable."
        )

    company_jobs = [
        job for job in board_jobs if consider_job_matches_source(source, job)
    ]
    if not company_jobs:
        return (
            f"No jobs found on the Consider board for {source.company}; "
            "the company may not currently have postings there."
        )
    return (
        f"No internship postings matched for {source.company}; "
        f"the Consider board has {len(company_jobs)} active job(s) for this company."
    )


def location_from_consider_job(job: dict[str, Any]) -> str:
    locations = job.get("locations")
    if isinstance(locations, list) and locations:
        first = locations[0]
        if isinstance(first, str) and first.strip():
            return clean_title(first)
    normalized = job.get("normalizedLocations")
    if isinstance(normalized, list) and normalized:
        first = normalized[0]
        if isinstance(first, dict):
            label = first.get("label") or first.get("value")
            if isinstance(label, str) and label.strip():
                return clean_title(label)
    return "Unknown"


def collect_direct_job_url_posting(
    source: CompanySource,
    collected_date: str,
) -> list[JobPosting]:
    posting_url = source.careers_url
    if "/job/" not in posting_url.lower():
        return []

    title = title_from_blackrock_job_url(posting_url)
    if not is_specific_internship_listing(title, posting_url):
        title = clean_title(title or "Internship posting")

    return [
        JobPosting(
            title=title,
            company=source.company,
            location=location_from_blackrock_job_url(posting_url),
            posting_url=posting_url,
            date_collected=collected_date,
            source_url=source.careers_url,
        )
    ]


def extract_consider_board_links(html: str) -> list[LinkCandidate]:
    links: list[LinkCandidate] = []
    for href, text in re.findall(
        r'href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        candidate = LinkCandidate(text=clean_title(strip_html(text)), href=href)
        if is_likely_job_link(candidate):
            links.append(candidate)
    return links


def iter_json_ld_job_records(payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return

        node_type = node.get("@type", "")
        types = node_type if isinstance(node_type, list) else [node_type]
        if any(str(item).lower() == "jobposting" for item in types):
            records.append(node)

        graph = node.get("@graph")
        if graph is not None:
            visit(graph)

    visit(payload)
    return records


def walk_job_records(payload: Any) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[int] = set()

    def visit(node: Any) -> None:
        node_id = id(node)
        if node_id in seen:
            return
        if isinstance(node, (dict, list)):
            seen.add(node_id)

        if isinstance(node, list):
            for item in node:
                visit(item)
            return

        if not isinstance(node, dict):
            return

        title = first_string(node, JOB_TITLE_KEYS)
        url = first_string(node, JOB_URL_KEYS)
        if title and url and looks_like_job_record(node):
            matches.append(
                {
                    "title": title,
                    "url": url,
                    "location": first_string(node, JOB_LOCATION_KEYS) or "Unknown",
                }
            )

        for value in node.values():
            if isinstance(value, (dict, list)):
                visit(value)

        for key in JOB_RECORD_KEYS:
            child = node.get(key)
            if isinstance(child, list):
                for item in child:
                    if isinstance(item, dict):
                        visit(item)

    visit(payload)
    return matches


def looks_like_job_record(record: dict[str, Any]) -> bool:
    searchable = " ".join(
        str(record.get(key, "")) for key in ("title", "jobTitle", "name", "url", "jobUrl")
    ).lower()
    return any(
        keyword in searchable
        for keyword in ("intern", "internship", "student", "graduate", "summer", "/job/")
    )


def first_string(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("name") or value.get("title")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return ""


def title_from_blackrock_job_url(url: str) -> str:
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) >= 3 and path_parts[0] == "job":
        slug = path_parts[2]
        return clean_title(slug.replace("-", " ").title())
    return clean_title(path_parts[-1].replace("-", " ")) if path_parts else "Untitled posting"


def location_from_blackrock_job_url(url: str) -> str:
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    if len(path_parts) >= 3 and path_parts[0] == "job":
        return clean_title(path_parts[1].replace("-", " ").title())
    return "Unknown"


def title_from_pwc_job_path(path: str) -> str:
    slug = path.split("/")[-1].split("?")[0]
    slug = slug.replace("---", " - ").replace("_", " ")
    return clean_title(slug)


def location_from_pwc_job_path(path: str) -> str:
    parts = [part for part in path.split("/") if part and part != "job"]
    if not parts:
        return "Unknown"
    region_city = parts[0]
    if "-" in region_city:
        _, city = region_city.split("-", 1)
        return clean_title(city.replace("-", " "))
    return clean_title(region_city.replace("-", " "))


def normalize_job_url(url: str, *, base_url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""
    return normalize_link(base_url, cleaned)


def extract_json_ld_location(record: dict[str, Any]) -> str:
    location = record.get("jobLocation")
    if isinstance(location, dict):
        name = location.get("name") or location.get("address", {}).get("addressLocality")
        if isinstance(name, str) and name.strip():
            return clean_title(name)
    if isinstance(location, str) and location.strip():
        return clean_title(location)
    return "Unknown"


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)
