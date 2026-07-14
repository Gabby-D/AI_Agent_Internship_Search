"""Generate local Markdown review reports for filtered postings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from internship_search.internship_listing import listing_category_label
from internship_search.monitored_companies import (
    read_monitored_no_openings_jsonl,
    render_monitored_no_openings_section,
)
from internship_search.posting_filter import FilteredPosting, read_filtered_postings_jsonl
from internship_search.source_registry import CompanySource, read_source_registry


@dataclass(frozen=True)
class ReviewReport:
    content: str
    output_path: Path


def generate_review_report_file(
    included_path: Path | str = "data/filtered_postings.jsonl",
    excluded_path: Path | str = "data/excluded_postings.jsonl",
    registry_path: Path | str = "data/source_registry.json",
    output_path: Path | str = "data/latest_report.md",
    monitored_path: Path | str | None = "data/monitored_no_openings.jsonl",
) -> ReviewReport:
    """Generate a Markdown report from local filtered posting files."""

    included = read_filtered_postings_jsonl(included_path)
    excluded = read_filtered_postings_jsonl(excluded_path)
    sources = read_source_registry(registry_path)
    monitored = (
        read_monitored_no_openings_jsonl(monitored_path)
        if monitored_path is not None
        else []
    )
    content = render_review_report(
        included=included,
        excluded=excluded,
        sources=sources,
        monitored_no_openings=monitored,
    )
    path = write_review_report(content=content, output_path=output_path)
    return ReviewReport(content=content, output_path=path)


def render_review_report(
    included: list[FilteredPosting],
    excluded: list[FilteredPosting],
    sources: list[CompanySource],
    monitored_no_openings: list | None = None,
) -> str:
    """Render a human-readable Markdown report."""

    connection_by_company = {
        source.company: source.has_connection for source in sources
    }
    included_by_company = group_postings_by_company(included)
    excluded_by_company = group_postings_by_company(excluded)

    lines = [
        "# Internship Search Review",
        "",
        "## Summary",
        "",
        f"- Included postings: {len(included)}",
        f"- Excluded postings: {len(excluded)}",
        f"- Companies with included postings: {len(included_by_company)}",
        f"- Monitored companies with no openings: {len(monitored_no_openings or [])}",
        "",
        "## Included Postings",
        "",
    ]

    if included_by_company:
        for company, postings in included_by_company.items():
            connection_note = (
                "connection available"
                if connection_by_company.get(company, False)
                else "no known connection"
            )
            lines.extend([f"### {company} ({connection_note})", ""])
            for posting in postings:
                lines.extend(render_posting(posting))
    else:
        lines.extend(["No included postings found.", ""])

    lines.extend(render_monitored_no_openings_section(monitored_no_openings or []))

    lines.extend(["## Excluded Summary", ""])
    if excluded_by_company:
        for company, postings in excluded_by_company.items():
            lines.append(f"- {company}: {len(postings)} excluded")
    else:
        lines.append("- No excluded postings.")

    excluded_by_type = group_excluded_by_listing_type(excluded)
    if excluded_by_type:
        lines.extend(["", "## Excluded By Listing Type", ""])
        for listing_type, count in excluded_by_type:
            lines.append(f"- {listing_type}: {count}")

    lines.extend(
        [
            "",
            "## Questions And Missing Information",
            "",
            "- Locations are currently `Unknown` for many postings because collectors still rely on career-page extraction.",
            "- Monitored companies remain on the list until a specific internship listing is found.",
            "- Generic program and search pages are excluded so included results favor actual internship listings.",
            "- Some JavaScript-heavy career sites may still need improved collectors or browser automation.",
            "",
        ]
    )

    return "\n".join(lines)


def render_posting(posting: FilteredPosting) -> list[str]:
    reasons = " ".join(posting.reasons)
    return [
        f"- **{posting.title}**",
        f"  - Location: {posting.location}",
        f"  - Collected: {posting.date_collected}",
        f"  - URL: {posting.posting_url}",
        f"  - Relevance: {reasons}",
        "",
    ]


def write_review_report(content: str, output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n", encoding="utf-8")
    return path


def summarize_review_report(report: ReviewReport) -> str:
    return "\n".join(
        [
            "Review report summary",
            "=====================",
            f"Wrote report to: {report.output_path}",
        ]
    )


def group_postings_by_company(
    postings: list[FilteredPosting],
) -> dict[str, list[FilteredPosting]]:
    grouped: dict[str, list[FilteredPosting]] = {}
    for posting in postings:
        grouped.setdefault(posting.company, []).append(posting)
    return dict(sorted(grouped.items()))


def group_excluded_by_listing_type(
    excluded: list[FilteredPosting],
) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for posting in excluded:
        listing_type = extract_listing_type_label(posting.reasons)
        counts[listing_type] = counts.get(listing_type, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def extract_listing_type_label(reasons: list[str]) -> str:
    for reason in reasons:
        if reason.startswith("Listing type: "):
            return reason.removeprefix("Listing type: ").rstrip(".")
    return listing_category_label("not_internship")
