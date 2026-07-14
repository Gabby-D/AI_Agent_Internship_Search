"""Apply internet-search results to improve source registry careers URLs."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

from internship_search.internet_search import SearchResult, score_result
from internship_search.source_registry import CompanySource, normalize_company_name


def enrich_sources_from_search_results(
    sources: list[CompanySource],
    search_results_path: Path | str,
    *,
    min_score: int = 15,
) -> tuple[list[CompanySource], list[str]]:
    """Return registry sources with improved careers URLs from saved search results."""

    grouped = read_search_results_by_company(search_results_path)
    if not grouped:
        return sources, ["No internet search results found for registry enrichment."]

    enriched: list[CompanySource] = []
    notes: list[str] = []

    for source in sources:
        company_key = normalize_company_name(source.company)
        results = grouped.get(company_key, [])
        if not results:
            enriched.append(source)
            continue

        best = pick_best_careers_result(results, company=source.company, min_score=min_score)
        alternates = pick_alternate_careers_results(
            results,
            company=source.company,
            min_score=min_score,
            exclude_url=best.url if best else "",
        )

        updated = source
        if best and should_replace_careers_url(source.careers_url, best.url, best.relevance_score):
            updated = replace(
                updated,
                careers_url=best.url,
                notes=append_note(
                    updated.notes,
                    f"Careers URL updated from internet-search ({best.relevance_score}).",
                ),
            )
            notes.append(f"{source.company}: careers URL set to {best.url}")

        if alternates:
            alternate_urls = tuple(
                url
                for url in (*updated.alternate_careers_urls, *alternates)
                if url and url != updated.careers_url
            )
            updated = replace(updated, alternate_careers_urls=alternate_urls)
            notes.append(
                f"{source.company}: added {len(alternate_urls)} alternate careers URL(s)."
            )

        enriched.append(updated)

    return enriched, notes


def read_search_results_by_company(path: Path | str) -> dict[str, list[SearchResult]]:
    results_path = Path(path)
    if not results_path.exists():
        return {}

    grouped: dict[str, list[SearchResult]] = {}
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        result = SearchResult(**payload)
        company = company_from_search_query(result.query)
        if not company:
            continue
        grouped.setdefault(normalize_company_name(company), []).append(result)

    for company, company_results in grouped.items():
        grouped[company] = sorted(
            company_results,
            key=lambda result: (-result.relevance_score, result.url),
        )
    return grouped


def company_from_search_query(query: str) -> str:
    match = re.search(r"\s+summer\s+\d{4}\s+internship\s+careers\s*$", query, re.IGNORECASE)
    if match:
        return query[: match.start()].strip()
    return query.strip()


def pick_best_careers_result(
    results: list[SearchResult],
    *,
    company: str,
    min_score: int,
) -> SearchResult | None:
    ranked = [
        replace(result, relevance_score=score_result(result, company=company))
        for result in results
    ]
    ranked.sort(key=lambda result: (-result.relevance_score, result.url))
    for result in ranked:
        if result.relevance_score < min_score:
            continue
        if is_job_posting_url(result.url):
            return result
        if is_careers_search_url(result.url):
            return result
        if result.relevance_score >= min_score + 10:
            return result
    return None


def pick_alternate_careers_results(
    results: list[SearchResult],
    *,
    company: str,
    min_score: int,
    exclude_url: str,
) -> tuple[str, ...]:
    alternates: list[str] = []
    seen: set[str] = set()
    for result in results:
        scored = replace(result, relevance_score=score_result(result, company=company))
        if scored.relevance_score < min_score:
            continue
        if scored.url in seen or scored.url == exclude_url:
            continue
        if not (is_job_posting_url(scored.url) or is_careers_search_url(scored.url)):
            continue
        seen.add(scored.url)
        alternates.append(scored.url)
    return tuple(alternates)


def should_replace_careers_url(current_url: str, candidate_url: str, candidate_score: int) -> bool:
    if candidate_url == current_url:
        return False
    if is_job_posting_url(candidate_url) and not is_job_posting_url(current_url):
        return True
    if is_careers_search_url(candidate_url) and not is_careers_search_url(current_url):
        return True
    return candidate_score >= score_result(
        SearchResult(
            title="",
            url=current_url,
            snippet="",
            provider="registry",
            query="",
            date_searched="",
        ),
        company="",
    ) + 10


def is_job_posting_url(url: str) -> bool:
    lowered = url.lower()
    return "/job/" in lowered or "jobid=" in lowered or "requisition" in lowered


def is_careers_search_url(url: str) -> bool:
    lowered = url.lower()
    return "search-jobs" in lowered or "search?keyword" in lowered


def append_note(existing: str, addition: str) -> str:
    if not existing:
        return addition
    if addition in existing:
        return existing
    return f"{existing} {addition}"
