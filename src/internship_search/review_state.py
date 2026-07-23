"""Store posting review status and UI-edited preferences."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from internship_search.email_summary import read_scored_postings_jsonl, read_sent_history
from internship_search.job_collector import read_postings_jsonl
from internship_search.location_filter import (
    DEFAULT_LOCATION_PREFERENCES_PATH,
    matches_allowed_location,
    summarize_allowed_locations,
)
from internship_search.monitored_companies import read_collection_errors_jsonl
from internship_search.posting_filter import read_filtered_postings_jsonl
from internship_search.posting_history import inactive_posting_urls, read_history
from internship_search.private_inputs import Preferences, load_private_inputs
from internship_search.source_registry import read_source_registry, normalize_company_name


REVIEW_STATUSES = ("to_review", "applied", "not_interested", "archived")
EMAIL_STATUSES = ("ready", "emailed", "inactive", "not_scored", "excluded")
LEGACY_REVIEW_STATUSES = {
    "": "to_review",
    "interested": "to_review",
    "ignored": "not_interested",
    "needs_follow_up": "to_review",
}


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
class SuggestedCompanyOverview:
    company_name: str
    reason: str
    source: str


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
    summary: str = ""
    highlights: list[str] = field(default_factory=list)
    notes: str = ""
    suggested_company_overview: SuggestedCompanyOverview | None = None


def load_review_dashboard(
    data_dir: Path | str = "data",
    private_dir: Path | str = "private",
    filters: ReviewFilters | None = None,
) -> dict:
    data_path = Path(data_dir)
    private_path = Path(private_dir)
    private_inputs = load_private_inputs(private_path)
    scored_by_url = {
        posting.posting_url: posting
        for posting in read_scored_postings_jsonl(data_path / "scored_postings.jsonl")
    }
    reviews = read_posting_reviews(data_path / "posting_reviews.json")
    notes_by_url = read_posting_notes(data_path / "posting_notes.json")
    registry_path = data_path / "source_registry.json"
    sources = read_source_registry(registry_path) if registry_path.exists() else []
    connection_by_company = {
        source.company: source.has_connection
        for source in sources
    }
    careers_url_by_company = {source.company: source.careers_url for source in sources}
    collected_postings_path = data_path / "postings.jsonl"
    collection_errors_path = data_path / "collection_errors.jsonl"
    has_scan_results = collected_postings_path.exists() or collection_errors_path.exists()
    internship_counts: dict[str, int] = {}
    for posting in read_postings_jsonl(collected_postings_path):
        company_key = normalize_company_name(posting.company)
        internship_counts[company_key] = internship_counts.get(company_key, 0) + 1
    source_issues = {
        normalize_company_name(error.company): error.message
        for error in read_collection_errors_jsonl(collection_errors_path)
    }
    connection_by_company.update(
        {
            company.name: company.has_connection
            for company in private_inputs.companies
        }
    )
    sent_urls = read_sent_history(data_path / "email_sent_history.json")
    inactive_urls = inactive_posting_urls(read_history(data_path / "posting_history.json"))
    new_posting_urls = {
        posting.posting_url
        for posting in read_postings_jsonl(data_path / "new_postings.jsonl")
    }

    # Load suggested and dismissed companies
    dismissed_path = data_path / "company_dismissals.json"
    dismissed_names = set()
    if dismissed_path.exists():
        try:
            dismissed_names = set(json.loads(dismissed_path.read_text(encoding="utf-8")))
        except Exception:
            pass
    dismissed_normalized = {normalize_company_name(name) for name in dismissed_names}

    my_company_names = {normalize_company_name(c.name) for c in private_inputs.companies}

    discovered_path = data_path / "discovered_companies.json"
    discovered_companies = []
    if discovered_path.exists():
        try:
            discovered_companies = json.loads(discovered_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    suggested_by_company = {}
    suggested_companies_list = []
    for item in discovered_companies:
        name = item.get("name", "")
        norm_name = normalize_company_name(name)
        suggested_by_company[norm_name] = item
        if norm_name not in my_company_names and norm_name not in dismissed_normalized:
            suggested_companies_list.append(item)

    location_preferences_path = private_path / "location_preferences.txt"
    postings: list[ReviewablePosting] = []
    source_filtered_postings = read_filtered_postings_jsonl(
        data_path / "filtered_postings.jsonl"
    )
    eligibility_by_url = {
        posting.posting_url: posting.eligibility_text
        for posting in source_filtered_postings
    }
    for filtered in source_filtered_postings:
        if not filtered.included:
            continue
        if not posting_matches_location_policy(
            filtered.location,
            filtered.title,
            preferences_path=location_preferences_path,
            details=filtered.eligibility_text,
        ):
            continue
        scored = scored_by_url.get(filtered.posting_url)
        norm_company = normalize_company_name(filtered.company)
        suggested_overview = None
        if norm_company not in my_company_names and norm_company in suggested_by_company:
            s_info = suggested_by_company[norm_company]
            suggested_overview = SuggestedCompanyOverview(
                company_name=s_info.get("name", filtered.company),
                reason=s_info.get("reason", ""),
                source=s_info.get("source", ""),
            )
        postings.append(
            build_reviewable_posting(
                filtered=filtered,
                included=True,
                scored=scored,
                review_status=normalize_review_status(reviews.get(filtered.posting_url, "")),
                has_connection=connection_by_company.get(filtered.company, False),
                is_new=filtered.posting_url in new_posting_urls,
                sent_urls=sent_urls,
                inactive_urls=inactive_urls,
                notes=notes_by_url.get(filtered.posting_url, ""),
                suggested_company_overview=suggested_overview,
            )
        )

    postings.sort(key=review_posting_sort_key)
    filtered_postings = filter_review_postings(
        postings,
        filters,
        preferences_path=location_preferences_path,
        enforce_location=False,
    )
    companies = sorted({posting.company for posting in postings})

    posting_payloads = []
    for posting in filtered_postings:
        payload = asdict(posting)
        display_location = summarize_allowed_locations(
            posting.location,
            preferences_path=location_preferences_path,
            details=eligibility_by_url.get(posting.posting_url, ""),
        )
        payload["location"] = display_location
        if display_location != posting.location:
            payload["summary"] = payload["summary"].replace(
                posting.location, display_location
            )
            payload["highlights"] = [
                highlight.replace(posting.location, display_location)
                for highlight in payload["highlights"]
            ]
        posting_payloads.append(payload)

    return {
        "postings": posting_payloads,
        "preferences": {
            "likes": private_inputs.preferences.likes,
            "dislikes": private_inputs.preferences.dislikes,
            "source": "private",
        },
        "activity": read_activity_log(data_path / "activity_log.jsonl"),
        "monitored_companies": [
            {
                "name": company.name,
                "website": company.website,
                "careers_url": careers_url_by_company.get(company.name, company.website),
                "has_connection": company.has_connection,
                "connection_name": company.connection_name,
                "internships_found": internship_counts.get(
                    normalize_company_name(company.name),
                    0,
                ),
                "source_issue": source_issues.get(
                    normalize_company_name(company.name),
                    "",
                ),
                "has_scan_results": has_scan_results,
            }
            for company in private_inputs.companies
        ],
        "suggested_companies": suggested_companies_list,
        "industries": private_inputs.industries,
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
            "Showing roles that match the user's preference of location, plus fully remote roles. "
            "If nothing appears below, no matching roles are available right now."
        ),
        "active_filters": asdict(filters or ReviewFilters()),
    }


def extract_deadline_from_text(text: str) -> str | None:
    if not text:
        return None
    text_lower = text.lower()
    patterns = [
        r"(?:deadline|apply by|apply before|before|due date|due|by)[:\s]+([a-zA-Z]+\s+\d+(?:st|nd|rd|th)?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
        r"\b([a-zA-Z]+\s+\d+(?:st|nd|rd|th)?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+deadline\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1).strip().title()
    return None


def build_factual_posting_summary(posting, notes: str = "") -> str:
    loc_lower = (posting.location or "").lower()
    title_lower = (posting.title or "").lower()
    
    if not posting.location or posting.location.strip() in {"", "Unknown", "unknown"}:
        location_val = "Unknown"
        work_arrangement = "Unknown"
    else:
        location_val = posting.location
        if "remote" in loc_lower or "remote" in title_lower:
            work_arrangement = "Remote"
        elif "hybrid" in loc_lower or "hybrid" in title_lower:
            work_arrangement = "Hybrid"
        elif "on-site" in loc_lower or "onsite" in loc_lower or "on site" in loc_lower:
            work_arrangement = "On-site"
        else:
            work_arrangement = "Unknown"

    program = "Unknown"
    if posting.title:
        keywords = [
            "software engineering", "software engineer", "quantitative research", 
            "quantitative trading", "data science", "data scientist", 
            "business operations", "operations analyst", "financial analyst", 
            "investment banking", "operations", "finance", "engineering", "analyst", "mba", "phd", "undergraduate", "graduate"
        ]
        for kw in keywords:
            if kw in title_lower:
                program = kw.title()
                break

    timing = "Unknown"
    if posting.title:
        match = re.search(r"\b(summer|fall|spring|winter)?\s*(202\d)\b", title_lower)
        if match:
            timing = match.group(0).title()

    # Extract deadline if known/accessible
    deadline = extract_deadline_from_text(posting.title)
    if not deadline:
        deadline = extract_deadline_from_text(notes)
    if not deadline:
        deadline = "Unknown"

    lines = [
        f"Role: {posting.title or 'Unknown'}",
        f"Company: {posting.company or 'Unknown'}",
        f"Location: {location_val}",
        f"Work Arrangement: {work_arrangement}",
        f"Program or Team: {program}",
        f"Timing: {timing}",
        "Responsibilities: Unknown (posting body not stored)",
        "Qualifications: Unknown (posting body not stored)",
        f"Application Deadline: {deadline}"
    ]
    return "\n".join(lines)


def build_factual_posting_highlights(posting) -> list[str]:
    highlights = []
    title_lower = (posting.title or "").lower()
    
    if not posting.title:
        highlights.append("Professional internship program opportunity.")
    elif "software" in title_lower or "engineer" in title_lower or "developer" in title_lower:
        highlights.append("Technical role focused on software development / engineering.")
    elif "quantitative" in title_lower or "quant" in title_lower or "trading" in title_lower:
        highlights.append("Quantitative role involving modeling, analysis, or financial markets.")
    elif "data" in title_lower or "analyst" in title_lower or "analytics" in title_lower:
        highlights.append("Data-centric role focused on analysis, reporting, or statistics.")
    elif "operations" in title_lower or "logistics" in title_lower:
        highlights.append("Operations-focused role involving logistics, supply chain, or process optimization.")
    else:
        highlights.append("Professional internship program opportunity.")

    if posting.location:
        loc_lower = posting.location.lower()
        if "remote" in loc_lower:
            highlights.append("Fully remote work arrangement option.")
        elif "hybrid" in loc_lower:
            highlights.append("Hybrid onsite/offsite model.")
        elif posting.location.strip() not in {"", "Unknown", "unknown"}:
            highlights.append(f"Located onsite at {posting.location}.")
        
    return highlights


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
    notes: str,
    suggested_company_overview: SuggestedCompanyOverview | None = None,
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
        summary=build_factual_posting_summary(filtered, notes=notes),
        highlights=build_factual_posting_highlights(filtered),
        notes=notes,
        suggested_company_overview=suggested_company_overview,
    )


def normalize_review_status(status: str) -> str:
    normalized = status.strip().lower()
    return LEGACY_REVIEW_STATUSES.get(normalized, normalized or "to_review")


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
    *,
    preferences_path: Path | str = DEFAULT_LOCATION_PREFERENCES_PATH,
    enforce_location: bool = True,
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
        if enforce_location and not matches_location_filter(
            posting,
            active.location,
            preferences_path=preferences_path,
        ):
            continue
        filtered.append(posting)
    return filtered


def matches_review_status(posting: ReviewablePosting, review_status: str | None) -> bool:
    if not review_status or review_status == "any":
        return True
    return posting.review_status == review_status


def matches_connection_filter(posting: ReviewablePosting, connection: str | None) -> bool:
    if not connection or connection == "any":
        return True
    if connection == "connected":
        return posting.has_connection
    if connection == "no_connection":
        return not posting.has_connection
    return True


def matches_location_filter(
    posting: ReviewablePosting,
    location: str | None,
    *,
    preferences_path: Path | str = DEFAULT_LOCATION_PREFERENCES_PATH,
) -> bool:
    return posting_matches_location_policy(
        posting.location,
        posting.title,
        preferences_path=preferences_path,
    )


def posting_matches_location_policy(
    location: str,
    title: str,
    *,
    preferences_path: Path | str = DEFAULT_LOCATION_PREFERENCES_PATH,
    details: str = "",
) -> bool:
    return matches_allowed_location(
        location,
        title,
        preferences_path=preferences_path,
        details=details,
    )


def build_review_summary(postings: list[ReviewablePosting]) -> dict[str, int]:
    return {
        "total": len(postings),
        "included": sum(1 for posting in postings if posting.included),
        "excluded": sum(1 for posting in postings if not posting.included),
        "connected": sum(1 for posting in postings if posting.has_connection),
        "email_ready": sum(1 for posting in postings if posting.email_status == "ready"),
        "emailed": sum(1 for posting in postings if posting.email_status == "emailed"),
        "new_postings": sum(1 for posting in postings if posting.is_new),
        "to_review": sum(1 for posting in postings if posting.review_status == "to_review"),
    }


def review_posting_sort_key(posting: ReviewablePosting) -> tuple:
    return (
        posting.review_status == "to_review",
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


def append_activity_log(
    action: str,
    subject: str,
    details: dict | None = None,
    output_path: Path | str = "data/activity_log.jsonl",
) -> Path:
    """Append a dated local audit event for a user action."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    event = {
        "timestamp": timestamp.isoformat(),
        "date": timestamp.date().isoformat(),
        "action": action,
        "subject": subject,
        "details": details or {},
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    return path


def get_activity_type(action: str) -> str:
    action = str(action or "").strip()
    if action == "opportunity_status_updated":
        return "posting status"
    elif action == "posting_note_updated":
        return "note edit"
    elif action in {"company_list_updated", "company_suggestion_dismissed"}:
        return "company edit"
    elif action in {"reference_file_updated", "reference_attachment_uploaded", "reference_attachment_deleted"}:
        return "file upload"
    elif action == "collection":
        return "collection"
    elif action == "scoring":
        return "scoring"
    elif action == "email":
        return "email"
    elif action == "preferences_updated":
        return "company edit"
    else:
        return "other"


def read_activity_log(
    path: Path | str = "data/activity_log.jsonl",
    limit: int = 1000,
) -> list[dict]:
    log_path = Path(path)
    if not log_path.exists():
        return []
    
    events = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            # Map activity type
            event["activity_type"] = get_activity_type(event.get("action"))
            
            # Extract details
            details = event.get("details", {})
            if not isinstance(details, dict):
                details = {}
            
            # Determine api_invoked (top-level preference)
            if "api_invoked" in event:
                pass
            elif "api_invoked" in details:
                event["api_invoked"] = details["api_invoked"]
            else:
                if event.get("action") == "scoring" and details.get("provider") == "gemini":
                    event["api_invoked"] = True
                else:
                    event["api_invoked"] = False
            
            # Determine cost (top-level preference)
            if "cost" in event:
                pass
            elif "cost" in details:
                event["cost"] = details["cost"]
            else:
                if event.get("api_invoked") and ("total_tokens" in details or "prompt_tokens" in details):
                    tokens = details.get("total_tokens", details.get("prompt_tokens", 0) + details.get("output_tokens", 0))
                    event["cost"] = {
                        "amount": 0.0,
                        "currency": "USD",
                        "basis": f"Gemini API free tier ({tokens} tokens)"
                    }
                else:
                    event["cost"] = {"status": "unavailable"}
            
            events.append(event)
        except Exception:
            pass
            
    return list(reversed(events[-limit:]))


def read_posting_notes(path: Path | str = "data/posting_notes.json") -> dict[str, str]:
    """Read local notes keyed by posting URL."""

    notes_path = Path(path)
    if not notes_path.exists():
        return {}
    raw = json.loads(notes_path.read_text(encoding="utf-8"))
    return {
        posting_url: str(entry.get("notes", ""))
        for posting_url, entry in raw.get("notes", {}).items()
        if isinstance(entry, dict)
    }


def set_posting_note(
    posting_url: str,
    notes: str,
    output_path: Path | str = "data/posting_notes.json",
) -> str:
    """Save or clear a local note for one posting."""

    normalized_url = posting_url.strip()
    if not normalized_url:
        raise ValueError("posting_url is required")
    if not isinstance(notes, str):
        raise ValueError("notes must be a string")
    normalized_notes = notes.strip()
    if len(normalized_notes) > 10_000:
        raise ValueError("notes must be 10,000 characters or fewer")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {"notes": {}}
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.setdefault("notes", {})
    if normalized_notes:
        entries[normalized_url] = {
            "notes": normalized_notes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        entries.pop(normalized_url, None)

    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return normalized_notes


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
    normalized_status = normalize_review_status(status)
    if normalized_status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = {"reviews": {}}
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))

    updated_at = datetime.now(timezone.utc).isoformat()
    raw.setdefault("reviews", {})[posting_url] = {
        "status": normalized_status,
        "updated_at": updated_at,
    }

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
