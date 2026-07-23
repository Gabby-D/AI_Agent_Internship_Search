from internship_search.private_inputs import Company
from internship_search.source_registry import (
    build_company_source,
    build_seed_source_registry,
    normalize_company_name,
    normalize_url,
    read_source_registry,
    write_source_registry,
)


def test_normalize_url_adds_https_when_missing():
    assert normalize_url("www.pwc.com") == "https://www.pwc.com"
    assert normalize_url("https://www.pwc.com") == "https://www.pwc.com"


def test_normalize_company_name_collapses_case_and_spaces():
    assert normalize_company_name("  McKinsey  & Co ") == "mckinsey & co"


def test_build_company_source_uses_known_seed_metadata():
    source = build_company_source(
        Company(name="BlackRock", website="www.blackrock.com", has_connection=True)
    )

    assert source.company == "BlackRock"
    assert source.website == "https://www.blackrock.com"
    assert source.careers_url == "https://careers.blackrock.com/search-jobs"
    assert source.source_type == "company_careers_search"
    assert source.collector == "blackrock_jobs"
    assert source.origin == "seed"
    assert source.has_connection is True


def test_build_company_source_uses_known_seed_metadata_for_pwc():
    source = build_company_source(
        Company(name="PWC", website="www.pwc.com", has_connection=True)
    )

    assert source.careers_url == "https://jobs-us.pwc.com/us/en/search-results?keywords=intern"
    assert source.collector == "pwc_jobs"


def test_build_company_source_uses_complete_mckinsey_api_collector():
    source = build_company_source(
        Company(
            name="McKinsey & Co",
            website="https://www.mckinsey.com",
            has_connection=False,
        )
    )

    assert source.careers_url.startswith(
        "https://www.mckinsey.com/careers/search-jobs"
    )
    assert source.collector == "mckinsey_jobs"


def test_known_companies_use_complete_public_ats_boards():
    expected = {
        "Ansa Bio": "greenhouse.io/ansabiotechnologies",
        "Applied Intuition": "ashbyhq.com/applied",
        "Flexport": "greenhouse.io/flexport",
        "Khan Academy": "greenhouse.io/khanacademy",
        "KoBold Metals": "greenhouse.io/koboldmetals",
        "Palantir": "lever.co/palantir",
        "Patreon": "ashbyhq.com/patreon",
        "Rigetti": "lever.co/rigetti",
        "Robinhood": "greenhouse.io/robinhood",
        "SpaceX": "greenhouse.io/spacex",
        "Stripe": "greenhouse.io/stripe",
    }

    for company_name, expected_url_part in expected.items():
        source = build_company_source(
            Company(
                name=company_name,
                website=f"https://{company_name.lower().replace(' ', '')}.example",
                has_connection=False,
            )
        )
        assert expected_url_part in source.careers_url
        assert source.source_type == "company_careers_search"


def test_retired_or_stale_career_urls_are_replaced_with_current_official_pages():
    expected = {
        "Bank of America": "careers.bankofamerica.com/en-us/students",
        "Boeing": "jobs.boeing.com/category/internship-jobs",
        "Deloitte": "deloitte.com/us/en/careers/internships",
        "DYMO / Newell Brands": "jobs.newellbrands.com",
        "Northrop Grumman": "jobs.northropgrumman.com/careers",
        "Pixar": "jobs.disneycareers.com/search-jobs",
        "RTX": "careers.rtx.com/global/en/search-results",
        "Upside Foods": "upsidefoods.com/careers",
    }

    for company_name, expected_url_part in expected.items():
        source = build_company_source(
            Company(
                name=company_name,
                website="https://stale.example",
                has_connection=False,
            )
        )
        assert expected_url_part in source.careers_url


def test_build_company_source_falls_back_to_website_for_unknown_company():
    source = build_company_source(
        Company(name="Example Co", website="example.com", has_connection=False)
    )

    assert source.careers_url == "https://example.com"
    assert source.source_type == "company_website"
    assert source.origin == "seed"


def test_registry_can_be_written_and_read(tmp_path):
    sources = build_seed_source_registry(
        [
            Company(name="PWC", website="www.pwc.com", has_connection=True),
            Company(name="Bain", website="www.bain.com", has_connection=False),
        ]
    )
    output_path = tmp_path / "source_registry.json"

    write_source_registry(sources, output_path)
    loaded_sources = read_source_registry(output_path)

    assert [source.company for source in loaded_sources] == ["PWC", "Bain"]
    assert loaded_sources[0].origin == "seed"
    assert loaded_sources[1].has_connection is False
