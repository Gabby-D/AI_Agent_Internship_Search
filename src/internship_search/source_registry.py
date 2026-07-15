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
        careers_url="https://careers.blackrock.com/search-jobs?keywords=2027%20intern",
        source_type="company_careers_search",
        notes="Students page is JavaScript-heavy; search results expose static job links.",
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
        notes="Undergraduate page often times out; search endpoint is more reliable.",
        alternate_careers_urls=(
            "https://www.mckinsey.com/careers/students/undergraduate-degree",
        ),
    ),
    "pixar": SourceMetadata(
        careers_url="https://jobs.disney.com/en/search-jobs?keywords=pixar%20intern",
        source_type="company_careers_search",
        notes="Pixar internships are posted on the Disney careers portal.",
        alternate_careers_urls=("https://www.pixar.com/careers",),
    ),
    "levi's": SourceMetadata(
        careers_url="https://careers.levistrauss.com/go/Internships-%26-Entry-Level-Opportunities/8775602/",
        source_type="company_careers_page",
        notes="Levi Strauss internships and entry-level programs page.",
    ),
    "bluevine": SourceMetadata(
        careers_url="https://www.bluevine.com/careers",
        source_type="company_careers_page",
        notes="Bluevine careers page.",
    ),
    "stripe": SourceMetadata(
        careers_url="https://stripe.com/jobs/search?query=intern",
        source_type="company_careers_search",
        notes="Stripe job search filtered for internships.",
    ),
    "robinhood": SourceMetadata(
        careers_url="https://careers.robinhood.com",
        source_type="company_careers_page",
        notes="Robinhood careers portal.",
    ),
    "patreon": SourceMetadata(
        careers_url="https://www.patreon.com/careers",
        source_type="company_careers_page",
        notes="Patreon careers page.",
    ),
    "relling": SourceMetadata(
        careers_url="https://www.ycombinator.com/companies/relling/jobs",
        source_type="company_careers_page",
        notes="Official Y Combinator jobs page for Relling.",
        collector="ycombinator_jobs",
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
