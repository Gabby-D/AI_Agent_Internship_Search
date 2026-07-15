"""Load local private inputs used to guide internship searches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence


class PrivateInputError(ValueError):
    """Raised when a required private input file cannot be parsed."""


@dataclass(frozen=True)
class Company:
    name: str
    website: str
    has_connection: bool


@dataclass(frozen=True)
class Preferences:
    likes: list[str]
    dislikes: list[str]


@dataclass(frozen=True)
class Course:
    code: str
    title: str
    category: str


@dataclass(frozen=True)
class ProgramInfo:
    faculty: str | None
    major: str | None
    minor_or_concentration: str | None


@dataclass(frozen=True)
class PrivateInputs:
    companies: list[Company]
    industries: list[str]
    preferences: Preferences
    program: ProgramInfo
    courses: list[Course]
    connections_notes: str
    resume_path: Path | None


_COMPANIES_FILENAME = "list_of_companies.md"
_PREFERENCES_FILENAME = "preferences.md"
_EDITABLE_TEXT_FILENAMES = frozenset(
    {"mcgill_class_list.md", "connections.md", "resume_summary.md"}
)


def load_private_inputs(private_dir: Path | str = "private") -> PrivateInputs:
    """Load all current private inputs from the local private directory."""

    private_path = Path(private_dir)
    companies, industries = parse_companies_file(
        _read_required_file(private_path / "list_of_companies.md")
    )
    preferences = parse_preferences_file(
        _read_required_file(private_path / "preferences.md")
    )
    program, courses = parse_course_file(
        _read_required_file(private_path / "mcgill_class_list.md")
    )
    connections_notes = _read_optional_file(private_path / "connections.md").strip()
    resume_path = private_path / "Resume - Gabrielle Dar.pdf"

    return PrivateInputs(
        companies=companies,
        industries=industries,
        preferences=preferences,
        program=program,
        courses=courses,
        connections_notes=connections_notes,
        resume_path=resume_path if resume_path.exists() else None,
    )


def read_companies(
    private_dir: Path | str = "private",
) -> tuple[list[Company], list[str]]:
    """Read the editable company and industry lists."""

    return parse_companies_file(
        _read_required_file(Path(private_dir) / _COMPANIES_FILENAME)
    )


def replace_companies(
    companies: Sequence[Company | Mapping[str, object]],
    industries: Sequence[str],
    private_dir: Path | str = "private",
) -> None:
    """Replace all companies and industries with a validated Markdown document."""

    normalized_companies = [_coerce_company(company) for company in companies]
    normalized_industries = [_validate_list_value(industry, "Industry") for industry in industries]
    content = _format_companies_file(normalized_companies, normalized_industries)
    _write_validated_file(
        Path(private_dir) / _COMPANIES_FILENAME,
        content,
        parse_companies_file,
    )


def read_preferences(private_dir: Path | str = "private") -> Preferences:
    """Read the editable preference lists."""

    return parse_preferences_file(
        _read_required_file(Path(private_dir) / _PREFERENCES_FILENAME)
    )


def replace_preferences(
    likes: Sequence[str],
    dislikes: Sequence[str],
    private_dir: Path | str = "private",
) -> None:
    """Replace likes and dislikes with a validated Markdown document."""

    content = _format_preferences_file(
        [_validate_list_value(like, "Like") for like in likes],
        [_validate_list_value(dislike, "Dislike") for dislike in dislikes],
    )
    _write_validated_file(
        Path(private_dir) / _PREFERENCES_FILENAME,
        content,
        parse_preferences_file,
    )


def read_editable_text(
    filename: str,
    private_dir: Path | str = "private",
) -> str:
    """Read one of the raw text files exposed for editing."""

    return _read_optional_file(_editable_text_path(filename, private_dir))


def write_editable_text(
    filename: str,
    content: str,
    private_dir: Path | str = "private",
) -> None:
    """Write an editable raw text file, validating course data when applicable."""

    if not isinstance(content, str):
        raise PrivateInputError("Editable text content must be a string.")

    path = _editable_text_path(filename, private_dir)
    validator = parse_course_file if filename == "mcgill_class_list.md" else None
    _write_validated_file(path, content, validator)


def parse_companies_file(content: str) -> tuple[list[Company], list[str]]:
    companies: list[Company] = []
    industries: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()

        if _is_markdown_table_row(stripped):
            cells = _split_markdown_table_row(stripped)
            if _is_table_header_or_separator(cells):
                continue
            if len(cells) != 3:
                raise PrivateInputError(
                    "Expected companies table rows to have 3 columns: "
                    "Name, Website, and connection status."
                )
            companies.append(
                Company(
                    name=cells[0],
                    website=cells[1],
                    has_connection=_parse_yes_no(cells[2]),
                )
            )
            continue

        if stripped.startswith("-"):
            industry = stripped.lstrip("-").strip()
            if industry:
                industries.append(industry)

    if not companies:
        raise PrivateInputError("No companies found in private/list_of_companies.md.")

    return companies, industries


def parse_preferences_file(content: str) -> Preferences:
    sections = _parse_markdown_sections(content)
    likes = _parse_list_items(sections.get("things i like", []))
    dislikes = _parse_list_items(sections.get("things i don't like", []))

    if not likes:
        raise PrivateInputError("No likes found in private/preferences.md.")

    return Preferences(likes=likes, dislikes=dislikes)


def parse_course_file(content: str) -> tuple[ProgramInfo, list[Course]]:
    sections = _parse_markdown_sections(content)
    program_lines = sections.get("program", [])

    program = ProgramInfo(
        faculty=_parse_program_field(program_lines, "Faculty/School"),
        major=_parse_program_field(program_lines, "Major"),
        minor_or_concentration=_parse_program_field(
            program_lines,
            "Minor/Concentration",
        ),
    )

    courses: list[Course] = []
    for section, lines in sections.items():
        if section == "program":
            continue
        category = section.title()
        for item in _parse_list_items(lines):
            if ":" not in item:
                continue
            code, title = item.split(":", maxsplit=1)
            courses.append(Course(code=code.strip(), title=title.strip(), category=category))

    if not courses:
        raise PrivateInputError("No courses found in private/mcgill_class_list.md.")

    return program, courses


def summarize_private_inputs(inputs: PrivateInputs) -> str:
    connected_companies = [
        company.name for company in inputs.companies if company.has_connection
    ]

    lines = [
        "Private input summary",
        "=====================",
        f"Companies: {len(inputs.companies)}",
        f"Companies with connections: {len(connected_companies)}",
        f"Industries of interest: {len(inputs.industries)}",
        f"Preference likes: {len(inputs.preferences.likes)}",
        f"Preference dislikes: {len(inputs.preferences.dislikes)}",
        f"Courses: {len(inputs.courses)}",
        f"Connections notes present: {'yes' if inputs.connections_notes else 'no'}",
        f"Resume found: {'yes' if inputs.resume_path else 'no'}",
        "",
        "Companies:",
    ]
    lines.extend(
        f"- {company.name} ({'connection' if company.has_connection else 'no connection'})"
        for company in inputs.companies
    )

    if inputs.industries:
        lines.append("")
        lines.append("Industries:")
        lines.extend(f"- {industry}" for industry in inputs.industries)

    return "\n".join(lines)


def _read_required_file(path: Path) -> str:
    if not path.exists():
        raise PrivateInputError(f"Required private input file is missing: {path}")
    return path.read_text(encoding="utf-8")


def _read_optional_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _editable_text_path(filename: str, private_dir: Path | str) -> Path:
    if filename not in _EDITABLE_TEXT_FILENAMES:
        allowed = ", ".join(sorted(_EDITABLE_TEXT_FILENAMES))
        raise PrivateInputError(f"Unsupported editable text file: {filename}. Allowed: {allowed}")
    return Path(private_dir) / filename


def _write_validated_file(
    path: Path,
    content: str,
    validator: Callable[[str], object] | None,
) -> None:
    """Validate supplied content before and after its UTF-8 write."""

    if validator:
        validator(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if validator:
        validator(_read_required_file(path))


def _coerce_company(company: Company | Mapping[str, object]) -> Company:
    if isinstance(company, Company):
        name, website, has_connection = (
            company.name,
            company.website,
            company.has_connection,
        )
    elif isinstance(company, Mapping):
        required_fields = {"name", "website", "has_connection"}
        missing_fields = required_fields - company.keys()
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise PrivateInputError(f"Company row is missing required fields: {missing}")
        name = company["name"]
        website = company["website"]
        has_connection = company["has_connection"]
    else:
        raise PrivateInputError("Each company row must be a Company or mapping.")

    if not isinstance(has_connection, bool):
        raise PrivateInputError("Company has_connection must be a boolean.")
    return Company(
        name=_validate_table_value(name, "Company name"),
        website=_validate_table_value(website, "Company website"),
        has_connection=has_connection,
    )


def _validate_table_value(value: object, label: str) -> str:
    result = _validate_list_value(value, label)
    if "|" in result or "\n" in result or "\r" in result:
        raise PrivateInputError(f"{label} cannot contain Markdown table separators.")
    return result


def _validate_list_value(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PrivateInputError(f"{label} must be a non-empty string.")
    return value.strip()


def _format_companies_file(companies: Sequence[Company], industries: Sequence[str]) -> str:
    lines = [
        "# List of Companies",
        "",
        "| Name | Website | I know someone in the company |",
        "|------|---------|-------------------------------|",
    ]
    lines.extend(
        f"| {company.name} | {company.website} | "
        f"{'yes' if company.has_connection else 'no'} |"
        for company in companies
    )
    lines.extend(["", "## Industries of interest"])
    lines.extend(f"- {industry}" for industry in industries)
    return "\n".join(lines) + "\n"


def _format_preferences_file(likes: Sequence[str], dislikes: Sequence[str]) -> str:
    lines = ["# Preferences", "", "## Things I like"]
    lines.extend(f"{index}. {like}" for index, like in enumerate(likes, start=1))
    lines.extend(["", "## Things I don't like"])
    lines.extend(
        f"{index}. {dislike}" for index, dislike in enumerate(dislikes, start=1)
    )
    return "\n".join(lines) + "\n"


def _parse_markdown_sections(content: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped.removeprefix("## ").strip().lower()
            sections[current_section] = []
        elif current_section:
            sections[current_section].append(stripped)

    return sections


def _parse_list_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            item = stripped.lstrip("-").strip()
        elif "." in stripped and stripped.split(".", maxsplit=1)[0].isdigit():
            item = stripped.split(".", maxsplit=1)[1].strip()
        else:
            continue
        item = item.replace("**", "").strip()
        if item:
            items.append(item)
    return items


def _parse_program_field(lines: list[str], field_name: str) -> str | None:
    prefix = f"{field_name}:"
    for item in _parse_list_items(lines):
        if item.startswith(prefix):
            return item.removeprefix(prefix).strip()
    return None


def _is_markdown_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def _split_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip("|").split("|")]


def _is_table_header_or_separator(cells: list[str]) -> bool:
    lowered = [cell.lower() for cell in cells]
    return "name" in lowered or all(set(cell) <= {"-"} for cell in cells)


def _parse_yes_no(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "yes":
        return True
    if normalized in {"no", ""}:
        return False
    raise PrivateInputError(f"Expected yes/no connection value, got: {value}")
