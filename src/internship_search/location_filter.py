"""Location matching against private user preferences and remote-work terms."""

from __future__ import annotations

import re
from pathlib import Path

REMOTE_MARKERS = (
    "remote",
    "online",
    "virtual",
    "work from home",
    "work-from-home",
    "wfh",
    "anywhere",
    "fully online",
    "distributed",
    "work remotely",
)

DEFAULT_LOCATION_PREFERENCES_PATH = Path("private/location_preferences.txt")
LOCATION_FILTER_REASON = "Excluded because location does not match the user's preference of location."


def normalize_location_text(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip()).lower()


def is_unknown_location(location: str) -> bool:
    text = location.strip().lower()
    return not text or text == "unknown"


def matches_allowed_location(
    location: str,
    title: str | None = None,
    preferences_path: Path | str = DEFAULT_LOCATION_PREFERENCES_PATH,
) -> bool:
    """Return True when a location matches private preferences or is fully remote."""

    if is_unknown_location(location):
        if not title or not title.strip():
            return False
        return _location_text_is_allowed(
            normalize_location_text(title), load_location_markers(preferences_path)
        )

    return _location_text_is_allowed(
        normalize_location_text(location), load_location_markers(preferences_path)
    )


def _location_text_is_allowed(text: str, preferred_markers: tuple[str, ...]) -> bool:
    if not text:
        return False
    if contains_marker(text, REMOTE_MARKERS):
        if "(" in text or ")" in text:
            return contains_marker(text, preferred_markers)
        return True
    return contains_marker(text, preferred_markers)


def load_location_markers(path: Path | str = DEFAULT_LOCATION_PREFERENCES_PATH) -> tuple[str, ...]:
    preference_path = Path(path)
    if not preference_path.exists():
        return ()
    return tuple(
        line.strip().lower()
        for line in preference_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def summarize_allowed_locations(
    location: str,
    preferences_path: Path | str = DEFAULT_LOCATION_PREFERENCES_PATH,
) -> str:
    """Show matching location entries without listing every available office."""

    original = location.strip()
    if not original:
        return location

    markers = load_location_markers(preferences_path)
    parts = [
        part.strip(" \t\r\n-–—•")
        for part in re.split(r"\s*(?:\||;|\r?\n|•)\s*", original)
        if part.strip(" \t\r\n-–—•")
    ]
    if len(parts) < 2:
        return original

    matching = [
        part
        for part in parts
        if _location_text_is_allowed(normalize_location_text(part), markers)
    ]
    if not matching:
        return original

    unique_matching = list(dict.fromkeys(matching))
    summary = " | ".join(unique_matching)
    if len(unique_matching) < len(parts):
        summary += " | …"
    return summary
