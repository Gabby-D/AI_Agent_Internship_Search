from internship_search.job_collector import JobPosting
from internship_search.posting_history import (
    canonical_posting_id,
    deduplicate_current_postings,
    detect_new_postings,
    read_history,
    role_key,
)


def make_posting(
    *,
    title: str = "2027 Summer Intern",
    company: str = "Example Co",
    location: str = "New York",
    url: str = "https://example.com/jobs/1#details",
    collected: str = "2026-07-08",
    source_url: str = "https://example.com/careers",
) -> JobPosting:
    return JobPosting(
        title=title,
        company=company,
        location=location,
        posting_url=url,
        date_collected=collected,
        source_url=source_url,
    )


def run_detection(tmp_path, postings, history=None):
    return detect_new_postings(
        current_postings=postings,
        existing_history=history or {},
        history_output_path=tmp_path / "posting_history.json",
        changes_output_path=tmp_path / "posting_changes.jsonl",
        new_output_path=tmp_path / "new_postings.jsonl",
    )


def test_canonical_posting_id_removes_fragment():
    assert canonical_posting_id("https://example.com/jobs/1?b=2&a=1#details") == (
        "https://example.com/jobs/1?b=2&a=1"
    )


def test_role_key_normalizes_company_title_and_location():
    assert role_key(make_posting()) == "example co|2027 summer intern|new york"


def test_detect_new_postings_marks_first_run_as_new(tmp_path):
    result = run_detection(tmp_path, [make_posting()])

    assert [change.status for change in result.changes] == ["new"]
    assert len(result.new_postings) == 1
    assert result.history_output_path.exists()


def test_detect_new_postings_marks_repeated_url_as_seen(tmp_path):
    first = run_detection(tmp_path, [make_posting()])
    history = read_history(first.history_output_path)
    second = detect_new_postings(
        current_postings=[make_posting(collected="2026-07-09")],
        existing_history=history,
        history_output_path=tmp_path / "posting_history_2.json",
        changes_output_path=tmp_path / "posting_changes_2.jsonl",
        new_output_path=tmp_path / "new_postings_2.jsonl",
    )

    assert [change.status for change in second.changes] == ["seen"]
    assert second.new_postings == []


def test_detect_new_postings_marks_content_change(tmp_path):
    first = run_detection(tmp_path, [make_posting(title="2027 Summer Intern")])
    history = read_history(first.history_output_path)
    second = detect_new_postings(
        current_postings=[make_posting(title="2027 Summer Analyst Intern")],
        existing_history=history,
        history_output_path=tmp_path / "posting_history_2.json",
        changes_output_path=tmp_path / "posting_changes_2.jsonl",
        new_output_path=tmp_path / "new_postings_2.jsonl",
    )

    assert [change.status for change in second.changes] == ["changed"]
    assert "title changed" in second.changes[0].reason


def test_detect_new_postings_marks_missing_previous_posting(tmp_path):
    first = run_detection(tmp_path, [make_posting()])
    history = read_history(first.history_output_path)
    second = detect_new_postings(
        current_postings=[],
        existing_history=history,
        history_output_path=tmp_path / "posting_history_2.json",
        changes_output_path=tmp_path / "posting_changes_2.jsonl",
        new_output_path=tmp_path / "new_postings_2.jsonl",
    )

    assert [change.status for change in second.changes] == ["missing"]
    assert "likely closed or expired" in second.changes[0].reason
    updated_history = read_history(second.history_output_path)
    assert next(iter(updated_history.values())).active is False


def test_detect_new_postings_deduplicates_current_urls(tmp_path):
    result = run_detection(
        tmp_path,
        [
            make_posting(url="https://example.com/jobs/1#first"),
            make_posting(url="https://example.com/jobs/1#second"),
        ],
    )

    assert [change.status for change in result.changes] == ["new"]
    assert len(result.new_postings) == 1


def test_deduplicate_current_postings_merges_same_role_different_urls():
    deduped = deduplicate_current_postings(
        [
            make_posting(
                url="https://boards.greenhouse.io/example/jobs/123?utm_source=one",
                source_url="job-board://duckduckgo_job_board",
            ),
            make_posting(
                url="https://example.com/careers/jobs/123",
                source_url="https://example.com/careers",
            ),
        ]
    )

    assert len(deduped.postings_by_id) == 1
    assert len(deduped.duplicate_changes) == 1
    assert deduped.duplicate_changes[0].status == "duplicate"


def test_deduplicate_current_postings_prefers_career_page_over_linkedin():
    deduped = deduplicate_current_postings(
        [
            make_posting(
                url="https://www.linkedin.com/jobs/view/999",
                source_url="job-board://duckduckgo_job_board",
                title="2027 Summer Analyst Intern",
                company="Example Capital",
                location="New York, NY",
            ),
            make_posting(
                url="https://boards.greenhouse.io/example/jobs/123",
                source_url="https://example.com/careers",
                title="2027 Summer Analyst Intern",
                company="Example Capital",
                location="New York, NY",
            ),
        ]
    )

    kept = next(iter(deduped.postings_by_id.values()))
    assert "greenhouse.io" in kept.posting_url


def test_detect_new_postings_matches_same_role_at_alternate_url(tmp_path):
    first = run_detection(
        tmp_path,
        [
            make_posting(
                url="https://example.com/careers/jobs/123",
            )
        ],
    )
    history = read_history(first.history_output_path)
    second = detect_new_postings(
        current_postings=[
            make_posting(
                url="https://boards.greenhouse.io/example/jobs/123",
                collected="2026-07-09",
            )
        ],
        existing_history=history,
        history_output_path=tmp_path / "posting_history_2.json",
        changes_output_path=tmp_path / "posting_changes_2.jsonl",
        new_output_path=tmp_path / "new_postings_2.jsonl",
    )

    assert second.new_postings == []
    assert [change.status for change in second.changes] == ["changed"]
    assert "URL changed" in second.changes[0].reason


def test_detect_new_postings_marks_reopened_role(tmp_path):
    first = run_detection(tmp_path, [make_posting()])
    history = read_history(first.history_output_path)
    missing = detect_new_postings(
        current_postings=[],
        existing_history=history,
        history_output_path=tmp_path / "posting_history_missing.json",
        changes_output_path=tmp_path / "posting_changes_missing.jsonl",
        new_output_path=tmp_path / "new_postings_missing.jsonl",
    )
    history = read_history(missing.history_output_path)
    reopened = detect_new_postings(
        current_postings=[make_posting(collected="2026-07-10")],
        existing_history=history,
        history_output_path=tmp_path / "posting_history_reopened.json",
        changes_output_path=tmp_path / "posting_changes_reopened.jsonl",
        new_output_path=tmp_path / "new_postings_reopened.jsonl",
    )

    assert [change.status for change in reopened.changes] == ["changed"]
    assert "reappeared" in reopened.changes[0].reason
    updated_history = read_history(reopened.history_output_path)
    assert next(iter(updated_history.values())).active is True
