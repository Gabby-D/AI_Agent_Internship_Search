"""Location matching for Bay Area, Israel, and fully remote internships."""

from __future__ import annotations

BAY_AREA_MARKERS = (
    "bay area",
    "san francisco",
    "silicon valley",
    "palo alto",
    "mountain view",
    "san jose",
    "oakland",
    "berkeley",
    "menlo park",
    "sunnyvale",
    "cupertino",
    "redwood city",
    "south san francisco",
    "emeryville",
    "fremont",
    "san mateo",
    "millbrae",
    "burlingame",
    "foster city",
    "san bruno",
    "san carlos",
    "belmont",
    "hayward",
    "richmond, ca",
    "richmond, california",
    "walnut creek",
    "pleasanton",
    "livermore",
)

ISRAEL_MARKERS = (
    "israel",
    "tel aviv",
    "tel-aviv",
    "jerusalem",
    "haifa",
    "herzliya",
    "ramat gan",
    "ra'anana",
    "raanana",
    "petah tikva",
    "beer sheva",
    "be'er sheva",
)

REMOTE_MARKERS = (
    "remote",
    "virtual",
    "work from home",
    "work-from-home",
    "wfh",
    "anywhere",
    "fully online",
    "distributed",
    "work remotely",
)

DISALLOWED_LOCATION_MARKERS = (
    "new york",
    "nyc",
    "manhattan",
    "brooklyn",
    "chicago",
    "los angeles",
    "atlanta",
    "boston",
    "houston",
    "dallas",
    "philadelphia",
    "philly",
    "pittsburgh",
    "cleveland",
    "detroit",
    "minneapolis",
    "cincinnati",
    "sacramento",
    "irvine",
    "seattle",
    "denver",
    "miami",
    "austin",
    "washington, dc",
    "washington dc",
    "richmond, va",
    "portland",
    "charlotte",
    "nashville",
    "baltimore",
    "st. louis",
    "st louis",
    "kansas city",
    "orlando",
    "tampa",
    "phoenix",
    "honolulu",
    "london",
    "toronto",
    "vancouver",
    "montreal",
)

LOCATION_FILTER_REASON = (
    "Excluded because location is not Bay Area, Israel, or fully remote."
)


def normalize_location_text(*parts: str) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip()).lower()


def is_unknown_location(location: str) -> bool:
    text = location.strip().lower()
    return not text or text == "unknown"


def matches_allowed_location(location: str, title: str | None = None) -> bool:
    """Return True when location indicates Bay Area, Israel, or fully remote work."""

    if is_unknown_location(location):
        if not title or not title.strip():
            return False
        return _location_text_is_allowed(normalize_location_text(title))

    return _location_text_is_allowed(normalize_location_text(location))


def _location_text_is_allowed(text: str) -> bool:
    if not text:
        return False
    if contains_marker(text, DISALLOWED_LOCATION_MARKERS):
        return False
    if contains_marker(text, REMOTE_MARKERS):
        return True
    if contains_marker(text, ISRAEL_MARKERS):
        return True
    if contains_marker(text, BAY_AREA_MARKERS):
        return True
    return False


def contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)
