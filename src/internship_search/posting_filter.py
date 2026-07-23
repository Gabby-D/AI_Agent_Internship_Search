"""Filter posting candidates for likely Summer 2027 internship relevance."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from internship_search.internship_listing import (
    classify_internship_listing,
    listing_category_label,
)
from internship_search.job_collector import JobPosting, read_postings_jsonl
from internship_search.location_filter import LOCATION_FILTER_REASON, matches_allowed_location


INTERNSHIP_TERMS = {
    "intern",
    "internship",
    "summer analyst",
    "summer associate",
    "associate consultant intern",
    "co-op",
    "coop",
}

EARLY_CAREER_TERMS = {
    "campus",
    "early career",
    "entry-level",
    "graduate",
    "program",
    "student",
    "students",
}

TARGET_YEAR_TERMS = {
    "2027",
    "summer 2027",
}

UNDERGRADUATE_ELIGIBILITY_PATTERNS = (
    re.compile(r"\bundergraduate\b", re.IGNORECASE),
    re.compile(r"\bbachelor(?:'s|s)?\b", re.IGNORECASE),
    re.compile(r"\bcollege (?:student|students|degree)\b", re.IGNORECASE),
)

GRADUATE_ONLY_PATTERNS = (
    re.compile(r"\bgraduate (?:degree|program|student|students)\b", re.IGNORECASE),
    re.compile(r"\badvanced graduate\b", re.IGNORECASE),
    re.compile(r"\bpostgraduate\b", re.IGNORECASE),
    re.compile(r"\bmaster(?:'s|s)?\b", re.IGNORECASE),
    re.compile(r"\bmba\b", re.IGNORECASE),
    re.compile(r"\bph\.?d\.?\b", re.IGNORECASE),
    re.compile(r"\bdoctoral\b|\bdoctorate\b", re.IGNORECASE),
    re.compile(r"\bj\.?d\.?\b", re.IGNORECASE),
    re.compile(r"\bll\.?m\.?\b", re.IGNORECASE),
    re.compile(r"\bm\.?d\.?\b", re.IGNORECASE),
    re.compile(r"\blaw (?:school|student|students)\b", re.IGNORECASE),
    re.compile(r"\bmedical (?:school|student|students)\b", re.IGNORECASE),
)

GRADUATE_ONLY_REASON = (
    "Excluded because the role is intended for graduate or advanced-degree students, "
    "not undergraduate applicants."
)


@dataclass(frozen=True)
class FilteredPosting:
    title: str
    company: str
    location: str
    posting_url: str
    date_collected: str
    source_url: str
    included: bool
    reasons: list[str]
    eligibility_text: str = ""


@dataclass(frozen=True)
class FilterResult:
    included: list[FilteredPosting]
    excluded: list[FilteredPosting]
    included_output_path: Path
    excluded_output_path: Path
    monitored_output_path: Path | None = None
    monitored_companies: "list[MonitoredNoOpening] | None" = None


def filter_postings_file(
    input_path: Path | str = "data/postings.jsonl",
    included_output_path: Path | str = "data/filtered_postings.jsonl",
    excluded_output_path: Path | str = "data/excluded_postings.jsonl",
    registry_path: Path | str | None = "data/source_registry.json",
    monitored_output_path: Path | str | None = "data/monitored_no_openings.jsonl",
    collection_errors_path: Path | str | None = "data/collection_errors.jsonl",
) -> FilterResult:
    postings = read_postings_jsonl(input_path)
    return filter_postings(
        postings=postings,
        included_output_path=included_output_path,
        excluded_output_path=excluded_output_path,
        registry_path=registry_path,
        monitored_output_path=monitored_output_path,
        collection_errors_path=collection_errors_path,
    )


def filter_postings(
    postings: list[JobPosting],
    included_output_path: Path | str = "data/filtered_postings.jsonl",
    excluded_output_path: Path | str = "data/excluded_postings.jsonl",
    registry_path: Path | str | None = "data/source_registry.json",
    monitored_output_path: Path | str | None = "data/monitored_no_openings.jsonl",
    collection_errors_path: Path | str | None = "data/collection_errors.jsonl",
) -> FilterResult:
    filtered = [evaluate_posting(posting) for posting in postings]
    included = [posting for posting in filtered if posting.included]
    excluded = [posting for posting in filtered if not posting.included]

    included_path = write_filtered_postings_jsonl(included, included_output_path)
    excluded_path = write_filtered_postings_jsonl(excluded, excluded_output_path)
    clear_stale_scored_postings(included)

    monitored_path = None
    monitored_companies = None
    if registry_path is not None and monitored_output_path is not None:
        from internship_search.monitored_companies import generate_monitored_no_openings_file

        monitored_result = generate_monitored_no_openings_file(
            registry_path=registry_path,
            included=included,
            excluded=excluded,
            postings=postings,
            output_path=monitored_output_path,
            collection_errors_path=collection_errors_path,
        )
        monitored_path = monitored_result.output_path
        monitored_companies = monitored_result.companies

    return FilterResult(
        included=included,
        excluded=excluded,
        included_output_path=included_path,
        excluded_output_path=excluded_path,
        monitored_output_path=monitored_path,
        monitored_companies=monitored_companies,
    )


def evaluate_posting(posting: JobPosting) -> FilteredPosting:
    searchable = build_searchable_text(posting)
    reasons: list[str] = []

    classification = classify_internship_listing(posting.title, posting.posting_url)

    if classification.is_specific:
        reasons.append(
            f"Listing type: {listing_category_label(classification.category)}."
        )
        reasons.extend(classification.reasons)
        if is_graduate_only_posting(posting):
            reasons.append(GRADUATE_ONLY_REASON)
            return to_filtered_posting(posting=posting, included=False, reasons=reasons)
        if not matches_allowed_location(posting.location, posting.title):
            reasons.append(LOCATION_FILTER_REASON)
            return to_filtered_posting(posting=posting, included=False, reasons=reasons)
        target_year_matches = sorted(term for term in TARGET_YEAR_TERMS if term in searchable)
        if target_year_matches:
            reasons.append(f"Mentions target year terms: {', '.join(target_year_matches)}.")
        return to_filtered_posting(posting=posting, included=True, reasons=reasons)

    reasons.append(
        f"Listing type: {listing_category_label(classification.category)}."
    )
    reasons.extend(classification.reasons)
    return to_filtered_posting(posting=posting, included=False, reasons=reasons)


def mentions_internship_terms(searchable: str) -> bool:
    return any(
        term in searchable
        for term in INTERNSHIP_TERMS | EARLY_CAREER_TERMS | TARGET_YEAR_TERMS
    )


def is_graduate_only_posting(posting: JobPosting) -> bool:
    """Return True for advanced-degree roles that are not open to undergraduates."""

    searchable = f"{posting.title} {posting.eligibility_text}".strip()
    if any(pattern.search(searchable) for pattern in UNDERGRADUATE_ELIGIBILITY_PATTERNS):
        return False
    return any(pattern.search(searchable) for pattern in GRADUATE_ONLY_PATTERNS)


def write_filtered_postings_jsonl(
    postings: list[FilteredPosting],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(posting), sort_keys=True) for posting in postings]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def read_filtered_postings_jsonl(path: Path | str) -> list[FilteredPosting]:
    postings_path = Path(path)
    if not postings_path.exists():
        return []

    postings: list[FilteredPosting] = []
    for line in postings_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            postings.append(FilteredPosting(**json.loads(line)))
    return postings


def summarize_filter_result(result: FilterResult) -> str:
    lines = [
        "Posting filter summary",
        "======================",
        f"Included postings: {len(result.included)}",
        f"Excluded postings: {len(result.excluded)}",
        f"Wrote included postings to: {result.included_output_path}",
        f"Wrote excluded postings to: {result.excluded_output_path}",
    ]
    if result.monitored_output_path is not None:
        monitored_count = len(result.monitored_companies or [])
        lines.append(f"Monitored companies with no openings: {monitored_count}")
        lines.append(f"Wrote monitored list to: {result.monitored_output_path}")

    if result.included:
        lines.append("")
        lines.append("Included by company:")
        company_counts: dict[str, int] = {}
        for posting in result.included:
            company_counts[posting.company] = company_counts.get(posting.company, 0) + 1
        lines.extend(
            f"- {company}: {count}"
            for company, count in sorted(company_counts.items())
        )

    return "\n".join(lines)


def build_searchable_text(posting: JobPosting) -> str:
    return " ".join(
        [
            posting.title,
            posting.company,
            posting.location,
            posting.posting_url,
            posting.eligibility_text,
        ]
    ).lower()


def to_filtered_posting(
    posting: JobPosting,
    included: bool,
    reasons: list[str],
) -> FilteredPosting:
    return FilteredPosting(
        title=posting.title,
        company=posting.company,
        location=posting.location,
        posting_url=posting.posting_url,
        date_collected=posting.date_collected,
        source_url=posting.source_url,
        included=included,
        reasons=reasons,
        eligibility_text=posting.eligibility_text,
    )


def clear_stale_scored_postings(
    included: list[FilteredPosting],
    scored_path: Path | str = "data/scored_postings.jsonl",
) -> None:
    """Drop stale scored results when the included set is empty."""

    if included:
        return

    from internship_search.fit_scoring import write_scored_postings_jsonl

    write_scored_postings_jsonl([], scored_path)
