from internship_search.internship_listing import (
    classify_internship_listing,
    is_generic_landing_page,
    is_specific_internship_listing,
    listing_category_label,
)


def test_specific_blackrock_job_listing_is_included():
    assert is_specific_internship_listing(
        "2027 Summer Internship Program - AMERS at BlackRock",
        "https://careers.blackrock.com/job/new-york/2027-summer-internship-program-amers/45831/90628276544",
    )


def test_specific_summer_analyst_intern_is_included():
    assert is_specific_internship_listing(
        "2027 Summer Analyst Intern",
        "https://example.com/jobs/2027-summer-analyst-intern",
    )


def test_bain_program_page_is_excluded():
    assert not is_specific_internship_listing(
        "Internships & Programs",
        "https://www.bain.com/careers/work-with-us/internships-programs/",
    )


def test_bain_named_program_detail_pages_are_specific_listings():
    assert is_specific_internship_listing(
        "Associate Consultant Internship",
        "https://www.bain.com/careers/work-with-us/internships-programs/associate-consultant-internship/",
    )
    assert is_specific_internship_listing(
        "Summer Associate",
        "https://www.bain.com/careers/work-with-us/internships-programs/summer-associate/",
    )


def test_pwc_search_page_is_excluded():
    assert not is_specific_internship_listing(
        "Search internships Search and apply to an internship",
        "https://jobs-us.pwc.com/us/en/entry-level",
    )


def test_pwc_advance_internship_landing_page_is_excluded():
    assert not is_specific_internship_listing(
        "Advance Internship",
        "https://www.pwc.com/us/en/careers/entry-level/internships.html",
    )


def test_bakar_internships_resource_page_is_excluded():
    assert not is_specific_internship_listing(
        "Internships",
        "https://bio.bakarlabs.org/resources?accordion=4",
    )


def test_blackrock_students_overview_is_excluded():
    assert not is_specific_internship_listing(
        "Students & Graduates overview",
        "https://careers.blackrock.com/students-and-graduates",
    )


def test_careers_overview_without_internship_terms_is_excluded():
    assert not is_specific_internship_listing(
        "Careers Overview",
        "https://example.com/careers",
    )


def test_is_generic_landing_page_detects_program_navigation():
    assert is_generic_landing_page(
        "see programs in the americas",
        "https://careers.blackrock.com/students-and-graduates-americas",
    )


def test_internal_mobility_blog_title_does_not_count_as_internship():
    classification = classify_internship_listing(
        "Here's Why This Vice President Never Stops Investing in Herself internal mobility",
        "https://careers.blackrock.com/blog-employee-story",
    )

    assert classification.category == "blog_or_story"
    assert not classification.is_specific


def test_blackrock_search_jobs_page_is_generic_search_page():
    classification = classify_internship_listing(
        "Search internships",
        "https://careers.blackrock.com/search-jobs?keywords=2027%20intern",
    )

    assert classification.category == "generic_search_page"
    assert not classification.is_specific


def test_mckinsey_undergraduate_page_is_generic_program_page():
    classification = classify_internship_listing(
        "Student internships overview",
        "https://www.mckinsey.com/careers/students/undergraduate-degree",
    )

    assert classification.category == "generic_program_page"
    assert not classification.is_specific


def test_classify_specific_listing_includes_explicit_reasons():
    classification = classify_internship_listing(
        "2027 Summer Analyst Intern",
        "https://example.com/jobs/2027-summer-analyst-intern",
    )

    assert classification.is_specific
    assert classification.category == "specific_listing"
    assert any("specific" in reason.lower() for reason in classification.reasons)


def test_listing_category_label_formats_categories():
    assert listing_category_label("generic_search_page") == "Generic search page"


def test_classify_linkedin_and_indeed_job_urls_as_specific_listings():
    assert is_specific_internship_listing(
        "2027 Summer Analyst Intern at BlackRock | LinkedIn",
        "https://www.linkedin.com/jobs/view/12345",
    )
    assert is_specific_internship_listing(
        "BlackRock - 2027 Summer Analyst Intern | Indeed.com",
        "https://www.indeed.com/viewjob?jk=abc123",
    )
    assert not is_specific_internship_listing(
        "Internship search results | LinkedIn",
        "https://www.linkedin.com/jobs/search?keywords=intern",
    )
