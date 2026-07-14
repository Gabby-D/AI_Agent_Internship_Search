from internship_search.email_summary import (
    generate_weekly_email_summary_file,
    read_sent_history,
    render_weekly_email_summary,
    select_email_postings,
)
from internship_search.fit_scoring import ScoredPosting, write_scored_postings_jsonl
from internship_search.job_collector import JobPosting, write_postings_jsonl
from internship_search.source_registry import CompanySource, write_source_registry


def make_scored_posting(
    *,
    title: str = "2027 Summer Analyst Intern",
    company: str = "Connected Co",
    url: str = "https://example.com/jobs/1",
    score: int = 75,
    fit_level: str = "strong",
) -> ScoredPosting:
    return ScoredPosting(
        title=title,
        company=company,
        location="Remote",
        posting_url=url,
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        score=score,
        fit_level=fit_level,
        provider="local_rule_based",
        explanations=["Company has a known connection."],
        gaps=["Deadline is unknown."],
    )


def make_job_posting(url: str = "https://example.com/jobs/1") -> JobPosting:
    return JobPosting(
        title="2027 Summer Analyst Intern",
        company="Connected Co",
        location="Remote",
        posting_url=url,
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
    )


def make_source(company: str = "Connected Co", has_connection: bool = True) -> CompanySource:
    return CompanySource(
        company=company,
        website="https://example.com",
        careers_url="https://example.com/careers",
        source_type="company_careers_page",
        origin="seed",
        has_connection=has_connection,
        notes="Test source",
    )


def test_select_email_postings_includes_all_unsent_postings():
    new_posting = make_scored_posting(url="https://example.com/jobs/new", score=35, fit_level="weak")
    high_priority = make_scored_posting(url="https://example.com/jobs/high", score=60, fit_level="medium")
    already_sent = make_scored_posting(url="https://example.com/jobs/sent", score=90, fit_level="strong")

    selected = select_email_postings(
        scored_postings=[already_sent, new_posting, high_priority],
        new_posting_urls={
            "https://example.com/jobs/new",
            "https://example.com/jobs/sent",
        },
        sent_posting_urls={"https://example.com/jobs/sent"},
    )

    assert [posting.posting_url for posting in selected] == [
        "https://example.com/jobs/high",
        "https://example.com/jobs/new",
    ]


def test_render_weekly_email_summary_groups_roles_and_highlights_connection():
    content = render_weekly_email_summary(
        selected_postings=[make_scored_posting()],
        new_posting_urls={"https://example.com/jobs/1"},
        sources=[make_source()],
        subject="Weekly internship summary: 1 postings to review",
        recipient="gabrielle.dar@gmail.com",
        send_status="Draft only",
    )

    assert "# Weekly Internship Email Summary" in content
    assert "Recipient: gabrielle.dar@gmail.com" in content
    assert "### Connected Co (connection available)" in content
    assert "#### Strong Fit" in content
    assert "Deadline: Not available" in content
    assert "Recommended Next Actions" in content


def test_generate_weekly_email_summary_file_writes_markdown(tmp_path):
    scored_path = tmp_path / "scored.jsonl"
    new_path = tmp_path / "new.jsonl"
    registry_path = tmp_path / "registry.json"
    output_path = tmp_path / "weekly_email_summary.md"
    sent_history_path = tmp_path / "email_sent_history.json"

    write_scored_postings_jsonl([make_scored_posting()], scored_path)
    write_postings_jsonl([make_job_posting()], new_path)
    write_source_registry([make_source()], registry_path)

    summary = generate_weekly_email_summary_file(
        scored_path=scored_path,
        new_postings_path=new_path,
        registry_path=registry_path,
        output_path=output_path,
        sent_history_path=sent_history_path,
    )

    assert summary.output_path == output_path
    assert output_path.exists()
    assert "Selected postings: 1" in output_path.read_text(encoding="utf-8")
    assert read_sent_history(sent_history_path) == set()


def test_generate_weekly_email_summary_file_excludes_previously_sent_postings(tmp_path):
    scored_path = tmp_path / "scored.jsonl"
    new_path = tmp_path / "new.jsonl"
    registry_path = tmp_path / "registry.json"
    output_path = tmp_path / "weekly_email_summary.md"
    sent_history_path = tmp_path / "email_sent_history.json"

    write_scored_postings_jsonl([make_scored_posting()], scored_path)
    write_postings_jsonl([make_job_posting()], new_path)
    write_source_registry([make_source()], registry_path)
    sent_history_path.write_text(
        '{"sent_posting_urls": ["https://example.com/jobs/1"]}\n',
        encoding="utf-8",
    )

    summary = generate_weekly_email_summary_file(
        scored_path=scored_path,
        new_postings_path=new_path,
        registry_path=registry_path,
        output_path=output_path,
        sent_history_path=sent_history_path,
    )

    assert summary.selected_postings == []
    assert "no unsent new internships" in summary.subject
    assert "No unsent new internships are ready" in output_path.read_text(encoding="utf-8")
