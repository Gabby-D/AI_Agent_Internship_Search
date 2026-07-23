from internship_search.job_collector import JobPosting
from internship_search.posting_filter import (
    evaluate_posting,
    filter_postings,
)


def make_posting(
    title: str,
    posting_url: str = "https://example.com/jobs/1",
    company: str = "Example Co",
    location: str = "Unknown",
    eligibility_text: str = "",
) -> JobPosting:
    return JobPosting(
        title=title,
        company=company,
        location=location,
        posting_url=posting_url,
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        eligibility_text=eligibility_text,
    )


def test_evaluate_posting_includes_internship():
    result = evaluate_posting(
        make_posting(
            title="2027 Summer Analyst Intern",
            posting_url="https://example.com/jobs/2027-summer-analyst-intern",
            location="San Francisco, CA",
        )
    )

    assert result.included is True
    assert result.reasons[0] == "Listing type: Specific internship listing."
    assert any("target year" in reason for reason in result.reasons)


def test_evaluate_posting_excludes_disliked_marketing_role():
    result = evaluate_posting(make_posting(title="Example Internship", location="Remote"))

    assert result.included is True


def test_evaluate_posting_excludes_unclear_role():
    result = evaluate_posting(make_posting(title="Careers Overview"))

    assert result.included is False
    assert result.reasons[0] == "Listing type: Not an internship listing."


def test_evaluate_posting_excludes_generic_internship_landing_page():
    result = evaluate_posting(
        make_posting(
            title="Internships & Programs",
            posting_url="https://www.bain.com/careers/work-with-us/internships-programs/",
        )
    )

    assert result.included is False
    assert result.reasons[0] == "Listing type: Generic program page."
    assert any("program navigation" in reason for reason in result.reasons)


def test_evaluate_posting_excludes_pwc_search_page():
    result = evaluate_posting(
        make_posting(
            title="Search internships Search and apply to an internship",
            posting_url="https://jobs-us.pwc.com/us/en/entry-level",
            company="PWC",
        )
    )

    assert result.included is False
    assert result.reasons[0] == "Listing type: Generic search page."


def test_evaluate_posting_excludes_blackrock_blog_story():
    result = evaluate_posting(
        make_posting(
            title="Here's Why This Vice President Never Stops Investing in Herself internal mobility",
            posting_url="https://careers.blackrock.com/blog-employee-story",
            company="BlackRock",
        )
    )

    assert result.included is False
    assert result.reasons[0] == "Listing type: Blog or career story."


def test_evaluate_posting_excludes_non_preferred_location():
    result = evaluate_posting(
        make_posting(
            title="2027 Summer Internship Program Amers",
            posting_url="https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/45831/90628276544",
            company="BlackRock",
            location="New York",
        )
    )

    assert result.included is False
    assert any("user's preference of location" in reason for reason in result.reasons)


def test_evaluate_posting_includes_remote_role():
    result = evaluate_posting(
        make_posting(
            title="2027 Summer Internship Program",
            posting_url="https://careers.blackrock.com/job/remote/2027-summer-internship-program/45831/90628276544",
            company="BlackRock",
            location="Remote",
        )
    )

    assert result.included is True


def test_evaluate_posting_excludes_graduate_only_internship():
    result = evaluate_posting(
        make_posting(
            title="Associate Intern",
            location="Remote",
            eligibility_text=(
                "Candidates must be enrolled in an advanced graduate degree "
                "program such as an MBA or PhD."
            ),
        )
    )

    assert result.included is False
    assert any("graduate or advanced-degree" in reason for reason in result.reasons)


def test_evaluate_posting_keeps_role_open_to_undergraduates_and_graduates():
    result = evaluate_posting(
        make_posting(
            title="Business Analyst Intern",
            location="Remote",
            eligibility_text=(
                "Open to undergraduate students and eligible graduate students."
            ),
        )
    )

    assert result.included is True


def test_evaluate_posting_excludes_graduate_program_in_title():
    result = evaluate_posting(
        make_posting(
            title="Global Helpdesk Intern - Graduate Program",
            location="Remote",
        )
    )

    assert result.included is False


def test_evaluate_posting_excludes_graduate_engineer_even_with_bachelors_text():
    result = evaluate_posting(
        make_posting(
            title="Fall 2026 Graduate Engineer Internship/Co-op",
            location="Remote",
            eligibility_text=(
                "Must be enrolled in a graduate program and hold a bachelor's "
                "degree in engineering."
            ),
        )
    )

    assert result.included is False
    assert any("graduate or advanced-degree" in reason for reason in result.reasons)


def test_evaluate_posting_checks_flexible_location_details(monkeypatch):
    observed: dict[str, str] = {}

    def fake_location_match(location, title, preferences_path=None, *, details=None):
        observed["details"] = details
        return "Preferred City" in details

    monkeypatch.setattr(
        "internship_search.posting_filter.matches_allowed_location",
        fake_location_match,
    )

    result = evaluate_posting(
        make_posting(
            title="Fall 2026 Software Engineering Internship/Co-op",
            location="Flexible - Any Company Site",
            eligibility_text="Teams are available in Preferred City.",
        )
    )

    assert result.included is True
    assert observed["details"] == "Teams are available in Preferred City."


def test_evaluate_posting_excludes_jd_internship():
    result = evaluate_posting(
        make_posting(
            title="Tax-JD Intern - Summer 2027",
            location="Remote",
        )
    )

    assert result.included is False
    assert any("graduate or advanced-degree" in reason for reason in result.reasons)


def test_filter_postings_writes_included_and_excluded_outputs(tmp_path):
    postings = [
        make_posting(
            title="2027 Summer Intern",
            posting_url="https://example.com/jobs/1",
            location="San Francisco, CA",
        ),
        make_posting(title="Marketing Internship", posting_url="https://example.com/jobs/2"),
    ]

    result = filter_postings(
        postings=postings,
        included_output_path=tmp_path / "filtered.jsonl",
        excluded_output_path=tmp_path / "excluded.jsonl",
        registry_path=None,
        monitored_output_path=None,
    )

    assert len(result.included) == 1
    assert len(result.excluded) == 1
    assert result.included_output_path.read_text(encoding="utf-8").strip()
    assert result.excluded_output_path.read_text(encoding="utf-8").strip()


def test_clear_stale_scored_postings_writes_empty_file(tmp_path):
    from internship_search.fit_scoring import ScoredPosting, write_scored_postings_jsonl
    from internship_search.posting_filter import clear_stale_scored_postings

    scored_path = tmp_path / "scored_postings.jsonl"
    write_scored_postings_jsonl(
        [
            ScoredPosting(
                title="Atlanta - Tax-JD - Intern",
                company="PWC",
                location="Atlanta",
                posting_url="https://example.com/jobs/pwc",
                date_collected="2026-07-13",
                source_url="https://example.com/careers",
                score=70,
                fit_level="moderate",
                provider="local_rule_based",
                explanations=[],
                gaps=[],
            )
        ],
        scored_path,
    )

    clear_stale_scored_postings([], scored_path)

    assert scored_path.read_text(encoding="utf-8") == ""
