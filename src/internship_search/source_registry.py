"""Build and store company career source registry entries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from internship_search.private_inputs import Company, load_private_inputs


@dataclass(frozen=True)
class SourceMetadata:
    careers_url: str
    source_type: str
    notes: str
    alternate_careers_urls: tuple[str, ...] = ()
    collector: str = "auto"


@dataclass(frozen=True)
class CompanySource:
    company: str
    website: str
    careers_url: str
    source_type: str
    origin: str
    has_connection: bool
    notes: str
    alternate_careers_urls: tuple[str, ...] = ()
    collector: str = "auto"


KNOWN_SEED_SOURCE_METADATA: dict[str, SourceMetadata] = {
    "pwc": SourceMetadata(
        careers_url="https://jobs-us.pwc.com/us/en/search-results?keywords=intern",
        source_type="company_careers_search",
        notes="PwC US internship search results on the jobs portal.",
        alternate_careers_urls=(
            "https://www.pwc.com/us/en/careers/entry-level/internships.html",
        ),
        collector="pwc_jobs",
    ),
    "blackrock": SourceMetadata(
        careers_url="https://careers.blackrock.com/search-jobs",
        source_type="company_careers_search",
        notes=(
            "Scan every page of the complete public jobs search, then identify "
            "internship opportunities locally so keyword variations are not missed."
        ),
        alternate_careers_urls=(
            "https://careers.blackrock.com/en/students-and-graduates",
        ),
        collector="blackrock_jobs",
    ),
    "crowdstrike": SourceMetadata(
        careers_url=(
            "https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers"
        ),
        source_type="company_careers_search",
        notes="Complete CrowdStrike public Workday careers board.",
        collector="workday_api",
    ),
    "berkeley research group": SourceMetadata(
        careers_url=(
            "https://thinkbrg.wd5.myworkdayjobs.com/"
            "BRG_External_Career_Site"
        ),
        source_type="company_careers_search",
        notes="Complete Berkeley Research Group public Workday careers board.",
        collector="workday_api",
    ),
    "bayer": SourceMetadata(
        careers_url=(
            "https://jobs.bayer.com/search"
            "?q=&sortColumn=referencedate&sortDirection=desc"
        ),
        source_type="company_careers_search",
        notes="Complete Bayer public SuccessFactors jobs search.",
        collector="bayer_successfactors",
    ),
    "bain": SourceMetadata(
        careers_url="https://www.bain.com/careers/work-with-us/internships-programs/",
        source_type="company_careers_page",
        notes="Official internships and programs page.",
        alternate_careers_urls=(
            "https://careers.bain.com/recruits/signin?folderId=10403",
        ),
    ),
    "bakar bio labs": SourceMetadata(
        careers_url="https://jobs.bakarlabs.org/jobs",
        source_type="job_board",
        notes="Official Bakar Labs companies job board.",
        collector="consider_board",
    ),
    "mckinsey & co": SourceMetadata(
        careers_url="https://www.mckinsey.com/careers/search-jobs?keywords=intern",
        source_type="company_careers_search",
        notes="Uses McKinsey's public jobs API for complete internship search results.",
        alternate_careers_urls=(
            "https://www.mckinsey.com/careers/students/undergraduate-degree",
        ),
        collector="mckinsey_jobs",
    ),
    "pixar": SourceMetadata(
        careers_url="https://jobs.disneycareers.com/search-jobs/pixar/391/1",
        source_type="company_careers_search",
        notes=(
            "Page through Disney's complete Pixar keyword results, retain only "
            "Pixar Animation Studios roles, then filter internship titles locally."
        ),
        collector="pixar_jobs",
    ),
    "levi's": SourceMetadata(
        careers_url="https://levistraussandco.wd5.myworkdayjobs.com/en-US/External",
        source_type="company_careers_search",
        notes=(
            "Complete Levi Strauss public Workday board. The former Phenom "
            "careers.levistrauss.com host no longer resolves."
        ),
        collector="workday_api",
    ),
    "bluevine": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/bluevineus",
        source_type="company_careers_search",
        notes="Complete public Greenhouse board plus the official global careers page.",
        alternate_careers_urls=(
            "https://www.bluevine.com/careers",
        ),
    ),
    "stripe": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/stripe",
        source_type="company_careers_search",
        notes="Complete Stripe public Greenhouse job board.",
    ),
    "robinhood": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/robinhood",
        source_type="company_careers_search",
        notes="Complete Robinhood public Greenhouse job board.",
    ),
    "patreon": SourceMetadata(
        careers_url="https://jobs.ashbyhq.com/patreon",
        source_type="company_careers_search",
        notes="Complete Patreon public Ashby job board.",
    ),
    "relling": SourceMetadata(
        careers_url="https://www.ycombinator.com/companies/relling/jobs",
        source_type="company_careers_page",
        notes="Official Y Combinator jobs page for Relling.",
        collector="ycombinator_jobs",
    ),
    "khan academy": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/khanacademy",
        source_type="company_careers_search",
        notes="Complete Khan Academy public Greenhouse job board.",
    ),
    "palantir": SourceMetadata(
        careers_url="https://jobs.lever.co/palantir",
        source_type="company_careers_search",
        notes="Complete Palantir public Lever job board.",
    ),
    "applied intuition": SourceMetadata(
        careers_url="https://jobs.ashbyhq.com/applied",
        source_type="company_careers_search",
        notes="Complete Applied Intuition public Ashby job board.",
    ),
    "flexport": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/flexport",
        source_type="company_careers_search",
        notes="Complete Flexport public Greenhouse job board.",
    ),
    "spacex": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/spacex",
        source_type="company_careers_search",
        notes="Complete SpaceX public Greenhouse job board.",
    ),
    "ayar labs": SourceMetadata(
        careers_url=(
            "https://recruitingbypaycor.com/career/CareerHome.action"
            "?clientId=8a7883c66a3387ef016a468ba9d104e6"
        ),
        source_type="company_careers_search",
        notes="Complete Ayar Labs public Paycor careers board.",
        collector="paycor_html",
    ),
    "form energy": SourceMetadata(
        careers_url="https://jobs.ashbyhq.com/formenergy",
        source_type="company_careers_search",
        notes="Complete Form Energy public Ashby job board.",
    ),
    "kobold metals": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/koboldmetals",
        source_type="company_careers_search",
        notes="Complete KoBold Metals public Greenhouse job board.",
    ),
    "upside foods": SourceMetadata(
        careers_url="https://upsidefoods.com/careers/",
        source_type="company_careers_page",
        notes="UPSIDE Foods official careers page; its former Greenhouse board is retired.",
    ),
    "ansa bio": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/ansabiotechnologies",
        source_type="company_careers_search",
        notes="Complete Ansa Biotechnologies public Greenhouse job board.",
    ),
    "rigetti": SourceMetadata(
        careers_url="https://jobs.lever.co/rigetti",
        source_type="company_careers_search",
        notes="Complete Rigetti public Lever job board.",
    ),
    "boeing": SourceMetadata(
        careers_url="https://jobs.boeing.com/category/internship-jobs/185/9287/1/content",
        source_type="company_careers_search",
        notes="Official Boeing internship-job category with bounded pagination.",
        alternate_careers_urls=("https://jobs.boeing.com/en/internships",),
    ),
    "united airlines": SourceMetadata(
        careers_url=(
            "https://careers.united.com/us/en/students/c/"
            "student-and-early-career-jobs"
        ),
        source_type="company_careers_search",
        notes="Official United student and early-career opportunities.",
        alternate_careers_urls=(
            "https://careers.united.com/us/en/search-results?keywords=intern",
        ),
    ),
    "goldman sachs": SourceMetadata(
        careers_url="https://higher.gs.com/results",
        source_type="company_careers_search",
        notes=(
            "Page through Goldman Sachs' complete official campus-role API and "
            "filter current internship and summer-analyst listings locally."
        ),
        collector="goldman_higher",
    ),
    "jpmorgan chase": SourceMetadata(
        careers_url=(
            "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/"
            "en/sites/CX_1001/requisitions"
        ),
        source_type="company_careers_search",
        notes=(
            "Page through JPMorgan Chase's complete official Oracle Recruiting "
            "campus site and filter internship and summer-analyst titles locally."
        ),
        collector="oracle_recruiting_api",
    ),
    "lemonade": SourceMetadata(
        careers_url="https://makers.lemonade.com/",
        source_type="company_careers_search",
        notes=(
            "Read Lemonade's complete official structured role list and filter "
            "specific internships locally."
        ),
        collector="lemonade_jobs",
    ),
    "bank of america": SourceMetadata(
        careers_url=(
            "https://careers.bankofamerica.com/en-us/students/job-search"
        ),
        source_type="company_careers_search",
        notes="Complete official Bank of America campus opportunities feed.",
        alternate_careers_urls=(
            "https://careers.bankofamerica.com/en-us/students",
        ),
        collector="bank_of_america_jobs",
    ),
    "northrop grumman": SourceMetadata(
        careers_url=(
            "https://jobs.northropgrumman.com/careers"
            "?domain=ngc.com"
        ),
        source_type="company_careers_search",
        notes=(
            "Page through Northrop Grumman's official Eightfold searches for "
            "all supported internship-title variants."
        ),
        alternate_careers_urls=(
            "https://www.northropgrumman.com/careers/"
            "students-and-entry-level-careers-start-a-career-of-purpose",
        ),
        collector="eightfold_pcsx",
    ),
    "rtx": SourceMetadata(
        careers_url="https://careers.rtx.com/global/en/campusprograms",
        source_type="company_careers_search",
        notes=(
            "Uses RTX's accessible campus-programs page to configure the "
            "complete public Phenom jobs widget. The former campus search URL "
            "now 404s, and search-result HTML remains Cloudflare-blocked."
        ),
        collector="phenom_api",
    ),
    "the aerospace corporation": SourceMetadata(
        careers_url="https://aero.wd5.myworkdayjobs.com/External",
        source_type="company_careers_search",
        notes=(
            "Complete Aerospace Corporation public Workday board. The "
            "aerospace.org careers pages return Cloudflare 403 to unattended "
            "clients."
        ),
        collector="workday_api",
    ),
    "bolt threads": SourceMetadata(
        careers_url="https://boltthreads.com/",
        source_type="company_status_page",
        notes=(
            "Official Bolt Threads site states that the company is no longer "
            "operating; a successful scan therefore has no openings."
        ),
        collector="closed_company",
    ),
    "clif bar and company": SourceMetadata(
        careers_url=(
            "https://wd3.myworkdaysite.com/recruiting/mdlz/External"
            "?q=Clif"
        ),
        source_type="company_careers_search",
        notes=(
            "Clif Bar recruiting is handled by parent company Mondelēz; scan "
            "the complete public Workday result set for Clif."
        ),
        collector="workday_api",
    ),
    "dymo / newell brands": SourceMetadata(
        careers_url="https://jobs.newellbrands.com/?locale=en_US",
        source_type="company_careers_search",
        notes="Official Newell Brands jobs portal.",
        alternate_careers_urls=(
            "https://careers.newellbrands.com/early-careers/",
        ),
    ),
    "deloitte": SourceMetadata(
        careers_url=(
            "https://apply.deloitte.com/en_US/careers/SearchJobs/feed/"
            "?3_149_3=637&3_5_3=478&jobSort=relevancy&jobRecordsPerPage=1000"
        ),
        source_type="company_careers_search",
        notes=(
            "Complete official Deloitte US intern search feed; job details "
            "provide all listed locations and undergraduate eligibility text."
        ),
        alternate_careers_urls=(
            "https://www.deloitte.com/us/en/careers/internships.html",
        ),
        collector="avature_rss",
    ),
    "earth mine / nokia": SourceMetadata(
        careers_url="https://jobs.nokia.com/en/sites/CX_1/jobs",
        source_type="company_careers_search",
        notes=(
            "Complete official Nokia Oracle Recruiting search, paged through "
            "the public API and filtered locally for internships."
        ),
        alternate_careers_urls=(
            "https://www.nokia.com/careers/our-locations/united-states/"
            "students-and-graduates/",
        ),
        collector="oracle_recruiting_api",
    ),
    "everstream analytics": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/everstreamanalytics",
        source_type="company_careers_search",
        notes="Complete Everstream Analytics public Greenhouse job board.",
        alternate_careers_urls=(
            "https://www.everstream.ai/careers/",
        ),
        collector="greenhouse_api",
    ),
    "farallon capital management": SourceMetadata(
        careers_url=(
            "https://job-boards.greenhouse.io/faralloncapitalmanagementllc"
        ),
        source_type="company_careers_search",
        notes="Complete official Farallon Capital Management Greenhouse job board.",
        alternate_careers_urls=("https://www.faralloncapital.com/careers",),
        collector="greenhouse_api",
    ),
    "meyer sound": SourceMetadata(
        careers_url=(
            "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/"
            "recruitment.html?cid=00a315c7-e5f5-4392-94c9-185170c8222a"
            "&ccId=19000101_000001&lang=en_US"
        ),
        source_type="company_careers_search",
        notes="Complete official Meyer Sound ADP Workforce Now careers board.",
        alternate_careers_urls=("https://meyersound.com/contact/",),
        collector="adp_workforce_now",
    ),
    "morgan stanley": SourceMetadata(
        careers_url=(
            "https://morganstanley.eightfold.ai/careers"
            "?domain=morganstanley.com"
        ),
        source_type="company_careers_search",
        notes=(
            "Page through Morgan Stanley's official Eightfold searches for all "
            "supported internship-title variants and merge the complete results."
        ),
        alternate_careers_urls=(
            "https://www.morganstanley.com/people-opportunities/students-graduates",
        ),
        collector="eightfold_pcsx",
    ),
    "general dynamics": SourceMetadata(
        careers_url="https://www.gd.com/careers/job-search",
        source_type="company_careers_search",
        notes=(
            "Page through General Dynamics' complete official aggregate careers "
            "API while preserving the short-lived public page session."
        ),
        collector="general_dynamics_jobs",
    ),
    "novi connect": SourceMetadata(
        careers_url=(
            "https://noviconnect.notion.site/"
            "Careers-at-Novi-3dc7cb55c4684965a7b8d4f83cfaee5c"
        ),
        source_type="company_careers_search",
        notes="Complete official Novi public Notion open-positions page.",
        alternate_careers_urls=("https://www.noviconnect.com/careers",),
        collector="notion_public_page",
    ),
    "paypal": SourceMetadata(
        careers_url=(
            "https://paypal.eightfold.ai/careers"
            "?domain=paypal.com"
        ),
        source_type="company_careers_search",
        notes=(
            "Page through PayPal's official Eightfold searches for all "
            "supported internship-title variants."
        ),
        alternate_careers_urls=(
            "https://careers.pypl.com/university-hiring/University-Overview/"
            "default.aspx",
        ),
        collector="eightfold_pcsx",
    ),
    "powerbar": SourceMetadata(
        careers_url=(
            "https://recruitingbypaycor.com/career/CareerHome.action"
            "?clientId=8a7883d092732c3e01928d67c1c30437"
        ),
        source_type="company_careers_search",
        notes=(
            "Complete official Premier Nutrition Paycor board for the "
            "PowerBar parent-company organization."
        ),
        alternate_careers_urls=("https://www.premiernutrition.com/careers/",),
        collector="paycor_html",
    ),
    "profusa": SourceMetadata(
        careers_url="https://profusa.com/careers-profusa/",
        source_type="company_careers_page",
        notes=(
            "Official Profusa careers page; a successful page with no "
            "internship listing is a verified zero-opening result."
        ),
        collector="profusa_careers",
    ),
    "stellarus": SourceMetadata(
        careers_url=(
            "https://ecge.fa.us2.oraclecloud.com/hcmUI/"
            "CandidateExperience/en/sites/CX_6001/jobs"
        ),
        source_type="company_careers_search",
        notes=(
            "Complete Oracle Recruiting board linked by the official "
            "Stellarus healthcare careers page."
        ),
        alternate_careers_urls=("https://www.stellarus.com/careers",),
        collector="oracle_recruiting_api",
    ),
    "symbio": SourceMetadata(
        careers_url="https://symb.io/careers",
        source_type="company_status_page",
        notes=(
            "The former Symbio Robotics careers domain currently redirects to "
            "a domain-parking page; fail visibly if that state changes."
        ),
        collector="parked_company_domain",
    ),
    "wiz": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/wizinc",
        source_type="company_careers_search",
        notes="Complete public Greenhouse board embedded by Wiz careers.",
        alternate_careers_urls=("https://www.wiz.io/careers",),
        collector="greenhouse_api",
    ),
    "zipline": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/flyzipline",
        source_type="company_careers_search",
        notes="Complete public Zipline Greenhouse board.",
        alternate_careers_urls=("https://www.zipline.com/open-roles",),
        collector="greenhouse_api",
    ),
    "rafael": SourceMetadata(
        careers_url="https://career.rafael.co.il/",
        source_type="company_careers_search",
        notes=(
            "Official Rafael careers portal still returns HTTP 491 (Link11) to "
            "unattended clients. The corporate site is bot-challenged, and no "
            "public ATS board or careers API was found. Keep this as a source "
            "diagnostic; do not treat it as verified zero openings."
        ),
    ),
    "wix": SourceMetadata(
        careers_url="https://careers.wix.com/positions",
        source_type="company_careers_search",
        notes=(
            "Complete official Wix position sitemap. Student and intern titles "
            "are identified locally. The Workday CXS board is currently unavailable."
        ),
        collector="wix_positions",
    ),
    "cloudflare": SourceMetadata(
        careers_url="https://job-boards.greenhouse.io/cloudflare",
        source_type="company_careers_search",
        notes="Complete public Cloudflare Greenhouse job board.",
        alternate_careers_urls=("https://www.cloudflare.com/careers/jobs/",),
        collector="greenhouse_api",
    ),
    "elbit systems": SourceMetadata(
        careers_url="https://elbitsystemscareer.com/jobs",
        source_type="company_careers_search",
        notes=(
            "Complete Elbit Systems jobs JSON from the official careers host. "
            "Student-category and internship titles are identified locally."
        ),
        collector="elbit_jobs",
    ),
    "dell": SourceMetadata(
        careers_url=(
            "https://iawmqy.fa.ocs.oraclecloud.com/hcmUI/"
            "CandidateExperience/en/sites/careers/jobs"
        ),
        source_type="company_careers_search",
        notes="Complete official Dell Oracle Recruiting jobs board.",
        alternate_careers_urls=("https://jobs.dell.com/en/search-jobs",),
        collector="oracle_recruiting_api",
    ),
    "hp": SourceMetadata(
        careers_url="https://apply.hp.com/careers?domain=hp.com",
        source_type="company_careers_search",
        notes=(
            "Page through HP's official Eightfold searches for all supported "
            "internship-title variants."
        ),
        alternate_careers_urls=("https://jobs.hp.com/",),
        collector="eightfold_pcsx",
    ),
    "ibm": SourceMetadata(
        careers_url="https://www.ibm.com/careers/search",
        source_type="company_careers_search",
        notes=(
            "Complete IBM careers search API for roles tagged Internship or Intern. "
            "The former BrassRing search page is blocked by a WAF challenge."
        ),
        collector="ibm_careers",
    ),
    "intel": SourceMetadata(
        careers_url="https://intel.wd1.myworkdayjobs.com/External",
        source_type="company_careers_search",
        notes="Complete official Intel public Workday careers board.",
        collector="workday_api",
    ),
    "oracle": SourceMetadata(
        careers_url=(
            "https://eeho.fa.us2.oraclecloud.com/hcmUI/"
            "CandidateExperience/en/sites/jobsearch/jobs"
        ),
        source_type="company_careers_search",
        notes="Complete official Oracle Recruiting jobs board.",
        alternate_careers_urls=(
            "https://www.oracle.com/careers/students-grads/",
        ),
        collector="oracle_recruiting_api",
    ),
    "osem": SourceMetadata(
        careers_url="https://jobdetails.nestle.com/search/?q=&locationsearch=Israel",
        source_type="company_careers_search",
        notes=(
            "Official Osem-Nestle Israel SuccessFactors search. Israeli student "
            "roles are treated as internship-equivalent opportunities."
        ),
        collector="successfactors_html",
    ),
    "the coca-cola company": SourceMetadata(
        careers_url="https://careers.coca-colacompany.com/",
        source_type="company_careers_search",
        notes=(
            "Official Coca-Cola careers search. Unsupported API responses are "
            "reported as source issues rather than zero openings."
        ),
    ),
    "sodastream": SourceMetadata(
        careers_url=(
            "https://www.pepsicojobs.com/main/jobs?keywords=SodaStream"
        ),
        source_type="company_careers_search",
        notes=(
            "Complete official PepsiCo jobs API filtered to SodaStream-branded "
            "roles, with bounded pagination."
        ),
        collector="jibe_jobs",
    ),
    "cyberark": SourceMetadata(
        careers_url=(
            "https://paloaltonetworks.wd5.myworkdayjobs.com/"
            "panwexternalcareers"
        ),
        source_type="company_careers_search",
        notes=(
            "CyberArk recruiting is now handled by Palo Alto Networks; scan the "
            "complete parent Workday board and retain CyberArk-labelled roles."
        ),
        alternate_careers_urls=("https://www.cyberark.com/careers/",),
        collector="cyberark_parent_workday",
    ),
    "toyota": SourceMetadata(
        careers_url="https://careers.toyota.com/us/en/search-results",
        source_type="company_careers_search",
        notes="Complete Toyota Motor North America public Phenom jobs search.",
        collector="phenom_api",
    ),
}


def build_seed_source_registry(companies: list[Company]) -> list[CompanySource]:
    """Build source registry entries for user-provided seed companies."""

    return [build_company_source(company) for company in companies]


def build_company_source(company: Company) -> CompanySource:
    normalized_name = normalize_company_name(company.name)
    metadata = KNOWN_SEED_SOURCE_METADATA.get(
        normalized_name,
        SourceMetadata(
            careers_url=normalize_url(company.website),
            source_type="company_website",
            notes="Fallback to company website; careers URL still needs review.",
        ),
    )

    return CompanySource(
        company=company.name,
        website=normalize_url(company.website),
        careers_url=metadata.careers_url,
        source_type=metadata.source_type,
        origin="seed",
        has_connection=company.has_connection,
        notes=metadata.notes,
        alternate_careers_urls=metadata.alternate_careers_urls,
        collector=metadata.collector,
    )


def load_seed_source_registry(private_dir: Path | str = "private") -> list[CompanySource]:
    """Load private seed companies and convert them into source registry entries."""

    inputs = load_private_inputs(private_dir)
    return build_seed_source_registry(inputs.companies)


def write_source_registry(
    sources: list[CompanySource],
    output_path: Path | str = "data/source_registry.json",
) -> Path:
    """Write source registry entries to a local JSON file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(source) for source in sources]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def read_source_registry(path: Path | str = "data/source_registry.json") -> list[CompanySource]:
    """Read source registry entries from a JSON file."""

    registry_path = Path(path)
    raw_sources = json.loads(registry_path.read_text(encoding="utf-8"))
    sources: list[CompanySource] = []
    for source in raw_sources:
        sources.append(
            CompanySource(
                alternate_careers_urls=tuple(source.get("alternate_careers_urls", [])),
                collector=source.get("collector", "auto"),
                **{
                    key: source[key]
                    for key in source
                    if key not in {"alternate_careers_urls", "collector"}
                },
            )
        )
    return sources


def summarize_source_registry(sources: list[CompanySource]) -> str:
    """Create a safe human-readable registry summary."""

    seed_count = sum(1 for source in sources if source.origin == "seed")
    connected_count = sum(1 for source in sources if source.has_connection)
    lines = [
        "Company source registry",
        "=======================",
        f"Sources: {len(sources)}",
        f"Seed sources: {seed_count}",
        f"Sources with connections: {connected_count}",
        "",
        "Sources:",
    ]
    lines.extend(
        f"- {source.company}: {source.careers_url} "
        f"({source.source_type}, {source.origin})"
        for source in sources
    )
    return "\n".join(lines)


def normalize_company_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


def normalize_url(url: str) -> str:
    stripped = url.strip()
    if not stripped:
        return stripped
    if stripped.startswith(("http://", "https://")):
        return stripped
    return f"https://{stripped}"
