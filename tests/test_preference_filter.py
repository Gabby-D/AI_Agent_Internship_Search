from internship_search.preference_filter import title_dislike_matches


def test_title_dislike_matches_common_word_forms():
    assert title_dislike_matches("Tax Intern", ["Taxes"]) == ["Taxes"]
    assert title_dislike_matches(
        "Software Engineer Internship",
        ["engineering"],
    ) == ["engineering"]


def test_title_dislike_matches_multiword_role_identity():
    assert title_dislike_matches(
        "Social Media Intern",
        ["social media managing"],
    ) == ["social media managing"]


def test_title_dislike_does_not_exclude_unrelated_role():
    assert title_dislike_matches(
        "Business Operations Intern",
        ["Taxes", "engineering", "marketing"],
    ) == []
