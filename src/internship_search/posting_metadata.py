"""Deterministic posting metadata enrichment for company names and locations."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from internship_search.job_collector import JobPosting, clean_title

FetchJson = Callable[[str], dict]

GREENHOUSE_URL_RE = re.compile(
    r"https?://(?:job-boards|boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)",
    re.IGNORECASE,
)
LEVER_URL_RE = re.compile(
    r"https?://jobs\.lever\.co/([^/]+)/([^/?#]+)",
    re.IGNORECASE,
)
JOB_APPLICATION_TITLE_RE = re.compile(
    r"^job application for (.+) at (.+)$",
    re.IGNORECASE,
)
TITLE_SUFFIX_RE = re.compile(
    r"\s*\|\s*(LinkedIn|Indeed\.com|Glassdoor|Monster)\s*$",
    re.IGNORECASE,
)
ELLIPSIS_COMPANY_MARKERS = {"...", "…", "unknown company"}

BOARD_SLUG_COMPANY_NAMES = {
    "alpineinternships": "Alpine",
    "aquaticcapitalmanagement": "Aquatic Capital Management",
    "palantir": "Palantir",
    "thelibragroup": "Libra Group",
    "virtu": "Virtu Financial",
    "walleyecapital-external-students": "Walleye Capital",
}

_LOCATION_CACHE: dict[str, tuple[str, str, str]] = {}


def enrich_job_posting(
    posting: JobPosting,
    *,
    snippet: str = "",
    fetch_json: FetchJson | None = None,
    use_remote_apis: bool = True,
) -> JobPosting:
    """Fill missing company, title, and location fields using parsers and public APIs."""

    enriched = enrich_job_posting_local(posting, snippet=snippet)
    if not use_remote_apis:
        return enriched

    remote_title, remote_company, remote_location = fetch_remote_posting_metadata(
        posting.posting_url,
        fetch_json=fetch_json,
    )
    title = prefer_title(enriched.title, remote_title)
    company = prefer_company(enriched.company, remote_company)
    location = prefer_location(enriched.location, remote_location)

    if (
        title == enriched.title
        and company == enriched.company
        and location == enriched.location
    ):
        return enriched
    return replace(enriched, title=title, company=company, location=location)


def enrich_job_posting_local(posting: JobPosting, *, snippet: str = "") -> JobPosting:
    title, company = parse_job_board_title(posting.title, posting.posting_url)
    location = posting.location

    if is_missing_company(company):
        company = infer_company_from_posting_url(posting.posting_url) or company
    if is_missing_company(posting.company):
        company = prefer_company(posting.company, company)
    else:
        company = prefer_company(company, posting.company)

    title = prefer_title(posting.title, title)
    location = prefer_location(location, infer_location_from_snippet(snippet))

    if title == posting.title and company == posting.company and location == posting.location:
        return posting
    return replace(posting, title=title, company=company, location=location)


def enrich_job_postings(
    postings: list[JobPosting],
    *,
    snippets_by_url: dict[str, str] | None = None,
    fetch_json: FetchJson | None = None,
    use_remote_apis: bool = True,
) -> list[JobPosting]:
    snippets = snippets_by_url or {}
    return [
        enrich_job_posting(
            posting,
            snippet=snippets.get(posting.posting_url, ""),
            fetch_json=fetch_json,
            use_remote_apis=use_remote_apis,
        )
        for posting in postings
    ]


def merge_posting_metadata(primary: JobPosting, secondary: JobPosting) -> JobPosting:
    return replace(
        primary,
        title=prefer_title(primary.title, secondary.title),
        company=prefer_company(primary.company, secondary.company),
        location=prefer_location(primary.location, secondary.location),
    )


def parse_job_board_title(title: str, url: str) -> tuple[str, str]:
    cleaned = clean_title(TITLE_SUFFIX_RE.sub("", title))
    match = JOB_APPLICATION_TITLE_RE.match(cleaned)
    if match:
        role = clean_title(match.group(1))
        company = clean_title(match.group(2))
        if not is_missing_company(company):
            return role, company
        inferred = infer_company_from_posting_url(url)
        return role, inferred or company

    if " at " in cleaned.lower():
        role, company = cleaned.rsplit(" at ", maxsplit=1)
        role = clean_title(role)
        company = clean_title(company.split(" | ", maxsplit=1)[0])
        if not is_missing_company(company):
            return role, company

    if " - " in cleaned and "indeed.com" in url.lower():
        company, role = cleaned.split(" - ", maxsplit=1)
        return clean_title(role.split(" | ", maxsplit=1)[0]), clean_title(company)

    return cleaned, infer_company_from_posting_url(url) or ""


def infer_company_from_posting_url(url: str) -> str:
    greenhouse = parse_greenhouse_url(url)
    if greenhouse:
        return company_name_from_board_slug(greenhouse[0])

    lever = parse_lever_url(url)
    if lever:
        return company_name_from_board_slug(lever[0])

    domain = urlparse(url).netloc.lower()
    if "linkedin.com" in domain:
        return ""
    if "indeed.com" in domain:
        return ""
    return ""


def infer_location_from_snippet(snippet: str) -> str:
    cleaned = clean_title(snippet)
    if not cleaned:
        return ""

    patterns = (
        r"\b(?:location|based in|office)\s*:\s*([^|.;]+)",
        r"\bin\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*,\s*[A-Z]{2})\b",
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*,\s*[A-Z]{2})\b",
        r"\b(Remote|Hybrid)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            value = clean_title(match.group(1))
            if value and value.lower() not in {"intern", "internship", "summer", "untitled", "untitled posting"}:
                return value
    return ""


def fetch_remote_posting_metadata(
    url: str,
    *,
    fetch_json: FetchJson | None = None,
) -> tuple[str, str, str]:
    if fetch_json is None and url in _LOCATION_CACHE:
        return _LOCATION_CACHE[url]

    loader = fetch_json or fetch_json_request
    greenhouse = parse_greenhouse_url(url)
    if greenhouse:
        board, job_id = greenhouse
        try:
            payload = loader(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}")
        except Exception:  # noqa: BLE001 - enrichment is best effort.
            payload = {}
        title = clean_title(str(payload.get("title", "")))
        company = clean_title(str(payload.get("company_name", ""))) or company_name_from_board_slug(board)
        location_data = payload.get("location", {})
        location = ""
        if isinstance(location_data, dict):
            location = clean_title(str(location_data.get("name", "")))
        if not title and not company and not location:
            result = ("", "", "")
        else:
            result = (title, company, location)
        _LOCATION_CACHE[url] = result
        return result

    lever = parse_lever_url(url)
    if lever:
        company_slug, posting_id = lever
        try:
            payload = loader(
                f"https://api.lever.co/v0/postings/{company_slug}/{posting_id}?mode=json"
            )
        except Exception:  # noqa: BLE001 - enrichment is best effort.
            payload = {}
        title = clean_title(str(payload.get("text", "")))
        company = company_name_from_board_slug(company_slug)
        categories = payload.get("categories", {})
        location = ""
        if isinstance(categories, dict):
            location = clean_title(str(categories.get("location", "")))
        if not title and not company and not location:
            result = ("", "", "")
        else:
            result = (title, company, location)
        _LOCATION_CACHE[url] = result
        return result

    _LOCATION_CACHE[url] = ("", "", "")
    return "", "", ""


def parse_greenhouse_url(url: str) -> tuple[str, str] | None:
    match = GREENHOUSE_URL_RE.search(url)
    if not match:
        return None
    return match.group(1), match.group(2)


def parse_lever_url(url: str) -> tuple[str, str] | None:
    match = LEVER_URL_RE.search(url)
    if not match:
        return None
    return match.group(1), match.group(2)


def company_name_from_board_slug(slug: str) -> str:
    normalized = slug.strip().lower()
    if normalized in BOARD_SLUG_COMPANY_NAMES:
        return BOARD_SLUG_COMPANY_NAMES[normalized]

    cleaned = normalized
    for suffix in ("-external-students", "-students", "internships", "-jobs"):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    cleaned = cleaned.replace("-", " ").strip()
    if not cleaned:
        return clean_title(slug.replace("-", " "))
    return clean_title(cleaned.title())


def prefer_title(current: str, candidate: str) -> str:
    if is_better_title(candidate, current):
        return candidate
    return current


def prefer_company(current: str, candidate: str) -> str:
    if is_better_company(candidate, current):
        return candidate
    return current


def prefer_location(current: str, candidate: str) -> str:
    if is_missing_location(current) and not is_missing_location(candidate):
        return candidate
    return current


def is_better_title(candidate: str, current: str) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    if JOB_APPLICATION_TITLE_RE.match(current):
        return True
    if current.startswith("Job Application for"):
        return True
    return len(candidate) < len(current) and " at " in current


def is_better_company(candidate: str, current: str) -> bool:
    if not candidate:
        return False
    if is_missing_company(current):
        return True
    if is_missing_company(candidate):
        return False
    if current in {candidate, candidate.title()}:
        return False
    if len(candidate) > len(current) and not is_missing_company(candidate):
        return True
    return False


def is_missing_company(value: str) -> bool:
    if not str(value).strip():
        return True
    cleaned = clean_title(value).lower()
    return cleaned in ELLIPSIS_COMPANY_MARKERS or cleaned in {"unknown company", "untitled posting"}


def is_missing_location(value: str) -> bool:
    if not str(value).strip():
        return True
    return clean_title(value).lower() in {"unknown", "untitled posting"}


def fetch_json_request(url: str) -> dict:
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
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if isinstance(payload, dict):
        return payload
    return {}


def clear_posting_metadata_cache() -> None:
    _LOCATION_CACHE.clear()
