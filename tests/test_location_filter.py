from internship_search.location_filter import matches_allowed_location


def test_matches_allowed_location_accepts_bay_area_cities():
    assert matches_allowed_location("San Francisco, CA")
    assert matches_allowed_location("Palo Alto, California")
    assert matches_allowed_location("Bay Area")
    assert matches_allowed_location("Richmond, CA")


def test_matches_allowed_location_accepts_israel():
    assert matches_allowed_location("Tel Aviv, Israel")
    assert matches_allowed_location("Jerusalem")


def test_matches_allowed_location_accepts_remote():
    assert matches_allowed_location("Remote")
    assert matches_allowed_location("Fully remote - US")
    assert matches_allowed_location("Unknown", "Remote Analyst Program")


def test_matches_allowed_location_rejects_other_regions():
    assert not matches_allowed_location("New York, NY")
    assert not matches_allowed_location("Chicago, IL")
    assert not matches_allowed_location("Unknown")
    assert not matches_allowed_location("")
    assert not matches_allowed_location("Richmond, VA")
    assert not matches_allowed_location("Atlanta, GA")
    assert not matches_allowed_location("Boston, MA")
    assert not matches_allowed_location("Irvine, CA")


def test_matches_allowed_location_rejects_multi_location_strings():
    assert not matches_allowed_location("San Francisco | New York")
    assert not matches_allowed_location("Boston, MA and San Francisco, CA")


def test_matches_allowed_location_rejects_hybrid_remote_in_other_cities():
    assert not matches_allowed_location("New York, NY (Remote)")
