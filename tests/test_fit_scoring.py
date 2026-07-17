from pathlib import Path

from internship_search.fit_scoring import (
    score_posting,
    score_postings,
)
from internship_search.posting_filter import FilteredPosting
from internship_search.private_inputs import (
    Course,
    Preferences,
    PrivateInputs,
    ProgramInfo,
)
from internship_search.source_registry import CompanySource


def make_private_inputs() -> PrivateInputs:
    return PrivateInputs(
        companies=[],
        industries=["finance", "operations"],
        preferences=Preferences(
            likes=["Preferred location", "Preferred work arrangement"],
            dislikes=["marketing"],
        ),
        program=ProgramInfo(
            faculty="Desautels Faculty of Management",
            major="Mathematics and Statistics for Management",
            minor_or_concentration="Operations Management",
        ),
        courses=[
            Course(code="MGCR 233", title="Data Programming for Business", category="Core"),
            Course(code="MGSC 373", title="Operations Research", category="Analytics"),
        ],
        connections_notes="",
        resume_path=Path("resume.pdf"),
    )


def make_posting(
    title: str = "2027 Summer Analyst Intern",
    company: str = "Connected Co",
) -> FilteredPosting:
    return FilteredPosting(
        title=title,
        company=company,
        location="Remote",
        posting_url="https://example.com/jobs/2027-summer-analyst-intern",
        date_collected="2026-07-08",
        source_url="https://example.com/careers",
        included=True,
        reasons=["Mentions internship terms: intern."],
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


def test_score_posting_labels_strong_fit_with_connection_and_relevant_terms():
    scored = score_posting(
        posting=make_posting(),
        private_inputs=make_private_inputs(),
        has_connection=True,
    )

    assert scored.score >= 75
    assert scored.fit_level == "strong"
    assert scored.provider == "local_rule_based"
    assert "Company has a known connection." in scored.explanations


def test_score_posting_penalizes_disliked_terms():
    scored = score_posting(
        posting=make_posting(title="Marketing Internship"),
        private_inputs=make_private_inputs(),
        has_connection=False,
    )

    assert scored.score < 50
    assert scored.fit_level == "weak"
    assert any("Penalized disliked terms" in explanation for explanation in scored.explanations)


def test_score_postings_writes_sorted_output(tmp_path):
    postings = [
        make_posting(title="General Internship", company="No Connection Co"),
        make_posting(title="2027 Summer Analyst Intern", company="Connected Co"),
    ]

    result = score_postings(
        postings=postings,
        private_inputs=make_private_inputs(),
        sources=[make_source("Connected Co", True), make_source("No Connection Co", False)],
        output_path=tmp_path / "scored.jsonl",
        provider_name="local",
    )

    assert result.output_path.exists()
    assert result.scored_postings[0].company == "Connected Co"
    assert "score" in result.output_path.read_text(encoding="utf-8")
