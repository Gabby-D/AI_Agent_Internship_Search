from internship_search.posting_filter import FilteredPosting
from internship_search.review_state import (
    build_factual_posting_summary,
    build_factual_posting_highlights
)


def test_summary_with_complete_metadata():
    # Arrangement: Remote, Program: Software Engineering, Timing: Summer 2027
    posting = FilteredPosting(
        title="Software Engineering Summer 2027 Intern",
        company="Tech Giant",
        location="San Francisco, CA (Remote)",
        posting_url="https://techgiant.com/careers/1",
        date_collected="2026-07-16",
        source_url="https://techgiant.com",
        included=True,
        reasons=[]
    )
    
    summary = build_factual_posting_summary(posting)
    expected = (
        "Role: Software Engineering Summer 2027 Intern\n"
        "Company: Tech Giant\n"
        "Location: San Francisco, CA (Remote)\n"
        "Work Arrangement: Remote\n"
        "Program or Team: Software Engineering\n"
        "Timing: Summer 2027\n"
        "Responsibilities: Unknown (posting body not stored)\n"
        "Qualifications: Unknown (posting body not stored)\n"
        "Application Deadline: Unknown"
    )
    assert summary == expected

    highlights = build_factual_posting_highlights(posting)
    assert "Technical role focused on software development / engineering." in highlights
    assert "Fully remote work arrangement option." in highlights


def test_summary_with_sparse_metadata():
    # Empty location and title without program keywords or timing details
    posting = FilteredPosting(
        title="Intern",
        company="",
        location="",
        posting_url="https://example.com/job",
        date_collected="2026-07-16",
        source_url="https://example.com",
        included=True,
        reasons=[]
    )
    
    summary = build_factual_posting_summary(posting)
    expected = (
        "Role: Intern\n"
        "Company: Unknown\n"
        "Location: Unknown\n"
        "Work Arrangement: Unknown\n"
        "Program or Team: Unknown\n"
        "Timing: Unknown\n"
        "Responsibilities: Unknown (posting body not stored)\n"
        "Qualifications: Unknown (posting body not stored)\n"
        "Application Deadline: Unknown"
    )
    assert summary == expected

    highlights = build_factual_posting_highlights(posting)
    assert highlights == ["Professional internship program opportunity."]


def test_work_arrangements_casing():
    # Test Hybrid matching
    posting_hybrid = FilteredPosting(
        title="2027 Hybrid operations intern",
        company="OpCo",
        location="Tel Aviv",
        posting_url="https://opco.com/1",
        date_collected="2026-07-16",
        source_url="https://opco.com",
        included=True,
        reasons=[]
    )
    summary = build_factual_posting_summary(posting_hybrid)
    assert "Work Arrangement: Hybrid" in summary
    assert "Program or Team: Operations" in summary
    assert "Timing: 2027" in summary

    # Test On-site matching
    posting_onsite = FilteredPosting(
        title="Financial Analyst Intern",
        company="Bank",
        location="New York (onsite)",
        posting_url="https://bank.com/1",
        date_collected="2026-07-16",
        source_url="https://bank.com",
        included=True,
        reasons=[]
    )
    summary = build_factual_posting_summary(posting_onsite)
    assert "Work Arrangement: On-site" in summary
    assert "Program or Team: Financial Analyst" in summary
    
    highlights = build_factual_posting_highlights(posting_onsite)
    assert "Located onsite at New York (onsite)." in highlights


def test_deadline_extraction():
    # 1. From title
    posting_title = FilteredPosting(
        title="Operations Intern - Apply by Oct 15",
        company="OpCo",
        location="Tel Aviv",
        posting_url="https://opco.com/1",
        date_collected="2026-07-16",
        source_url="https://opco.com",
        included=True,
        reasons=[]
    )
    summary = build_factual_posting_summary(posting_title)
    assert "Application Deadline: Oct 15" in summary

    # 2. From notes
    posting_notes = FilteredPosting(
        title="Quant Researcher",
        company="HedgeFund",
        location="New York",
        posting_url="https://hf.com/1",
        date_collected="2026-07-16",
        source_url="https://hf.com",
        included=True,
        reasons=[]
    )
    summary = build_factual_posting_summary(posting_notes, notes="Must submit application before Nov 1st!")
    assert "Application Deadline: Nov 1St" in summary or "Application Deadline: Nov 1st" in summary or "Application Deadline: Nov 1St" in summary or "Nov 1st" in summary

