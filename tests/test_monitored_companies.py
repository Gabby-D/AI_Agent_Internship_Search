from internship_search.job_collector import CollectionError, JobPosting
from internship_search.monitored_companies import (
    build_monitored_no_openings,
    generate_monitored_no_openings_file,
    render_monitored_no_openings_section,
    write_monitored_no_openings_jsonl,
)
from internship_search.posting_filter import FilteredPosting
from internship_search.source_registry import CompanySource, write_source_registry


def make_source(company: str, has_connection: bool = False) -> CompanySource:
    return CompanySource(
        company=company,
        website=f"https://{company.lower().replace(' ', '')}.com",
        careers_url=f"https://{company.lower().replace(' ', '')}.com/careers",
        source_type="company_careers_page",
        origin="seed",
        has_connection=has_connection,
        notes="Test source",
    )


def make_posting(company: str, title: str = "2027 Summer Analyst Intern") -> JobPosting:
    return JobPosting(
        title=title,
        company=company,
        location="Remote",
        posting_url=f"https://example.com/jobs/{company.lower().replace(' ', '-')}",
        date_collected="2026-07-08",
        source_url=f"https://example.com/{company.lower()}/careers",
    )


def make_filtered_posting(company: str, included: bool) -> FilteredPosting:
    return FilteredPosting(
        title="Internships & Programs" if not included else "2027 Summer Analyst Intern",
        company=company,
        location="Unknown",
        posting_url=f"https://example.com/{company.lower()}",
        date_collected="2026-07-08",
        source_url=f"https://example.com/{company.lower()}/careers",
        included=included,
        reasons=["test"],
    )


def test_build_monitored_no_openings_lists_registry_companies_without_included_postings():
    sources = [make_source("Bain"), make_source("PWC", True)]
    included = [make_filtered_posting("BlackRock", True)]
    excluded = [make_filtered_posting("Bain", False)]
    postings = [make_posting("Bain", "Internships & Programs")]

    monitored = build_monitored_no_openings(
        sources=sources,
        included=included,
        excluded=excluded,
        postings=postings,
    )

    assert [entry.company for entry in monitored] == ["Bain", "PWC"]
    assert monitored[0].status == "monitored_no_openings"
    assert "none were specific internship listings" in monitored[0].reason


def test_build_monitored_no_openings_includes_collection_error_reason():
    monitored = build_monitored_no_openings(
        sources=[make_source("McKinsey & Co")],
        included=[],
        excluded=[],
        postings=[],
        collection_errors=[
            CollectionError(
                company="McKinsey & Co",
                source_url="https://www.mckinsey.com/careers",
                message="The read operation timed out",
            )
        ],
    )

    assert monitored[0].collection_error == "The read operation timed out"
    assert "Collection failed" in monitored[0].reason


def test_generate_monitored_no_openings_file_writes_jsonl(tmp_path):
    registry_path = tmp_path / "source_registry.json"
    output_path = tmp_path / "monitored.jsonl"
    write_source_registry([make_source("Bain")], registry_path)

    result = generate_monitored_no_openings_file(
        registry_path=registry_path,
        included=[],
        excluded=[],
        postings=[],
        output_path=output_path,
        collection_errors_path=None,
    )

    assert result.output_path.exists()
    assert len(result.companies) == 1
    assert result.companies[0].company == "Bain"


def test_render_monitored_no_openings_section():
    monitored = build_monitored_no_openings(
        sources=[make_source("Bain")],
        included=[],
        excluded=[],
        postings=[],
    )
    section_text = "\n".join(render_monitored_no_openings_section(monitored))

    assert "## Monitored Companies (No Openings)" in section_text
    assert "### Bain" in section_text
