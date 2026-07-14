"""LinkedIn and Indeed listing URL normalization, filtering, and parsing."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

LINKEDIN_JOB_VIEW_RE = re.compile(
    r"(?:https?://)?(?:[\w.-]+\.)?linkedin\.com/jobs/view/(\d+)",
    re.IGNORECASE,
)
INDEED_JK_RE = re.compile(r"[?&]jk=([a-z0-9]+)", re.IGNORECASE)

LINKEDIN_INDEED_LIMITATIONS = (
    "LinkedIn and Indeed are searched via public DuckDuckGo site: queries; logged-in listings are not available.",
    "No official LinkedIn or Indeed API is used; coverage depends on what search indexes publicly.",
    "Aggregator URLs are kept when no company career-page URL exists for the same role.",
)


def is_linkedin_listing_url(url: str) -> bool:
    return "linkedin.com/jobs/view/" in url.lower()


def is_indeed_listing_url(url: str) -> bool:
    lowered = url.lower()
    return "indeed.com/viewjob" in lowered or ("indeed.com" in lowered and "jk=" in lowered)


def is_aggregator_listing_url(url: str) -> bool:
    return is_linkedin_listing_url(url) or is_indeed_listing_url(url)


def is_public_aggregator_listing_url(url: str) -> bool:
    lowered = url.lower()
    if "linkedin.com/jobs/search" in lowered:
        return False
    if "indeed.com/jobs?" in lowered or "indeed.com/q-" in lowered:
        return False
    if is_linkedin_listing_url(url):
        return True
    return is_indeed_listing_url(url)


def normalize_linkedin_job_url(url: str) -> str:
    match = LINKEDIN_JOB_VIEW_RE.search(url.strip())
    if not match:
        return url.strip().lower()
    return f"https://www.linkedin.com/jobs/view/{match.group(1)}"


def normalize_indeed_job_url(url: str) -> str:
    stripped = url.strip()
    jk_match = INDEED_JK_RE.search(stripped)
    if jk_match:
        return f"https://www.indeed.com/viewjob?jk={jk_match.group(1).lower()}"

    parsed = urlparse(stripped)
    if "indeed.com" not in parsed.netloc.lower():
        return stripped.lower()
    if "/viewjob" in parsed.path.lower():
        return stripped.split("#", maxsplit=1)[0].rstrip("/").lower()
    return stripped.lower()


def canonical_aggregator_job_url(url: str) -> str | None:
    if is_linkedin_listing_url(url):
        return normalize_linkedin_job_url(url)
    if is_indeed_listing_url(url):
        return normalize_indeed_job_url(url)
    return None


def job_board_platform(url: str) -> str:
    if is_linkedin_listing_url(url):
        return "linkedin"
    if is_indeed_listing_url(url):
        return "indeed"
    lowered = url.lower()
    if "greenhouse.io" in lowered:
        return "greenhouse"
    if "lever.co" in lowered:
        return "lever"
    if "myworkdayjobs.com" in lowered or "workday.com" in lowered:
        return "workday"
    return "other"


def count_job_board_platforms(postings: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for posting in postings:
        platform = job_board_platform(posting.posting_url)
        counts[platform] = counts.get(platform, 0) + 1
    return counts


def build_linkedin_indeed_limitations(
    postings: list,
    *,
    provider_name: str,
) -> list[str]:
    if provider_name not in {"duckduckgo_job_board", "auto"}:
        return []

    limitations = list(LINKEDIN_INDEED_LIMITATIONS)
    counts = count_job_board_platforms(postings)
    if counts.get("linkedin", 0) == 0:
        limitations.append("No LinkedIn listing URLs returned this run.")
    if counts.get("indeed", 0) == 0:
        limitations.append("No Indeed listing URLs returned this run.")
    return limitations
