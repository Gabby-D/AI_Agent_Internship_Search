"""Generate weekly email summaries from local posting results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from internship_search.email_delivery import EmailDeliveryResult, deliver_email, summarize_email_delivery
from internship_search.env_loader import get_env, load_env_into_process
from internship_search.fit_scoring import ScoredPosting
from internship_search.job_collector import read_postings_jsonl
from internship_search.source_registry import CompanySource, read_source_registry


def posting_matches_location_policy(location: str, title: str) -> bool:
    from internship_search.location_filter import matches_allowed_location

    return matches_allowed_location(location, title)


@dataclass(frozen=True)
class EmailSummary:
    subject: str
    content: str
    output_path: Path
    sent_history_output_path: Path
    selected_postings: list[ScoredPosting]
    send_status: str
    email_sent: bool
    delivery_result: EmailDeliveryResult | None = None


DEFAULT_RECIPIENT = "gabrielle.dar@gmail.com"


def generate_weekly_email_summary_file(
    scored_path: Path | str = "data/scored_postings.jsonl",
    new_postings_path: Path | str = "data/new_postings.jsonl",
    registry_path: Path | str = "data/source_registry.json",
    output_path: Path | str = "data/weekly_email_summary.md",
    sent_history_path: Path | str = "data/email_sent_history.json",
    history_path: Path | str | None = "data/posting_history.json",
    recipient: str | None = None,
    send: bool = False,
) -> EmailSummary:
    """Generate a local email-ready Markdown summary and optionally send it."""

    load_env_into_process()
    resolved_recipient = resolve_recipient(recipient)
    scored_postings = read_scored_postings_jsonl(scored_path)
    new_posting_urls = {
        posting.posting_url for posting in read_postings_jsonl(new_postings_path)
    }
    sent_history = read_sent_history(sent_history_path)
    sources = read_source_registry(registry_path)
    inactive_urls: set[str] = set()
    if history_path is not None:
        from internship_search.posting_history import inactive_posting_urls, read_history

        inactive_urls = inactive_posting_urls(read_history(history_path))
    selected = select_email_postings(
        scored_postings=scored_postings,
        new_posting_urls=new_posting_urls,
        sent_posting_urls=set(sent_history),
        excluded_urls=inactive_urls,
    )
    subject = build_subject(selected)
    delivery_result: EmailDeliveryResult | None = None
    email_sent = False
    send_status = describe_send_status(send_requested=send, recipient=resolved_recipient)

    if send:
        delivery_result = deliver_email(
            subject=subject,
            body=render_delivery_email_body(
                selected_postings=selected,
                new_posting_urls=new_posting_urls,
                sources=sources,
            ),
            recipient=resolved_recipient,
        )
        email_sent = delivery_result.sent
        send_status = describe_send_status(
            send_requested=True,
            recipient=resolved_recipient,
            delivery_result=delivery_result,
        )

    content = render_weekly_email_summary(
        selected_postings=selected,
        new_posting_urls=new_posting_urls,
        sources=sources,
        subject=subject,
        recipient=resolved_recipient,
        send_status=send_status,
    )
    path = write_email_summary(content, output_path)

    sent_history_output = Path(sent_history_path)
    if email_sent:
        sent_history_output = write_sent_history(
            sent_posting_urls=sent_history | {posting.posting_url for posting in selected},
            output_path=sent_history_path,
        )

    return EmailSummary(
        subject=subject,
        content=content,
        output_path=path,
        sent_history_output_path=sent_history_output,
        selected_postings=selected,
        send_status=send_status,
        email_sent=email_sent,
        delivery_result=delivery_result,
    )


def read_scored_postings_jsonl(path: Path | str) -> list[ScoredPosting]:
    scored_path = Path(path)
    if not scored_path.exists():
        return []

    postings: list[ScoredPosting] = []
    for line in scored_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            postings.append(ScoredPosting(**json.loads(line)))
    return postings


def select_email_postings(
    scored_postings: list[ScoredPosting],
    new_posting_urls: set[str],
    sent_posting_urls: set[str] | None = None,
    excluded_urls: set[str] | None = None,
) -> list[ScoredPosting]:
    sent_urls = sent_posting_urls or set()
    blocked_urls = excluded_urls or set()
    selected = [
        posting
        for posting in scored_postings
        if posting.posting_url not in sent_urls
        and posting.posting_url not in blocked_urls
        and posting_matches_location_policy(posting.location, posting.title)
    ]
    return sorted(
        selected,
        key=lambda posting: (-posting.score, posting.company, posting.title),
    )


def render_weekly_email_summary(
    selected_postings: list[ScoredPosting],
    new_posting_urls: set[str],
    sources: list[CompanySource],
    subject: str,
    recipient: str | None,
    send_status: str,
) -> str:
    connection_by_company = {
        source.company: source.has_connection for source in sources
    }
    grouped = group_by_company_and_fit(selected_postings)
    connected_count = sum(
        1
        for posting in selected_postings
        if connection_by_company.get(posting.company, False)
    )

    lines = [
        "# Weekly Internship Email Summary",
        "",
        f"Subject: {subject}",
        f"Recipient: {recipient or 'Not configured'}",
        f"Send status: {send_status}",
        "",
        "## Summary",
        "",
        f"- Selected postings: {len(selected_postings)}",
        f"- Unsent internships included: {len(selected_postings)}",
        f"- Latest-run new postings included: {count_new_postings(selected_postings, new_posting_urls)}",
        f"- Connected-company postings: {connected_count}",
        "",
        "## Recommended Postings",
        "",
    ]

    if not grouped:
        lines.extend(
            [
                "No unsent new internships are ready for this summary.",
                "",
            ]
        )
    else:
        for company, by_fit in grouped.items():
            connection_note = (
                "connection available"
                if connection_by_company.get(company, False)
                else "no known connection"
            )
            lines.extend([f"### {company} ({connection_note})", ""])
            for fit_level, postings in by_fit.items():
                lines.extend([f"#### {fit_level.title()} Fit", ""])
                for posting in postings:
                    lines.extend(render_email_posting(posting, new_posting_urls))

    lines.extend(render_next_actions(selected_postings, connection_by_company))
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Deadlines are listed as `Not available` until individual posting pages are parsed.",
            "- This summary intentionally excludes postings already included in previous weekly email summaries.",
            "- Sent history is updated only after a successful email send.",
            "",
        ]
    )
    return "\n".join(lines)


def render_delivery_email_body(
    selected_postings: list[ScoredPosting],
    new_posting_urls: set[str],
    sources: list[CompanySource],
) -> str:
    connection_by_company = {
        source.company: source.has_connection for source in sources
    }
    grouped = group_by_company_and_fit(selected_postings)
    lines = [
        "Weekly internship summary",
        "",
        f"Selected postings: {len(selected_postings)}",
        f"Latest-run new postings included: {count_new_postings(selected_postings, new_posting_urls)}",
        "",
        "Recommended postings:",
        "",
    ]

    if not grouped:
        lines.append("No unsent new internships are ready for this summary.")
        return "\n".join(lines)

    for company, by_fit in grouped.items():
        connection_note = (
            "connection available"
            if connection_by_company.get(company, False)
            else "no known connection"
        )
        lines.append(f"{company} ({connection_note})")
        for fit_level, postings in by_fit.items():
            lines.append(f"  {fit_level.title()} fit:")
            for posting in postings:
                new_label = "new in latest run" if posting.posting_url in new_posting_urls else "unsent"
                explanation = " ".join(posting.explanations) or "No explanation available."
                lines.extend(
                    [
                        f"  - {posting.title} ({new_label}, score {posting.score})",
                        f"    Location: {posting.location}",
                        f"    Link: {posting.posting_url}",
                        f"    Fit explanation: {explanation}",
                    ]
                )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_email_posting(
    posting: ScoredPosting,
    new_posting_urls: set[str],
) -> list[str]:
    new_label = "new in latest run" if posting.posting_url in new_posting_urls else "unsent"
    explanation = " ".join(posting.explanations) or "No explanation available."
    gaps = " ".join(posting.gaps) or "No major gaps listed."
    return [
        f"- **{posting.title}** ({new_label}, score {posting.score})",
        f"  - Location: {posting.location}",
        "  - Deadline: Not available",
        f"  - Link: {posting.posting_url}",
        f"  - Fit explanation: {explanation}",
        f"  - Gaps to review: {gaps}",
        "",
    ]


def render_next_actions(
    selected_postings: list[ScoredPosting],
    connection_by_company: dict[str, bool],
) -> list[str]:
    lines = ["## Recommended Next Actions", ""]
    if not selected_postings:
        lines.append("- Re-run collection, filtering, scoring, and new-posting detection next week.")
        return lines

    connected_companies = sorted(
        {
            posting.company
            for posting in selected_postings
            if connection_by_company.get(posting.company, False)
        }
    )
    if connected_companies:
        lines.append(
            "- Ask contacts at connected companies about internship timelines: "
            + ", ".join(connected_companies)
            + "."
        )

    top_posting = max(selected_postings, key=lambda posting: posting.score)
    lines.extend(
        [
            f"- Review the top-scoring role first: {top_posting.company} - {top_posting.title}.",
            "- Open each link to confirm location, deadline, and whether the role is an active posting.",
            "- Save application deadlines once the collector can parse them from individual pages.",
        ]
    )
    return lines


def group_by_company_and_fit(
    postings: list[ScoredPosting],
) -> dict[str, dict[str, list[ScoredPosting]]]:
    grouped: dict[str, dict[str, list[ScoredPosting]]] = {}
    for posting in postings:
        by_fit = grouped.setdefault(posting.company, {})
        by_fit.setdefault(posting.fit_level, []).append(posting)
    return dict(sorted(grouped.items()))


def build_subject(postings: list[ScoredPosting]) -> str:
    if not postings:
        return "Weekly internship summary: no unsent new internships"
    return f"Weekly internship summary: {len(postings)} new internships to review"


def count_new_postings(
    postings: list[ScoredPosting],
    new_posting_urls: set[str],
) -> int:
    return sum(1 for posting in postings if posting.posting_url in new_posting_urls)


def describe_send_status(
    *,
    send_requested: bool,
    recipient: str,
    delivery_result: EmailDeliveryResult | None = None,
) -> str:
    if not send_requested:
        return "Draft only"
    if not recipient:
        return "Draft only, recipient not configured"
    if delivery_result is None:
        return "Send requested"
    if delivery_result.sent:
        return summarize_email_delivery(delivery_result)
    return summarize_email_delivery(delivery_result)


def resolve_recipient(recipient: str | None) -> str:
    load_env_into_process()
    return (recipient or get_env("EMAIL_TO") or DEFAULT_RECIPIENT).strip()


def read_sent_history(path: Path | str) -> set[str]:
    history_path = Path(path)
    if not history_path.exists():
        return set()

    raw = json.loads(history_path.read_text(encoding="utf-8"))
    return set(raw.get("sent_posting_urls", []))


def write_sent_history(sent_posting_urls: set[str], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sent_posting_urls": sorted(sent_posting_urls)}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def write_email_summary(content: str, output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n", encoding="utf-8")
    return path


def summarize_email_summary(summary: EmailSummary) -> str:
    lines = [
        "Weekly email summary",
        "====================",
        f"Subject: {summary.subject}",
        f"Selected postings: {len(summary.selected_postings)}",
        f"Wrote draft to: {summary.output_path}",
        f"Send status: {summary.send_status}",
    ]
    if summary.email_sent:
        lines.append(f"Updated sent history at: {summary.sent_history_output_path}")
    return "\n".join(lines)
