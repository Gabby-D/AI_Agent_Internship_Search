"""Classify whether a posting is a specific internship listing or a generic page."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

INTERNSHIP_TERMS = (
    "internship",
    "summer analyst",
    "summer associate",
    "associate consultant intern",
    "co-op",
    "coop",
)

INTERNSHIP_TERM_PATTERNS = (
    re.compile(r"\binternships?\b", re.IGNORECASE),
    re.compile(r"\bintern\b", re.IGNORECASE),
    re.compile(r"\bsummer analyst\b", re.IGNORECASE),
    re.compile(r"\bsummer associate\b", re.IGNORECASE),
    re.compile(r"\bassociate consultant intern\b", re.IGNORECASE),
    re.compile(r"\bco-?op\b", re.IGNORECASE),
)

GENERIC_EXACT_TITLES = {
    "careers",
    "events & programs",
    "find jobs",
    "internships",
    "jobs",
    "students",
    "students & graduates overview",
    "internship program",
    "internship programs",
}

GENERIC_TITLE_FRAGMENTS = (
    "advance internship",
    "analyst relations",
    "campus programs",
    "contract opportunit",
    "explore programs",
    "find a role",
    "golden ticket",
    "internships & programs",
    "join our talent community",
    "learn about our",
    "overview",
    "saved jobs",
    "search and apply",
    "search intern",
    "search opportunit",
    "see programs in",
    "student development programs",
    "student programs quiz",
    "students & graduates",
    "talent community",
    "view programs",
    "why this",
    "work with us",
)

GENERIC_URL_FRAGMENTS = (
    "/campus-programs",
    "/entry-level",
    "/events",
    "/find-a-role",
    "/golden-ticket",
    "/internships-programs",
    "/internships.html",
    "/programs-events",
    "/resources?",
    "/saved-jobs",
    "/search-jobs",
    "/students-and-graduates",
    "/students/",
    "/undergraduate",
    "/work-with-us/",
    "beamery.com",
    "indeed.com/jobs?",
    "indeed.com/q-",
    "linkedin.com/jobs/search",
    "talentexchange.",
)

BLOG_URL_FRAGMENTS = (
    "/blog",
    "/blog-",
    "/career-stories",
    "/life-at-",
)

SPECIFIC_URL_FRAGMENTS = (
    "/job/",
    "/jobs/",
    "/jobs/view/",
    "/opening/",
    "/position/",
    "/viewjob",
    "careersection",
    "gh_jid=",
    "jobid=",
    "jk=",
    "requisition",
    "reqid=",
)

ROLE_TITLE_TERMS = (
    "analyst",
    "associate",
    "consultant",
    "developer",
    "engineer",
    "finance",
    "operations",
    "research",
    "risk",
    "technology",
)

LONG_NARRATIVE_TITLE_WORDS = 12
LISTING_CATEGORIES = {
    "specific_listing",
    "generic_program_page",
    "generic_search_page",
    "blog_or_story",
    "not_internship",
}


@dataclass(frozen=True)
class ListingClassification:
    is_specific: bool
    category: str
    reasons: list[str]


def classify_internship_listing(title: str, url: str) -> ListingClassification:
    """Classify a posting candidate with explicit category and reasons."""

    normalized_title = normalize_text(title)
    normalized_url = url.lower().strip()
    reasons: list[str] = []

    if is_blog_or_story_page(normalized_title, normalized_url):
        reasons.append("URL or title looks like a blog or employee story page.")
        return ListingClassification(
            is_specific=False,
            category="blog_or_story",
            reasons=reasons,
        )

    if not mentions_internship(normalized_title, normalized_url):
        reasons.append("Does not mention internship-related terms.")
        return ListingClassification(
            is_specific=False,
            category="not_internship",
            reasons=reasons,
        )

    generic_reason = generic_page_reason(normalized_title, normalized_url)
    if generic_reason:
        reasons.append(generic_reason)
        category = (
            "generic_search_page"
            if is_search_page(normalized_title, normalized_url)
            else "generic_program_page"
        )
        return ListingClassification(
            is_specific=False,
            category=category,
            reasons=reasons,
        )

    if has_specific_job_url(normalized_url):
        reasons.append("URL points to a specific job posting path.")
        return ListingClassification(
            is_specific=True,
            category="specific_listing",
            reasons=reasons,
        )

    if has_specific_job_title(normalized_title):
        if "2027" in normalized_title or "2026" in normalized_title:
            reasons.append("Title includes a target internship year.")
        elif "summer" in normalized_title and "intern" in normalized_title:
            reasons.append("Title includes a summer internship role.")
        else:
            reasons.append("Title includes a specific internship role.")
        return ListingClassification(
            is_specific=True,
            category="specific_listing",
            reasons=reasons,
        )

    reasons.append(
        "Mentions internships but lacks a specific role title or job posting URL."
    )
    return ListingClassification(
        is_specific=False,
        category="generic_program_page",
        reasons=reasons,
    )


def is_specific_internship_listing(title: str, url: str) -> bool:
    return classify_internship_listing(title, url).is_specific


def mentions_internship(title: str, url: str) -> bool:
    searchable = f"{title} {url}"
    return any(pattern.search(searchable) for pattern in INTERNSHIP_TERM_PATTERNS)


def is_generic_landing_page(title: str, url: str) -> bool:
    return generic_page_reason(title, url) is not None


def generic_page_reason(title: str, url: str) -> str | None:
    if title in GENERIC_EXACT_TITLES:
        return f"Title matches a generic careers page: '{title}'."

    matched_fragment = next(
        (fragment for fragment in GENERIC_TITLE_FRAGMENTS if fragment in title),
        "",
    )
    if matched_fragment:
        return f"Title looks like a program navigation page ('{matched_fragment}')."

    matched_url = next(
        (fragment for fragment in GENERIC_URL_FRAGMENTS if fragment in url),
        "",
    )
    if matched_url and not has_specific_job_url(url):
        return f"URL looks like a general careers page ('{matched_url}')."

    if re.fullmatch(r"(search )?internships?", title):
        return "Title is a generic internships search label."

    if is_long_narrative_title(title) and not has_specific_job_url(url):
        return "Title looks like page copy rather than a job posting title."

    return None


def is_search_page(title: str, url: str) -> bool:
    search_markers = (
        "search intern",
        "search and apply",
        "search opportunit",
        "/search-jobs",
        "/entry-level",
        "keywords=",
    )
    searchable = f"{title} {url}"
    return any(marker in searchable for marker in search_markers)


def is_blog_or_story_page(title: str, url: str) -> bool:
    if any(fragment in url for fragment in BLOG_URL_FRAGMENTS):
        return True
    story_markers = (
        "career story",
        "employee story",
        "why this vice president",
        "never stops investing",
        "life at ",
    )
    return any(marker in title for marker in story_markers)


def is_long_narrative_title(title: str) -> bool:
    return len(title.split()) >= LONG_NARRATIVE_TITLE_WORDS


def has_specific_job_url(url: str) -> bool:
    if any(fragment in url for fragment in BLOG_URL_FRAGMENTS):
        return False
    if "linkedin.com/jobs/search" in url:
        return False
    if "indeed.com/jobs?" in url or "indeed.com/q-" in url:
        return False
    if not any(fragment in url for fragment in SPECIFIC_URL_FRAGMENTS):
        return False

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    if "/job/" in url and path.count("/") >= 3:
        return True
    if "/jobs/" in url and path.endswith("/jobs"):
        return False
    if "linkedin.com/jobs/view/" in url:
        return True
    if "indeed.com/viewjob" in url:
        return True
    if "/jobs/" in url and len(path.split("/")) >= 3:
        return True
    if any(
        marker in url
        for marker in ("jobid=", "requisition", "reqid=", "gh_jid=", "careersection")
    ):
        return True
    return "/opening/" in url or "/position/" in url


def has_specific_job_title(title: str) -> bool:
    if re.search(r"\b20(26|27)\b", title):
        return True
    if re.search(r"\bsummer\b", title) and re.search(r"\bintern", title):
        return len(title.split()) >= 3
    if re.search(r"\bintern", title) and any(
        re.search(rf"\b{re.escape(role)}\b", title) for role in ROLE_TITLE_TERMS
    ):
        return True
    return False


def listing_category_label(category: str) -> str:
    labels = {
        "specific_listing": "Specific internship listing",
        "generic_program_page": "Generic program page",
        "generic_search_page": "Generic search page",
        "blog_or_story": "Blog or career story",
        "not_internship": "Not an internship listing",
    }
    return labels.get(category, category.replace("_", " ").title())


def normalize_text(value: str) -> str:
    return " ".join(value.lower().split())
