"""Store posting review status and UI-edited preferences."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from internship_search.email_summary import read_scored_postings_jsonl, read_sent_history
from internship_search.job_collector import read_postings_jsonl
from internship_search.posting_filter import read_filtered_postings_jsonl
from internship_search.posting_history import inactive_posting_urls, read_history
from internship_search.private_inputs import Preferences, load_private_inputs
from internship_search.source_registry import read_source_registry


REVIEW_STATUSES = ("interested", "applied", "ignored", "needs_follow_up")
EMAIL_STATUSES = ("ready", "emailed", "inactive", "not_scored", "excluded")


@dataclass(frozen=True)
class ReviewEntry:
    posting_url: str
    status: str
    updated_at: str


@dataclass(frozen=True)
class ReviewFilters:
    review_status: str | None = None
    company: str | None = None
    connection: str | None = None
    email_status: str | None = None
    included: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class ReviewablePosting:
    title: str
    company: str
    location: str
    posting_url: str
    date_collected: str
    included: bool
    score: int | None
    fit_level: str | None
    provider: str | None
    review_status: str
    has_connection: bool
    is_new: bool
    email_status: str
    explanations: list[str]
    gaps: list[str]


def load_review_dashboard(
    data_dir: Path | str = "data",
    private_dir: Path | str = "private",
    filters: ReviewFilters | None = None,
) -> dict:
    data_path = Path(data_dir)
    scored_by_url = {
        posting.posting_url: posting
        for posting in read_scored_postings_jsonl(data_path / "scored_postings.jsonl")
    }
    reviews = read_posting_reviews(data_path / "posting_reviews.json")
    connection_by_company = {
        source.company: source.has_connection
        for source in read_source_registry(data_path / "source_registry.json")
    }
    sent_urls = read_sent_history(data_path / "email_sent_history.json")
    inactive_urls = inactive_posting_urls(read_history(data_path / "posting_history.json"))
    new_posting_urls = {
        posting.posting_url
        for posting in read_postings_jsonl(data_path / "new_postings.jsonl")
    }

    postings: list[ReviewablePosting] = []
    for filtered in read_filtered_postings_jsonl(data_path / "filtered_postings.jsonl"):
        if not filtered.included:
            continue
        if not posting_matches_location_policy(filtered.location, filtered.title):
            continue
        scored = scored_by_url.get(filtered.posting_url)
        postings.append(
            build_reviewable_posting(
                filtered=filtered,
                included=True,
                scored=scored,
                review_status=reviews.get(filtered.posting_url, ""),
                has_connection=connection_by_company.get(filtered.company, False),
                is_new=filtered.posting_url in new_posting_urls,
                sent_urls=sent_urls,
                inactive_urls=inactive_urls,
            )
        )

    postings.sort(key=review_posting_sort_key)
    filtered_postings = filter_review_postings(postings, filters)
    companies = sorted({posting.company for posting in postings})

    return {
        "postings": [asdict(posting) for posting in filtered_postings],
        "preferences": load_ui_preferences(private_dir, data_path / "ui_preferences.json"),
        "status_options": list(REVIEW_STATUSES),
        "filter_options": {
            "companies": companies,
            "review_statuses": ["any", "not_reviewed", *REVIEW_STATUSES],
            "email_statuses": ["any", *EMAIL_STATUSES],
            "connection_options": ["any", "connected", "no_connection"],
            "included_options": ["included"],
            "location_options": ["preferred"],
        },
        "summary": build_review_summary(filtered_postings),
        "location_policy": (
            "Showing Bay Area, Israel, and fully remote internships only. "
            "If nothing appears below, no matching roles are available right now."
        ),
        "active_filters": asdict(filters or ReviewFilters()),
    }


def build_reviewable_posting(
    *,
    filtered,
    included: bool,
    scored,
    review_status: str,
    has_connection: bool,
    is_new: bool,
    sent_urls: set[str],
    inactive_urls: set[str],
) -> ReviewablePosting:
    return ReviewablePosting(
        title=filtered.title,
        company=filtered.company,
        location=filtered.location,
        posting_url=filtered.posting_url,
        date_collected=filtered.date_collected,
        included=included,
        score=scored.score if scored else None,
        fit_level=scored.fit_level if scored else None,
        provider=scored.provider if scored else None,
        review_status=review_status,
        has_connection=has_connection,
        is_new=is_new,
        email_status=classify_email_status(
            included=included,
            scored=scored is not None,
            posting_url=filtered.posting_url,
            sent_urls=sent_urls,
            inactive_urls=inactive_urls,
        ),
        explanations=scored.explanations if scored else [],
        gaps=scored.gaps if scored else (filtered.reasons if not included else []),
    )


def classify_email_status(
    *,
    included: bool,
    scored: bool,
    posting_url: str,
    sent_urls: set[str],
    inactive_urls: set[str],
) -> str:
    if not included:
        return "excluded"
    if posting_url in sent_urls:
        return "emailed"
    if posting_url in inactive_urls:
        return "inactive"
    if not scored:
        return "not_scored"
    return "ready"


def filter_review_postings(
    postings: list[ReviewablePosting],
    filters: ReviewFilters | None = None,
) -> list[ReviewablePosting]:
    active = filters or ReviewFilters()
    filtered: list[ReviewablePosting] = []
    for posting in postings:
        if not matches_review_status(posting, active.review_status):
            continue
        if active.company and active.company != "any" and posting.company != active.company:
            continue
        if not matches_connection_filter(posting, active.connection):
            continue
        if active.email_status and active.email_status != "any":
            if posting.email_status != active.email_status:
                continue
        if active.included and active.included != "any":
            if active.included == "included" and not posting.included:
                continue
            if active.included == "excluded" and posting.included:
                continue
        if not matches_location_filter(posting, active.location):
            continue
        filtered.append(posting)
    return filtered


def matches_review_status(posting: ReviewablePosting, review_status: str | None) -> bool:
    if not review_status or review_status == "any":
        return True
    if review_status == "not_reviewed":
        return posting.review_status == ""
    return posting.review_status == review_status


def matches_connection_filter(posting: ReviewablePosting, connection: str | None) -> bool:
    if not connection or connection == "any":
        return True
    if connection == "connected":
        return posting.has_connection
    if connection == "no_connection":
        return not posting.has_connection
    return True


def matches_location_filter(posting: ReviewablePosting, location: str | None) -> bool:
    return posting_matches_location_policy(posting.location, posting.title)


def posting_matches_location_policy(location: str, title: str) -> bool:
    from internship_search.location_filter import matches_allowed_location

    return matches_allowed_location(location, title)


def build_review_summary(postings: list[ReviewablePosting]) -> dict[str, int]:
    return {
        "total": len(postings),
        "included": sum(1 for posting in postings if posting.included),
        "excluded": sum(1 for posting in postings if not posting.included),
        "connected": sum(1 for posting in postings if posting.has_connection),
        "email_ready": sum(1 for posting in postings if posting.email_status == "ready"),
        "emailed": sum(1 for posting in postings if posting.email_status == "emailed"),
        "new_postings": sum(1 for posting in postings if posting.is_new),
        "not_reviewed": sum(1 for posting in postings if posting.review_status == ""),
    }


def review_posting_sort_key(posting: ReviewablePosting) -> tuple:
    return (
        posting.review_status == "",
        not posting.included,
        posting.email_status != "ready",
        -(posting.score or 0),
        posting.company,
        posting.title,
    )


def parse_review_filters(query: dict[str, list[str]]) -> ReviewFilters:
    return ReviewFilters(
        review_status=first_query_value(query, "review_status"),
        company=first_query_value(query, "company"),
        connection=first_query_value(query, "connection"),
        email_status=first_query_value(query, "email_status"),
        included=first_query_value(query, "included"),
        location=first_query_value(query, "location"),
    )


def first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key, [])
    if not values:
        return None
    value = values[0].strip()
    return value or None


def load_ui_preferences(
    private_dir: Path | str = "private",
    preferences_path: Path | str = "data/ui_preferences.json",
) -> dict:
    path = Path(preferences_path)
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            "likes": raw.get("likes", []),
            "dislikes": raw.get("dislikes", []),
            "source": "ui",
        }

    private_inputs = load_private_inputs(private_dir)
    return {
        "likes": private_inputs.preferences.likes,
        "dislikes": private_inputs.preferences.dislikes,
        "source": "private",
    }


def save_ui_preferences(
    likes: list[str],
    dislikes: list[str],
    output_path: Path | str = "data/ui_preferences.json",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "likes": [item.strip() for item in likes if item.strip()],
        "dislikes": [item.strip() for item in dislikes if item.strip()],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def read_posting_reviews(path: Path | str) -> dict[str, str]:
    reviews_path = Path(path)
    if not reviews_path.exists():
        return {}

    raw = json.loads(reviews_path.read_text(encoding="utf-8"))
    return {
        posting_url: entry["status"]
        for posting_url, entry in raw.get("reviews", {}).items()
    }


def set_posting_review(
    posting_url: str,
    status: str,
    output_path: Path | str = "data/posting_reviews.json",
) -> ReviewEntry:
    normalized_status = status.strip().lower()
    if normalized_status and normalized_status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {"reviews": {}}
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))

    updated_at = datetime.now(timezone.utc).isoformat()
    if normalized_status:
        raw.setdefault("reviews", {})[posting_url] = {
            "status": normalized_status,
            "updated_at": updated_at,
        }
    else:
        raw.setdefault("reviews", {}).pop(posting_url, None)

    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return ReviewEntry(
        posting_url=posting_url,
        status=normalized_status,
        updated_at=updated_at,
    )


def preferences_from_payload(payload: dict) -> Preferences:
    likes = payload.get("likes", [])
    dislikes = payload.get("dislikes", [])
    if not isinstance(likes, list) or not isinstance(dislikes, list):
        raise ValueError("Preferences payload must include likes and dislikes lists.")
    return Preferences(
        likes=[str(item) for item in likes],
        dislikes=[str(item) for item in dislikes],
    )
