from pathlib import Path

from internship_search.company_discovery import (
    DiscoveredCompany,
    discover_companies,
    merge_discovered_sources,
    render_discovery_report,
    write_discovered_companies,
)
from internship_search.private_inputs import (
    Company,
    Preferences,
    PrivateInputs,
    ProgramInfo,
)
from internship_search.source_registry import CompanySource, read_source_registry


def make_private_inputs() -> PrivateInputs:
    return PrivateInputs(
        companies=[
            Company(name="PWC", website="www.pwc.com", has_connection=True),
            Company(name="BlackRock", website="www.blackrock.com", has_connection=True),
        ],
        industries=["example industry", "research"],
        preferences=Preferences(
            likes=["Preferred location", "Preferred work arrangement"],
            dislikes=["marketing", "social media"],
        ),
        program=ProgramInfo(
            faculty="Desautels Faculty of Management",
            major="Mathematics and Statistics for Management",
            minor_or_concentration="Operations Management",
        ),
        courses=[],
        connections_notes="",
        resume_path=Path("resume.pdf"),
    )


def make_source(company: str = "PWC") -> CompanySource:
    return CompanySource(
        company=company,
        website="https://example.com",
        careers_url="https://example.com/careers",
        source_type="company_careers_page",
        origin="seed",
        has_connection=False,
        notes="Test source",
    )


def test_discover_companies_excludes_existing_seed_companies():
    suggestions = discover_companies(
        private_inputs=make_private_inputs(),
        existing_sources=[make_source("Goldman Sachs")],
        use_internet=False,
    ).suggestions
    names = {suggestion.name for suggestion in suggestions}

    assert "PWC" not in names
    assert "BlackRock" not in names
    assert "Goldman Sachs" not in names
    assert names == set()


def test_render_discovery_report_includes_review_fields():
    suggestion = DiscoveredCompany(
        name="Example Company",
        website="https://example.com",
        careers_url="https://example.com/careers",
        industry_tags=["example industry"],
        reason="Example suggestion.",
        source="test",
        origin="discovered",
        should_add_to_source_registry=True,
        review_status="suggested",
    )
    report = render_discovery_report([suggestion])

    assert "# Discovered Company Suggestions" in report
    assert "Should add to source registry" in report
    assert "Review status: suggested" in report


def test_write_discovered_companies_writes_json(tmp_path):
    suggestions = [DiscoveredCompany(
        name="Example Company",
        website="https://example.com",
        careers_url="https://example.com/careers",
        industry_tags=["example industry"],
        reason="Example suggestion.",
        source="test",
        origin="discovered",
        should_add_to_source_registry=True,
        review_status="suggested",
    )]
    output_path = tmp_path / "discovered_companies.json"

    write_discovered_companies(suggestions[:1], output_path)

    assert output_path.exists()
    assert "careers_url" in output_path.read_text(encoding="utf-8")


def test_merge_discovered_sources_adds_suggestions_without_duplicates(tmp_path):
    suggestions = [
        DiscoveredCompany(
            name=f"Example Company {index}",
            website=f"https://example{index}.com",
            careers_url=f"https://example{index}.com/careers",
            industry_tags=["example industry"],
            reason="Example suggestion.",
            source="test",
            origin="discovered",
            should_add_to_source_registry=True,
            review_status="suggested",
        )
        for index in (1, 2)
    ]
    output_path = tmp_path / "source_registry.json"

    merge_discovered_sources(
        existing_sources=[make_source("PWC")],
        suggestions=suggestions[:2],
        output_path=output_path,
    )
    sources = read_source_registry(output_path)

    assert len(sources) == 3
    assert {source.origin for source in sources} == {"seed", "discovered"}
