"""Source-specific career page collectors for difficult company sites."""

from __future__ import annotations

import html as html_module
import json
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urljoin, urlparse
from urllib.request import Request, urlopen

from internship_search.internship_listing import (
    is_specific_internship_listing,
    mentions_internship,
)
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
GetJson = Callable[[str], Any]

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
MCKINSEY_JOBS_API = (
    "https://gateway.mckinsey.com/apigw-x0cceuow60/v1/api/jobs/search"
)
PHENOM_REFNUM_RE = re.compile(r'"refNum"\s*:\s*"([^"]+)"')
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
EXHAUSTIVE_API_STRATEGIES = {
    "ashby_api",
    "breezy_html",
    "consider_board",
    "greenhouse_api",
    "lever_api",
    "mckinsey_jobs",
    "phenom_api",
    "teamtailor_html",
    "workday_api",
}
MAX_ATS_API_PAGES = 100

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
    complete: bool = False


def collect_postings_for_source(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> CollectorOutcome:
    """Run source-aware collectors and merge unique posting candidates."""

    strategies = resolve_collector_strategies(source)
    if (
        "phenompeople.com" in html
        and '"widgetApiEndpoint"' in html
        and "phenom_api" not in strategies
    ):
        strategies = ("phenom_api", *strategies)
    postings_by_url: dict[str, JobPosting] = {}
    strategies_tried: list[str] = []
    successful_strategies: set[str] = set()
    strategy_warnings: list[str] = []

    for strategy in strategies:
        strategies_tried.append(strategy)
        try:
            extracted = run_collector_strategy(
                strategy=strategy,
                source=source,
                html=html,
                collected_date=collected_date,
            )
        except Exception as error:  # noqa: BLE001 - fall back to other strategies.
            strategy_warnings.append(f"{strategy} failed: {error}")
            continue
        successful_strategies.add(strategy)
        for posting in extracted:
            existing = postings_by_url.get(posting.posting_url)
            if existing is None:
                postings_by_url[posting.posting_url] = posting
                continue
            from internship_search.posting_metadata import merge_posting_metadata

            postings_by_url[posting.posting_url] = merge_posting_metadata(
                existing,
                posting,
            )

    warning = "; ".join(strategy_warnings)
    if not postings_by_url:
        empty_warning = ""
        if "consider_board" in strategies_tried:
            empty_warning = consider_board_empty_warning(source)
        elif (
            "generic_links" in strategies_tried
            and not successful_strategies.intersection(EXHAUSTIVE_API_STRATEGIES)
        ):
            empty_warning = UNSUPPORTED_LAYOUT_WARNING
        warning = "; ".join(part for part in [warning, empty_warning] if part)

    return CollectorOutcome(
        postings=sorted(
            postings_by_url.values(),
            key=lambda posting: (posting.title.lower(), posting.posting_url),
        ),
        strategies_tried=tuple(strategies_tried),
        warning=warning,
        complete=bool(successful_strategies.intersection(EXHAUSTIVE_API_STRATEGIES)),
    )


def resolve_collector_strategies(source: CompanySource) -> tuple[str, ...]:
    if source.collector and source.collector != "auto":
        if source.collector == "blackrock_jobs":
            return ("blackrock_jobs", "json_ld", "embedded_json", "semantic_detail")
        if source.collector == "pwc_jobs":
            return ("pwc_jobs", "json_ld", "embedded_json", "semantic_detail")
        if source.collector == "ycombinator_jobs":
            return ("ycombinator_jobs",)
        return (source.collector,)

    normalized_name = normalize_company_name(source.company)
    careers_host = urlparse(source.careers_url).netloc.lower()

    if host_matches_domain(careers_host, "myworkdayjobs.com"):
        return ("workday_api", "embedded_json", "generic_links")
    if host_matches_domain(careers_host, "greenhouse.io"):
        return ("greenhouse_api", "json_ld", "embedded_json", "generic_links")
    if host_matches_domain(careers_host, "lever.co"):
        return ("lever_api", "embedded_json", "generic_links")
    if host_matches_domain(careers_host, "ashbyhq.com"):
        return ("ashby_api", "embedded_json", "generic_links")
    if host_matches_domain(careers_host, "breezy.hr"):
        return ("breezy_html", "json_ld", "embedded_json", "generic_links")
    if host_matches_domain(careers_host, "teamtailor.com"):
        return (
            "teamtailor_html",
            "json_ld",
            "embedded_json",
            "semantic_detail",
            "generic_links",
        )

    if normalized_name == "blackrock" or "careers.blackrock.com" in careers_host:
        return ("blackrock_jobs", "json_ld", "embedded_json", "semantic_detail")
    if normalized_name == "bakar bio labs" or "jobs.bakarlabs.org" in careers_host:
        return ("consider_board",)
    if normalized_name == "pwc" or "jobs-us.pwc.com" in careers_host:
        return ("pwc_jobs", "json_ld", "embedded_json", "semantic_detail", "generic_links")
    if normalized_name == "mckinsey & co" or "mckinsey.com" in careers_host:
        return ("mckinsey_jobs", "json_ld", "embedded_json", "semantic_detail", "generic_links")
    if source.source_type == "job_board":
        return ("embedded_json", "semantic_detail", "generic_links")
    return ("json_ld", "embedded_json", "semantic_detail", "generic_links")


def host_matches_domain(host: str, domain: str) -> bool:
    normalized = host.lower().split(":", 1)[0]
    return normalized == domain or normalized.endswith(f".{domain}")


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
    if strategy == "workday_api":
        return collect_workday_postings(source, collected_date)
    if strategy == "greenhouse_api":
        return collect_greenhouse_postings(source, collected_date)
    if strategy == "lever_api":
        return collect_lever_postings(source, collected_date)
    if strategy == "ashby_api":
        return collect_ashby_postings(source, collected_date)
    if strategy == "breezy_html":
        return collect_breezy_postings(source, html, collected_date)
    if strategy == "teamtailor_html":
        return collect_teamtailor_postings(source, html, collected_date)
    if strategy == "mckinsey_jobs":
        return collect_mckinsey_postings(source, collected_date)
    if strategy == "phenom_api":
        return collect_phenom_postings(source, html, collected_date)
    if strategy == "direct_job_url":
        return collect_direct_job_url_posting(source, collected_date)
    if strategy == "semantic_detail":
        return collect_semantic_detail_posting(source, html, collected_date)
    if strategy == "generic_links":
        from internship_search.job_collector import extract_postings_from_html

        return extract_postings_from_html(
            source=source,
            html=html,
            collected_date=collected_date,
        )
    return []


def collect_breezy_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Read Breezy's complete public openings page, including an empty board."""

    if not host_matches_domain(urlparse(source.careers_url).netloc, "breezy.hr"):
        raise ValueError("Breezy collector requires a breezy.hr careers URL.")
    return extract_postings_from_html(
        source=source,
        html=html,
        collected_date=collected_date,
    )


def collect_phenom_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
    *,
    post_json: PostJson | None = None,
) -> list[JobPosting]:
    """Page through every job exposed by a public Phenom careers widget."""

    refnum_match = PHENOM_REFNUM_RE.search(html)
    if not refnum_match:
        raise ValueError("Phenom refNum could not be determined from the careers page.")
    refnum = refnum_match.group(1)
    locale = _phenom_config_value(html, "locale", "en_us")
    country = _phenom_config_value(html, "country", "us")
    page_id = _phenom_config_value(html, "pageId", "page20")
    parsed = urlparse(source.careers_url)
    endpoint = f"{parsed.scheme}://{parsed.netloc}/widgets"
    query = parse_qs(parsed.query)
    keywords = next(iter(query.get("keywords", [])), "").strip()
    poster = post_json or post_public_json
    page_size = 100
    offset = 0
    postings: list[JobPosting] = []
    seen_ids: set[str] = set()
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        payload = poster(
            endpoint,
            {
                "lang": locale,
                "deviceType": "desktop",
                "country": country,
                "pageName": "search-results",
                "size": page_size,
                "from": offset,
                "jobs": True,
                "counts": True,
                "all_fields": ["category", "country", "state", "city", "type"],
                "clearAll": False,
                "jdsource": "facets",
                "isSliderEnable": False,
                "pageId": page_id,
                "siteType": "external",
                "keywords": keywords,
                "global": country == "global",
                "selected_fields": {},
                "sort": {"order": "desc", "field": "postedDate"},
                "locationData": {},
                "refNum": refnum,
                "ddoKey": "refineSearch",
            },
        )
        result = payload.get("refineSearch", {})
        data = result.get("data", {}) if isinstance(result, dict) else {}
        records = data.get("jobs", []) if isinstance(data, dict) else []
        if not isinstance(records, list):
            raise ValueError("Phenom jobs widget returned an unexpected response.")
        total = int(result.get("totalHits", 0) or 0) if isinstance(result, dict) else 0
        if not records:
            if total and offset < total:
                raise ValueError("Phenom jobs widget returned an incomplete empty page.")
            exhausted = True
            break

        for record in records:
            if not isinstance(record, dict):
                continue
            title = clean_title(str(record.get("title") or ""))
            stable_id = str(
                record.get("jobId")
                or record.get("reqId")
                or record.get("jobSeqNo")
                or ""
            ).strip()
            if not stable_id or stable_id in seen_ids:
                continue
            seen_ids.add(stable_id)
            posting_url = str(
                record.get("jobUrl")
                or record.get("url")
                or _phenom_job_url(source.careers_url, stable_id, title)
            ).strip()
            if not is_specific_internship_listing(title, posting_url):
                continue
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=_phenom_location(record),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=semantic_page_text(
                        str(record.get("descriptionTeaser") or "")
                    ),
                )
            )

        offset += len(records)
        if offset >= total or len(records) < page_size:
            exhausted = True
            break

    if not exhausted:
        raise RuntimeError(
            f"Phenom pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


def _phenom_config_value(html: str, key: str, default: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]+)"', html)
    return match.group(1) if match else default


def _phenom_job_url(careers_url: str, job_id: str, title: str) -> str:
    parsed = urlparse(careers_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    locale_prefix = path_parts[:2] if len(path_parts) >= 2 else ["global", "en"]
    slug = quote(re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"))
    path = "/" + "/".join([*locale_prefix, "job", quote(job_id), slug])
    return parsed._replace(path=path, query="", fragment="").geturl()


def _phenom_location(record: dict[str, Any]) -> str:
    raw_location = record.get("location")
    if isinstance(raw_location, list):
        values = [clean_title(str(item)) for item in raw_location if str(item).strip()]
        if values:
            return "; ".join(values)
    if isinstance(raw_location, dict):
        values = [
            clean_title(str(raw_location.get(key)))
            for key in ("city", "state", "country")
            if raw_location.get(key)
        ]
        if values:
            return ", ".join(values)
    if isinstance(raw_location, str) and raw_location.strip():
        return clean_title(raw_location)
    values = [
        clean_title(str(record.get(key)))
        for key in ("city", "state", "country")
        if record.get(key)
    ]
    return ", ".join(values) if values else "Unknown"


def collect_mckinsey_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Load every current internship match from McKinsey's public jobs API."""

    loader = get_json or get_public_json
    page_size = 100
    start = 1
    seen_ids: set[str] = set()
    postings: list[JobPosting] = []
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        endpoint = (
            f"{MCKINSEY_JOBS_API}?pageSize={page_size}&start={start}"
            "&lang=en&q=intern"
        )
        payload = loader(endpoint)
        if not isinstance(payload, dict) or not isinstance(payload.get("docs"), list):
            raise ValueError("McKinsey jobs API returned an unexpected response.")

        records = payload["docs"]
        if not records:
            exhausted = True
            break

        for record in records:
            if not isinstance(record, dict):
                continue
            job_id = str(record.get("jobID") or "").strip()
            friendly_url = str(record.get("friendlyURL") or "").strip()
            if not job_id or not friendly_url or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = clean_title(str(record.get("title") or ""))
            posting_url = (
                "https://www.mckinsey.com/careers/search-jobs/jobs/"
                f"{friendly_url}"
            )
            if not is_specific_internship_listing(title, posting_url):
                continue

            cities = record.get("cities")
            location = " | ".join(
                clean_title(str(city))
                for city in cities
                if clean_title(str(city))
            ) if isinstance(cities, list) else "Unknown"
            eligibility_text = semantic_page_text(
                " ".join(
                    str(record.get(key) or "")
                    for key in ("yourBackground", "whatYouWillDo", "title")
                )
            )
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=location or "Unknown",
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=eligibility_text,
                )
            )

        total = int(payload.get("numFound", 0) or 0)
        start += len(records)
        if (total and len(seen_ids) >= total) or len(records) < page_size:
            exhausted = True
            break

    if not exhausted:
        raise RuntimeError(
            f"McKinsey pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


def collect_teamtailor_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Read a complete public Teamtailor jobs page without requiring an API key."""

    normalized = html.lower()
    if "teamtailor" not in normalized or not (
        "job filters" in normalized
        or re.search(r"\b\d+\s+jobs?\b", strip_html(normalized))
        or "/jobs/" in normalized
    ):
        raise ValueError("Teamtailor public jobs page was not recognized.")
    from internship_search.job_collector import extract_postings_from_html

    return extract_postings_from_html(
        source=source,
        html=html,
        collected_date=collected_date,
    )


def collect_lever_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Load every currently open posting from Lever's public postings API."""

    path_parts = [part for part in urlparse(source.careers_url).path.split("/") if part]
    if not path_parts:
        raise ValueError("Lever board name could not be determined from the careers URL.")
    account = path_parts[0]
    loader = get_json or get_public_json
    postings: list[JobPosting] = []
    seen_ids: set[str] = set()
    skip = 0
    page_size = 100
    api_host = "api.eu.lever.co" if ".eu.lever.co" in urlparse(source.careers_url).netloc else "api.lever.co"
    exhausted = False
    for _ in range(MAX_ATS_API_PAGES):
        payload = loader(
            f"https://{api_host}/v0/postings/{account}"
            f"?mode=json&skip={skip}&limit={page_size}"
        )
        if not isinstance(payload, list):
            raise ValueError("Lever API returned an unexpected response.")
        if not payload:
            exhausted = True
            break
        new_records = 0
        for record in payload:
            if not isinstance(record, dict):
                continue
            record_id = str(
                record.get("id") or record.get("hostedUrl") or record.get("applyUrl") or ""
            )
            if not record_id or record_id in seen_ids:
                continue
            seen_ids.add(record_id)
            new_records += 1
            title = clean_title(str(record.get("text", "")))
            posting_url = str(record.get("hostedUrl") or record.get("applyUrl") or "").strip()
            if not posting_url or not is_specific_internship_listing(title, posting_url):
                continue
            categories = record.get("categories") if isinstance(record.get("categories"), dict) else {}
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=clean_title(str(categories.get("location") or "Unknown")),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=semantic_page_text(
                        " ".join(
                            [
                                str(record.get("descriptionPlain") or ""),
                                json.dumps(record.get("lists") or []),
                            ]
                        )
                    ),
                )
            )
        skip += len(payload)
        if not new_records or len(payload) < page_size:
            exhausted = True
            break
    if not exhausted:
        raise RuntimeError(
            f"Lever pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


def collect_greenhouse_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Load every currently open posting from Greenhouse's public board API."""

    board = greenhouse_board_token(source.careers_url)
    if not board:
        raise ValueError("Greenhouse board token could not be determined from the careers URL.")
    loader = get_json or get_public_json
    payload = loader(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Greenhouse API returned an unexpected response.")
    records = payload["jobs"]
    postings: list[JobPosting] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        title = clean_title(str(record.get("title", "")))
        posting_url = str(record.get("absolute_url") or "").strip()
        if not posting_url or not is_specific_internship_listing(title, posting_url):
            continue
        location = record.get("location") if isinstance(record.get("location"), dict) else {}
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=clean_title(str(location.get("name") or "Unknown")),
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
                eligibility_text=semantic_page_text(str(record.get("content") or "")),
            )
        )
    return postings


def greenhouse_board_token(careers_url: str) -> str:
    parsed = urlparse(careers_url)
    query = parse_qs(parsed.query)
    query_token = next(iter(query.get("for", [])), "").strip()
    if query_token:
        return query_token
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts or path_parts[0].lower() in {"embed", "jobs"}:
        return ""
    return path_parts[0]


def collect_ashby_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Load every currently open posting from Ashby's public job-board API."""

    path_parts = [part for part in urlparse(source.careers_url).path.split("/") if part]
    if not path_parts:
        raise ValueError("Ashby board name could not be determined from the careers URL.")
    board = path_parts[0]
    loader = get_json or get_public_json
    payload = loader(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Ashby API returned an unexpected response.")
    records = payload["jobs"]
    postings: list[JobPosting] = []
    for record in records:
        if not isinstance(record, dict) or record.get("isListed") is False:
            continue
        title = clean_title(str(record.get("title", "")))
        posting_url = str(record.get("jobUrl") or record.get("applyUrl") or "").strip()
        if not posting_url or not is_specific_internship_listing(title, posting_url):
            continue
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=clean_title(str(record.get("location") or "Unknown")),
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
                eligibility_text=semantic_page_text(
                    str(
                        record.get("descriptionPlain")
                        or record.get("descriptionHtml")
                        or record.get("description")
                        or ""
                    )
                ),
            )
        )
    return postings


def collect_workday_postings(
    source: CompanySource,
    collected_date: str,
    *,
    post_json: PostJson | None = None,
) -> list[JobPosting]:
    """Page through Workday's public CXS endpoint until every result is read."""

    parsed = urlparse(source.careers_url)
    host_parts = parsed.netloc.split(".")
    path_parts = [part for part in parsed.path.split("/") if part]
    if not host_parts or not path_parts:
        raise ValueError("Workday tenant and site could not be determined from the careers URL.")
    tenant = host_parts[0]
    site = next(
        (part for part in path_parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", part)),
        "",
    )
    if not site:
        raise ValueError("Workday site could not be determined from the careers URL.")

    poster = post_json or post_public_json
    endpoint = f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
    postings: list[JobPosting] = []
    seen_paths: set[str] = set()
    offset = 0
    page_size = 100

    exhausted = False
    for _ in range(MAX_ATS_API_PAGES):
        payload = poster(
            endpoint,
            {
                "appliedFacets": {},
                "limit": page_size,
                "offset": offset,
                "searchText": "",
            },
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobPostings"), list):
            raise ValueError("Workday API returned an unexpected response.")
        records = payload["jobPostings"]
        if not records:
            exhausted = True
            break
        new_records = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            external_path = str(record.get("externalPath") or "").strip()
            if not external_path or external_path in seen_paths:
                continue
            seen_paths.add(external_path)
            new_records += 1
            title = clean_title(str(record.get("title", "")))
            posting_url = urljoin(source.careers_url, external_path)
            if not is_specific_internship_listing(title, posting_url):
                continue
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=clean_title(str(record.get("locationsText") or "Unknown")),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                )
            )
        total = int(payload.get("total", 0) or 0)
        offset += len(records)
        if (
            not new_records
            or (total and offset >= total)
            or (not total and len(records) < page_size)
        ):
            exhausted = True
            break
    if not exhausted:
        raise RuntimeError(
            f"Workday pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


def get_public_json(url: str) -> Any:
    request = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "internship-search/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def post_public_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
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


def collect_semantic_detail_posting(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Extract a job represented by the current page using visible semantic labels."""

    if not html:
        return []
    title_candidates = [
        clean_title(html_module.unescape(strip_html(candidate)))
        for candidate in H1_RE.findall(html)
    ]
    title = next(
        (
            candidate
            for candidate in title_candidates
            if mentions_internship(candidate, "")
            and is_specific_internship_listing(candidate, source.careers_url)
        ),
        "",
    )
    if not title:
        return []

    page_text = semantic_page_text(html)
    normalized = page_text.lower()
    if any(
        marker in normalized
        for marker in (
            "applications are now closed",
            "application is now closed",
            "applications have closed",
            "position has been filled",
            "this job is no longer available",
        )
    ):
        return []

    evidence_markers = (
        "apply now",
        "date posted:",
        "employment type",
        "job id",
        "job requisition",
        "description & requirements",
    )
    if not any(marker in normalized for marker in evidence_markers):
        return []

    return [
        JobPosting(
            title=title,
            company=source.company,
            location=extract_semantic_detail_locations(page_text),
            posting_url=source.careers_url,
            date_collected=collected_date,
            source_url=source.careers_url,
            eligibility_text=page_text,
        )
    ]


def semantic_page_text(html: str) -> str:
    with_breaks = re.sub(
        r"</?(?:p|div|section|li|h[1-6]|br|dt|dd|article|main)[^>]*>",
        "\n",
        html,
        flags=re.IGNORECASE,
    )
    without_tags = strip_html(with_breaks)
    lines: list[str] = []
    for line in without_tags.splitlines():
        unescaped = html_module.unescape(line).strip()
        if unescaped:
            lines.append(clean_title(unescaped))
    return "\n".join(lines)


def extract_semantic_detail_locations(page_text: str) -> str:
    """Read all locations from common visible job-detail labels."""

    bain_match = re.search(
        r"Location\(s\)\s+(.*?)(?:\s+View requirements|\s+Apply now|"
        r"\s+Description & Requirements|\s+See all programs)",
        page_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if bain_match:
        return normalize_location_list(bain_match.group(1))

    blackrock_match = re.search(
        r"Location:\s*(.*?)\s*Additional Locations:\s*(.*?)"
        r"(?:\s*See More|\s*Team:)",
        page_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if blackrock_match:
        return normalize_location_list(
            f"{blackrock_match.group(1)} | {blackrock_match.group(2)}"
        )

    location_match = re.search(
        r"(?:Location|Locations):\s*(.*?)(?:\s+Employment type|\s+Team:|"
        r"\s+Job (?:ID|Requisition)|\s+Apply now|\s+Description)",
        page_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if location_match:
        return normalize_location_list(location_match.group(1))
    return "Unknown"


def normalize_location_list(value: str) -> str:
    cleaned = re.sub(r"\+\s*\d+\s+offices?", "|", value, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:Show less|See More)\b", "", cleaned, flags=re.IGNORECASE)
    pieces = re.split(r"\s*\|\s*|\s{2,}|\n+", cleaned)
    locations: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        location = clean_title(piece).strip(" ,;|")
        if not location:
            continue
        key = location.lower()
        if key in seen:
            continue
        seen.add(key)
        locations.append(location)
    return " | ".join(locations) if locations else "Unknown"


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
                    eligibility_text=semantic_page_text(
                        str(record.get("description") or "")
                    ),
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
                    eligibility_text=semantic_page_text(
                        str(
                            record.get("description")
                            or record.get("descriptionPlain")
                            or record.get("qualifications")
                            or record.get("requirements")
                            or ""
                        )
                    ),
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

    exhausted = False
    for _ in range(MAX_ATS_API_PAGES):
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
            exhausted = True
            break

        all_jobs.extend(flatten_consider_board_groups(groups))
        response_meta = response.get("meta") or {}
        sequence = str(response_meta.get("sequence", "")).strip()
        if not sequence or sequence in seen_sequences:
            exhausted = True
            break
        seen_sequences.add(sequence)
        meta = {
            "sequence": sequence,
            "size": min(int(response_meta.get("size", 60)) * 2, 200),
        }

    if not exhausted:
        raise RuntimeError(
            f"Consider-board pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )

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
    if not re.search(r"/(?:job|jobs|job-detail|jobdetails)/", posting_url, re.IGNORECASE):
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
    if isinstance(location, list):
        locations = [
            extract_json_ld_location({"jobLocation": item})
            for item in location
            if isinstance(item, (dict, str))
        ]
        return " | ".join(
            value for index, value in enumerate(locations)
            if value != "Unknown" and value not in locations[:index]
        ) or "Unknown"
    if isinstance(location, dict):
        name = location.get("name") or location.get("address", {}).get("addressLocality")
        if isinstance(name, str) and name.strip():
            return clean_title(name)
    if isinstance(location, str) and location.strip():
        return clean_title(location)
    return "Unknown"


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)
