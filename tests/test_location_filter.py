from internship_search.location_filter import matches_allowed_location


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


def test_matches_allowed_location_rejects_multi_location_strings(tmp_path):
    preferences = write_preferences(tmp_path)
    assert not matches_allowed_location("Preferred City | Other City", preferences_path=preferences)
    assert not matches_allowed_location("Other City and Preferred City", preferences_path=preferences)


def test_matches_allowed_location_rejects_hybrid_remote_in_other_cities(tmp_path):
    preferences = write_preferences(tmp_path)
    assert not matches_allowed_location("Other City (Remote)", preferences_path=preferences)
