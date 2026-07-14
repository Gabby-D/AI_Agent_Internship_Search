"""Score filtered postings against private profile inputs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from internship_search.posting_filter import FilteredPosting, read_filtered_postings_jsonl
from internship_search.private_inputs import PrivateInputs, load_private_inputs
from internship_search.source_registry import CompanySource, read_source_registry


@dataclass(frozen=True)
class ScoredPosting:
    title: str
    company: str
    location: str
    posting_url: str
    date_collected: str
    source_url: str
    score: int
    fit_level: str
    provider: str
    explanations: list[str]
    gaps: list[str]


PROVIDER_NAME = "local_rule_based"


@dataclass(frozen=True)
class ScoreResult:
    scored_postings: list[ScoredPosting]
    output_path: Path
    provider: str = PROVIDER_NAME
    usage: "AiUsage | None" = None
    resume_scoring_note: str = ""
    ai_fallback_count: int = 0


PROFILE_TERMS = {
    "analytics": {"analytics", "analysis", "data", "statistics", "decision"},
    "finance": {"finance", "financial", "accounting", "economics", "analyst"},
    "operations": {"operations", "logistics", "supply", "optimization"},
    "math": {"math", "probability", "calculus", "linear algebra", "statistics"},
    "programming": {"programming", "data", "technology"},
    "geopolitics": {"geopolitics", "international", "politics"},
}

DISLIKED_TERMS = {"marketing", "social media"}
PREFERRED_LOCATION_TERMS = {"bay area", "israel", "remote"}
PREFERENCE_STOPWORDS = {
    "and",
    "can",
    "company",
    "have",
    "high",
    "hired",
    "where",
    "with",
}


def score_postings_file(
    postings_path: Path | str = "data/filtered_postings.jsonl",
    private_dir: Path | str = "private",
    registry_path: Path | str = "data/source_registry.json",
    output_path: Path | str = "data/scored_postings.jsonl",
    provider_name: str | None = None,
    resume_aware: bool | None = None,
) -> ScoreResult:
    postings = read_filtered_postings_jsonl(postings_path)
    private_inputs = load_private_inputs(private_dir)
    sources = read_source_registry(registry_path)
    return score_postings(
        postings=postings,
        private_inputs=private_inputs,
        sources=sources,
        output_path=output_path,
        provider_name=provider_name,
        private_dir=private_dir,
        resume_aware=resume_aware,
    )


def score_postings(
    postings: list[FilteredPosting],
    private_inputs: PrivateInputs,
    sources: list[CompanySource],
    output_path: Path | str = "data/scored_postings.jsonl",
    provider_name: str | None = None,
    private_dir: Path | str = "private",
    resume_aware: bool | None = None,
) -> ScoreResult:
    from internship_search.ai_scoring import AiUsage, get_fit_scorer

    scorer = get_fit_scorer(
        provider_name,
        private_dir=private_dir,
        resume_aware=resume_aware,
    )
    from internship_search.location_filter import matches_allowed_location

    usage = AiUsage()
    scored: list[ScoredPosting] = []
    ai_fallback_count = 0

    for posting in postings:
        if not posting.included:
            continue
        if not matches_allowed_location(posting.location, posting.title):
            continue
        parsed = scorer.score_posting(
            posting=posting,
            private_inputs=private_inputs,
            has_connection=company_has_connection(posting.company, sources),
        )
        usage = usage.add(parsed.usage)
        if scorer.name == "gemini" and parsed.provider != "gemini":
            ai_fallback_count += 1
        scored.append(
            ScoredPosting(
                title=posting.title,
                company=posting.company,
                location=posting.location,
                posting_url=posting.posting_url,
                date_collected=posting.date_collected,
                source_url=posting.source_url,
                score=parsed.score,
                fit_level=parsed.fit_level,
                provider=parsed.provider,
                explanations=parsed.explanations,
                gaps=parsed.gaps,
            )
        )

    scored = sorted(scored, key=lambda posting: (-posting.score, posting.company, posting.title))
    path = write_scored_postings_jsonl(scored, output_path)
    from internship_search.resume_scoring import (
        load_resume_scoring_config,
        summarize_resume_scoring_config,
    )

    resume_config = load_resume_scoring_config(private_dir, resume_aware=resume_aware)
    return ScoreResult(
        scored_postings=scored,
        output_path=path,
        provider=scorer.name,
        usage=usage,
        resume_scoring_note=summarize_resume_scoring_config(resume_config),
        ai_fallback_count=ai_fallback_count,
    )


def score_posting(
    posting: FilteredPosting,
    private_inputs: PrivateInputs,
    has_connection: bool,
) -> ScoredPosting:
    text = searchable_text(posting)
    score = 35
    explanations: list[str] = []
    gaps: list[str] = []

    if "intern" in text or "internship" in text:
        score += 15
        explanations.append("Role appears internship-related.")
    if "2027" in text:
        score += 15
        explanations.append("Role explicitly mentions 2027.")
    else:
        gaps.append("Does not explicitly mention Summer 2027.")

    matched_profile_themes = match_profile_themes(text)
    if matched_profile_themes:
        score += min(20, 5 * len(matched_profile_themes))
        explanations.append(
            "Matches profile themes: " + ", ".join(sorted(matched_profile_themes)) + "."
        )
    else:
        gaps.append("No clear match to coursework themes from the current posting text.")

    matched_preferences = match_preferences(text, private_inputs)
    if matched_preferences:
        score += min(15, 3 * len(matched_preferences))
        explanations.append(
            "Matches preferences: " + ", ".join(matched_preferences[:5]) + "."
        )

    if has_connection:
        score += 10
        explanations.append("Company has a known connection.")

    disliked_matches = sorted(term for term in DISLIKED_TERMS if term in text)
    if disliked_matches:
        score -= 35
        explanations.append("Penalized disliked terms: " + ", ".join(disliked_matches) + ".")

    if posting.location == "Unknown":
        gaps.append("Location is unknown.")
    if is_general_program_page(posting):
        gaps.append("Looks like a general program page rather than a specific open role.")

    clamped_score = max(0, min(100, score))
    if not explanations:
        explanations.append("Limited information available for scoring.")

    return ScoredPosting(
        title=posting.title,
        company=posting.company,
        location=posting.location,
        posting_url=posting.posting_url,
        date_collected=posting.date_collected,
        source_url=posting.source_url,
        score=clamped_score,
        fit_level=fit_level(clamped_score),
        provider=PROVIDER_NAME,
        explanations=explanations,
        gaps=gaps,
    )


def write_scored_postings_jsonl(
    postings: list[ScoredPosting],
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(asdict(posting), sort_keys=True) for posting in postings]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def summarize_score_result(result: ScoreResult) -> str:
    from internship_search.ai_scoring import AiUsage, summarize_ai_usage
    from internship_search.env_loader import get_env

    lines = [
        "Fit scoring summary",
        "===================",
        f"Provider: {result.provider}",
        f"Scored postings: {len(result.scored_postings)}",
        f"Wrote scored postings to: {result.output_path}",
    ]
    if result.resume_scoring_note:
        lines.append(result.resume_scoring_note)
    if result.scored_postings:
        lines.append("")
        lines.append("Top scored postings:")
        for posting in result.scored_postings[:5]:
            lines.append(
                f"- {posting.company}: {posting.title} "
                f"({posting.score}, {posting.fit_level}, {posting.provider})"
            )
    if result.ai_fallback_count:
        lines.append(
            f"AI fallback postings: {result.ai_fallback_count} "
            "(Gemini unavailable; used local rule-based scoring)."
        )
    if isinstance(result.usage, AiUsage) and result.usage.total_tokens:
        usage_summary = summarize_ai_usage(
            result.usage,
            model=get_env("AI_PROVIDER_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash",
        )
        if usage_summary:
            lines.extend(["", usage_summary])
    return "\n".join(lines)


def searchable_text(posting: FilteredPosting) -> str:
    return " ".join(
        [
            posting.title,
            posting.company,
            posting.location,
            posting.posting_url,
            " ".join(posting.reasons),
        ]
    ).lower()


def match_profile_themes(text: str) -> set[str]:
    matches: set[str] = set()
    for theme, terms in PROFILE_TERMS.items():
        if any(term in text for term in terms):
            matches.add(theme)
    return matches


def match_preferences(text: str, private_inputs: PrivateInputs) -> list[str]:
    matches: list[str] = []
    for preference in private_inputs.preferences.likes + private_inputs.industries:
        normalized = preference.lower()
        terms = [
            term
            for term in normalized.replace("-", " ").split()
            if len(term) > 3 and term not in PREFERENCE_STOPWORDS
        ]
        if terms and any(term in text for term in terms):
            matches.append(preference)
    if any(term in text for term in PREFERRED_LOCATION_TERMS):
        matches.append("preferred location")
    return matches


def company_has_connection(company: str, sources: list[CompanySource]) -> bool:
    for source in sources:
        if source.company == company:
            return source.has_connection
    return False


def fit_level(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 50:
        return "medium"
    return "weak"


def is_general_program_page(posting: FilteredPosting) -> bool:
    from internship_search.internship_listing import is_generic_landing_page, normalize_text

    return is_generic_landing_page(
        normalize_text(posting.title),
        posting.posting_url.lower(),
    )
