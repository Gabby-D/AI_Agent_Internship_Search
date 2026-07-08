from internship_search.private_inputs import (
    PrivateInputError,
    load_private_inputs,
    parse_companies_file,
    parse_preferences_file,
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
