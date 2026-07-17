"""Suggest similar companies for expanding internship searches."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from internship_search.internet_search import (
    SearchProvider,
    SearchResult,
    is_blocked_domain,
    search_internet,
)
from internship_search.private_inputs import PrivateInputs, load_private_inputs
from internship_search.source_registry import (
    CompanySource,
    normalize_company_name,
    read_source_registry,
    write_source_registry,
)


@dataclass(frozen=True)
class DiscoveredCompany:
    name: str
    website: str
    careers_url: str
    industry_tags: list[str]
    reason: str
    source: str
    origin: str
    should_add_to_source_registry: bool
    review_status: str
    evidence_title: str = ""
    evidence_url: str = ""
    evidence_snippet: str = ""


@dataclass(frozen=True)
class CompanyDiscoveryResult:
    suggestions: list[DiscoveredCompany]
    output_path: Path
    report_path: Path
    registry_output_path: Path | None
    internet_suggestions: int = 0
    curated_suggestions: int = 0
    search_errors: list[str] | None = None


MAX_DISCOVERY_QUERIES = 15
MAX_RESULTS_PER_QUERY = 10

DISCOVERY_BLOCKED_FRAGMENTS = (
    "extern.com",
    "glassdoor.com",
    "handshake.com",
    "indeed.com",
    "linkedin.com",
    "medium.com",
    "quora.com",
    "reddit.com",
    "university",
    "wikipedia.org",
    "youtube.com",
)

DOMAIN_COMPANY_NAMES = {
    "blackrock": "BlackRock",
    "goldmansachs": "Goldman Sachs",
    "jpmorganchase": "JPMorgan Chase",
    "jpmorgan": "JPMorgan Chase",
    "morganstanley": "Morgan Stanley",
    "deloitte": "Deloitte",
    "ey": "EY",
    "pwc": "PWC",
    "bain": "Bain",
    "mckinsey": "McKinsey & Co",
    "palantir": "Palantir",
    "anduril": "Anduril",
    "lockheedmartin": "Lockheed Martin",
    "northropgrumman": "Northrop Grumman",
    "rtx": "RTX",
}


CURATED_DISCOVERY_CANDIDATES: list[DiscoveredCompany] = []
def discover_companies_file(
    private_dir: Path | str = "private",
    registry_path: Path | str = "data/source_registry.json",
    output_path: Path | str = "data/discovered_companies.json",
    report_path: Path | str = "data/discovered_companies.md",
    update_registry: bool = False,
    use_internet: bool = True,
    search_provider: SearchProvider | None = None,
) -> CompanyDiscoveryResult:
    private_inputs = load_private_inputs(private_dir)
    existing_sources = read_source_registry(registry_path) if Path(registry_path).exists() else []
    discovery = discover_companies(
        private_inputs,
        existing_sources,
        use_internet=use_internet,
        search_provider=search_provider,
    )
    suggestions_output = write_discovered_companies(discovery.suggestions, output_path)
    report_output = write_discovery_report(discovery, report_path)
    registry_output = None
    if update_registry:
        registry_output = merge_discovered_sources(
            existing_sources=existing_sources,
            suggestions=discovery.suggestions,
            output_path=registry_path,
        )
    return CompanyDiscoveryResult(
        suggestions=discovery.suggestions,
        output_path=suggestions_output,
        report_path=report_output,
        registry_output_path=registry_output,
        internet_suggestions=discovery.internet_suggestions,
        curated_suggestions=discovery.curated_suggestions,
        search_errors=discovery.search_errors,
    )


@dataclass(frozen=True)
class DiscoveryBundle:
    suggestions: list[DiscoveredCompany]
    internet_suggestions: int
    curated_suggestions: int
    search_errors: list[str]


def discover_companies(
    private_inputs: PrivateInputs,
    existing_sources: list[CompanySource] | None = None,
    *,
    use_internet: bool = True,
    search_provider: SearchProvider | None = None,
) -> DiscoveryBundle:
    dismissed_path = Path("data/company_dismissals.json")
    dismissed_names = set()
    if dismissed_path.exists():
        try:
            dismissed_names = {
                normalize_company_name(name)
                for name in json.loads(dismissed_path.read_text(encoding="utf-8"))
            }
        except Exception:
            pass

    existing_names = {
        normalize_company_name(company.name)
        for company in private_inputs.companies
    }
    existing_names.update(
        normalize_company_name(source.company)
        for source in existing_sources or []
    )
    existing_names.update(dismissed_names)
    disliked_terms = {
        term.lower()
        for dislike in private_inputs.preferences.dislikes
        for term in dislike.replace("-", " ").split()
        if len(term) > 3
    }
    interest_terms = normalize_interest_terms(private_inputs)

    curated = [
        candidate
        for candidate in CURATED_DISCOVERY_CANDIDATES
        if normalize_company_name(candidate.name) not in existing_names
        and matches_interests(candidate, interest_terms)
        and not matches_disliked_terms(candidate, disliked_terms)
    ]

    search_errors: list[str] = []
    internet: list[DiscoveredCompany] = []
    if use_internet:
        internet, search_errors = discover_companies_from_internet(
            private_inputs=private_inputs,
            interest_terms=interest_terms,
            disliked_terms=disliked_terms,
            existing_names=existing_names,
            provider=search_provider,
        )

    suggestions = merge_discovery_suggestions(curated, internet)
    return DiscoveryBundle(
        suggestions=sorted(suggestions, key=lambda company: (company.industry_tags[0], company.name)),
        internet_suggestions=len([s for s in suggestions if s.source.startswith("internet_search")]),
        curated_suggestions=len([s for s in suggestions if s.source == "local_curated_seed"]),
        search_errors=search_errors,
    )


def discover_companies_from_internet(
    *,
    private_inputs: PrivateInputs,
    interest_terms: set[str],
    disliked_terms: set[str],
    existing_names: set[str],
    provider: SearchProvider | None = None,
) -> tuple[list[DiscoveredCompany], list[str]]:
    suggestions: list[DiscoveredCompany] = []
    errors: list[str] = []
    seen_names: set[str] = set()

    for query in build_discovery_queries(private_inputs):
        response = search_internet(
            query=query,
            provider=provider,
            max_results=MAX_RESULTS_PER_QUERY,
            output_path=None,
        )
        errors.extend(response.errors)
        for result in response.results:
            if result.relevance_score < 0:
                continue
            company = discovered_company_from_search_result(
                result=result,
                interest_terms=interest_terms,
                disliked_terms=disliked_terms,
            )
            if company is None:
                continue
            normalized = normalize_company_name(company.name)
            if normalized in existing_names or normalized in seen_names:
                continue
            seen_names.add(normalized)
            suggestions.append(company)

    return suggestions, errors


def build_discovery_queries(private_inputs: PrivateInputs) -> list[str]:
    queries: list[str] = []
    for industry in private_inputs.industries:
        queries.append(f"{normalize_query_term(industry)} companies summer 2027 internship careers")
    for company in private_inputs.companies:
        if company.name.lower() in ("test", "existing", "new co"):
            continue
        queries.append(f"companies similar to {company.name} summer internship careers")
    for preference in private_inputs.preferences.likes[:3]:
        queries.append(f"{normalize_query_term(preference)} internship companies careers")
    return dedupe_queries(queries)[:MAX_DISCOVERY_QUERIES]


def normalize_query_term(value: str) -> str:
    return (
        value.lower()
        .replace("finanacial", "financial")
        .replace("arospace", "aerospace")
        .replace("defence", "defense")
    )


def dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        normalized = query.lower().strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(query)
    return unique


def discovered_company_from_search_result(
    *,
    result: SearchResult,
    interest_terms: set[str],
    disliked_terms: set[str],
) -> DiscoveredCompany | None:
    if is_discovery_blocked_result(result.url, result.title):
        return None

    name = extract_company_name(result.title, result.url)
    if not name:
        return None

    website = website_from_url(result.url)
    careers_url = result.url if looks_like_careers_url(result.url) else website
    industry_tags = infer_industry_tags(result, interest_terms)
    candidate = DiscoveredCompany(
        name=name,
        website=website,
        careers_url=careers_url,
        industry_tags=industry_tags,
        reason=(
            f"Found via internet search ({result.provider}) for query '{result.query}'. "
            f"{result.snippet or 'No snippet available.'}"
        ),
        source=f"internet_search:{result.provider}",
        origin="discovered",
        should_add_to_source_registry=True,
        review_status="suggested",
        evidence_title=result.title,
        evidence_url=result.url,
        evidence_snippet=result.snippet,
    )
    if not matches_interests(candidate, interest_terms):
        return None
    if matches_disliked_terms(candidate, disliked_terms):
        return None
    return candidate


def merge_discovery_suggestions(
    curated: list[DiscoveredCompany],
    internet: list[DiscoveredCompany],
) -> list[DiscoveredCompany]:
    merged: dict[str, DiscoveredCompany] = {
        normalize_company_name(company.name): company for company in curated
    }
    for company in internet:
        normalized = normalize_company_name(company.name)
        existing = merged.get(normalized)
        if existing is None:
            merged[normalized] = company
            continue
        if looks_like_careers_url(company.careers_url) and not looks_like_careers_url(existing.careers_url):
            merged[normalized] = DiscoveredCompany(
                name=existing.name,
                website=existing.website,
                careers_url=company.careers_url,
                industry_tags=existing.industry_tags,
                reason=existing.reason,
                source=existing.source,
                origin=existing.origin,
                should_add_to_source_registry=existing.should_add_to_source_registry,
                review_status=existing.review_status,
                evidence_title=company.evidence_title,
                evidence_url=company.evidence_url,
                evidence_snippet=company.evidence_snippet,
            )
    return list(merged.values())


def is_discovery_blocked_result(url: str, title: str) -> bool:
    searchable = f"{url} {title}".lower()
    domain = urlparse(url).netloc.lower()
    if is_blocked_domain(domain):
        return True
    return any(fragment in searchable for fragment in DISCOVERY_BLOCKED_FRAGMENTS)


def extract_company_name(title: str, url: str) -> str:
    lowered_title = title.lower()
    if " at " in lowered_title:
        return clean_company_name(title.rsplit(" at ", 1)[-1])

    for suffix in (" careers", " internships", " jobs", " | linkedin"):
        if suffix in lowered_title:
            return clean_company_name(title[: lowered_title.index(suffix)])

    domain_key = domain_key_from_url(url)
    if domain_key in DOMAIN_COMPANY_NAMES:
        return DOMAIN_COMPANY_NAMES[domain_key]

    if domain_key:
        return clean_company_name(domain_key.replace("-", " "))
    return ""


def clean_company_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" -|:")
    return cleaned


def domain_key_from_url(url: str) -> str:
    domain = urlparse(url).netloc.lower().replace("www.", "")
    if domain.startswith("careers."):
        domain = domain.removeprefix("careers.")
    if domain.startswith("jobs."):
        domain = domain.removeprefix("jobs.")
    return domain.split(".")[0]


def website_from_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def looks_like_careers_url(url: str) -> bool:
    lowered = url.lower()
    return any(
        marker in lowered
        for marker in ("/career", "/job", "/jobs", "/student", "/intern", "internship")
    )


def infer_industry_tags(result: SearchResult, interest_terms: set[str]) -> list[str]:
    searchable = " ".join([result.title, result.url, result.snippet, result.query]).lower()
    tags = [term for term in sorted(interest_terms) if term in searchable]
    if tags:
        return tags[:4]
    return ["discovered"]


def normalize_interest_terms(private_inputs: PrivateInputs) -> set[str]:
    terms: set[str] = set()
    for value in private_inputs.industries + private_inputs.preferences.likes:
        normalized = (
            value.lower()
            .replace("finanacial", "financial")
            .replace("aropace", "aerospace")
            .replace("defence", "defense defence")
        )
        terms.update(term for term in normalized.replace("-", " ").split() if len(term) > 3)
    return terms


def matches_interests(company: DiscoveredCompany, interest_terms: set[str]) -> bool:
    searchable = " ".join(company.industry_tags + [company.reason]).lower()
    return any(term in searchable for term in interest_terms)


def matches_disliked_terms(company: DiscoveredCompany, disliked_terms: set[str]) -> bool:
    searchable = " ".join(company.industry_tags + [company.reason]).lower()
    return any(term in searchable for term in disliked_terms)


def write_discovered_companies(
    suggestions: list[DiscoveredCompany],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(suggestion) for suggestion in suggestions], indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_discovery_report(
    discovery: DiscoveryBundle | list[DiscoveredCompany],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(discovery, DiscoveryBundle):
        content = render_discovery_report(
            discovery.suggestions,
            internet_suggestions=discovery.internet_suggestions,
            curated_suggestions=discovery.curated_suggestions,
            search_errors=discovery.search_errors,
        )
    else:
        content = render_discovery_report(discovery)
    path.write_text(content + "\n", encoding="utf-8")
    return path


def render_discovery_report(
    suggestions: list[DiscoveredCompany],
    *,
    internet_suggestions: int | None = None,
    curated_suggestions: int | None = None,
    search_errors: list[str] | None = None,
) -> str:
    lines = [
        "# Discovered Company Suggestions",
        "",
        "These companies are suggested for review before adding them to active collection.",
        "",
        "## Summary",
        "",
        f"- Suggestions: {len(suggestions)}",
    ]
    if internet_suggestions is not None:
        lines.append(f"- Internet search suggestions: {internet_suggestions}")
    if curated_suggestions is not None:
        lines.append(f"- Curated suggestions: {curated_suggestions}")
    lines.extend(
        [
        "- Source: curated seed list plus internet search results when available.",
        "",
        "## Suggestions",
        "",
        ]
    )
    if not suggestions:
        lines.extend(["No new company suggestions found.", ""])
        return "\n".join(lines)

    for company in suggestions:
        lines.extend(
            [
                f"### {company.name}",
                "",
                f"- Website: {company.website}",
                f"- Careers: {company.careers_url}",
                f"- Industry tags: {', '.join(company.industry_tags)}",
                f"- Reason: {company.reason}",
                f"- Source: {company.source}",
                f"- Should add to source registry: {'yes' if company.should_add_to_source_registry else 'no'}",
                f"- Review status: {company.review_status}",
            ]
        )
        if company.evidence_title:
            lines.extend(
                [
                    f"- Evidence title: {company.evidence_title}",
                    f"- Evidence URL: {company.evidence_url}",
                    f"- Evidence snippet: {company.evidence_snippet}",
                ]
            )
        lines.append("")

    if search_errors:
        lines.extend(["## Search Errors", ""])
        lines.extend(f"- {error}" for error in search_errors)
        lines.append("")

    return "\n".join(lines)


def merge_discovered_sources(
    existing_sources: list[CompanySource],
    suggestions: list[DiscoveredCompany],
    output_path: Path | str,
) -> Path:
    by_name = {
        normalize_company_name(source.company): source
        for source in existing_sources
    }
    for suggestion in suggestions:
        if not suggestion.should_add_to_source_registry:
            continue
        normalized = normalize_company_name(suggestion.name)
        by_name.setdefault(
            normalized,
            CompanySource(
                company=suggestion.name,
                website=suggestion.website,
                careers_url=suggestion.careers_url,
                source_type="company_careers_page",
                origin="discovered",
                has_connection=False,
                notes=suggestion.reason,
            ),
        )
    sources = sorted(by_name.values(), key=lambda source: (source.origin, source.company))
    return write_source_registry(sources, output_path)


def summarize_company_discovery(result: CompanyDiscoveryResult) -> str:
    lines = [
        "Company discovery summary",
        "=========================",
        f"Suggested companies: {len(result.suggestions)}",
        f"Internet search suggestions: {result.internet_suggestions}",
        f"Curated suggestions: {result.curated_suggestions}",
        f"Wrote suggestions to: {result.output_path}",
        f"Wrote report to: {result.report_path}",
    ]
    if result.search_errors:
        lines.append(f"Search errors: {len(result.search_errors)}")
    if result.registry_output_path:
        lines.append(f"Updated source registry: {result.registry_output_path}")
    else:
        lines.append("Source registry update: skipped for review")
    return "\n".join(lines)
