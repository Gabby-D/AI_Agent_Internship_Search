from internship_search.location_filter import (
    matches_allowed_location,
    summarize_allowed_locations,
)


def write_preferences(tmp_path):
    path = tmp_path / "location_preferences.txt"
    path.write_text("preferred city\npreferred country\n", encoding="utf-8")
    return path


def test_matches_allowed_location_accepts_private_preferences(tmp_path):
    preferences = write_preferences(tmp_path)
    assert matches_allowed_location("Preferred City", preferences_path=preferences)
    assert matches_allowed_location("Preferred Country", preferences_path=preferences)


def test_matches_allowed_location_accepts_remote(tmp_path):
    preferences = write_preferences(tmp_path)
    assert matches_allowed_location("Remote", preferences_path=preferences)
    assert matches_allowed_location("Fully remote - Example Region", preferences_path=preferences)
    assert matches_allowed_location("Online", preferences_path=preferences)
    assert matches_allowed_location("Unknown", "Remote Analyst Program", preferences_path=preferences)


def test_matches_allowed_location_rejects_other_regions(tmp_path):
    preferences = write_preferences(tmp_path)
    assert not matches_allowed_location("Other City", preferences_path=preferences)
    assert not matches_allowed_location("Unknown", preferences_path=preferences)
    assert not matches_allowed_location("", preferences_path=preferences)


def test_israel_region_labels_match_when_israel_is_preferred(tmp_path):
    preferences = tmp_path / "location_preferences.txt"
    preferences.write_text("israel\nbay area\n", encoding="utf-8")

    assert matches_allowed_location("North, Israel", preferences_path=preferences)
    assert matches_allowed_location("Sharon, Israel", preferences_path=preferences)
    assert matches_allowed_location("Jerusalem Area, Israel", preferences_path=preferences)
    assert not matches_allowed_location("North Carolina, United States", preferences_path=preferences)


def test_san_jose_costa_rica_is_not_mistaken_for_bay_area(tmp_path):
    preferences = tmp_path / "location_preferences.txt"
    preferences.write_text("san jose\nisrael\n", encoding="utf-8")

    assert matches_allowed_location("San Jose, CA", preferences_path=preferences)
    assert not matches_allowed_location(
        "Costa Rica, San Jose",
        preferences_path=preferences,
    )


def test_matches_allowed_location_accepts_any_preferred_location_in_multi_location_role(tmp_path):
    preferences = write_preferences(tmp_path)
    assert matches_allowed_location("Preferred City | Other City", preferences_path=preferences)
    assert matches_allowed_location("Other City and Preferred City", preferences_path=preferences)


def test_matches_allowed_location_rejects_hybrid_remote_in_other_cities(tmp_path):
    preferences = write_preferences(tmp_path)
    assert not matches_allowed_location("Other City (Remote)", preferences_path=preferences)


def test_flexible_location_uses_structured_job_details(tmp_path):
    preferences = write_preferences(tmp_path)

    assert matches_allowed_location(
        "Flexible - Any Company Site",
        "Software Engineering Internship",
        preferences_path=preferences,
        details="Teams are available in Other City and Preferred City.",
    )
    assert not matches_allowed_location(
        "Flexible - Any Company Site",
        "Software Engineering Internship",
        preferences_path=preferences,
        details="Teams are available only in Other City.",
    )
    assert not matches_allowed_location(
        "Multiple Locations",
        "Summer Analyst Program",
        preferences_path=preferences,
        details="Submit an online application for teams in Other City.",
    )


def test_summarize_allowed_locations_hides_non_preferred_entries(tmp_path):
    preferences = tmp_path / "location_preferences.txt"
    preferences.write_text("Preferred City\nPreferred Country\n", encoding="utf-8")

    assert summarize_allowed_locations(
        "Other City | Preferred City, CA | Another City",
        preferences_path=preferences,
    ) == "Preferred City, CA | …"


def test_summarize_allowed_locations_keeps_multiple_matches_and_remote(tmp_path):
    preferences = tmp_path / "location_preferences.txt"
    preferences.write_text("Preferred City\nPreferred Country\n", encoding="utf-8")

    assert summarize_allowed_locations(
        "Preferred City | Remote | Preferred Country | Other City",
        preferences_path=preferences,
    ) == "Preferred City | Remote | Preferred Country | …"


def test_summarize_allowed_locations_leaves_single_location_unchanged(tmp_path):
    preferences = tmp_path / "location_preferences.txt"
    preferences.write_text("Preferred City\n", encoding="utf-8")

    assert summarize_allowed_locations(
        "Preferred City, CA",
        preferences_path=preferences,
    ) == "Preferred City, CA"


def test_summarize_flexible_location_uses_only_preferred_detail_locations(tmp_path):
    preferences = write_preferences(tmp_path)

    assert summarize_allowed_locations(
        "Multiple Locations",
        preferences_path=preferences,
        details="Available in Other City, Preferred City, and Another City.",
    ) == "Preferred City | â€¦"
