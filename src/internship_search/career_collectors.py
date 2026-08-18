"""Source-specific career page collectors for difficult company sites."""

from __future__ import annotations

import base64
import gzip
import html as html_module
import json
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse
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
GetJsonWithHeaders = Callable[[str, dict[str, str]], Any]

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
IBM_CAREERS_API = "https://www-api.ibm.com/search/api/v2"
IBM_INTERNSHIP_FIELD = "field_keyword_18"
IBM_INTERNSHIP_FACETS = ("Internship", "Intern")
ELBIT_JOBS_PATHS = (
    "/cron/jobs.json",
    "/api/jobs",
    "/api/v1/jobs",
    "/api/jobs/search",
)
WIX_SITEMAP_PATH = "/sitemap.xml"
WIX_TITLE_SUFFIXES = (" | Wix Careers", " | Wix")
OG_TITLE_RE = re.compile(
    r'property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']|'
    r'content=["\']([^"\']+)["\'][^>]*property=["\']og:title["\']',
    re.IGNORECASE,
)
ELBIT_STUDENT_CATEGORIES = {
    "6",
    "students",
    "student",
    "סטודנטים",
    "סטודנט",
}
PHENOM_REFNUM_RE = re.compile(r'"refNum"\s*:\s*"([^"]+)"')
NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
DISNEY_RESULT_ROW_RE = re.compile(
    r"<tr[^>]*>(?P<row>.*?)</tr>",
    re.IGNORECASE | re.DOTALL,
)
DISNEY_JOB_RE = re.compile(
    r'<a[^>]+href=["\'](?P<url>/job/[^"\']+)["\'][^>]*>.*?'
    r"<h2[^>]*>(?P<title>.*?)</h2>",
    re.IGNORECASE | re.DOTALL,
)
DISNEY_BRAND_RE = re.compile(
    r'<span[^>]+class=["\'][^"\']*\bjob-brand\b[^"\']*["\'][^>]*>'
    r"(?P<brand>.*?)</span>",
    re.IGNORECASE | re.DOTALL,
)
DISNEY_LOCATION_RE = re.compile(
    r'<span[^>]+class=["\'][^"\']*\bjob-location\b[^"\']*["\'][^>]*>'
    r"(?P<location>.*?)</span>",
    re.IGNORECASE | re.DOTALL,
)
DISNEY_TOTAL_PAGES_RE = re.compile(
    r'class=["\'][^"\']*\bpagination-total-pages\b[^"\']*["\'][^>]*>'
    r"\s*of\s*(?P<total>\d+)",
    re.IGNORECASE | re.DOTALL,
)
PAYCOR_JOB_RE = re.compile(
    r'<a[^>]+href=["\'](?P<url>https://recruitingbypaycor\.com/'
    r'career/JobIntroduction\.action\?[^"\']+)["\'][^>]+'
    r'ns-qa=["\'](?P<title>[^"\']+)["\'][^>]*>.*?</a>\s*</div>\s*'
    r'<div[^>]+class=["\']gnewtonCareerGroupJobDescriptionClass["\'][^>]*>'
    r'(?P<location>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
BAYER_RESULT_ROW_RE = re.compile(
    r'<tr[^>]+class=["\'][^"\']*\bdata-row\b[^"\']*["\'][^>]*>'
    r'(?P<row>.*?)</tr>',
    re.IGNORECASE | re.DOTALL,
)
BAYER_JOB_RE = re.compile(
    r'<a[^>]+href=["\'](?P<url>/job/[^"\']+)["\'][^>]*'
    r'class=["\'][^"\']*\bjobTitle-link\b[^"\']*["\'][^>]*>'
    r'(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
SUCCESSFACTORS_JOB_RE = re.compile(
    r'<a(?=[^>]+class=["\'][^"\']*\bjobTitle-link\b[^"\']*["\'])'
    r'(?=[^>]+href=["\'](?P<url>/job/[^"\']+)["\'])[^>]*>'
    r'(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
BAYER_LOCATION_RE = re.compile(
    r'<td[^>]+class=["\'][^"\']*\bcolLocation\b[^"\']*["\'][^>]*>'
    r'(?P<location>.*?)</td>',
    re.IGNORECASE | re.DOTALL,
)
BAYER_TOTAL_RE = re.compile(
    r'class=["\']paginationLabel["\'][^>]*>.*?\bof\s*<b>(?P<total>[\d,]+)</b>',
    re.IGNORECASE | re.DOTALL,
)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
EXHAUSTIVE_API_STRATEGIES = {
    "avature_rss",
    "ashby_api",
    "bank_of_america_jobs",
    "bayer_successfactors",
    "successfactors_html",
    "breezy_html",
    "consider_board",
    "adp_workforce_now",
    "eightfold_pcsx",
    "general_dynamics_jobs",
    "notion_public_page",
    "parked_company_domain",
    "profusa_careers",
    "greenhouse_api",
    "jibe_jobs",
    "elbit_jobs",
    "wix_positions",
    "goldman_higher",
    "ibm_careers",
    "lemonade_jobs",
    "lever_api",
    "mckinsey_jobs",
    "oracle_recruiting_api",
    "paycor_html",
    "phenom_api",
    "pixar_jobs",
    "teamtailor_html",
    "workday_api",
    "cyberark_parent_workday",
    "closed_company",
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
    if host_matches_domain(careers_host, "recruitingbypaycor.com"):
        return ("paycor_html",)

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
    if strategy == "cyberark_parent_workday":
        return collect_cyberark_parent_workday_postings(source, collected_date)
    if strategy == "adp_workforce_now":
        return collect_adp_workforce_now_postings(source, collected_date)
    if strategy == "eightfold_pcsx":
        return collect_eightfold_postings(source, collected_date)
    if strategy == "general_dynamics_jobs":
        return collect_general_dynamics_postings(source, collected_date)
    if strategy == "notion_public_page":
        return collect_notion_public_page_postings(source, collected_date)
    if strategy == "parked_company_domain":
        return collect_parked_company_domain_postings(source, html)
    if strategy == "profusa_careers":
        return collect_profusa_postings(source, html, collected_date)
    if strategy == "avature_rss":
        return collect_avature_rss_postings(source, html, collected_date)
    if strategy == "oracle_recruiting_api":
        return collect_oracle_recruiting_postings(source, html, collected_date)
    if strategy == "goldman_higher":
        return collect_goldman_higher_postings(source, collected_date)
    if strategy == "ibm_careers":
        return collect_ibm_careers_postings(source, collected_date)
    if strategy == "elbit_jobs":
        return collect_elbit_postings(source, collected_date)
    if strategy == "wix_positions":
        return collect_wix_postings(source, collected_date)
    if strategy == "lemonade_jobs":
        return collect_lemonade_postings(source, html, collected_date)
    if strategy == "pixar_jobs":
        return collect_pixar_postings(source, html, collected_date)
    if strategy == "closed_company":
        return collect_closed_company_postings(source, html)
    if strategy == "bank_of_america_jobs":
        return collect_bank_of_america_postings(source, collected_date)
    if strategy == "bayer_successfactors":
        return collect_bayer_postings(source, html, collected_date)
    if strategy == "successfactors_html":
        return collect_successfactors_postings(source, html, collected_date)
    if strategy == "greenhouse_api":
        return collect_greenhouse_postings(source, collected_date)
    if strategy == "jibe_jobs":
        return collect_jibe_postings(source, collected_date)
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
    if strategy == "paycor_html":
        return collect_paycor_postings(source, html, collected_date)
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


def collect_paycor_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Read every current posting from a public Paycor CareerHome page."""

    if not host_matches_domain(
        urlparse(source.careers_url).netloc,
        "recruitingbypaycor.com",
    ):
        raise ValueError("Paycor collector requires a recruitingbypaycor.com URL.")
    if not parse_qs(urlparse(source.careers_url).query).get("clientId"):
        raise ValueError("Paycor collector requires a clientId query parameter.")

    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for match in PAYCOR_JOB_RE.finditer(html):
        title = clean_title(html_module.unescape(match.group("title")))
        posting_url = html_module.unescape(match.group("url"))
        if posting_url in seen_urls:
            continue
        seen_urls.add(posting_url)
        if not is_specific_internship_listing(title, posting_url):
            continue
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=semantic_page_text(match.group("location")) or "Unknown",
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
            )
        )
    return postings


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
        location = greenhouse_posting_location(record)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=location,
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
                eligibility_text=semantic_page_text(str(record.get("content") or "")),
            )
        )
    return postings


def greenhouse_posting_location(record: dict[str, Any]) -> str:
    """Prefer a board's explicit posting locations over generic office labels."""

    metadata = record.get("metadata")
    if isinstance(metadata, list):
        for item in metadata:
            if not isinstance(item, dict):
                continue
            if str(item.get("name") or "").strip().lower() != "job posting location":
                continue
            value = item.get("value")
            values = value if isinstance(value, list) else [value]
            cleaned = [clean_title(str(part)) for part in values if str(part or "").strip()]
            if cleaned:
                return ", ".join(dict.fromkeys(cleaned))

    offices = record.get("offices")
    if isinstance(offices, list):
        cleaned = [
            clean_title(str(office.get("location") or office.get("name") or ""))
            for office in offices
            if isinstance(office, dict)
        ]
        cleaned = [value for value in cleaned if value]
        if cleaned:
            return ", ".join(dict.fromkeys(cleaned))

    location = record.get("location") if isinstance(record.get("location"), dict) else {}
    return clean_title(str(location.get("name") or "Unknown"))


def collect_jibe_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Page through a Jibe jobs API and retain company-labelled internships."""

    parsed = urlparse(source.careers_url)
    query = parse_qs(parsed.query)
    keyword = next(iter(query.get("keywords") or query.get("keyword") or [""]), "")
    if not keyword:
        raise ValueError("Jibe source URL must include a company keyword.")

    api_url = f"{parsed.scheme}://{parsed.netloc}/api/jobs"
    loader = get_json or get_public_json
    page = 1
    page_size = 100
    seen_ids: set[str] = set()
    postings: list[JobPosting] = []
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        payload = loader(
            f"{api_url}?{urlencode({'keywords': keyword, 'limit': page_size, 'page': page})}"
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
            raise ValueError("Jibe jobs API returned an unexpected response.")
        records = payload["jobs"]
        for wrapper in records:
            record = wrapper.get("data") if isinstance(wrapper, dict) else None
            if not isinstance(record, dict):
                continue
            job_id = str(record.get("req_id") or record.get("slug") or "").strip()
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            title = clean_title(str(record.get("title") or ""))
            details = semantic_page_text(
                " ".join(
                    str(record.get(key) or "")
                    for key in ("description", "qualifications", "responsibilities")
                )
            )
            hiring_organization = str(record.get("hiring_organization") or "")
            if keyword.lower() not in f"{title} {hiring_organization}".lower():
                continue
            apply_url = str(record.get("apply_url") or "").strip()
            posting_url = (
                apply_url
                if apply_url.startswith(("http://", "https://"))
                else f"{parsed.scheme}://{parsed.netloc}/main/jobs/{quote(job_id)}"
            )
            if not is_specific_internship_listing(title, posting_url):
                continue
            location = clean_title(
                str(
                    record.get("full_location")
                    or record.get("location_name")
                    or record.get("short_location")
                    or "Unknown"
                )
            )
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=location,
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=details,
                )
            )

        total = int(payload.get("totalCount", 0) or 0)
        if (
            not records
            or (total and page * page_size >= total)
            or (not total and len(records) < page_size)
        ):
            exhausted = True
            break
        page += 1

    if not exhausted:
        raise RuntimeError(f"Jibe pagination exceeded {MAX_ATS_API_PAGES} API pages.")
    return postings


def collect_adp_workforce_now_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Page through an ADP Workforce Now public career center."""

    parsed = urlparse(source.careers_url)
    query = parse_qs(parsed.query)
    cid = next(iter(query.get("cid", [])), "").strip()
    cc_id = next(iter(query.get("ccId", [])), "").strip()
    lang = next(iter(query.get("lang", ["en_US"])), "en_US").strip() or "en_US"
    if not cid or not cc_id:
        raise ValueError("ADP career-center cid and ccId could not be determined.")

    loader = get_json or get_public_json
    endpoint = (
        f"{parsed.scheme}://{parsed.netloc}/mascsr/default/careercenter/public/"
        "events/staffing/v1/job-requisitions"
    )
    page_size = 100
    skip = 0
    postings: list[JobPosting] = []
    seen_ids: set[str] = set()
    exhausted = False
    for _ in range(MAX_ATS_API_PAGES):
        params = {
            "cid": cid,
            "ccId": cc_id,
            "lang": lang,
            "locale": lang,
            "$top": page_size,
            "$skip": skip,
        }
        payload = loader(f"{endpoint}?{urlencode(params)}")
        if not isinstance(payload, dict) or not isinstance(
            payload.get("jobRequisitions"), list
        ):
            raise ValueError("ADP Workforce Now API returned an unexpected response.")
        records = payload["jobRequisitions"]
        if not records:
            exhausted = True
            break
        new_records = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            item_id = str(record.get("itemID") or "").strip()
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            new_records += 1
            title = clean_title(str(record.get("requisitionTitle") or ""))
            external_id = adp_external_job_id(record)
            if not external_id:
                continue
            posting_url = (
                f"{source.careers_url.split('&jobId=', 1)[0]}&jobId={quote(external_id)}"
            )
            if not is_specific_internship_listing(title, posting_url):
                continue
            locations = record.get("requisitionLocations")
            location_names = []
            if isinstance(locations, list):
                for location in locations:
                    if not isinstance(location, dict):
                        continue
                    name_code = location.get("nameCode")
                    if isinstance(name_code, dict):
                        name = clean_title(str(name_code.get("shortName") or ""))
                        if name:
                            location_names.append(name)
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location="; ".join(dict.fromkeys(location_names)) or "Unknown",
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                )
            )
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        total = int(meta.get("totalNumber", 0) or 0)
        skip += len(records)
        if not new_records or (total and skip >= total) or len(records) < page_size:
            exhausted = True
            break
    if not exhausted:
        raise RuntimeError(
            f"ADP Workforce Now pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


def adp_external_job_id(record: dict[str, Any]) -> str:
    custom_fields = record.get("customFieldGroup")
    if not isinstance(custom_fields, dict):
        return ""
    fields = custom_fields.get("stringFields")
    if not isinstance(fields, list):
        return ""
    for field in fields:
        if not isinstance(field, dict):
            continue
        name_code = field.get("nameCode")
        code = name_code.get("codeValue") if isinstance(name_code, dict) else ""
        if code == "ExternalJobID":
            return str(field.get("stringValue") or "").strip()
    return ""


def collect_eightfold_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Collect internship-title variants from an Eightfold public PCSX API."""

    parsed = urlparse(source.careers_url)
    if not parsed.netloc:
        raise ValueError("Eightfold careers host could not be determined.")
    loader = get_json or get_public_json
    api_base = f"{parsed.scheme}://{parsed.netloc}/api/pcsx"
    query = parse_qs(parsed.query)
    domain = next(iter(query.get("domain", [])), "").strip()
    if not domain:
        raise ValueError(
            "Eightfold domain could not be determined from the careers URL."
        )
    search_terms = ("intern", "summer analyst", "summer associate", "co-op")
    records_by_id: dict[str, dict[str, Any]] = {}
    for search_term in search_terms:
        start = 0
        exhausted = False
        for _ in range(MAX_ATS_API_PAGES):
            params = {
                "domain": domain,
                "query": search_term,
                "location": "",
                "start": start,
            }
            payload = loader(f"{api_base}/search?{urlencode(params)}")
            data = payload.get("data") if isinstance(payload, dict) else None
            records = data.get("positions") if isinstance(data, dict) else None
            if not isinstance(records, list):
                raise ValueError("Eightfold search API returned an unexpected response.")
            if not records:
                exhausted = True
                break
            for record in records:
                if not isinstance(record, dict):
                    continue
                position_id = str(record.get("id") or "").strip()
                if position_id:
                    records_by_id[position_id] = record
            start += len(records)
            total = int(data.get("count", 0) or 0)
            if (total and start >= total) or len(records) < 10:
                exhausted = True
                break
        if not exhausted:
            raise RuntimeError(
                f"Eightfold pagination exceeded {MAX_ATS_API_PAGES} API pages."
            )

    postings: list[JobPosting] = []
    for position_id, record in records_by_id.items():
        title = clean_title(str(record.get("name") or ""))
        position_path = str(record.get("positionUrl") or "").strip()
        posting_url = urljoin(source.careers_url, position_path)
        if not posting_url or not is_specific_internship_listing(title, posting_url):
            continue
        detail_params = {
            "position_id": position_id,
            "domain": domain,
            "hl": "en",
        }
        detail_payload = loader(
            f"{api_base}/position_details?{urlencode(detail_params)}"
        )
        detail = (
            detail_payload.get("data")
            if isinstance(detail_payload, dict)
            and isinstance(detail_payload.get("data"), dict)
            else {}
        )
        detail_url = str(detail.get("publicUrl") or "").strip()
        locations = detail.get("locations") or record.get("locations")
        if isinstance(locations, list):
            location = "; ".join(clean_title(str(item)) for item in locations if item)
        else:
            location = clean_title(str(locations or "Unknown"))
        postings.append(
            JobPosting(
                title=clean_title(str(detail.get("name") or title)),
                company=source.company,
                location=location or "Unknown",
                posting_url=detail_url or posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
                eligibility_text=semantic_page_text(
                    str(detail.get("jobDescription") or "")
                ),
            )
        )
    return postings


def collect_notion_public_page_postings(
    source: CompanySource,
    collected_date: str,
    *,
    post_json: PostJson | None = None,
) -> list[JobPosting]:
    """Read direct child role pages from a public Notion careers page."""

    parsed = urlparse(source.careers_url)
    page_id = notion_page_id(source.careers_url)
    if not page_id:
        raise ValueError("Notion public page ID could not be determined.")
    poster = post_json or post_public_json
    endpoint = f"{parsed.scheme}://{parsed.netloc}/api/v3/loadCachedPageChunkV2"
    cursors: list[dict[str, Any]] = [{"stack": []}]
    seen_cursors: set[str] = set()
    blocks_by_id: dict[str, dict[str, Any]] = {}
    exhausted = False
    for _ in range(MAX_ATS_API_PAGES):
        if not cursors:
            exhausted = True
            break
        cursor = cursors.pop(0)
        cursor_key = json.dumps(cursor, sort_keys=True, separators=(",", ":"))
        if cursor_key in seen_cursors:
            continue
        seen_cursors.add(cursor_key)
        payload = poster(
            endpoint,
            {
                "page": {"id": page_id},
                "cursor": cursor,
                "verticalColumns": False,
            },
        )
        record_map = payload.get("recordMap") if isinstance(payload, dict) else None
        block_map = record_map.get("block") if isinstance(record_map, dict) else None
        if not isinstance(block_map, dict):
            raise ValueError("Notion public page API returned an unexpected response.")
        for block_id, wrapper in block_map.items():
            block = notion_block_value(wrapper)
            if block:
                blocks_by_id[str(block_id)] = block
        next_cursors = payload.get("cursors")
        if isinstance(next_cursors, list):
            cursors.extend(
                item for item in next_cursors if isinstance(item, dict)
            )
        if not cursors:
            exhausted = True
            break
    if not exhausted:
        raise RuntimeError(
            f"Notion pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )

    root_id = page_id.lower()
    postings: list[JobPosting] = []
    for block in blocks_by_id.values():
        if (
            block.get("type") != "page"
            or block.get("alive") is False
            or str(block.get("parent_id") or "").lower() != root_id
        ):
            continue
        title = clean_title(notion_block_title(block))
        block_id = str(block.get("id") or "").strip()
        if not title or not block_id:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        posting_url = (
            f"{parsed.scheme}://{parsed.netloc}/{slug}-{block_id.replace('-', '')}"
        )
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


def notion_page_id(url: str) -> str:
    matches = re.findall(r"(?i)([0-9a-f]{32})(?:[/?#]|$)", url)
    if not matches:
        return ""
    compact = matches[-1].lower()
    return (
        f"{compact[:8]}-{compact[8:12]}-{compact[12:16]}-"
        f"{compact[16:20]}-{compact[20:]}"
    )


def notion_block_value(wrapper: Any) -> dict[str, Any]:
    if not isinstance(wrapper, dict):
        return {}
    value = wrapper.get("value")
    if isinstance(value, dict) and isinstance(value.get("value"), dict):
        return value["value"]
    return value if isinstance(value, dict) else {}


def notion_block_title(block: dict[str, Any]) -> str:
    properties = block.get("properties")
    title_parts = properties.get("title") if isinstance(properties, dict) else None
    if not isinstance(title_parts, list):
        return ""
    return "".join(
        str(part[0])
        for part in title_parts
        if isinstance(part, list) and part and isinstance(part[0], str)
    )


def collect_profusa_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Treat Profusa's current official careers page as a complete source."""

    page_text = semantic_page_text(html).lower()
    if "profusa" not in page_text or "careers" not in page_text:
        raise ValueError("The official Profusa careers-page content was not found.")
    return extract_postings_from_html(
        source=source,
        html=html,
        collected_date=collected_date,
    )


def collect_general_dynamics_postings(
    source: CompanySource,
    collected_date: str,
    *,
    fetch_page: FetchPage | None = None,
    get_json_with_headers: GetJsonWithHeaders | None = None,
) -> list[JobPosting]:
    """Use GD's aggregate API while preserving its public bootstrap session."""

    browser_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/138.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if fetch_page is not None and get_json_with_headers is not None:
        html = fetch_page(source.careers_url)
        loader = get_json_with_headers
    else:
        curl = shutil.which("curl.exe") or shutil.which("curl")
        if not curl:
            raise RuntimeError(
                "General Dynamics requires the standard curl executable, "
                "but it was not found."
            )
        session_directory = tempfile.TemporaryDirectory(prefix="internship-gd-")
        cookie_jar = f"{session_directory.name}/cookies.txt"

        def run_curl(url: str, headers: dict[str, str], *, save_cookies: bool) -> str:
            command = [
                curl,
                "--silent",
                "--show-error",
                "--fail-with-body",
                "--location",
                "--max-time",
                "30",
            ]
            if save_cookies:
                command.extend(["--cookie-jar", cookie_jar])
            else:
                command.extend(["--cookie", cookie_jar])
            for name, value in headers.items():
                command.extend(["--header", f"{name}: {value}"])
            command.append(url)
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                timeout=35,
            )
            if result.returncode:
                message = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(
                    f"General Dynamics request failed ({result.returncode}): {message}"
                )
            return result.stdout.decode("utf-8", errors="replace")

        def session_json(url: str, headers: dict[str, str]) -> Any:
            return json.loads(run_curl(url, headers, save_cookies=False))

        separator = "&" if "?" in source.careers_url else "?"
        html = run_curl(
            f"{source.careers_url}{separator}_={time.time_ns()}",
            browser_headers,
            save_cookies=True,
        )
        loader = session_json

    auth = general_dynamics_authentication(html)
    api_headers = {
        "User-Agent": browser_headers["User-Agent"],
        "Accept": "application/json, text/plain, */*",
        "Referer": source.careers_url,
        "api-auth-nonce": auth["nonce"],
        "api-auth-signature": auth["signature"],
        "api-auth-timestamp": auth["timestamp"],
    }
    parsed = urlparse(source.careers_url)
    endpoint = f"{parsed.scheme}://{parsed.netloc}/API/Careers/CareerSearch"
    postings_by_url: dict[str, JobPosting] = {}
    page_size = 100
    for search_term in ("intern", "co-op", "summer analyst", "summer associate"):
        exhausted = False
        for page in range(MAX_ATS_API_PAGES):
            request_payload = {
                "address": [],
                "facets": [],
                "page": page,
                "what": search_term,
                "pageSize": str(page_size),
            }
            compressed = gzip.compress(
                json.dumps(request_payload, separators=(",", ":")).encode("utf-8")
            )
            encoded = base64.b64encode(compressed).decode("ascii")
            payload = loader(
                f"{endpoint}?{urlencode({'request': encoded})}",
                api_headers,
            )
            records = payload.get("Results") if isinstance(payload, dict) else None
            if not isinstance(records, list):
                raise ValueError(
                    "General Dynamics careers API returned an unexpected response."
                )
            if not records:
                exhausted = True
                break
            for record in records:
                if not isinstance(record, dict):
                    continue
                title = clean_title(str(record.get("Title") or ""))
                link = record.get("Link")
                path = link.get("Url") if isinstance(link, dict) else ""
                posting_url = urljoin(source.careers_url, str(path or ""))
                # Every API record is already a specific GD job detail. GD's
                # detail URLs end in "-opportunity" rather than a conventional
                # /job/ path, so apply the internship term check directly.
                if not posting_url or not mentions_internship(title, posting_url):
                    continue
                locations = record.get("LocationNames")
                if isinstance(locations, list):
                    location = "; ".join(
                        clean_title(str(item)) for item in locations if item
                    )
                else:
                    location = clean_title(str(locations or "Unknown"))
                postings_by_url[posting_url] = JobPosting(
                    title=title,
                    company=source.company,
                    location=location or "Unknown",
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=semantic_page_text(
                        str(record.get("Excerpt") or "")
                    ),
                )
            page_count = int(payload.get("PageCount", 0) or 0)
            if (page_count and page + 1 >= page_count) or len(records) < page_size:
                exhausted = True
                break
        if not exhausted:
            raise RuntimeError(
                "General Dynamics pagination exceeded "
                f"{MAX_ATS_API_PAGES} API pages."
            )
    return list(postings_by_url.values())


def general_dynamics_authentication(html: str) -> dict[str, str]:
    values = {}
    for key in ("nonce", "signature", "timestamp"):
        match = re.search(
            rf'data-{key}=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        values[key] = (
            html_module.unescape(match.group(1)).strip() if match else ""
        )
    if not all(values.values()):
        raise ValueError(
            "General Dynamics public API authentication metadata was not found."
        )
    return values


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
    path_parts = [part for part in parsed.path.split("/") if part]
    if not path_parts:
        raise ValueError("Workday tenant and site could not be determined from the careers URL.")
    if host_matches_domain(parsed.netloc, "myworkdaysite.com"):
        try:
            recruiting_index = path_parts.index("recruiting")
            tenant = path_parts[recruiting_index + 1]
            site = path_parts[recruiting_index + 2]
        except (ValueError, IndexError) as error:
            raise ValueError(
                "Workday recruiting tenant and site could not be determined."
            ) from error
        posting_base_url = (
            f"{parsed.scheme}://{parsed.netloc}/recruiting/{tenant}/{site}/"
        )
    else:
        tenant = parsed.netloc.split(".")[0]
        site = next(
            (part for part in path_parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", part)),
            "",
        )
        posting_base_url = source.careers_url.split("?", 1)[0]
    if not site:
        raise ValueError("Workday site could not be determined from the careers URL.")

    poster = post_json or post_public_json
    endpoint = f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"
    query = parse_qs(parsed.query)
    search_text = next(
        iter(query.get("q") or query.get("keywords") or query.get("keyword") or [""]),
        "",
    )
    postings: list[JobPosting] = []
    seen_paths: set[str] = set()
    offset = 0
    # Workday's public CXS service rejects limits above 20 for some tenants.
    page_size = 20

    exhausted = False
    for _ in range(MAX_ATS_API_PAGES):
        payload = poster(
            endpoint,
            {
                "appliedFacets": {},
                "limit": page_size,
                "offset": offset,
                "searchText": search_text,
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
            posting_url = (
                f"{posting_base_url.rstrip('/')}/{external_path.lstrip('/')}"
            )
            if not is_specific_internship_listing(title, posting_url):
                continue
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=_workday_location(record),
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


def _workday_location(record: dict[str, Any]) -> str:
    raw_text = str(record.get("locationsText") or "").strip()
    if raw_text:
        return clean_title(raw_text)
    bullets = record.get("bulletFields")
    if isinstance(bullets, list):
        for item in reversed(bullets):
            candidate = clean_title(str(item or ""))
            if not candidate or candidate == "Untitled posting":
                continue
            if re.fullmatch(r"R-\d+", candidate, re.IGNORECASE):
                continue
            if candidate.lower() in {"spotlight job", "hot job"}:
                continue
            return candidate
    return "Unknown"


def collect_cyberark_parent_workday_postings(
    source: CompanySource,
    collected_date: str,
    *,
    post_json: PostJson | None = None,
) -> list[JobPosting]:
    """Retain only CyberArk-labelled roles from its parent Workday board."""

    postings = collect_workday_postings(
        source,
        collected_date,
        post_json=post_json,
    )
    return [
        posting
        for posting in postings
        if "cyberark" in f"{posting.title} {posting.eligibility_text}".lower()
    ]


def collect_closed_company_postings(
    source: CompanySource,
    html: str,
) -> list[JobPosting]:
    """Treat a current official closure notice as a complete empty source."""

    page_text = semantic_page_text(html).lower()
    if "company is no longer operating" not in page_text:
        raise ValueError("The official company closure notice was not found.")
    return []


def collect_parked_company_domain_postings(
    source: CompanySource,
    html: str,
) -> list[JobPosting]:
    """Treat a verified domain-parking redirect as a complete empty source."""

    compact_html = re.sub(r"\s+", "", html).lower()
    if (
        'window.location.href="/lander"' not in compact_html
        and "window.location.href='/lander'" not in compact_html
    ):
        raise ValueError("The expected parked-domain redirect was not found.")
    return []


def collect_avature_rss_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
    *,
    fetch_page: FetchPage | None = None,
) -> list[JobPosting]:
    """Read every item from an Avature search RSS feed."""

    try:
        root = ET.fromstring(html)
    except ET.ParseError as error:
        raise ValueError("Avature RSS feed returned invalid XML.") from error

    loader = fetch_page or fetch_public_page
    postings: list[JobPosting] = []
    for item in root.findall(".//item"):
        title = clean_title(item.findtext("title") or "")
        posting_url = (item.findtext("link") or item.findtext("guid") or "").strip()
        if not posting_url or not is_specific_internship_listing(title, posting_url):
            continue
        detail_html = loader(posting_url)
        location_block = re.search(
            r'<div[^>]+class=["\'][^"\']*\barticle__header--locations\b'
            r'[^"\']*["\'][^>]*>(.*?)</div>',
            detail_html,
            re.IGNORECASE | re.DOTALL,
        )
        locations = (
            [
                clean_title(semantic_page_text(value))
                for value in re.findall(
                    r"<p[^>]*>(.*?)</p>",
                    location_block.group(1),
                    re.IGNORECASE | re.DOTALL,
                )
            ]
            if location_block
            else []
        )
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location="; ".join(location for location in locations if location)
                or "Unknown",
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
                eligibility_text=semantic_page_text(detail_html),
            )
        )
    return postings


def collect_oracle_recruiting_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Page through an Oracle Recruiting Cloud public career site search."""

    parsed_source_url = urlparse(source.careers_url)
    api_base_match = re.search(
        r'(https://[^"\'\s<>]+oraclecloud\.com(?::\d+)?)',
        html,
        re.IGNORECASE,
    )
    site_match = re.search(
        r'data-sitenumber=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )
    if not api_base_match and host_matches_domain(
        parsed_source_url.netloc,
        "oraclecloud.com",
    ):
        api_base = f"{parsed_source_url.scheme}://{parsed_source_url.netloc}"
    else:
        api_base = api_base_match.group(1).rstrip("/") if api_base_match else ""
    if not site_match:
        site_match = re.search(
            r"/sites/([^/?#]+)",
            parsed_source_url.path,
            re.IGNORECASE,
        )
    if not api_base_match or not site_match:
        if not api_base or not site_match:
            raise ValueError(
                "Oracle Recruiting API host or career-site number was not found."
            )

    site_number = site_match.group(1)
    endpoint = (
        f"{api_base}/hcmRestApi/resources/latest/"
        "recruitingCEJobRequisitions"
    )
    loader = get_json or get_public_json
    page_size = 100
    offset = 0
    postings: list[JobPosting] = []
    seen_ids: set[str] = set()
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        finder = (
            f"findReqs;siteNumber={site_number},limit={page_size},"
            f"offset={offset},keyword=intern"
        )
        query_string = urlencode(
            {
                "onlyData": "true",
                "expand": "requisitionList",
                "finder": finder,
            }
        )
        request_url = f"{endpoint}?{query_string}"
        payload = loader(request_url)
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("Oracle Recruiting API returned an unexpected response.")
        search = next(
            (item for item in payload["items"] if isinstance(item, dict)),
            None,
        )
        if not search:
            exhausted = True
            break
        requisition_list = search.get("requisitionList")
        if isinstance(requisition_list, list):
            records = requisition_list
        elif isinstance(requisition_list, dict):
            records = requisition_list.get("items")
        else:
            records = None
        if not isinstance(records, list):
            raise ValueError("Oracle Recruiting requisition list was missing.")
        for record in records:
            if not isinstance(record, dict):
                continue
            requisition_id = str(record.get("Id") or "").strip()
            if not requisition_id or requisition_id in seen_ids:
                continue
            seen_ids.add(requisition_id)
            title = clean_title(str(record.get("Title") or ""))
            site_root_match = re.search(
                rf"^(.*?/sites/{re.escape(site_number)})(?:/|$)",
                source.careers_url.split("?", 1)[0],
                re.IGNORECASE,
            )
            site_root = (
                site_root_match.group(1)
                if site_root_match
                else source.careers_url.split("?", 1)[0].rstrip("/")
            )
            posting_url = f"{site_root}/job/{quote(requisition_id)}"
            if not is_specific_internship_listing(title, posting_url):
                continue
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=clean_title(
                        str(record.get("PrimaryLocation") or "Unknown")
                    ),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=semantic_page_text(
                        " ".join(
                            str(record.get(key) or "")
                            for key in (
                                "ShortDescriptionStr",
                                "ExternalQualificationsStr",
                                "ExternalResponsibilitiesStr",
                                "StudyLevel",
                            )
                        )
                    ),
                )
            )
        total = int(search.get("TotalJobsCount", 0) or 0)
        offset += len(records)
        if (
            not records
            or (total and offset >= total)
            or (not total and len(records) < page_size)
        ):
            exhausted = True
            break

    if not exhausted:
        raise RuntimeError(
            f"Oracle Recruiting pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


GOLDMAN_HIGHER_API = "https://api-higher.gs.com/gateway/api/v1/graphql"
GOLDMAN_HIGHER_QUERY = """
query GetCampusRoles($searchQueryInput: RoleSearchQueryInput!) {
  roleSearch(searchQueryInput: $searchQueryInput) {
    totalCount
    items {
      roleId
      corporateTitle
      jobTitle
      jobFunction
      locations { primary state country city }
      status
      division
      skills
      jobType { code description }
      educationLevel
      startDate
      gradDegreeStartDate
      gradDegreeEndDate
    }
  }
}
""".strip()


def collect_goldman_higher_postings(
    source: CompanySource,
    collected_date: str,
    *,
    post_json: PostJson | None = None,
) -> list[JobPosting]:
    """Page through Goldman Sachs' official current campus-role API."""

    poster = post_json or post_public_json
    page_size = 20
    page_number = 0
    postings: list[JobPosting] = []
    seen_ids: set[str] = set()
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        payload = poster(
            GOLDMAN_HIGHER_API,
            {
                "query": GOLDMAN_HIGHER_QUERY,
                "variables": {
                    "searchQueryInput": {
                        "page": {
                            "pageSize": page_size,
                            "pageNumber": page_number,
                        },
                        "sort": {
                            "sortStrategy": "POSTED_DATE",
                            "sortOrder": "DESC",
                        },
                        "experiences": ["CAMPUS"],
                        "searchTerm": "",
                    }
                },
            },
        )
        role_search = (
            payload.get("data", {}).get("roleSearch")
            if isinstance(payload, dict)
            else None
        )
        if not isinstance(role_search, dict):
            raise ValueError("Goldman Sachs role API returned an unexpected response.")
        records = role_search.get("items")
        if not isinstance(records, list):
            raise ValueError("Goldman Sachs role list was missing.")

        for record in records:
            if not isinstance(record, dict):
                continue
            role_id = str(record.get("roleId") or "").strip()
            if not role_id or role_id in seen_ids:
                continue
            seen_ids.add(role_id)
            title = clean_title(str(record.get("jobTitle") or ""))
            posting_url = f"https://higher.gs.com/roles/{quote(role_id)}"
            if not is_specific_internship_listing(title, posting_url):
                continue
            locations = record.get("locations")
            location_texts = []
            if isinstance(locations, list):
                for location in locations:
                    if not isinstance(location, dict):
                        continue
                    parts = [
                        clean_title(str(location.get(key) or ""))
                        for key in ("city", "state", "country")
                    ]
                    rendered = ", ".join(part for part in parts if part)
                    if rendered and rendered not in location_texts:
                        location_texts.append(rendered)
            job_type = record.get("jobType")
            eligibility_parts = [
                record.get("educationLevel"),
                record.get("corporateTitle"),
                record.get("jobFunction"),
                record.get("division"),
                job_type.get("description") if isinstance(job_type, dict) else "",
            ]
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location="; ".join(location_texts) or "Unknown",
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=semantic_page_text(
                        " ".join(str(part or "") for part in eligibility_parts)
                    ),
                )
            )

        total = int(role_search.get("totalCount", 0) or 0)
        page_number += 1
        if (
            not records
            or (total and page_number * page_size >= total)
            or (not total and len(records) < page_size)
        ):
            exhausted = True
            break

    if not exhausted:
        raise RuntimeError(
            f"Goldman Sachs pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


def collect_ibm_careers_postings(
    source: CompanySource,
    collected_date: str,
    *,
    post_json: PostJson | None = None,
) -> list[JobPosting]:
    """Page IBM's public careers search API for internship-tagged roles."""

    poster = post_json or post_public_json
    page_size = 30
    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for facet in IBM_INTERNSHIP_FACETS:
        offset = 0
        exhausted = False
        for _ in range(MAX_ATS_API_PAGES):
            payload = poster(
                IBM_CAREERS_API,
                ibm_careers_search_body(facet=facet, offset=offset, page_size=page_size),
            )
            hits = ibm_careers_hits(payload)
            if not hits:
                exhausted = True
                break
            for record in hits:
                posting = ibm_careers_posting(source, record, collected_date)
                if posting is None or posting.posting_url in seen_urls:
                    continue
                seen_urls.add(posting.posting_url)
                postings.append(posting)
            offset += len(hits)
            if len(hits) < page_size:
                exhausted = True
                break
        if not exhausted:
            raise RuntimeError(
                f"IBM careers pagination exceeded {MAX_ATS_API_PAGES} API pages."
            )
    return postings


def ibm_careers_search_body(
    *,
    facet: str,
    offset: int,
    page_size: int,
) -> dict[str, Any]:
    return {
        "appId": "careers",
        "scopes": ["careers2"],
        "query": {"bool": {"must": []}},
        "post_filter": {"bool": {"must": [{"term": {IBM_INTERNSHIP_FIELD: facet}}]}},
        "size": page_size,
        "from": offset,
        "sort": [{"_score": "desc"}, {"pageviews": "desc"}],
        "lang": "zz",
        "localeSelector": {},
        "sm": {"query": "", "lang": "zz"},
        "_source": [
            "_id",
            "title",
            "url",
            "description",
            "language",
            "field_keyword_05",
            "field_keyword_08",
            "field_keyword_17",
            "field_keyword_18",
            "field_keyword_19",
        ],
    }


def ibm_careers_hits(payload: Any) -> list[dict[str, Any]]:
    hits = payload.get("hits") if isinstance(payload, dict) else None
    records = hits.get("hits") if isinstance(hits, dict) else None
    if not isinstance(records, list):
        raise ValueError("IBM careers API returned an unexpected response.")
    return [record for record in records if isinstance(record, dict)]


def ibm_careers_posting(
    source: CompanySource,
    record: dict[str, Any],
    collected_date: str,
) -> JobPosting | None:
    details = record.get("_source")
    if not isinstance(details, dict):
        details = record
    title = clean_title(str(details.get("title") or ""))
    posting_url = str(details.get("url") or "").strip()
    if (
        not posting_url
        or not posting_url.startswith(("http://", "https://"))
        or not is_specific_internship_listing(title, posting_url)
    ):
        return None
    location_parts = [
        clean_title(str(details.get(key) or ""))
        for key in ("field_keyword_19", "field_keyword_05", "field_keyword_17")
        if details.get(key)
    ]
    return JobPosting(
        title=title,
        company=source.company,
        location="; ".join(part for part in location_parts if part) or "Unknown",
        posting_url=posting_url,
        date_collected=collected_date,
        source_url=source.careers_url,
        eligibility_text=semantic_page_text(
            " ".join(
                str(details.get(key) or "")
                for key in ("field_keyword_08", "description")
            )
        ),
    )


def collect_elbit_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Read Elbit's official same-origin jobs JSON and keep student/intern roles."""

    parsed = urlparse(source.careers_url)
    if not parsed.netloc:
        raise ValueError("Elbit careers host could not be determined.")
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    loader = get_json or get_public_json
    records: list[Any] | None = None
    errors: list[str] = []
    for path in ELBIT_JOBS_PATHS:
        endpoint = f"{origin}{path}"
        try:
            payload = loader(endpoint)
        except Exception as error:  # noqa: BLE001 - try the next official path.
            errors.append(f"{path} failed: {error}")
            continue
        extracted = elbit_job_records(payload)
        if extracted is not None:
            records = extracted
            break
        errors.append(f"{path} returned an unexpected response.")
    if records is None:
        detail = "; ".join(errors) if errors else "no jobs JSON endpoint responded."
        raise ValueError(f"Elbit jobs API was not found: {detail}")

    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        title = clean_title(
            str(
                record.get("title")
                or record.get("name")
                or record.get("jobTitle")
                or ""
            )
        )
        category = clean_title(
            str(
                record.get("category")
                or record.get("expertise")
                or record.get("areaOfInterest")
                or ""
            )
        )
        category_id = str(
            record.get("categoryId")
            or record.get("expertise")
            or record.get("category")
            or ""
        ).strip()
        category_ids = {category_id.lower()} if category_id else set()
        extra_ids = record.get("categoryIds")
        if isinstance(extra_ids, list):
            category_ids.update(str(item).strip().lower() for item in extra_ids if item)
        posting_url = elbit_job_url(origin, record)
        searchable = " ".join(part for part in (title, category, posting_url) if part)
        is_student_category = bool(category_ids & ELBIT_STUDENT_CATEGORIES) or (
            category.lower() in ELBIT_STUDENT_CATEGORIES
        )
        if is_student_category:
            searchable = f"{searchable} student"
        if not posting_url or posting_url in seen_urls:
            continue
        if not (
            is_student_category or is_specific_internship_listing(searchable, posting_url)
        ):
            continue
        seen_urls.add(posting_url)
        location = elbit_display_location(
            str(
                record.get("location")
                or record.get("locationAddress")
                or record.get("area")
                or record.get("city")
                or record.get("region")
                or ""
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
                eligibility_text=semantic_page_text(
                    " ".join(
                        str(record.get(key) or "")
                        for key in (
                            "category",
                            "description",
                            "jobDescription",
                            "content",
                        )
                    )
                ),
            )
        )
    return postings


def elbit_job_records(payload: Any) -> list[Any] | None:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in ("jobs", "data", "items", "results"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return candidate
        if isinstance(candidate, dict):
            nested = elbit_job_records(candidate)
            if nested is not None:
                return nested
    return None


def elbit_job_url(origin: str, record: dict[str, Any]) -> str:
    raw_url = str(
        record.get("url")
        or record.get("jobUrl")
        or record.get("link")
        or record.get("applyUrl")
        or ""
    ).strip()
    if raw_url:
        return normalize_link(origin, raw_url)
    job_id = str(record.get("id") or record.get("jobId") or record.get("_id") or "").strip()
    if not job_id:
        return ""
    return f"{origin}/jobs?id={quote(job_id)}"


def elbit_display_location(location: str) -> str:
    cleaned = clean_title(location)
    if not cleaned or cleaned.lower() in {"unknown", "untitled posting"}:
        return "Israel"
    if "israel" in cleaned.lower() or "ישראל" in cleaned:
        return cleaned
    return f"{cleaned}, Israel"


def collect_wix_postings(
    source: CompanySource,
    collected_date: str,
    *,
    fetch_page: FetchPage | None = None,
) -> list[JobPosting]:
    """Read every public Wix /position/ URL from the official sitemap."""

    parsed = urlparse(source.careers_url)
    if not parsed.netloc:
        raise ValueError("Wix careers host could not be determined.")
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    loader = fetch_page or fetch_public_page
    sitemap_xml = loader(f"{origin}{WIX_SITEMAP_PATH}")
    position_urls = wix_position_urls(sitemap_xml)
    if not position_urls:
        raise ValueError("Wix sitemap did not include any position pages.")
    if len(position_urls) > MAX_ATS_API_PAGES:
        raise RuntimeError(
            f"Wix sitemap pagination exceeded {MAX_ATS_API_PAGES} position pages."
        )

    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for posting_url in position_urls:
        if posting_url in seen_urls:
            continue
        seen_urls.add(posting_url)
        try:
            html = loader(posting_url)
        except Exception:  # noqa: BLE001 - stale sitemap rows should not fail the scan.
            continue
        title = wix_position_title(html)
        if not title or not is_specific_internship_listing(title, posting_url):
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


def wix_position_urls(sitemap_xml: str) -> list[str]:
    try:
        root = ET.fromstring(sitemap_xml)
    except ET.ParseError as error:
        raise ValueError("Wix sitemap XML was invalid.") from error
    urls: list[str] = []
    seen: set[str] = set()
    for element in root.iter():
        if not element.tag.endswith("loc") or not element.text:
            continue
        loc = element.text.strip()
        path = urlparse(loc).path.lower()
        if "/position/" not in path or loc in seen:
            continue
        seen.add(loc)
        urls.append(loc)
    return urls


def wix_position_title(html: str) -> str:
    match = OG_TITLE_RE.search(html)
    raw_title = ""
    if match:
        raw_title = match.group(1) or match.group(2) or ""
    if not raw_title:
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        raw_title = title_match.group(1) if title_match else ""
    title = clean_title(html_module.unescape(re.sub(r"<[^>]+>", " ", raw_title)))
    for suffix in WIX_TITLE_SUFFIXES:
        if title.endswith(suffix):
            title = title[: -len(suffix)].rstrip()
    return title


def collect_lemonade_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
) -> list[JobPosting]:
    """Read every Lemonade role from its official Next.js careers payload."""

    match = NEXT_DATA_RE.search(html)
    if not match:
        raise ValueError("Lemonade's official jobs payload was not found.")
    try:
        payload = json.loads(html_module.unescape(match.group(1)))
    except json.JSONDecodeError as error:
        raise ValueError("Lemonade's official jobs payload was invalid.") from error
    records = find_named_json_list(payload, "allRecipes")
    if records is None:
        raise ValueError("Lemonade's complete role list was not found.")

    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        title = clean_title(str(record.get("title") or record.get("pageTitle") or ""))
        posting_url = normalize_link(
            source.careers_url,
            str(record.get("link") or ""),
        )
        employment_type = str(record.get("employmentType") or "")
        if (
            not posting_url
            or posting_url in seen_urls
            or not is_specific_internship_listing(
                f"{title} {employment_type}",
                posting_url,
            )
        ):
            continue
        seen_urls.add(posting_url)
        postings.append(
            JobPosting(
                title=title,
                company=source.company,
                location=clean_title(str(record.get("location") or "Unknown")),
                posting_url=posting_url,
                date_collected=collected_date,
                source_url=source.careers_url,
                eligibility_text=semantic_page_text(
                    " ".join(
                        str(record.get(key) or "")
                        for key in ("employmentType", "content")
                    )
                ),
            )
        )
    return postings


def find_named_json_list(value: Any, key: str) -> list[Any] | None:
    """Return the first list stored under a named key in nested JSON."""

    if isinstance(value, dict):
        candidate = value.get(key)
        if isinstance(candidate, list):
            return candidate
        for child in value.values():
            found = find_named_json_list(child, key)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_named_json_list(child, key)
            if found is not None:
                return found
    return None


def collect_pixar_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
    *,
    fetch_page: FetchPage | None = None,
) -> list[JobPosting]:
    """Page through Disney's official results and retain Pixar internships."""

    loader = fetch_page or fetch_public_page
    page_html = html
    page_url = source.careers_url
    seen_urls: set[str] = set()
    postings: list[JobPosting] = []
    exhausted = False
    total_pages_match = DISNEY_TOTAL_PAGES_RE.search(html)
    total_pages = int(total_pages_match.group("total")) if total_pages_match else 1
    page_number = 1

    for _ in range(MAX_ATS_API_PAGES):
        for result in DISNEY_RESULT_ROW_RE.finditer(page_html):
            row = result.group("row")
            job_match = DISNEY_JOB_RE.search(row)
            brand_match = DISNEY_BRAND_RE.search(row)
            if not job_match or not brand_match:
                continue
            brand = clean_title(strip_html(brand_match.group("brand")))
            if brand.lower() != "pixar animation studios":
                continue
            title = clean_title(strip_html(job_match.group("title")))
            posting_url = normalize_link(page_url, job_match.group("url"))
            if (
                not posting_url
                or posting_url in seen_urls
                or not is_specific_internship_listing(title, posting_url)
            ):
                continue
            seen_urls.add(posting_url)
            location_match = DISNEY_LOCATION_RE.search(row)
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=(
                        clean_title(strip_html(location_match.group("location")))
                        if location_match
                        else "Unknown"
                    ),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                )
            )

        if page_number >= total_pages:
            exhausted = True
            break
        page_number += 1
        page_url = f"{source.careers_url}&p={page_number}"
        page_html = loader(page_url)

    if not exhausted:
        raise RuntimeError(f"Pixar pagination exceeded {MAX_ATS_API_PAGES} pages.")
    return postings


def collect_bank_of_america_postings(
    source: CompanySource,
    collected_date: str,
    *,
    get_json: GetJson | None = None,
) -> list[JobPosting]:
    """Read every opportunity from Bank of America's public campus jobs feed."""

    if not host_matches_domain(
        urlparse(source.careers_url).netloc,
        "careers.bankofamerica.com",
    ):
        raise ValueError("Bank of America collector requires its official careers URL.")

    getter = get_json or get_public_json
    endpoint = "https://careers.bankofamerica.com/services/campusjobssearchservlet"
    page_size = 100
    offset = 0
    postings: list[JobPosting] = []
    seen_ids: set[str] = set()
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        query = urlencode(
            {
                "start": offset,
                "rows": page_size,
                "search": "getAllJobs",
            }
        )
        payload = getter(f"{endpoint}?{query}")
        if not isinstance(payload, dict) or not isinstance(payload.get("jobsList"), list):
            raise ValueError("Bank of America campus feed returned an unexpected response.")
        records = payload["jobsList"]
        total = int(payload.get("totalMatches", 0) or 0)
        if not records:
            exhausted = True
            break

        new_records = 0
        for record in records:
            if not isinstance(record, dict):
                continue
            posting_id = str(record.get("jobRequisitionId") or "").strip()
            relative_url = str(record.get("jcrURL") or "").strip()
            posting_url = (
                urljoin("https://careers.bankofamerica.com", relative_url)
                if relative_url
                else str(record.get("externalUrl") or "").strip()
            )
            identity = posting_id or posting_url
            if not identity or identity in seen_ids:
                continue
            seen_ids.add(identity)
            new_records += 1
            title = clean_title(str(record.get("postingTitle") or ""))
            program_type = clean_title(str(record.get("jobSubFamily") or ""))
            if not mentions_internship(
                " ".join(part for part in (title, program_type) if part),
                posting_url,
            ):
                continue
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=clean_title(
                        str(
                            record.get("location")
                            or record.get("primaryLocation")
                            or record.get("locationString")
                            or "Unknown"
                        )
                    ),
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                    eligibility_text=semantic_page_text(
                        str(record.get("jobDescriptionExternal") or "")
                    ),
                )
            )
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
            f"Bank of America pagination exceeded {MAX_ATS_API_PAGES} API pages."
        )
    return postings


def collect_bayer_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
    *,
    fetch_page: FetchPage | None = None,
) -> list[JobPosting]:
    """Read every result page from Bayer's public SuccessFactors board."""

    if not host_matches_domain(urlparse(source.careers_url).netloc, "jobs.bayer.com"):
        raise ValueError("Bayer collector requires the official jobs.bayer.com URL.")

    fetcher = fetch_page or fetch_public_page
    page_size = 10
    offset = 0
    page_html = html
    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        if offset:
            query = urlencode(
                {
                    "q": "",
                    "sortColumn": "referencedate",
                    "sortDirection": "desc",
                    "startrow": offset,
                }
            )
            page_html = fetcher(f"https://jobs.bayer.com/search?{query}")

        total_match = BAYER_TOTAL_RE.search(page_html)
        if not total_match:
            raise ValueError("Bayer jobs page did not expose a result total.")
        total = int(total_match.group("total").replace(",", ""))
        rows = list(BAYER_RESULT_ROW_RE.finditer(page_html))
        if not rows:
            exhausted = offset >= total
            break

        new_rows = 0
        for row_match in rows:
            row = row_match.group("row")
            job_match = SUCCESSFACTORS_JOB_RE.search(row)
            if not job_match:
                continue
            posting_url = urljoin(source.careers_url, html_module.unescape(job_match.group("url")))
            if posting_url in seen_urls:
                continue
            seen_urls.add(posting_url)
            new_rows += 1
            title = clean_title(semantic_page_text(job_match.group("title")))
            if not mentions_internship(title, posting_url):
                continue
            location_match = BAYER_LOCATION_RE.search(row)
            location = (
                clean_title(semantic_page_text(location_match.group("location")))
                if location_match
                else "Unknown"
            )
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=location or "Unknown",
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                )
            )

        offset += len(rows)
        if not new_rows or offset >= total or len(rows) < page_size:
            exhausted = True
            break

    if not exhausted:
        raise RuntimeError(
            f"Bayer pagination exceeded {MAX_ATS_API_PAGES} result pages."
        )
    return postings


def collect_successfactors_postings(
    source: CompanySource,
    html: str,
    collected_date: str,
    *,
    fetch_page: FetchPage | None = None,
) -> list[JobPosting]:
    """Read every result page from a standard SuccessFactors jobs search."""

    fetcher = fetch_page or fetch_public_page
    parsed = urlparse(source.careers_url)
    base_query = parse_qs(parsed.query)
    offset = 0
    page_html = html
    postings: list[JobPosting] = []
    seen_urls: set[str] = set()
    exhausted = False

    for _ in range(MAX_ATS_API_PAGES):
        if offset:
            query = {key: values for key, values in base_query.items()}
            query["startrow"] = [str(offset)]
            page_url = parsed._replace(query=urlencode(query, doseq=True)).geturl()
            page_html = fetcher(page_url)

        total_match = BAYER_TOTAL_RE.search(page_html)
        if not total_match:
            raise ValueError("SuccessFactors jobs page did not expose a result total.")
        total = int(total_match.group("total").replace(",", ""))
        rows = list(BAYER_RESULT_ROW_RE.finditer(page_html))
        if not rows:
            exhausted = offset >= total
            break

        new_rows = 0
        for row_match in rows:
            row = row_match.group("row")
            job_match = SUCCESSFACTORS_JOB_RE.search(row)
            if not job_match:
                continue
            posting_url = urljoin(
                source.careers_url,
                html_module.unescape(job_match.group("url")),
            )
            if posting_url in seen_urls:
                continue
            seen_urls.add(posting_url)
            new_rows += 1
            title = clean_title(semantic_page_text(job_match.group("title")))
            if not mentions_internship(title, posting_url):
                continue
            location_match = BAYER_LOCATION_RE.search(row)
            location = (
                clean_title(semantic_page_text(location_match.group("location")))
                if location_match
                else "Unknown"
            )
            postings.append(
                JobPosting(
                    title=title,
                    company=source.company,
                    location=location or "Unknown",
                    posting_url=posting_url,
                    date_collected=collected_date,
                    source_url=source.careers_url,
                )
            )

        offset += len(rows)
        if not new_rows or offset >= total:
            exhausted = True
            break

    if not exhausted:
        raise RuntimeError(
            f"SuccessFactors pagination exceeded {MAX_ATS_API_PAGES} result pages."
        )
    return postings


def fetch_public_page(url: str) -> str:
    request = Request(
        url,
        headers={"Accept": "text/html", "User-Agent": "internship-search/1.0"},
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def get_public_json(url: str) -> Any:
    from internship_search.retry import retry_call

    def load_once() -> Any:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; internship-search/1.0; "
                    "+https://github.com/Gabby-D/AI_Agent_Internship_Search)"
                ),
            },
        )
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))

    return retry_call(load_once, max_attempts=4, base_delay_seconds=2.0, sleep=time.sleep)


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
