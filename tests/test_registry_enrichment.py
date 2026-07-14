from internship_search.registry_enrichment import (
    company_from_search_query,
    enrich_sources_from_search_results,
    should_replace_careers_url,
)
from internship_search.source_registry import CompanySource


def make_source(careers_url: str) -> CompanySource:
    return CompanySource(
        company="BlackRock",
        website="https://www.blackrock.com",
        careers_url=careers_url,
        source_type="company_careers_page",
        origin="seed",
        has_connection=True,
        notes="Seed source",
    )


def test_company_from_search_query_extracts_company_name():
    assert (
        company_from_search_query("BlackRock summer 2027 internship careers")
        == "BlackRock"
    )


def test_enrich_sources_from_search_results_updates_blackrock_job_url(tmp_path):
    search_path = tmp_path / "internet_search_results.jsonl"
    search_path.write_text(
        "\n".join(
            [
                (
                    '{"title":"2027 Summer Internship Program","url":'
                    '"https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/45831/90628276544",'
                    '"snippet":"Official posting","provider":"duckduckgo_html",'
                    '"query":"BlackRock summer 2027 internship careers",'
                    '"date_searched":"2026-07-09T00:00:00+00:00","relevance_score":40}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    sources = [
        make_source("https://careers.blackrock.com/en/students-and-graduates"),
    ]
    enriched, notes = enrich_sources_from_search_results(sources, search_path)

    assert enriched[0].careers_url.endswith("/90628276544")
    assert "internet-search" in enriched[0].notes
    assert any("BlackRock" in note for note in notes)


def test_should_replace_careers_url_prefers_specific_job_posting():
    assert should_replace_careers_url(
        "https://careers.blackrock.com/en/students-and-graduates",
        "https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/45831/90628276544",
        40,
    )
