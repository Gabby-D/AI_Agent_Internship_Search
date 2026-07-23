from internship_search.career_collectors import (
    clear_consider_board_cache,
    collect_ashby_postings,
    collect_blackrock_postings,
    collect_breezy_postings,
    collect_consider_board_postings,
    collect_direct_job_url_posting,
    collect_greenhouse_postings,
    collect_json_ld_postings,
    collect_pwc_postings,
    collect_semantic_detail_posting,
    collect_postings_for_source,
    collect_lever_postings,
    collect_mckinsey_postings,
    collect_paycor_postings,
    collect_phenom_postings,
    collect_workday_postings,
    collect_ycombinator_postings,
    company_names_match,
    consider_board_empty_warning,
    fetch_consider_board_jobs,
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

YCOMBINATOR_HTML = """
<script>
{&quot;jobPostings&quot;:[{&quot;id&quot;:97830,&quot;title&quot;:&quot;Business Operations Intern&quot;,
&quot;url&quot;:&quot;/companies/relling/jobs/ZFJwHfg-business-operations-intern&quot;,
&quot;applyUrl&quot;:&quot;https://account.ycombinator.com/authenticate&quot;,
&quot;location&quot;:&quot;San Francisco, CA, US&quot;,&quot;type&quot;:&quot;Internship&quot;}]}
</script>
"""


def test_collect_breezy_postings_treats_empty_public_board_as_complete():
    source = make_source(
        company="LeadGenius",
        careers_url="https://leadgenius.breezy.hr/",
        collector="auto",
    )

    outcome = collect_postings_for_source(
        source,
        "<html><body><h2>%LABEL_NO_POSITIONS%</h2></body></html>",
        "2026-07-23",
    )

    assert collect_breezy_postings(
        source,
        "<html><body><h2>%LABEL_NO_POSITIONS%</h2></body></html>",
        "2026-07-23",
    ) == []
    assert outcome.postings == []
    assert outcome.complete is True
    assert outcome.warning == ""


def test_collect_phenom_postings_pages_complete_public_widget():
    source = make_source(
        company="Example Airline",
        careers_url="https://careers.example.com/us/en/search-results",
        collector="auto",
    )
    html = (
        '<script>var phApp={"widgetApiEndpoint":"https://careers.example.com/widgets",'
        '"country":"us","locale":"en_us","refNum":"EXAMPLE","pageId":"page16"};</script>'
        "https://cdn.phenompeople.com/CareerConnectResources/example.js"
    )
    calls = []

    def fake_post_json(url, payload):
        calls.append((url, payload))
        if payload["from"] == 0:
            return {
                "refineSearch": {
                    "totalHits": 2,
                    "data": {
                        "jobs": [
                            {
                                "jobId": "INT-1",
                                "title": "2027 Data Science Intern",
                                "location": "San Francisco, CA",
                                "descriptionTeaser": "Open to undergraduate students.",
                            },
                            {
                                "jobId": "FT-1",
                                "title": "Senior Data Scientist",
                                "location": "Chicago, IL",
                            },
                        ]
                    },
                }
            }
        raise AssertionError("Unexpected extra Phenom page")

    postings = collect_phenom_postings(
        source,
        html,
        "2026-07-23",
        post_json=fake_post_json,
    )

    assert len(postings) == 1
    assert postings[0].title == "2027 Data Science Intern"
    assert postings[0].location == "San Francisco, CA"
    assert postings[0].eligibility_text == "Open to undergraduate students."
    assert postings[0].posting_url.endswith(
        "/us/en/job/INT-1/2027-data-science-intern"
    )
    assert calls[0][0] == "https://careers.example.com/widgets"
    assert calls[0][1]["ddoKey"] == "refineSearch"
    assert calls[0][1]["size"] == 100


def test_detected_phenom_page_is_marked_complete(monkeypatch):
    source = make_source(
        company="Example Airline",
        careers_url="https://careers.example.com/us/en/search-results",
        collector="auto",
    )
    html = (
        '<script>var phApp={"widgetApiEndpoint":"https://careers.example.com/widgets",'
        '"country":"us","locale":"en_us","refNum":"EXAMPLE","pageId":"page16"};</script>'
        "https://cdn.phenompeople.com/CareerConnectResources/example.js"
    )
    monkeypatch.setattr(
        "internship_search.career_collectors.post_public_json",
        lambda _url, _payload: {
            "refineSearch": {"totalHits": 0, "data": {"jobs": []}}
        },
    )

    outcome = collect_postings_for_source(source, html, "2026-07-23")

    assert "phenom_api" in outcome.strategies_tried
    assert outcome.complete is True
    assert outcome.warning == ""


def test_collect_ycombinator_postings_preserves_listing_location():
    postings = collect_ycombinator_postings(
        make_source(
            company="Relling",
            careers_url="https://www.ycombinator.com/companies/relling/jobs",
            collector="ycombinator_jobs",
        ),
        YCOMBINATOR_HTML,
        "2026-07-15",
    )

    assert len(postings) == 1
    assert postings[0].title == "Business Operations Intern"
    assert postings[0].location == "San Francisco, CA, US"
    assert postings[0].posting_url.endswith("business-operations-intern")


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


def test_collect_semantic_detail_posting_preserves_all_locations():
    html = """
    <html><body>
      <h1>Associate Consultant Internship</h1>
      <div>Job ID</div><div>10403</div>
      <div>Employment type</div><div>Temporary Full-Time</div>
      <div>Location(s)</div>
      <div>New York | San Francisco | Silicon Valley</div>
      <a href="/apply">Apply now</a>
      <h2>Description &amp; Requirements</h2>
    </body></html>
    """
    source = make_source(
        company="Bain",
        careers_url=(
            "https://www.bain.com/careers/work-with-us/internships-programs/"
            "associate-consultant-internship/"
        ),
        collector="auto",
    )
    postings = collect_semantic_detail_posting(source, html, "2026-07-22")

    assert len(postings) == 1
    assert postings[0].location == "New York | San Francisco | Silicon Valley"


def test_collect_mckinsey_postings_reads_every_api_page():
    records = [
        {
            "jobID": str(index),
            "title": f"Business Analyst Intern {index}",
            "friendlyURL": f"businessanalystintern-{index}",
            "cities": ["San Francisco", "New York"],
            "yourBackground": "Undergraduate degree in progress.",
            "whatYouWillDo": "Join a client team.",
        }
        for index in range(101)
    ]
    requested_urls = []

    def fake_get_json(url):
        requested_urls.append(url)
        start = int(url.split("start=", 1)[1].split("&", 1)[0])
        offset = start - 1
        return {
            "numFound": len(records),
            "docs": records[offset : offset + 100],
        }

    postings = collect_mckinsey_postings(
        make_source(
            company="McKinsey & Co",
            careers_url="https://www.mckinsey.com/careers/search-jobs",
            collector="mckinsey_jobs",
        ),
        "2026-07-23",
        get_json=fake_get_json,
    )

    assert len(postings) == 101
    assert len(requested_urls) == 2
    assert "start=1" in requested_urls[0]
    assert "start=101" in requested_urls[1]
    assert "Undergraduate degree in progress." in postings[0].eligibility_text


def test_collect_semantic_detail_posting_skips_explicitly_closed_program():
    html = """
    <html><body>
      <h1>Marketing Consulting Internship</h1>
      <div>Employment type</div><div>Program</div>
      <div>Location(s)</div><div>London</div>
      <p>Our applications are now closed.</p>
    </body></html>
    """
    source = make_source(
        company="Bain",
        careers_url=(
            "https://www.bain.com/careers/work-with-us/internships-programs/frwd/"
        ),
        collector="auto",
    )

    assert collect_semantic_detail_posting(source, html, "2026-07-22") == []


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


def test_collect_lever_postings_reads_complete_public_board():
    source = make_source(
        company="Example Co",
        careers_url="https://jobs.lever.co/example",
        collector="auto",
    )
    payload = [
        {
            "text": "Summer Product Intern",
            "hostedUrl": "https://jobs.lever.co/example/intern-1",
            "categories": {"location": "Remote"},
        },
        {
            "text": "Senior Engineer",
            "hostedUrl": "https://jobs.lever.co/example/job-2",
            "categories": {"location": "Remote"},
        },
    ]

    postings = collect_lever_postings(
        source,
        "2026-07-22",
        get_json=lambda url: payload,
    )

    assert [posting.title for posting in postings] == ["Summer Product Intern"]


def test_collect_lever_postings_finds_internship_after_first_api_page():
    source = make_source(
        company="Example Co",
        careers_url="https://jobs.lever.co/example",
        collector="auto",
    )
    skips: list[int] = []

    def get_json(url: str) -> list[dict]:
        skip = int(url.split("skip=")[-1].split("&")[0])
        skips.append(skip)
        if skip == 0:
            return [
                {
                    "id": f"job-{index}",
                    "text": "Senior Engineer",
                    "hostedUrl": f"https://jobs.lever.co/example/job-{index}",
                    "categories": {"location": "Remote"},
                }
                for index in range(100)
            ]
        return [
            {
                "id": "later-intern",
                "text": "2027 Summer Product Intern",
                "hostedUrl": "https://jobs.lever.co/example/later-intern",
                "categories": {"location": "Remote"},
            }
        ]

    postings = collect_lever_postings(
        source,
        "2026-07-22",
        get_json=get_json,
    )

    assert skips == [0, 100]
    assert [posting.title for posting in postings] == ["2027 Summer Product Intern"]


def test_collect_greenhouse_postings_reads_complete_public_board():
    source = make_source(
        company="Example Co",
        careers_url="https://job-boards.greenhouse.io/example",
        collector="auto",
    )
    payload = {
        "jobs": [
            {
                "title": "2027 Finance Intern",
                "absolute_url": "https://job-boards.greenhouse.io/example/jobs/1",
                "location": {"name": "New York"},
            }
        ]
    }

    postings = collect_greenhouse_postings(
        source,
        "2026-07-22",
        get_json=lambda url: payload,
    )

    assert len(postings) == 1
    assert postings[0].location == "New York"


def test_collect_greenhouse_postings_reads_embed_board_token():
    source = make_source(
        company="Example Co",
        careers_url="https://boards.greenhouse.io/embed/job_board?for=example",
        collector="auto",
    )
    requested: list[str] = []

    def get_json(url: str) -> dict:
        requested.append(url)
        return {"jobs": []}

    collect_greenhouse_postings(source, "2026-07-22", get_json=get_json)

    assert requested == [
        "https://boards-api.greenhouse.io/v1/boards/example/jobs?content=true"
    ]


def test_collect_ashby_postings_reads_complete_public_board():
    source = make_source(
        company="Example Co",
        careers_url="https://jobs.ashbyhq.com/example",
        collector="auto",
    )
    payload = {
        "jobs": [
            {
                "title": "Operations Intern",
                "jobUrl": "https://jobs.ashbyhq.com/example/1",
                "location": "Remote",
                "isListed": True,
            }
        ]
    }

    postings = collect_ashby_postings(
        source,
        "2026-07-22",
        get_json=lambda url: payload,
    )

    assert len(postings) == 1
    assert postings[0].title == "Operations Intern"


def test_collect_workday_postings_pages_until_total_is_reached():
    source = make_source(
        company="Example Co",
        careers_url="https://example.wd1.myworkdayjobs.com/en-US/External",
        collector="auto",
    )
    offsets: list[int] = []

    def post_json(url: str, payload: dict) -> dict:
        offsets.append(payload["offset"])
        if payload["offset"] == 0:
            return {
                "total": 3,
                "jobPostings": [
                    {
                        "title": "Summer Intern One",
                        "externalPath": "/job/intern-1",
                        "locationsText": "Remote",
                    },
                    {
                        "title": "Senior Engineer",
                        "externalPath": "/job/engineer-1",
                        "locationsText": "Remote",
                    },
                ],
            }
        return {
            "total": 3,
            "jobPostings": [
                {
                    "title": "Summer Intern Two",
                    "externalPath": "/job/intern-2",
                    "locationsText": "New York",
                }
            ],
        }

    postings = collect_workday_postings(
        source,
        "2026-07-22",
        post_json=post_json,
    )

    assert offsets == [0, 2]
    assert [posting.title for posting in postings] == [
        "Summer Intern One",
        "Summer Intern Two",
    ]


def test_complete_public_api_with_no_internships_is_not_an_access_failure(monkeypatch):
    source = make_source(
        company="Example Co",
        careers_url="https://jobs.lever.co/example",
        collector="auto",
    )
    monkeypatch.setattr(
        "internship_search.career_collectors.get_public_json",
        lambda url: [],
    )

    outcome = collect_postings_for_source(source, "<html></html>", "2026-07-22")

    assert outcome.postings == []
    assert outcome.complete is True
    assert outcome.warning == ""


def test_collect_paycor_postings_reads_complete_public_board():
    source = make_source(
        company="Example Co",
        careers_url=(
            "https://recruitingbypaycor.com/career/CareerHome.action"
            "?clientId=example123456789"
        ),
        collector="paycor_html",
    )
    html = """
    <div class="gnewtonCareerGroupRowClass">
      <div class="gnewtonCareerGroupJobTitleClass">
        <a href="https://recruitingbypaycor.com/career/JobIntroduction.action?clientId=example123456789&amp;id=intern-1"
           ns-qa="2027 Silicon Engineering Intern">
          2027 Silicon Engineering Intern
        </a>
      </div>
      <div class="gnewtonCareerGroupJobDescriptionClass">
        San Jose, CA
      </div>
    </div>
    <div class="gnewtonCareerGroupRowClass">
      <div class="gnewtonCareerGroupJobTitleClass">
        <a href="https://recruitingbypaycor.com/career/JobIntroduction.action?clientId=example123456789&amp;id=senior-1"
           ns-qa="Senior Silicon Engineer">
          Senior Silicon Engineer
        </a>
      </div>
      <div class="gnewtonCareerGroupJobDescriptionClass">
        San Jose, CA
      </div>
    </div>
    """

    postings = collect_paycor_postings(source, html, "2026-07-23")
    outcome = collect_postings_for_source(source, html, "2026-07-23")

    assert len(postings) == 1
    assert postings[0].title == "2027 Silicon Engineering Intern"
    assert postings[0].location == "San Jose, CA"
    assert "id=intern-1" in postings[0].posting_url
    assert outcome.complete is True
    assert outcome.warning == ""


def test_consider_board_fetches_later_batches():
    calls: list[dict] = []

    def post_json(url: str, payload: dict) -> dict:
        calls.append(payload)
        if len(calls) == 1:
            return {
                "jobs": [{"company": {"name": "One"}, "jobs": [{"id": "1"}]}],
                "meta": {"sequence": "next-token", "size": 60},
            }
        return {
            "jobs": [{"company": {"name": "Two"}, "jobs": [{"id": "2"}]}],
            "meta": {},
        }

    jobs = fetch_consider_board_jobs(
        board={"id": "example", "isParent": True},
        api_base="https://jobs.example.com",
        post_json=post_json,
    )

    assert [job["id"] for job in jobs] == ["1", "2"]
    assert calls[1]["meta"]["sequence"] == "next-token"


def test_public_api_failure_falls_back_and_reports_warning(monkeypatch):
    source = make_source(
        company="Example Co",
        careers_url="https://jobs.lever.co/example",
        collector="auto",
    )
    monkeypatch.setattr(
        "internship_search.career_collectors.get_public_json",
        lambda url: (_ for _ in ()).throw(RuntimeError("API unavailable")),
    )
    html = '<a href="/example/jobs/intern-1">2027 Summer Product Intern</a>'

    outcome = collect_postings_for_source(source, html, "2026-07-22")

    assert len(outcome.postings) == 1
    assert outcome.complete is False
    assert "lever_api failed: API unavailable" in outcome.warning


def test_direct_job_url_supports_plural_jobs_path():
    source = make_source(
        company="Example Co",
        careers_url=(
            "https://careers.example.com/en/jobs/r-123/"
            "2027-finance-summer-internship/"
        ),
        collector="direct_job_url",
    )

    postings = collect_direct_job_url_posting(source, "2026-07-23")

    assert len(postings) == 1
    assert postings[0].title == "2027 finance summer internship"
