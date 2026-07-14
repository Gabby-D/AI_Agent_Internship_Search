from internship_search.posting_filter import FilteredPosting, write_filtered_postings_jsonl
from internship_search.review_report import (
    generate_review_report_file,
    render_review_report,
)
from internship_search.source_registry import CompanySource, write_source_registry


def make_filtered_posting(
    *,
    company: str = "Example Co",
    included: bool = True,
) -> FilteredPosting:
    return FilteredPosting(
        title="2027 Summer Intern",
        company=company,
        location="Unknown",
        posting_url="https://example.com/jobs/1",
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        included=included,
        reasons=["Listing type: Specific internship listing.", "Title includes a target internship year."],
    )


def make_source(company: str = "Example Co", has_connection: bool = True) -> CompanySource:
    return CompanySource(
        company=company,
        website="https://example.com",
        careers_url="https://example.com/careers",
        source_type="company_careers_page",
        origin="seed",
        has_connection=has_connection,
        notes="Test source",
    )


def test_render_review_report_groups_by_company_and_connection_status():
    report = render_review_report(
        included=[make_filtered_posting(company="Connected Co")],
        excluded=[make_filtered_posting(company="Other Co", included=False)],
        sources=[make_source(company="Connected Co", has_connection=True)],
    )

    assert "# Internship Search Review" in report
    assert "### Connected Co (connection available)" in report
    assert "**2027 Summer Intern**" in report
    assert "- Other Co: 1 excluded" in report
    assert "Excluded By Listing Type" in report
    assert "Monitored Companies (No Openings)" in report
    assert "Questions And Missing Information" in report


def test_generate_review_report_file_writes_markdown(tmp_path):
    included_path = tmp_path / "filtered.jsonl"
    excluded_path = tmp_path / "excluded.jsonl"
    registry_path = tmp_path / "source_registry.json"
    output_path = tmp_path / "latest_report.md"

    write_filtered_postings_jsonl([make_filtered_posting()], included_path)
    write_filtered_postings_jsonl(
        [make_filtered_posting(company="Excluded Co", included=False)],
        excluded_path,
    )
    write_source_registry([make_source()], registry_path)

    report = generate_review_report_file(
        included_path=included_path,
        excluded_path=excluded_path,
        registry_path=registry_path,
        output_path=output_path,
    )

    assert report.output_path == output_path
    assert output_path.exists()
    assert "Included postings: 1" in output_path.read_text(encoding="utf-8")
