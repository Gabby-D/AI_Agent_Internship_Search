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


@dataclass(frozen=True)
class CompanySource:
    company: str
    website: str
    careers_url: str
    source_type: str
    origin: str
    has_connection: bool
    notes: str


KNOWN_SEED_SOURCE_METADATA: dict[str, SourceMetadata] = {
    "pwc": SourceMetadata(
        careers_url="https://www.pwc.com/us/en/careers/entry-level/internships.html",
        source_type="company_careers_page",
        notes="US internship page. PwC also has region-specific student career pages.",
    ),
    "blackrock": SourceMetadata(
        careers_url="https://careers.blackrock.com/en/students-and-graduates",
        source_type="company_careers_page",
        notes="Official students and graduates page.",
    ),
    "bain": SourceMetadata(
        careers_url="https://www.bain.com/careers/work-with-us/internships-programs/",
        source_type="company_careers_page",
        notes="Official internships and programs page.",
    ),
    "bakar bio labs": SourceMetadata(
        careers_url="https://jobs.bakarlabs.org/jobs",
        source_type="job_board",
        notes="Official Bakar Labs companies job board.",
    ),
    "mckinsey & co": SourceMetadata(
        careers_url="https://www.mckinsey.com/careers/students/undergraduate-degree",
        source_type="company_careers_page",
        notes="Official undergraduate opportunities page.",
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
    return [CompanySource(**source) for source in raw_sources]


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
