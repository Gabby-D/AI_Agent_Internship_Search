from internship_search.career_collectors import (
    clear_consider_board_cache,
    collect_blackrock_postings,
    collect_consider_board_postings,
    collect_json_ld_postings,
    collect_pwc_postings,
    collect_postings_for_source,
    company_names_match,
    consider_board_empty_warning,
)
from internship_search.source_registry import CompanySource


def make_source(
    company: str = "BlackRock",
    careers_url: str = "https://careers.blackrock.com/search-jobs?keywords=intern",
    collector: str = "blackrock_jobs",
) -> CompanySource:
    return CompanySource(
        company=company,
        website="https://www.blackrock.com",
        careers_url=careers_url,
        source_type="company_careers_search",
        origin="seed",
        has_connection=False,
        notes="",
        collector=collector,
    )


BLACKROCK_HTML = """
<html>
  <body>
    <a href="/job/new-york/2027-summer-internship-program-amers/45831/90628276544">
      2027 Summer Internship Program - AMERS
    </a>
    <a href="/job/new-york/private-asset-market-risk-modeler-vice-president/45831/96346391040">
      Private Asset Market Risk Modeler Vice President
    </a>
    <a href="/blog-employee-story">Career story</a>
  </body>
</html>
"""

CONSIDER_BOARD_RESPONSE = {
    "jobs": [
        {
            "company": {"name": "Glyphic Biotechnologies"},
            "jobs": [
                {
                    "title": "2027 Summer Intern, Assay Development",
                    "url": "https://job-boards.greenhouse.io/glyphicbiotechnologies/jobs/4258163009",
                    "locations": ["South San Francisco, California"],
                    "companyName": "Glyphic Biotechnologies",
                }
            ],
        },
        {
            "company": {"name": "Profluent Bio"},
            "jobs": [
                {
                    "title": "Scientist II, ML - Guided Protein Design Evaluation",
                    "url": "https://job-boards.greenhouse.io/profluent/jobs/5277263008",
                    "locations": ["Emeryville, California"],
                    "companyName": "Profluent Bio",
                }
            ],
        },
    ],
    "meta": {"size": 60},
}

PWC_HTML = """
<html>
  <body>
    <a href="/job/IL-Chicago/Chicago---Tax-JD---Intern---Summer-2027_612263EIB-1?source=US_ENT_Careers">
      Chicago - Tax JD - Intern - Summer 2027
    </a>
    <a href="/job/CA-Irvine/Irvine---Tax-Manager---Full-Time_612200EIB-1">
      Irvine - Tax Manager - Full-Time
    </a>
  </body>
</html>
"""


def test_collect_blackrock_postings_extracts_internship_job_urls():
    postings = collect_blackrock_postings(
        make_source(),
        BLACKROCK_HTML,
        "2026-07-09",
    )

    assert len(postings) == 1
    assert postings[0].title == "2027 Summer Internship Program Amers"
    assert postings[0].location == "New York"
    assert postings[0].posting_url.endswith("/90628276544")


def test_collect_blackrock_postings_parses_structured_search_results():
    html = """
    <html><body>
      <a class="section3__search-results-a" href="/job/new-york/2027-summer-internship-program-amers/45831/90628276544">
        <h2 class="section3__job-title">2027 Summer Internship Program - AMERS</h2>
        <span class="section3__job-info">New York, NY</span>
      </a>
    </body></html>
    """
    postings = collect_blackrock_postings(make_source(), html, "2026-07-10")

    assert len(postings) == 1
    assert postings[0].title == "2027 Summer Internship Program - AMERS"
    assert postings[0].location == "New York, NY"


def test_collect_json_ld_postings_extracts_jobposting_records():
    html = """
    <html>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "JobPosting",
            "title": "2027 Technology Summer Analyst Intern",
            "url": "https://careers.example.com/job/2027-tech-intern",
            "jobLocation": {"name": "New York"}
          }
        ]
      }
      </script>
    </html>
    """
    source = make_source(company="Example Co", careers_url="https://careers.example.com")

    postings = collect_json_ld_postings(source, html, "2026-07-09")

    assert len(postings) == 1
    assert postings[0].title == "2027 Technology Summer Analyst Intern"
    assert postings[0].posting_url == "https://careers.example.com/job/2027-tech-intern"


def test_collect_postings_for_source_uses_blackrock_strategy():
    outcome = collect_postings_for_source(
        make_source(),
        BLACKROCK_HTML,
        "2026-07-09",
    )

    assert outcome.strategies_tried[0] == "blackrock_jobs"
    assert len(outcome.postings) == 1


def test_collect_pwc_postings_extracts_internship_job_urls():
    source = make_source(
        company="PWC",
        careers_url="https://jobs-us.pwc.com/us/en/search-results?keywords=intern",
        collector="pwc_jobs",
    )

    postings = collect_pwc_postings(source, PWC_HTML, "2026-07-10")

    assert len(postings) == 1
    assert "Intern" in postings[0].title
    assert postings[0].location == "Chicago"
    assert postings[0].posting_url.startswith("https://jobs-us.pwc.com/job/IL-Chicago/")


def test_collect_consider_board_postings_filters_by_company(monkeypatch):
    clear_consider_board_cache()

    def fake_post_json(url: str, payload: dict) -> dict:
        assert url.endswith("/api-boards/search-jobs")
        assert payload["board"]["id"] == "bakar-bio-labs"
        return CONSIDER_BOARD_RESPONSE

    monkeypatch.setattr(
        "internship_search.career_collectors.post_consider_board_json",
        fake_post_json,
    )

    source = make_source(
        company="Glyphic Biotechnologies",
        careers_url="https://jobs.bakarlabs.org/jobs",
        collector="consider_board",
    )
    html = 'serverInitialData = {"board":{"id":"bakar-bio-labs","isParent":true}};'
    postings = collect_consider_board_postings(source, html, "2026-07-10")

    assert len(postings) == 1
    assert postings[0].title == "2027 Summer Intern, Assay Development"
    assert postings[0].company == "Glyphic Biotechnologies"
    assert "greenhouse.io/glyphicbiotechnologies" in postings[0].posting_url


def test_consider_board_empty_warning_distinguishes_company_without_internships(monkeypatch):
    clear_consider_board_cache()

    monkeypatch.setattr(
        "internship_search.career_collectors.post_consider_board_json",
        lambda url, payload: CONSIDER_BOARD_RESPONSE,
    )
    source = make_source(
        company="Profluent Bio",
        careers_url="https://jobs.bakarlabs.org/jobs",
        collector="consider_board",
    )
    html = 'serverInitialData = {"board":{"id":"bakar-bio-labs","isParent":true}};'
    collect_consider_board_postings(source, html, "2026-07-10")

    warning = consider_board_empty_warning(source)

    assert "No internship postings matched for Profluent Bio" in warning
    assert "1 active job" in warning


def test_collect_postings_for_source_uses_pwc_strategy():
    source = make_source(
        company="PWC",
        careers_url="https://jobs-us.pwc.com/us/en/search-results?keywords=intern",
        collector="pwc_jobs",
    )
    outcome = collect_postings_for_source(source, PWC_HTML, "2026-07-10")

    assert outcome.strategies_tried[0] == "pwc_jobs"
    assert len(outcome.postings) == 1


def test_company_names_match_is_case_insensitive():
    assert company_names_match("Glyphic Biotechnologies", "glyphic biotechnologies")
