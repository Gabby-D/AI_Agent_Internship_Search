import json

from internship_search.email_summary import write_sent_history
from internship_search.fit_scoring import ScoredPosting, write_scored_postings_jsonl
from internship_search.job_collector import JobPosting, write_postings_jsonl
from internship_search.posting_filter import FilteredPosting, write_filtered_postings_jsonl
from internship_search.review_state import (
    ReviewFilters,
    ReviewablePosting,
    classify_email_status,
    filter_review_postings,
    load_review_dashboard,
    load_ui_preferences,
    matches_location_filter,
    parse_review_filters,
    read_posting_reviews,
    save_ui_preferences,
    set_posting_review,
)
from internship_search.review_ui import is_address_in_use, render_review_page
from internship_search.source_registry import CompanySource, write_source_registry


def make_filtered_posting(
    *,
    title: str = "2027 Summer Intern",
    company: str = "Connected Co",
    included: bool = True,
    url: str = "https://example.com/jobs/1",
) -> FilteredPosting:
    return FilteredPosting(
        title=title,
        company=company,
        location="Remote",
        posting_url=url,
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        included=included,
        reasons=["Mentions internship terms: intern."],
    )


def make_scored_posting(url: str = "https://example.com/jobs/1") -> ScoredPosting:
    return ScoredPosting(
        title="2027 Summer Intern",
        company="Connected Co",
        location="Remote",
        posting_url=url,
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        score=80,
        fit_level="strong",
        provider="local_rule_based",
        explanations=["Company has a known connection."],
        gaps=["Deadline is unknown."],
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


def write_private_inputs(private_dir):
    private_dir.mkdir(parents=True, exist_ok=True)
    (private_dir / "list_of_companies.md").write_text(
        "# List of Companies\n\n"
        "| Name | Website | I know someone in the company |\n"
        "|------|---------|-------------------------------|\n"
        "| Connected Co | https://example.com | yes |\n",
        encoding="utf-8",
    )
    (private_dir / "preferences.md").write_text(
        "# Preferences\n"
        "## Things I like\n"
        "1. Paid position\n"
        "## Things I don't like\n"
        "1. marketing\n",
        encoding="utf-8",
    )
    (private_dir / "mcgill_class_list.md").write_text(
        "# McGill Course List\n"
        "## Program\n"
        "- **Major:** Mathematics and Statistics for Management\n"
        "## Management Core Courses\n"
        "- **MGCR 211:** Introduction to Financial Accounting\n",
        encoding="utf-8",
    )


def test_set_posting_review_writes_and_clears_status(tmp_path):
    reviews_path = tmp_path / "posting_reviews.json"
    entry = set_posting_review(
        posting_url="https://example.com/jobs/1",
        status="interested",
        output_path=reviews_path,
    )

    assert entry.status == "interested"
    assert read_posting_reviews(reviews_path) == {"https://example.com/jobs/1": "interested"}

    set_posting_review(
        posting_url="https://example.com/jobs/1",
        status="",
        output_path=reviews_path,
    )
    assert read_posting_reviews(reviews_path) == {}


def test_save_ui_preferences_writes_likes_and_dislikes(tmp_path):
    output_path = tmp_path / "ui_preferences.json"
    save_ui_preferences(
        likes=["Paid position", "Bay Area"],
        dislikes=["marketing"],
        output_path=output_path,
    )

    raw = json.loads(output_path.read_text(encoding="utf-8"))
    assert raw["likes"] == ["Paid position", "Bay Area"]
    assert raw["dislikes"] == ["marketing"]


def test_load_review_dashboard_includes_scores_and_review_status(tmp_path):
    data_dir = tmp_path / "data"
    private_dir = tmp_path / "private"
    write_private_inputs(private_dir)

    write_filtered_postings_jsonl(
        [make_filtered_posting()],
        data_dir / "filtered_postings.jsonl",
    )
    write_filtered_postings_jsonl(
        [make_filtered_posting(title="Marketing Intern", included=False, url="https://example.com/jobs/2")],
        data_dir / "excluded_postings.jsonl",
    )
    write_scored_postings_jsonl([make_scored_posting()], data_dir / "scored_postings.jsonl")
    write_source_registry([make_source()], data_dir / "source_registry.json")
    write_postings_jsonl(
        [make_job_posting(url="https://example.com/jobs/1")],
        data_dir / "new_postings.jsonl",
    )
    write_sent_history({"https://example.com/jobs/3"}, data_dir / "email_sent_history.json")
    set_posting_review(
        posting_url="https://example.com/jobs/1",
        status="needs_follow_up",
        output_path=data_dir / "posting_reviews.json",
    )

    dashboard = load_review_dashboard(data_dir, private_dir)
    included = next(item for item in dashboard["postings"] if item["included"])

    assert len(dashboard["postings"]) == 1

    assert included["score"] == 80
    assert included["provider"] == "local_rule_based"
    assert included["review_status"] == "needs_follow_up"
    assert included["has_connection"] is True
    assert included["is_new"] is True
    assert included["email_status"] == "ready"
    assert included["explanations"] == ["Company has a known connection."]
    assert included["gaps"] == ["Deadline is unknown."]
    assert dashboard["summary"]["email_ready"] == 1
    assert dashboard["summary"]["new_postings"] == 1
    assert dashboard["preferences"]["likes"] == ["Paid position"]
    assert "Connected Co" in dashboard["filter_options"]["companies"]


def make_job_posting(url: str = "https://example.com/jobs/1") -> JobPosting:
    return JobPosting(
        title="2027 Summer Intern",
        company="Connected Co",
        location="Remote",
        posting_url=url,
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
    )


def test_classify_email_status_marks_emailed_inactive_and_ready():
    assert classify_email_status(
        included=False,
        scored=False,
        posting_url="https://example.com/jobs/2",
        sent_urls=set(),
        inactive_urls=set(),
    ) == "excluded"
    assert classify_email_status(
        included=True,
        scored=True,
        posting_url="https://example.com/jobs/1",
        sent_urls={"https://example.com/jobs/1"},
        inactive_urls=set(),
    ) == "emailed"
    assert classify_email_status(
        included=True,
        scored=True,
        posting_url="https://example.com/jobs/1",
        sent_urls=set(),
        inactive_urls={"https://example.com/jobs/1"},
    ) == "inactive"
    assert classify_email_status(
        included=True,
        scored=True,
        posting_url="https://example.com/jobs/1",
        sent_urls=set(),
        inactive_urls=set(),
    ) == "ready"


def test_filter_review_postings_supports_status_company_connection_and_email_filters():
    postings = [
        ReviewablePosting(
            title="Analyst Intern",
            company="Connected Co",
            location="Remote",
            posting_url="https://example.com/jobs/1",
            date_collected="2026-07-08",
            included=True,
            score=80,
            fit_level="strong",
            provider="gemini",
            review_status="interested",
            has_connection=True,
            is_new=True,
            email_status="ready",
            explanations=["Strong fit."],
            gaps=[],
        ),
        ReviewablePosting(
            title="Marketing Intern",
            company="Other Co",
            location="Remote",
            posting_url="https://example.com/jobs/2",
            date_collected="2026-07-08",
            included=False,
            score=None,
            fit_level=None,
            provider=None,
            review_status="",
            has_connection=False,
            is_new=False,
            email_status="excluded",
            explanations=[],
            gaps=["Generic page."],
        ),
    ]

    filtered = filter_review_postings(
        postings,
        ReviewFilters(
            review_status="interested",
            company="Connected Co",
            connection="connected",
            email_status="ready",
            included="included",
        ),
    )

    assert [posting.posting_url for posting in filtered] == ["https://example.com/jobs/1"]


def test_filter_review_postings_hides_non_preferred_locations():
    postings = [
        ReviewablePosting(
            title="Bay Area Intern",
            company="Example Co",
            location="San Francisco, CA",
            posting_url="https://example.com/jobs/1",
            date_collected="2026-07-08",
            included=True,
            score=80,
            fit_level="strong",
            provider="local_rule_based",
            review_status="",
            has_connection=False,
            is_new=False,
            email_status="ready",
            explanations=[],
            gaps=[],
        ),
        ReviewablePosting(
            title="NYC Intern",
            company="Other Co",
            location="New York, NY",
            posting_url="https://example.com/jobs/2",
            date_collected="2026-07-08",
            included=True,
            score=70,
            fit_level="moderate",
            provider="local_rule_based",
            review_status="",
            has_connection=False,
            is_new=False,
            email_status="ready",
            explanations=[],
            gaps=[],
        ),
    ]

    filtered = filter_review_postings(postings)

    assert len(filtered) == 1
    assert filtered[0].location == "San Francisco, CA"


def test_filter_review_postings_rejects_title_only_remote_when_location_is_set():
    postings = [
        ReviewablePosting(
            title="Remote Analyst Program",
            company="Other Co",
            location="New York, NY",
            posting_url="https://example.com/jobs/2",
            date_collected="2026-07-08",
            included=True,
            score=70,
            fit_level="moderate",
            provider="local_rule_based",
            review_status="",
            has_connection=False,
            is_new=False,
            email_status="ready",
            explanations=[],
            gaps=[],
        ),
    ]

    filtered = filter_review_postings(postings)

    assert filtered == []


def test_load_review_dashboard_applies_query_style_filters(tmp_path):
    data_dir = tmp_path / "data"
    private_dir = tmp_path / "private"
    write_private_inputs(private_dir)
    write_filtered_postings_jsonl(
        [
            make_filtered_posting(),
            make_filtered_posting(
                title="Other Intern",
                company="Other Co",
                url="https://example.com/jobs/2",
            ),
        ],
        data_dir / "filtered_postings.jsonl",
    )
    write_scored_postings_jsonl(
        [make_scored_posting(), make_scored_posting(url="https://example.com/jobs/2")],
        data_dir / "scored_postings.jsonl",
    )
    write_source_registry(
        [
            make_source(),
            CompanySource(
                company="Other Co",
                website="https://other.example",
                careers_url="https://other.example/careers",
                source_type="company_careers_page",
                origin="seed",
                has_connection=False,
                notes="",
            ),
        ],
        data_dir / "source_registry.json",
    )

    filters = parse_review_filters({"company": ["Connected Co"], "connection": ["connected"]})
    dashboard = load_review_dashboard(data_dir, private_dir, filters=filters)

    assert len(dashboard["postings"]) == 1
    assert dashboard["postings"][0]["company"] == "Connected Co"
    assert dashboard["active_filters"]["company"] == "Connected Co"


def test_load_ui_preferences_prefers_saved_ui_file(tmp_path):
    private_dir = tmp_path / "private"
    write_private_inputs(private_dir)
    save_ui_preferences(
        likes=["Israel opportunities"],
        dislikes=["social media"],
        output_path=tmp_path / "ui_preferences.json",
    )

    preferences = load_ui_preferences(private_dir, tmp_path / "ui_preferences.json")
    assert preferences["source"] == "ui"
    assert preferences["likes"] == ["Israel opportunities"]


def test_load_review_dashboard_skips_stale_non_preferred_locations(tmp_path):
    data_dir = tmp_path / "data"
    private_dir = tmp_path / "private"
    write_private_inputs(private_dir)
    write_filtered_postings_jsonl(
        [
            make_filtered_posting(),
            FilteredPosting(
                title="Atlanta - Tax-JD - Intern - Summer-2027",
                company="PWC",
                location="Atlanta",
                posting_url="https://example.com/jobs/pwc-atlanta",
                date_collected="2026-07-13",
                source_url="https://example.com/careers",
                included=True,
                reasons=["Stale included record."],
            ),
        ],
        data_dir / "filtered_postings.jsonl",
    )
    write_scored_postings_jsonl([make_scored_posting()], data_dir / "scored_postings.jsonl")
    write_source_registry([make_source()], data_dir / "source_registry.json")

    dashboard = load_review_dashboard(data_dir, private_dir)

    assert len(dashboard["postings"]) == 1
    assert dashboard["postings"][0]["company"] == "Connected Co"


def test_render_review_page_includes_dashboard_controls():
    page = render_review_page()
    assert "Internship Review" in page
    assert "/api/dashboard" in page
    assert "To review" in page
    assert "Interested" in page
    assert "Applied" in page
    assert "Ignored" in page
    assert "Needs follow-up" in page
    assert page.index('key: "needs_follow_up"') < page.index('key: "ignored"')
    assert "Job title" in page
    assert "Open posting" in page
    assert "location-policy" in page
    assert "location_policy" in page or "/api/dashboard" in page


def test_is_address_in_use_detects_windows_port_conflict():
    error = OSError("address already in use")
    error.winerror = 10048

    assert is_address_in_use(error) is True
    assert is_address_in_use(OSError("permission denied")) is False
