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
        careers_url="https://jobs.disneycareers.com/search-jobs?keywords=pixar%20intern",
        source_type="company_careers_search",
        notes="Pixar openings are searched on Disney's current careers portal.",
        alternate_careers_urls=(
            "https://www.pixar.com/internships",
            "https://www.pixar.com/careers",
        ),
    ),
    "levi's": SourceMetadata(
        careers_url="https://careers.levistrauss.com/go/Internships-%26-Entry-Level-Opportunities/8775602/",
        source_type="company_careers_page",
        notes="Levi Strauss internships and entry-level programs page.",
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
    "form energy": SourceMetadata(
        careers_url="https://formenergy.com/careers/open-jobs/",
        source_type="company_careers_search",
        notes="Form Energy's official open-jobs page.",
        alternate_careers_urls=("https://formenergy.com/careers/",),
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
        careers_url=(
            "https://www.goldmansachs.com/careers/students/"
            "programs-and-internships"
        ),
        source_type="company_careers_page",
        notes="Official Goldman Sachs programs and internships index.",
    ),
    "bank of america": SourceMetadata(
        careers_url="https://careers.bankofamerica.com/en-us/students",
        source_type="company_careers_page",
        notes="Official Bank of America student opportunities and program links.",
        alternate_careers_urls=(
            "https://careers.bankofamerica.com/en-us/job-search",
        ),
    ),
    "northrop grumman": SourceMetadata(
        careers_url="https://jobs.northropgrumman.com/careers?query=intern",
        source_type="company_careers_search",
        notes="Official Northrop Grumman job search filtered for internships.",
        alternate_careers_urls=(
            "https://www.northropgrumman.com/careers/"
            "students-and-entry-level-careers-start-a-career-of-purpose",
        ),
    ),
    "rtx": SourceMetadata(
        careers_url=(
            "https://careers.rtx.com/global/en/campus?keywords=intern"
        ),
        source_type="company_careers_search",
        notes=(
            "Uses RTX's accessible campus page to configure the complete public "
            "Phenom internship search without relying on Cloudflare-blocked "
            "search-result HTML."
        ),
        collector="phenom_api",
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
        careers_url="https://www.deloitte.com/us/en/careers/internships.html",
        source_type="company_careers_page",
        notes="Official Deloitte US student internships page.",
        alternate_careers_urls=(
            "https://www.deloitte.com/us/en/careers/student-careers.html",
        ),
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
