import json

from internship_search.email_summary import write_sent_history
from internship_search.fit_scoring import ScoredPosting, write_scored_postings_jsonl
from internship_search.job_collector import JobPosting, write_postings_jsonl
from internship_search.posting_filter import FilteredPosting, write_filtered_postings_jsonl
from internship_search.review_state import (
    ReviewFilters,
    ReviewablePosting,
    append_activity_log,
    classify_email_status,
    filter_review_postings,
    load_review_dashboard,
    load_ui_preferences,
    matches_location_filter,
    parse_review_filters,
    read_posting_reviews,
    read_activity_log,
    read_posting_notes,
    save_ui_preferences,
    set_posting_note,
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


def test_set_posting_review_writes_to_review_status(tmp_path):
    reviews_path = tmp_path / "posting_reviews.json"
    entry = set_posting_review(
        posting_url="https://example.com/jobs/1",
        status="applied",
        output_path=reviews_path,
    )

    assert entry.status == "applied"
    assert read_posting_reviews(reviews_path) == {"https://example.com/jobs/1": "applied"}

    set_posting_review(
        posting_url="https://example.com/jobs/1",
        status="to_review",
        output_path=reviews_path,
    )
    assert read_posting_reviews(reviews_path) == {"https://example.com/jobs/1": "to_review"}


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


def test_activity_log_is_dated_and_newest_first(tmp_path):
    log_path = tmp_path / "activity_log.jsonl"
    append_activity_log("company_list_updated", "company list", {"count": 2}, log_path)
    append_activity_log("opportunity_status_updated", "https://example.com/jobs/1", {}, log_path)

    events = read_activity_log(log_path)

    assert len(events) == 2
    assert events[0]["action"] == "opportunity_status_updated"
    assert events[0]["date"]
    assert events[1]["details"] == {"count": 2}


def test_posting_notes_round_trip_and_clear(tmp_path):
    notes_path = tmp_path / "posting_notes.json"

    saved = set_posting_note(
        "https://example.com/jobs/1",
        "Ask about the team structure.",
        notes_path,
    )

    assert saved == "Ask about the team structure."
    assert read_posting_notes(notes_path) == {
        "https://example.com/jobs/1": "Ask about the team structure."
    }

    set_posting_note("https://example.com/jobs/1", "", notes_path)
    assert read_posting_notes(notes_path) == {}


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
        status="to_review",
        output_path=data_dir / "posting_reviews.json",
    )
    set_posting_note(
        "https://example.com/jobs/1",
        "Follow up after the information session.",
        data_dir / "posting_notes.json",
    )

    dashboard = load_review_dashboard(data_dir, private_dir)
    included = next(item for item in dashboard["postings"] if item["included"])

    assert len(dashboard["postings"]) == 1

    assert included["score"] == 80
    assert included["provider"] == "local_rule_based"
    assert included["review_status"] == "to_review"
    assert included["has_connection"] is True
    assert included["is_new"] is True
    assert included["email_status"] == "ready"
    assert included["explanations"] == ["Company has a known connection."]
    assert included["gaps"] == ["Deadline is unknown."]
    expected_summary = (
        "Role: 2027 Summer Intern\n"
        "Company: Connected Co\n"
        "Location: Remote\n"
        "Work Arrangement: Remote\n"
        "Program or Team: Unknown\n"
        "Timing: 2027\n"
        "Responsibilities: Unknown (posting body not stored)\n"
        "Qualifications: Unknown (posting body not stored)\n"
        "Application Deadline: Unknown"
    )
    assert included["summary"] == expected_summary
    assert included["highlights"] == [
        "Professional internship program opportunity.",
        "Fully remote work arrangement option."
    ]
    assert included["notes"] == "Follow up after the information session."
    assert dashboard["summary"]["email_ready"] == 1
    assert dashboard["summary"]["new_postings"] == 1
    assert dashboard["preferences"]["likes"] == ["Paid position"]
    assert "Connected Co" in dashboard["filter_options"]["companies"]
    assert dashboard["monitored_companies"] == [
        {
            "name": "Connected Co",
            "website": "https://example.com",
            "careers_url": "https://example.com/careers",
            "has_connection": True,
            "connection_name": "",
        }
    ]


def test_load_review_dashboard_uses_live_company_connection_status(tmp_path):
    data_dir = tmp_path / "data"
    private_dir = tmp_path / "private"
    write_private_inputs(private_dir)
    write_filtered_postings_jsonl(
        [make_filtered_posting()],
        data_dir / "filtered_postings.jsonl",
    )
    write_source_registry([make_source()], data_dir / "source_registry.json")

    (private_dir / "list_of_companies.md").write_text(
        "# List of Companies\n\n"
        "| Name | Website | I know someone in the company |\n"
        "|------|---------|-------------------------------|\n"
        "| Connected Co | https://example.com | no |\n"
        "| New Co | https://new.example | yes |\n",
        encoding="utf-8",
    )

    dashboard = load_review_dashboard(data_dir, private_dir)

    assert dashboard["postings"][0]["has_connection"] is False
    assert dashboard["monitored_companies"] == [
        {
            "name": "Connected Co",
            "website": "https://example.com",
            "careers_url": "https://example.com/careers",
            "has_connection": False,
            "connection_name": "",
        },
        {
            "name": "New Co",
            "website": "https://new.example",
            "careers_url": "https://new.example",
            "has_connection": True,
            "connection_name": "",
        },
    ]


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
    assert "Applied" in page
    assert "Not interested" in page
    assert "Archived" in page
    assert page.index('key: "not_interested"') < page.index('key: "archived"')
    assert "Job title" in page
    assert "Open posting" in page
    assert "location-policy" in page
    assert "location_policy" in page or "/api/dashboard" in page
    assert "monitored_companies" in page
    assert "}, 30000);" in page
    assert "Activity log" in page
    assert "/api/companies" in page
    assert "/api/input-file" in page


def test_render_review_page_uses_tabbed_navigation():
    page = render_review_page()

    for tab_id in ("postings", "companies", "preferences", "files", "activity"):
        assert f'data-tab="{tab_id}"' in page
        assert f'id="tab-{tab_id}"' in page
    assert "Reference Files" in page
    assert "switchTab" in page
    assert "initTabs()" in page


def test_render_review_page_shows_connection_indicator_for_postings():
    page = render_review_page()

    assert "Know someone" in page
    assert "posting.has_connection" in page
    assert "badge yes" in page
    assert "badge no" in page


def test_render_review_page_includes_posting_summaries_and_notes():
    page = render_review_page()

    assert "Summary &amp; notes" in page
    assert "Highlights" in page
    assert "Your notes" in page
    assert "/api/note" in page
    assert "data-save-note" in page


def test_is_address_in_use_detects_windows_port_conflict():
    error = OSError("address already in use")
    error.winerror = 10048

    assert is_address_in_use(error) is True
    assert is_address_in_use(OSError("permission denied")) is False


def test_load_review_dashboard_handles_suggestions_and_dismissals(tmp_path):
    data_dir = tmp_path / "data"
    private_dir = tmp_path / "private"
    write_private_inputs(private_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Write suggested companies
    suggestions = [
        {
            "name": "Lockheed Martin",
            "website": "https://www.lockheedmartin.com",
            "careers_url": "https://www.lockheedmartinjobs.com/college-students",
            "industry_tags": ["aerospace"],
            "reason": "Aerospace seed",
            "source": "local_curated_seed",
            "origin": "discovered",
            "should_add_to_source_registry": True,
            "review_status": "suggested"
        },
        {
            "name": "Dismissed Co",
            "website": "https://dismissed.example",
            "careers_url": "https://dismissed.example/careers",
            "industry_tags": ["finance"],
            "reason": "Finance seed",
            "source": "local_curated_seed",
            "origin": "discovered",
            "should_add_to_source_registry": True,
            "review_status": "suggested"
        }
    ]
    (data_dir / "discovered_companies.json").write_text(json.dumps(suggestions), encoding="utf-8")
    
    # 2. Write dismissed companies list
    (data_dir / "company_dismissals.json").write_text(json.dumps(["Dismissed Co"]), encoding="utf-8")
    
    # Write empty files for postings
    write_filtered_postings_jsonl([], data_dir / "filtered_postings.jsonl")
    write_scored_postings_jsonl([], data_dir / "scored_postings.jsonl")
    
    # Load dashboard
    dashboard = load_review_dashboard(data_dir, private_dir)
    
    # Assert Lockheed Martin is suggested, but Dismissed Co is not
    sug_companies = dashboard["suggested_companies"]
    sug_names = {c["name"] for c in sug_companies}
    assert "Lockheed Martin" in sug_names
    assert "Dismissed Co" not in sug_names
    
    # Verify monitored_companies includes connection_name field
    monitored = dashboard["monitored_companies"]
    assert len(monitored) > 0
    assert "connection_name" in monitored[0]

