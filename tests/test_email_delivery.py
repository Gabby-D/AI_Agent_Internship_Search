from internship_search.email_delivery import (
    EmailDeliveryResult,
    SmtpConfig,
    deliver_email,
    get_smtp_config,
)
from internship_search.email_summary import (
    generate_weekly_email_summary_file,
    render_delivery_email_body,
)
from internship_search.fit_scoring import ScoredPosting, write_scored_postings_jsonl
from internship_search.job_collector import JobPosting, write_postings_jsonl
from internship_search.source_registry import CompanySource, write_source_registry


def make_scored_posting() -> ScoredPosting:
    return ScoredPosting(
        title="2027 Summer Analyst Intern",
        company="Connected Co",
        location="Remote",
        posting_url="https://example.com/jobs/1",
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        score=75,
        fit_level="strong",
        provider="local_rule_based",
        explanations=["Company has a known connection."],
        gaps=["Deadline is unknown."],
    )


def make_job_posting() -> JobPosting:
    return JobPosting(
        title="2027 Summer Analyst Intern",
        company="Connected Co",
        location="Remote",
        posting_url="https://example.com/jobs/1",
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
    )


def make_source() -> CompanySource:
    return CompanySource(
        company="Connected Co",
        website="https://example.com",
        careers_url="https://example.com/careers",
        source_type="company_careers_page",
        origin="seed",
        has_connection=True,
        notes="Test source",
    )


def test_get_smtp_config_returns_none_without_credentials(monkeypatch):
    monkeypatch.setattr(
        "internship_search.email_delivery.load_env_into_process",
        lambda path=".env": {},
    )
    monkeypatch.delenv("EMAIL_FROM", raising=False)
    monkeypatch.delenv("EMAIL_SMTP_PASSWORD", raising=False)

    assert get_smtp_config() is None


def test_deliver_email_uses_mock_sender():
    sent_messages: list[tuple[str, str, str]] = []

    def mock_sender(subject: str, body: str, recipient: str, config: SmtpConfig) -> None:
        sent_messages.append((subject, body, recipient))

    config = SmtpConfig(
        host="smtp.example.com",
        port=587,
        username="sender@example.com",
        password="secret",
        from_address="sender@example.com",
    )
    result = deliver_email(
        subject="Weekly internship summary",
        body="One posting to review.",
        recipient="recipient@example.com",
        config=config,
        sender=mock_sender,
    )

    assert result.sent is True
    assert sent_messages == [("Weekly internship summary", "One posting to review.", "recipient@example.com")]


def test_deliver_email_reports_missing_credentials(monkeypatch):
    monkeypatch.setattr(
        "internship_search.email_delivery.get_smtp_config",
        lambda: None,
    )

    result = deliver_email(
        subject="Weekly internship summary",
        body="Body",
        recipient="recipient@example.com",
    )

    assert result.sent is False
    assert "credentials are not configured" in result.error


def test_render_delivery_email_body_includes_posting_links():
    body = render_delivery_email_body(
        selected_postings=[make_scored_posting()],
        new_posting_urls={"https://example.com/jobs/1"},
        sources=[make_source()],
    )

    assert "2027 Summer Analyst Intern" in body
    assert "https://example.com/jobs/1" in body


def test_generate_weekly_email_summary_file_updates_sent_history_only_after_send(tmp_path, monkeypatch):
    scored_path = tmp_path / "scored.jsonl"
    new_path = tmp_path / "new.jsonl"
    registry_path = tmp_path / "registry.json"
    output_path = tmp_path / "weekly_email_summary.md"
    sent_history_path = tmp_path / "email_sent_history.json"

    write_scored_postings_jsonl([make_scored_posting()], scored_path)
    write_postings_jsonl([make_job_posting()], new_path)
    write_source_registry([make_source()], registry_path)

    monkeypatch.setattr(
        "internship_search.email_summary.deliver_email",
        lambda **kwargs: EmailDeliveryResult(sent=True, recipient="recipient@example.com"),
    )

    summary = generate_weekly_email_summary_file(
        scored_path=scored_path,
        new_postings_path=new_path,
        registry_path=registry_path,
        output_path=output_path,
        sent_history_path=sent_history_path,
        send=True,
    )

    assert summary.email_sent is True
    assert "https://example.com/jobs/1" in sent_history_path.read_text(encoding="utf-8")
