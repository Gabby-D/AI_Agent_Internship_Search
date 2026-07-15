from internship_search.private_inputs import (
    Company,
    PrivateInputError,
    load_private_inputs,
    parse_companies_file,
    parse_preferences_file,
    read_companies,
    read_editable_text,
    read_preferences,
    replace_companies,
    replace_preferences,
    write_editable_text,
)


def test_parse_companies_file_reads_table_and_industries():
    content = """# List of Companies

| Name | Website | I know someone in the company |
|------|---------|-------------------------------|
| PWC | www.pwc.com | yes |
| Bain | www.bain.com | no |

## Industries of interest
- finance
- operations
"""

    companies, industries = parse_companies_file(content)

    assert [company.name for company in companies] == ["PWC", "Bain"]
    assert companies[0].has_connection is True
    assert companies[1].has_connection is False
    assert industries == ["finance", "operations"]


def test_parse_companies_file_rejects_invalid_connection_value():
    content = """| Name | Website | I know someone in the company |
|------|---------|-------------------------------|
| PWC | www.pwc.com | maybe |
"""

    try:
        parse_companies_file(content)
    except PrivateInputError as error:
        assert "Expected yes/no connection value" in str(error)
    else:
        raise AssertionError("Expected invalid connection value to raise")


def test_parse_preferences_file_reads_likes_and_dislikes():
    content = """# Preferences
## Things I like
1. Bay Area or Israel
2. Paid position

## Things I don't like
1. social media managing
2. marketing
"""

    preferences = parse_preferences_file(content)

    assert preferences.likes == ["Bay Area or Israel", "Paid position"]
    assert preferences.dislikes == ["social media managing", "marketing"]


def test_load_private_inputs_allows_empty_optional_connections(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir()
    (private_dir / "list_of_companies.md").write_text(
        """# List of Companies

| Name | Website | I know someone in the company |
|------|---------|-------------------------------|
| PWC | www.pwc.com | yes |
""",
        encoding="utf-8",
    )
    (private_dir / "preferences.md").write_text(
        """# Preferences
## Things I like
1. utilizing my skills

## Things I don't like
1. marketing
""",
        encoding="utf-8",
    )
    (private_dir / "mcgill_class_list.md").write_text(
        """# McGill Course List

## Program

- **Faculty/School:** Desautels Faculty of Management
- **Major:** Mathematics and Statistics for Management
- **Minor/Concentration:** Operations Management

## Mathematics and Statistics Courses

- **MATH 323:** Probability
""",
        encoding="utf-8",
    )
    (private_dir / "connections.md").write_text("", encoding="utf-8")

    inputs = load_private_inputs(private_dir)

    assert len(inputs.companies) == 1
    assert inputs.preferences.likes == ["utilizing my skills"]
    assert inputs.program.major == "Mathematics and Statistics for Management"
    assert inputs.courses[0].code == "MATH 323"
    assert inputs.connections_notes == ""
    assert inputs.resume_path is None


def test_replace_companies_round_trips_companies_and_industries(tmp_path):
    private_dir = tmp_path / "nested" / "private"

    replace_companies(
        [
            Company("Connected Co", "https://connected.example", True),
            {
                "name": "Independent Co",
                "website": "https://independent.example",
                "has_connection": False,
            },
        ],
        ["finance", "operations"],
        private_dir,
    )

    companies, industries = read_companies(private_dir)

    assert companies == [
        Company("Connected Co", "https://connected.example", True),
        Company("Independent Co", "https://independent.example", False),
    ]
    assert industries == ["finance", "operations"]


def test_replace_preferences_round_trips_likes_and_dislikes(tmp_path):
    private_dir = tmp_path / "private"

    replace_preferences(
        ["Paid position", "Remote work"],
        ["Marketing"],
        private_dir,
    )

    assert read_preferences(private_dir).likes == ["Paid position", "Remote work"]
    assert read_preferences(private_dir).dislikes == ["Marketing"]


def test_editable_text_round_trips_raw_files_and_validates_courses(tmp_path):
    private_dir = tmp_path / "private"
    course_content = """# McGill Course List

## Program
- **Major:** Mathematics

## Courses
- **MATH 323:** Probability
"""

    write_editable_text("mcgill_class_list.md", course_content, private_dir)
    write_editable_text("connections.md", "Met a recruiter.", private_dir)
    write_editable_text("resume_summary.md", "Data-focused student.", private_dir)

    assert read_editable_text("mcgill_class_list.md", private_dir) == course_content
    assert read_editable_text("connections.md", private_dir) == "Met a recruiter."
    assert read_editable_text("resume_summary.md", private_dir) == "Data-focused student."


def test_invalid_writer_content_does_not_mutate_existing_files(tmp_path):
    private_dir = tmp_path / "private"
    private_dir.mkdir()
    companies_path = private_dir / "list_of_companies.md"
    preferences_path = private_dir / "preferences.md"
    courses_path = private_dir / "mcgill_class_list.md"
    companies_path.write_text(
        "| Name | Website | I know someone in the company |\n"
        "|------|---------|-------------------------------|\n"
        "| Existing | https://existing.example | yes |\n",
        encoding="utf-8",
    )
    preferences_path.write_text(
        "# Preferences\n## Things I like\n1. Existing preference\n",
        encoding="utf-8",
    )
    courses_path.write_text(
        "# Courses\n## Core\n- MATH 323: Probability\n",
        encoding="utf-8",
    )

    originals = {
        path: path.read_text(encoding="utf-8")
        for path in (companies_path, preferences_path, courses_path)
    }

    for writer, args in (
        (replace_companies, ([], [], private_dir)),
        (replace_preferences, ([], [], private_dir)),
        (write_editable_text, ("mcgill_class_list.md", "# Courses\n", private_dir)),
    ):
        try:
            writer(*args)
        except PrivateInputError:
            pass
        else:
            raise AssertionError("Expected invalid content to raise")

    assert {
        path: path.read_text(encoding="utf-8")
        for path in (companies_path, preferences_path, courses_path)
    } == originals
