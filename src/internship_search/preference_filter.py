"""Deterministic exclusions for roles that conflict with explicit dislikes."""

from __future__ import annotations

import re
from collections.abc import Sequence


PREFERENCE_CONFLICT_REASON = (
    "Excluded because the role title conflicts with an explicit user dislike."
)
_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "and",
    "for",
    "in",
    "managing",
    "management",
    "of",
    "position",
    "positions",
    "role",
    "roles",
    "the",
    "with",
}


def title_dislike_matches(title: str, dislikes: Sequence[str]) -> list[str]:
    """Return explicit dislikes whose meaningful terms identify the role title."""

    title_terms = {_term_root(term) for term in _meaningful_terms(title)}
    matches: list[str] = []
    for dislike in dislikes:
        dislike_terms = {_term_root(term) for term in _meaningful_terms(dislike)}
        if not dislike_terms:
            continue
        overlap = title_terms.intersection(dislike_terms)
        required = 1 if len(dislike_terms) == 1 else 2
        if len(overlap) >= required:
            matches.append(dislike)
    return matches


def _meaningful_terms(value: str) -> list[str]:
    return [
        term
        for term in _WORD_RE.findall(value.lower())
        if len(term) >= 3 and term not in _STOPWORDS
    ]


def _term_root(term: str) -> str:
    if term in {"tax", "taxes"}:
        return "tax"
    if term.startswith("engineer"):
        return "engineer"
    if term.endswith("ies") and len(term) > 4:
        return f"{term[:-3]}y"
    if term.endswith("ing") and len(term) > 5:
        return term[:-3]
    if term.endswith("s") and len(term) > 4:
        return term[:-1]
    return term
