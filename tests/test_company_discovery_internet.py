from datetime import datetime, timezone
from pathlib import Path

from internship_search.company_discovery import (
    discover_companies,
    discover_companies_from_internet,
    discovered_company_from_search_result,
    extract_company_name,
)
from internship_search.internet_search import SearchResult
from internship_search.private_inputs import (
    Company,
    Preferences,
    PrivateInputs,
    ProgramInfo,
)
from internship_search.source_registry import CompanySource


def make_private_inputs() -> PrivateInputs:
    return PrivateInputs(
        companies=[
            Company(name="PWC", website="www.pwc.com", has_connection=True),
            Company(name="BlackRock", website="www.blackrock.com", has_connection=True),
        ],
        industries=["financial related", "aerospace and defence", "operations", "geopolitics"],
        preferences=Preferences(
            likes=["Located in the Bay Area or Israel", "Paid position"],
            dislikes=["marketing"],
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


class MockDiscoveryProvider:
    name = "mock_discovery"

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title="Citadel Careers",
                url="https://www.citadel.com/careers/students/",
                snippet="Official careers page for Citadel student internships.",
                provider=self.name,
                query=query,
                date_searched=datetime.now(timezone.utc).isoformat(),
            )
        ]


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
    assert {"JPMorgan Chase", "Lockheed Martin", "Palantir"}.issubset(names)


def test_discover_companies_from_internet_adds_new_company():
    private_inputs = make_private_inputs()
    interest_terms = {"financial", "operations", "aerospace", "geopolitics", "located", "israel", "paid", "position"}
    suggestions, errors = discover_companies_from_internet(
        private_inputs=private_inputs,
        interest_terms=interest_terms,
        disliked_terms={"marketing", "social"},
        existing_names=normalize_existing(),
        provider=MockDiscoveryProvider(),
    )

    assert errors == []
    assert len(suggestions) == 1
    assert suggestions[0].name == "Citadel"
    assert suggestions[0].source == "internet_search:mock_discovery"
    assert suggestions[0].evidence_url == "https://www.citadel.com/careers/students/"


def test_discover_companies_merges_internet_and_curated():
    bundle = discover_companies(
        private_inputs=make_private_inputs(),
        existing_sources=[],
        use_internet=True,
        search_provider=MockDiscoveryProvider(),
    )

    names = {company.name for company in bundle.suggestions}
    assert "Citadel" in names
    assert bundle.internet_suggestions >= 1
    assert bundle.curated_suggestions >= 1


def test_extract_company_name_from_search_result():
    assert extract_company_name(
        "2027 Summer Internship Program - AMERS at BlackRock",
        "https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/",
    ) == "BlackRock"


def test_discovered_company_from_search_result_includes_evidence():
    result = SearchResult(
        title="Citadel Careers",
        url="https://www.citadel.com/careers/students/",
        snippet="Student internships at Citadel.",
        provider="mock",
        query="finance companies summer 2027 internship careers",
        date_searched="2026-07-09T00:00:00+00:00",
        relevance_score=30,
    )
    company = discovered_company_from_search_result(
        result=result,
        interest_terms={"finance", "operations"},
        disliked_terms=set(),
    )

    assert company is not None
    assert company.evidence_title == "Citadel Careers"
    assert company.evidence_snippet == "Student internships at Citadel."


def normalize_existing() -> set[str]:
    return {
        "pwc",
        "blackrock",
        "bain",
        "bakar bio labs",
        "mckinsey & co",
    }
