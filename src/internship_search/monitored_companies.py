"""Track monitored companies with no specific internship openings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from internship_search.job_collector import CollectionError, JobPosting
from internship_search.posting_filter import FilteredPosting
from internship_search.source_registry import CompanySource, read_source_registry

MONITORED_STATUS = "monitored_no_openings"


@dataclass(frozen=True)
class MonitoredNoOpening:
    company: str
    website: str
    careers_url: str
    has_connection: bool
    status: str
    reason: str
    candidates_collected: int
    excluded_pages: int
    collection_error: str
    date_checked: str


@dataclass(frozen=True)
class MonitoredNoOpeningsResult:
    companies: list[MonitoredNoOpening]
    output_path: Path


def build_monitored_no_openings(
    sources: list[CompanySource],
    included: list[FilteredPosting],
    excluded: list[FilteredPosting],
    postings: list[JobPosting],
    collection_errors: list[CollectionError] | None = None,
    date_checked: str = "",
) -> list[MonitoredNoOpening]:
    companies_with_openings = {posting.company for posting in included}
    errors_by_company = {
        error.company: error.message for error in (collection_errors or [])
    }
    checked_on = date_checked or latest_collection_date(postings)

    monitored: list[MonitoredNoOpening] = []
    for source in sources:
        if source.company in companies_with_openings:
            continue

        company_postings = [posting for posting in postings if posting.company == source.company]
        company_excluded = [posting for posting in excluded if posting.company == source.company]
        collection_error = errors_by_company.get(source.company, "")

        monitored.append(
            MonitoredNoOpening(
                company=source.company,
                website=source.website,
                careers_url=source.careers_url,
                has_connection=source.has_connection,
                status=MONITORED_STATUS,
                reason=build_no_openings_reason(
                    collection_error=collection_error,
                    candidates_collected=len(company_postings),
                    excluded_pages=len(company_excluded),
                ),
                candidates_collected=len(company_postings),
                excluded_pages=len(company_excluded),
                collection_error=collection_error,
                date_checked=checked_on,
            )
        )

    return sorted(monitored, key=lambda entry: entry.company.lower())


def build_no_openings_reason(
    *,
    collection_error: str,
    candidates_collected: int,
    excluded_pages: int,
) -> str:
    if collection_error:
        return f"Collection failed: {collection_error}"
    if excluded_pages:
        return (
            f"Found {excluded_pages} page(s), but none were specific internship listings."
        )
    if candidates_collected:
        return "Collected candidates did not qualify as specific internship listings."
    return "No internship posting candidates found on the careers source."


def write_monitored_no_openings_jsonl(
    companies: list[MonitoredNoOpening],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(company), sort_keys=True) for company in companies]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def read_monitored_no_openings_jsonl(path: Path | str) -> list[MonitoredNoOpening]:
    monitored_path = Path(path)
    if not monitored_path.exists():
        return []

    companies: list[MonitoredNoOpening] = []
    for line in monitored_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            companies.append(MonitoredNoOpening(**json.loads(line)))
    return companies


def generate_monitored_no_openings_file(
    registry_path: Path | str,
    included: list[FilteredPosting],
    excluded: list[FilteredPosting],
    postings: list[JobPosting],
    output_path: Path | str = "data/monitored_no_openings.jsonl",
    collection_errors_path: Path | str | None = "data/collection_errors.jsonl",
) -> MonitoredNoOpeningsResult:
    sources = read_source_registry(registry_path)
    collection_errors = (
        read_collection_errors_jsonl(collection_errors_path)
        if collection_errors_path is not None
        else []
    )
    companies = build_monitored_no_openings(
        sources=sources,
        included=included,
        excluded=excluded,
        postings=postings,
        collection_errors=collection_errors,
    )
    path = write_monitored_no_openings_jsonl(companies, output_path)
    return MonitoredNoOpeningsResult(companies=companies, output_path=path)


def read_collection_errors_jsonl(path: Path | str) -> list[CollectionError]:
    errors_path = Path(path)
    if not errors_path.exists():
        return []

    errors: list[CollectionError] = []
    for line in errors_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            errors.append(CollectionError(**json.loads(line)))
    return errors


def write_collection_errors_jsonl(
    errors: list[CollectionError],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(error), sort_keys=True) for error in errors]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def summarize_monitored_no_openings(result: MonitoredNoOpeningsResult) -> str:
    lines = [
        "Monitored companies summary",
        "===========================",
        f"Companies with no specific openings: {len(result.companies)}",
        f"Wrote monitored list to: {result.output_path}",
    ]
    if result.companies:
        lines.append("")
        lines.append("Monitored companies:")
        for company in result.companies:
            connection = "connection" if company.has_connection else "no connection"
            lines.append(f"- {company.company} ({connection}): {company.reason}")
    return "\n".join(lines)


def render_monitored_no_openings_section(
    companies: list[MonitoredNoOpening],
) -> list[str]:
    lines = [
        "## Monitored Companies (No Openings)",
        "",
        "These seed companies are still being monitored, but no specific internship listings were found in the latest run.",
        "",
    ]
    if not companies:
        lines.extend(["All monitored companies currently have specific internship listings.", ""])
        return lines

    for company in companies:
        connection_note = (
            "connection available"
            if company.has_connection
            else "no known connection"
        )
        lines.extend(
            [
                f"### {company.company} ({connection_note})",
                "",
                f"- Status: {company.status}",
                f"- Checked: {company.date_checked or 'Unknown'}",
                f"- Careers source: {company.careers_url}",
                f"- Reason: {company.reason}",
                "",
            ]
        )
    return lines


def latest_collection_date(postings: list[JobPosting]) -> str:
    dates = [posting.date_collected for posting in postings if posting.date_collected]
    return max(dates) if dates else ""
